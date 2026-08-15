#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basculement de juin — propre aux Industriels ou general ?
=========================================================
Classe A : lecture seule, aucune ecriture en base.

CONTEXTE
industriels_ventilation.py (15/08/2026) montre un basculement net sur le
secteur Industriels :

  mai      62.7 % (n=83)   mediane +5.87 %
  juin     33.1 % (n=160)  mediane -4.23 %
  juillet  33.3 % (n=69)   mediane -3.67 %

QUESTION
Ce basculement est-il propre aux Industriels, ou touche-t-il l'ensemble du
marche ? Si tous les secteurs chutent en juin, c'est un changement de regime
de marche, pas une faiblesse sectorielle de V1 — et la conclusion sur les
Industriels serait a reconsiderer.

Ce script decrit, il ne teste aucun seuil.

Deux vues :
  1. hit rate mensuel par secteur (ACHAT et SURVEILLER confondus)
  2. contexte de marche : variation mensuelle du BRVM Composite, issue de
     boc_indices. Un hit rate qui chute dans un marche qui monte n'a pas le
     meme sens qu'un hit rate qui chute dans un marche qui baisse.

Usage :
    python3 tools/experiments/V1_SECTEURS/basculement_juin.py
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

HORIZON_MIN, HORIZON_MAX = 15, 25
SIGNAUX = ("ACHAT", "SURVEILLER")

SECTEUR_OFFICIEL = {
    "Conso de Base": ["NTLC", "PALC", "SPHC", "SICC", "STBC", "SOGC", "SLBC", "SCRC", "UNLC"],
    "Conso Discret.": ["BNBC", "CFAC", "LNBB", "NEIC", "ABJC", "PRSC", "UNXC"],
    "Energie": ["SMBC", "TTLC", "TTLS", "SHEC"],
    "Industriels": ["SDSC", "SEMC", "SIVC", "FTSC", "STAC", "CABC"],
    "Serv. Financiers": ["BOAB", "BOABF", "BOAC", "BOAM", "BOAN", "BOAS", "BICB", "BICC",
                         "CBIBF", "ECOC", "ETIT", "NSBC", "ORGT", "SAFC", "SGBC", "SIBC"],
    "Serv. Publics": ["CIEC", "SDCC"],
    "Telecoms": ["ONTBF", "ORAC", "SNTS"],
}
TICKER_SECTEUR = {t: s for s, ts in SECTEUR_OFFICIEL.items() for t in ts}


def charger(table, params, page=1000):
    sortie, offset = [], 0
    while True:
        reponse = requests.get(
            f"{URL}/rest/v1/{table}",
            headers={**HEADERS, "Range": f"{offset}-{offset + page - 1}"},
            params=params, timeout=60)
        reponse.raise_for_status()
        lot = reponse.json()
        if not lot:
            break
        sortie.extend(lot)
        if len(lot) < page:
            break
        offset += page
    return sortie


def mediane(valeurs):
    if not valeurs:
        return None
    tri = sorted(valeurs)
    n = len(tri)
    return tri[n // 2] if n % 2 else (tri[n // 2 - 1] + tri[n // 2]) / 2


def main():
    if not URL or not KEY:
        print("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env", file=sys.stderr)
        return 1

    print("=" * 78)
    print("BASCULEMENT DE JUIN — propre aux Industriels ou general ?")
    print("=" * 78)

    brut = charger("brvm_decisions_results", {
        "select": "ticker,signal,signal_date,verification_date,variation_pct",
    })

    lignes = []
    for r in brut:
        if r["signal"] not in SIGNAUX:
            continue
        secteur = TICKER_SECTEUR.get(r["ticker"])
        if not secteur or r.get("variation_pct") is None:
            continue
        try:
            d1 = datetime.strptime(r["signal_date"], "%Y-%m-%d")
            d2 = datetime.strptime(r["verification_date"], "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        if not (HORIZON_MIN <= (d2 - d1).days <= HORIZON_MAX):
            continue
        lignes.append({**r, "secteur": secteur, "mois": r["signal_date"][:7]})

    print(f"  {len(lignes)} verifications ACHAT+SURVEILLER a J+{HORIZON_MIN}-{HORIZON_MAX}")

    mois_tries = sorted({r["mois"] for r in lignes})
    secteurs_tries = sorted(SECTEUR_OFFICIEL)

    # ── Vue 1 : hit rate mensuel par secteur ─────────────────────────────────
    print()
    print("=" * 78)
    print("HIT RATE MENSUEL PAR SECTEUR  (n entre parentheses)")
    print("-" * 78)
    entete = f"  {'Secteur':<18}" + "".join(f"{m[5:]:>14}" for m in mois_tries)
    print(entete)
    print("-" * 78)

    cellules = defaultdict(dict)
    for r in lignes:
        cellules[r["secteur"]].setdefault(r["mois"], []).append(r)

    for secteur in secteurs_tries:
        ligne = f"  {secteur:<18}"
        for mois in mois_tries:
            obs = cellules[secteur].get(mois, [])
            if not obs:
                ligne += f"{'—':>14}"
            else:
                taux = sum(1 for r in obs if r["variation_pct"] > 0) / len(obs) * 100
                ligne += f"{taux:>8.1f}% ({len(obs):>2})"
        print(ligne)

    # Ligne globale
    print("-" * 78)
    ligne = f"  {'GLOBAL':<18}"
    for mois in mois_tries:
        obs = [r for r in lignes if r["mois"] == mois]
        if not obs:
            ligne += f"{'—':>14}"
        else:
            taux = sum(1 for r in obs if r["variation_pct"] > 0) / len(obs) * 100
            ligne += f"{taux:>8.1f}% ({len(obs):>3})"
    print(ligne)

    # ── Vue 2 : contexte de marche ───────────────────────────────────────────
    print()
    print("=" * 78)
    print("CONTEXTE DE MARCHE — BRVM Composite (source boc_indices)")
    print("-" * 78)

    composite = charger("boc_indices", {
        "select": "date_seance,valeur",
        "indice": "eq.BRVM_COMPOSITE",
        "order": "date_seance.asc",
    })

    if not composite:
        print("  boc_indices indisponible — contexte de marche non affiche")
    else:
        par_mois = defaultdict(list)
        for r in composite:
            par_mois[r["date_seance"][:7]].append((r["date_seance"], r["valeur"]))

        print(f"  {'Mois':<10} {'debut':>10} {'fin':>10} {'variation':>11}")
        print("-" * 78)
        for mois in sorted(par_mois):
            pts = sorted(par_mois[mois])
            debut, fin = pts[0][1], pts[-1][1]
            var = (fin - debut) / debut * 100 if debut else 0
            marque = "  <-- basculement" if mois in ("2026-06", "2026-07") else ""
            print(f"  {mois:<10} {debut:>10.2f} {fin:>10.2f} {var:>10.2f}%{marque}")

    # ── Mediane de variation par mois, tous secteurs ─────────────────────────
    print()
    print("=" * 78)
    print("MEDIANE DE VARIATION DES SIGNAUX, PAR MOIS")
    print("-" * 78)
    print(f"  {'Mois':<10} {'n':>5} {'hit':>8} {'mediane':>10}")
    print("-" * 78)
    for mois in mois_tries:
        obs = [r for r in lignes if r["mois"] == mois]
        taux = sum(1 for r in obs if r["variation_pct"] > 0) / len(obs) * 100
        med = mediane([r["variation_pct"] for r in obs])
        print(f"  {mois:<10} {len(obs):>5} {taux:>7.1f}% {med:>9.2f}%")

    print()
    print("=" * 78)
    print("LECTURE")
    print("  Si tous les secteurs chutent en juin -> changement de regime de")
    print("     marche, la conclusion sur les Industriels est a reconsiderer.")
    print("  Si seuls les Industriels chutent -> faiblesse sectorielle de V1,")
    print("     le constat tient.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
