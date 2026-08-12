#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill historique des commodites — Yahoo Finance -> Supabase.

Contexte : commodity_prices ne contient que ~15 mois (avril 2025 -> aout 2026),
soit ~15 observations mensuelles non chevauchantes. Insuffisant pour tester une
relation matiere premiere -> cours d'un titre expose. Yahoo sert 11 ans sur les
memes tickers : ~2800 points par serie, ~130 observations mensuelles.

Ce script est autonome : il ne modifie pas scrape_commodities.py, qui continue
d'assurer la mise a jour quotidienne. Il reprend a l'identique sa logique
d'extraction (champ 'close', valeurs nulles ignorees, arrondi 4 decimales) et
son upsert (on_conflict=commodity_id,trade_date, lots de 100).

Idempotent : rejouable sans creer de doublon. Par defaut il ne reecrit pas les
lignes existantes (--skip-existing) et signale les ecarts de prix constates.

Usage :
    python3 tools/backfill_commodities.py --dry-run
    python3 tools/backfill_commodities.py --days 4000
    python3 tools/backfill_commodities.py --days 4000 --only cocoa,cotton
    python3 tools/backfill_commodities.py --days 4000 --overwrite
"""

import argparse
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Identique a scrape_commodities.py — ne pas diverger.
COMMODITIES = {
    "cocoa":  {"yahoo": "CC=F", "name": "Cocoa"},
    "cotton": {"yahoo": "CT=F", "name": "Cotton"},
    "gold":   {"yahoo": "GC=F", "name": "Gold"},
    "crude":  {"yahoo": "CL=F", "name": "Crude Oil"},
    "usdxof": {"yahoo": "XOFUSD=X", "name": "USD/XOF"},
}

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36")
BATCH = 100
PAUSE_ENTRE_SERIES = 1.5
TOLERANCE_ECART = 0.005  # 0.5 % — au-dela, on signale
EUR_XOF = 655.957        # parite fixe, identique a scrape_commodities.py
SEUIL_BLOCAGE = 0.05     # >5 % de dates communes divergentes => refus d'ecrire


def entetes_supabase():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_yahoo(symbol, days):
    """Recupere l'historique quotidien. Retourne [{'date','price'}, ...].

    Reprend la logique de scrape_commodities.py, a une correction pres :
    utcfromtimestamp au lieu de fromtimestamp, pour que la date obtenue ne
    depende pas du fuseau de la machine qui execute le script.
    """
    fin = datetime.now(timezone.utc)
    debut = fin - timedelta(days=days)
    params = {
        "period1": int(debut.timestamp()),
        "period2": int(fin.timestamp()),
        "interval": "1d",
        "includePrePost": "false",
    }

    reponse = requests.get(
        YAHOO_URL.format(symbol=symbol),
        params=params,
        headers={"User-Agent": UA},
        timeout=60,
    )
    if reponse.status_code != 200:
        logger.warning("Yahoo %s : HTTP %s", symbol, reponse.status_code)
        return []

    resultat = reponse.json().get("chart", {}).get("result", [])
    if not resultat:
        logger.warning("Yahoo %s : aucune donnee", symbol)
        return []

    horodatages = resultat[0].get("timestamp", []) or []
    quote = resultat[0].get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close", []) or []

    lignes, ignorees = [], 0
    for ts, prix in zip(horodatages, closes):
        if prix is None:
            ignorees += 1
            continue
        jour = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        lignes.append({"date": jour, "price": round(float(prix), 4)})

    if ignorees:
        logger.info("  %s : %d point(s) nul(s) ignore(s)", symbol, ignorees)
    return lignes


def lire_existant(commodity_id):
    """Charge les couples (trade_date -> price) deja en base pour une commodite."""
    existant, decalage, taille = {}, 0, 1000
    while True:
        reponse = requests.get(
            f"{SUPABASE_URL}/rest/v1/commodity_prices",
            headers=entetes_supabase(),
            params={
                "select": "trade_date,price",
                "commodity_id": f"eq.{commodity_id}",
                "order": "trade_date.asc",
                "limit": taille,
                "offset": decalage,
            },
            timeout=60,
        )
        if reponse.status_code != 200:
            logger.error("Lecture %s : HTTP %s — %s",
                         commodity_id, reponse.status_code, reponse.text[:200])
            reponse.raise_for_status()

        lot = reponse.json()
        for ligne in lot:
            existant[ligne["trade_date"]] = (
                float(ligne["price"]) if ligne["price"] is not None else None
            )
        if len(lot) < taille:
            break
        decalage += taille
    return existant


def upsert(commodity_id, lignes):
    """Upsert par lots de 100. Retourne le nombre de lignes ecrites."""
    if not lignes:
        return 0

    charge = [
        {"commodity_id": commodity_id, "trade_date": l["date"], "price": l["price"]}
        for l in lignes
    ]
    ecrites = 0
    for debut in range(0, len(charge), BATCH):
        lot = charge[debut:debut + BATCH]
        reponse = requests.post(
            f"{SUPABASE_URL}/rest/v1/commodity_prices"
            f"?on_conflict=commodity_id,trade_date",
            headers={**entetes_supabase(),
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=lot,
            timeout=60,
        )
        if reponse.status_code in (200, 201, 204):
            ecrites += len(lot)
        else:
            # Le corps JSON de PostgREST porte le detail de l'erreur.
            logger.error("Upsert %s lot %d : HTTP %s — %s",
                         commodity_id, debut // BATCH, reponse.status_code,
                         reponse.text[:300])
            reponse.raise_for_status()
    return ecrites


def traiter(commodity_id, config, jours, dry_run, overwrite):
    """Backfill d'une commodite. Retourne un dict de statistiques."""
    logger.info("--- %s (%s) ---", commodity_id, config["yahoo"])
    stats = defaultdict(int)

    if commodity_id == "usdxof":
        # scrape_commodities.py L117-120 : Yahoo ne cote pas XOF de facon
        # exploitable. La valeur est derivee de EUR/USD via la parite fixe
        # EUR/XOF = 655.957. Le ticker XOFUSD=X du mapping n'est PAS utilise.
        eurusd = fetch_yahoo("EURUSD=X", jours)
        distant = [
            {"date": l["date"], "price": round(EUR_XOF / l["price"], 2)}
            for l in eurusd if l["price"] > 0
        ]
        logger.info("  derive de EUR/USD x %s", EUR_XOF)
    else:
        distant = fetch_yahoo(config["yahoo"], jours)

    if not distant:
        stats["statut"] = "ECHEC_FETCH"
        return stats

    stats["yahoo"] = len(distant)
    dates = [l["date"] for l in distant]
    logger.info("  Yahoo : %d points, %s -> %s",
                len(distant), min(dates), max(dates))

    existant = lire_existant(commodity_id)
    stats["existant"] = len(existant)
    logger.info("  Base  : %d points", len(existant))

    a_ecrire, ecarts = [], []
    for ligne in distant:
        ancien = existant.get(ligne["date"])
        if ancien is None and ligne["date"] not in existant:
            a_ecrire.append(ligne)
            stats["nouveaux"] += 1
            continue

        stats["deja_present"] += 1
        if ancien is not None and ancien != 0:
            ecart = abs(ligne["price"] - ancien) / abs(ancien)
            if ecart > TOLERANCE_ECART:
                ecarts.append((ligne["date"], ancien, ligne["price"], ecart))
        if overwrite:
            a_ecrire.append(ligne)

    if ecarts:
        # Un ecart signale soit une revision Yahoo, soit une divergence de
        # methode d'extraction entre ce script et scrape_commodities.py.
        # On ne l'ecrase pas silencieusement : on le montre.
        logger.warning("  %d ecart(s) > %.1f%% avec l'existant :",
                       len(ecarts), TOLERANCE_ECART * 100)
        for jour, ancien, nouveau, ecart in ecarts[:5]:
            logger.warning("    %s : base=%.4f yahoo=%.4f (%.2f%%)",
                           jour, ancien, nouveau, ecart * 100)
        if len(ecarts) > 5:
            logger.warning("    ... et %d autre(s)", len(ecarts) - 5)
        stats["ecarts"] = len(ecarts)

    # Un taux de divergence eleve ne signale pas des revisions ponctuelles mais
    # une incompatibilite de methode ou d'unite entre la source et l'existant.
    # Ecrire dans ce cas melange deux referentiels dans la meme serie.
    if stats["deja_present"] and ecarts:
        taux = len(ecarts) / stats["deja_present"]
        if taux > SEUIL_BLOCAGE:
            logger.error("  %s : %.0f%% des dates communes divergent — ECRITURE REFUSEE",
                         commodity_id, taux * 100)
            logger.error("  verifier l'unite / la methode d'extraction avant de reessayer")
            stats["statut"] = "BLOQUE_DIVERGENCE"
            stats["ecrites"] = 0
            return stats

    if dry_run:
        logger.info("  [DRY-RUN] %d ligne(s) seraient ecrites", len(a_ecrire))
        stats["ecrites"] = 0
        stats["statut"] = "DRY_RUN"
        return stats

    stats["ecrites"] = upsert(commodity_id, a_ecrire)
    logger.info("  Ecrites : %d", stats["ecrites"])
    stats["statut"] = "OK"
    return stats


def main():
    parseur = argparse.ArgumentParser(description="Backfill commodites Yahoo -> Supabase")
    parseur.add_argument("--days", type=int, default=4000,
                         help="profondeur en jours (defaut 4000, ~11 ans)")
    parseur.add_argument("--only",
                         help="liste de commodity_id separes par des virgules")
    parseur.add_argument("--dry-run", action="store_true",
                         help="simule sans ecrire")
    parseur.add_argument("--overwrite", action="store_true",
                         help="reecrit aussi les dates deja presentes")
    args = parseur.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env")
        return 1

    cibles = dict(COMMODITIES)
    if args.only:
        demandes = [c.strip() for c in args.only.split(",") if c.strip()]
        inconnues = [c for c in demandes if c not in COMMODITIES]
        if inconnues:
            logger.error("commodity_id inconnu(s) : %s", ", ".join(inconnues))
            return 1
        cibles = {c: COMMODITIES[c] for c in demandes}

    logger.info("Backfill %d jour(s) — %d serie(s)%s",
                args.days, len(cibles), " [DRY-RUN]" if args.dry_run else "")

    resultats = {}
    for index, (commodity_id, config) in enumerate(cibles.items()):
        try:
            resultats[commodity_id] = traiter(
                commodity_id, config, args.days, args.dry_run, args.overwrite)
        except requests.RequestException as exc:
            logger.error("%s : echec reseau — %s", commodity_id, exc)
            resultats[commodity_id] = {"statut": "ECHEC_RESEAU"}
        if index < len(cibles) - 1:
            time.sleep(PAUSE_ENTRE_SERIES)

    print("\n--- Resume ---")
    print(f"{'commodite':<10} {'statut':<14} {'yahoo':>7} {'base':>7} "
          f"{'nouveaux':>9} {'ecrites':>8} {'ecarts':>7}")
    total_ecrites = 0
    for commodity_id, stats in resultats.items():
        print(f"{commodity_id:<10} {stats.get('statut', '?'):<14} "
              f"{stats.get('yahoo', 0):>7} {stats.get('existant', 0):>7} "
              f"{stats.get('nouveaux', 0):>9} {stats.get('ecrites', 0):>8} "
              f"{stats.get('ecarts', 0):>7}")
        total_ecrites += stats.get("ecrites", 0)
    print(f"\nTotal ecrit : {total_ecrites}")

    echecs = [c for c, s in resultats.items()
              if s.get("statut", "").startswith(("ECHEC", "BLOQUE"))]
    if echecs:
        logger.error("echec sur : %s", ", ".join(echecs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
