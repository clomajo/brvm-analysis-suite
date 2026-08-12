#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingestion BOC -> Supabase.

Chaine complete : telechargement du bulletin, parsing (tools/parse_boc.py),
controles de coherence, puis upsert dans 4 tables.

Cibles (ADR-048) :
  - boc_indices            (date_seance, indice)   — phares, compartiments,
                                                     total return, sectoriels
  - boc_market_stats       (date_seance, marche)   — agregats ACTIONS/OBLIGATIONS
  - boc_market_indicators  (date_seance)           — 14 indicateurs
  - new_market_indicators  (extraction_date)       — 6 colonnes, conservee pour
                                                     ne pas casser report_generator.py

REGLE : aucune ecriture si un controle de coherence echoue. Les invariants du
bulletin (breadth, sommes des compartiments, recoupement des indices phares)
sont la seule protection contre un appariement de colonnes errone. Ecrire
malgre un echec reviendrait a les rendre inutiles.

Idempotent : upsert sur cle metier, rejouer une date met a jour sans dupliquer.

Usage :
    python3 tools/ingest_boc.py --date 2026-08-10 --dry-run
    python3 tools/ingest_boc.py --date 2026-08-10
    python3 tools/ingest_boc.py --file /tmp/boc/boc_20260810_2.pdf
    python3 tools/ingest_boc.py --from 2026-08-01 --to 2026-08-12   # plage
    python3 tools/ingest_boc.py --date 2026-08-10 --force           # ignore controles
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_boc import (  # noqa: E402
    URL_TEMPLATE,
    SchemaBocInconnu,
    parser_boc,
    telecharger,
)

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

# Base de reference des indices, telle que publiee au bas de chaque tableau.
# Etiquette le regime : les valeurs de regimes differents ne sont pas
# comparables directement (ADR-046).
BASE_PAR_TYPE = {
    "PHARE": None,              # non precisee dans l'encadre du haut
    "COMPARTIMENT": "2023-01-02",
    "TOTAL_RETURN": "2025-01-02",
    "SECTORIEL": "2025-01-02",
}

PAUSE_ENTRE_DATES = 1.5


def entetes(prefer=None):
    base = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        base["Prefer"] = prefer
    return base


def upsert(table, on_conflict, lignes):
    """Upsert PostgREST. Retourne le nombre de lignes envoyees."""
    if not lignes:
        return 0

    reponse = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}",
        headers=entetes("resolution=merge-duplicates,return=minimal"),
        json=lignes,
        timeout=60,
    )
    if reponse.status_code not in (200, 201, 204):
        # Le corps JSON de PostgREST porte le detail de l'erreur — l'afficher
        # avant raise_for_status, qui ne le montre pas.
        logger.error("%s : HTTP %s — %s", table, reponse.status_code,
                     reponse.text[:400])
        reponse.raise_for_status()
    return len(lignes)


def construire_indices(data, url):
    """Aplatit les 4 familles d'indices en lignes de boc_indices."""
    lignes = []
    commun = {
        "date_seance": data["date_seance"],
        "bulletin_numero": data["bulletin_numero"],
        "schema_version": data["schema_version"],
        "source_url": url,
    }

    # PostgREST (PGRST102) exige des clefs identiques sur tout le lot : les
    # lignes PHARE doivent donc porter explicitement a None les colonnes que
    # l'encadre du haut ne fournit pas.
    for nom, valeurs in data["indices_phares"].items():
        lignes.append({
            **commun,
            "type_indice": "PHARE",
            "indice": nom,
            "valeur": valeurs.get("valeur"),
            "var_jour_pct": valeurs.get("var_jour_pct"),
            "var_annuelle_pct": valeurs.get("var_annuelle_pct"),
            "nb_societes": None,
            "volume": None,
            "valeur_transigee": None,
            "per_moyen": None,
            "base_reference": BASE_PAR_TYPE["PHARE"],
        })

    familles = (
        ("COMPARTIMENT", data["indices_compartiments"]),
        ("TOTAL_RETURN", data["indice_total_return"]),
        ("SECTORIEL", data["indices_sectoriels"]),
    )
    for type_indice, bloc in familles:
        for nom, valeurs in bloc.items():
            lignes.append({
                **commun,
                "type_indice": type_indice,
                "indice": nom,
                "valeur": valeurs.get("valeur"),
                "var_jour_pct": valeurs.get("evol_jour"),
                "var_annuelle_pct": valeurs.get("evol_annuelle"),
                "nb_societes": _entier(valeurs.get("nb_societes")),
                "volume": _entier(valeurs.get("volume")),
                "valeur_transigee": valeurs.get("valeur_transigee"),
                "per_moyen": valeurs.get("per_moyen"),
                "base_reference": BASE_PAR_TYPE[type_indice],
            })
    return lignes


def _entier(valeur):
    """Convertit en int pour les colonnes INTEGER/BIGINT, en preservant None."""
    return None if valeur is None else int(round(valeur))


def construire_stats(data, url):
    """Une ligne par marche."""
    lignes = []
    for marche, bloc in data["agregats_marche"].items():
        if not bloc:
            continue
        lignes.append({
            "date_seance": data["date_seance"],
            "bulletin_numero": data["bulletin_numero"],
            "marche": marche,
            "capitalisation": bloc.get("capitalisation"),
            "capitalisation_evol_jour_pct": bloc.get("capitalisation_evol_jour_pct"),
            "volume_echange": _entier(bloc.get("volume_echange")),
            "volume_echange_evol_jour_pct": bloc.get("volume_echange_evol_jour_pct"),
            "valeur_transigee": bloc.get("valeur_transigee"),
            "valeur_transigee_evol_jour_pct": bloc.get("valeur_transigee_evol_jour_pct"),
            "nb_titres_transiges": _entier(bloc.get("nb_titres_transiges")),
            "nb_titres_transiges_evol_jour_pct": bloc.get(
                "nb_titres_transiges_evol_jour_pct"),
            "nb_hausse": _entier(bloc.get("nb_hausse")),
            "nb_hausse_evol_jour_pct": bloc.get("nb_hausse_evol_jour_pct"),
            "nb_baisse": _entier(bloc.get("nb_baisse")),
            "nb_baisse_evol_jour_pct": bloc.get("nb_baisse_evol_jour_pct"),
            "nb_inchanges": _entier(bloc.get("nb_inchanges")),
            "nb_inchanges_evol_jour_pct": bloc.get("nb_inchanges_evol_jour_pct"),
            "schema_version": data["schema_version"],
            "source_url": url,
        })
    return lignes


def construire_indicateurs(data, url):
    """Une ligne unique pour la seance."""
    ind = data["indicateurs"]
    if not ind:
        return []

    entiers = {"nb_societes_cotees", "nb_lignes_obligataires", "nb_sgi"}
    ligne = {
        "date_seance": data["date_seance"],
        "bulletin_numero": data["bulletin_numero"],
        "schema_version": data["schema_version"],
        "source_url": url,
    }
    for cle, valeur in ind.items():
        ligne[cle] = _entier(valeur) if cle in entiers else valeur
    return [ligne]


def construire_legacy(data):
    """Alimente new_market_indicators (6 colonnes) — cf. ADR-048.

    report_generator.py lit cette table dans 3 requetes. Elle est maintenue en
    parallele des tables boc_* jusqu'a sa migration.
    """
    phares = data["indices_phares"]
    actions = data["agregats_marche"].get("ACTIONS", {})

    # Schema reel : id, extraction_date, brvm_composite, brvm_30, brvm_prestige,
    # capitalisation_globale. Les colonnes volume_moyen_annuel et
    # valeur_moyenne_annuelle du INSERT de data_collector.py (L289-296)
    # N'EXISTENT PAS — ce script planterait s'il etait rebranche tel quel.
    # Ces deux mesures sont disponibles dans boc_market_indicators.
    return [{
        "extraction_date": data["date_seance"],
        "brvm_composite": phares.get("BRVM_COMPOSITE", {}).get("valeur"),
        "brvm_30": phares.get("BRVM_30", {}).get("valeur"),
        "brvm_prestige": phares.get("BRVM_PRESTIGE", {}).get("valeur"),
        "capitalisation_globale": actions.get("capitalisation"),
    }]


def ingerer(chemin_pdf, url, dry_run, force):
    """Parse puis ecrit. Retourne un dict de statistiques."""
    stats = {"statut": "?", "indices": 0, "stats": 0, "indicateurs": 0, "legacy": 0}

    try:
        data = parser_boc(chemin_pdf)
    except SchemaBocInconnu as exc:
        logger.error("  schema non reconnu : %s", exc)
        stats["statut"] = "SCHEMA_REJETE"
        return stats

    echecs = [c for c in data["controles"] if c["statut"] == "ECHEC"]
    if echecs:
        for controle in echecs:
            logger.error("  controle ECHEC : %s (%s vs %s)",
                         controle["controle"], controle["gauche"], controle["droite"])
        if not force:
            logger.error("  ECRITURE REFUSEE — %d controle(s) en echec", len(echecs))
            stats["statut"] = "CONTROLES_KO"
            return stats
        logger.warning("  --force : ecriture malgre %d echec(s)", len(echecs))

    lots = (
        ("boc_indices", "date_seance,indice", construire_indices(data, url), "indices"),
        ("boc_market_stats", "date_seance,marche", construire_stats(data, url), "stats"),
        ("boc_market_indicators", "date_seance",
         construire_indicateurs(data, url), "indicateurs"),
        ("new_market_indicators", "extraction_date", construire_legacy(data), "legacy"),
    )

    if dry_run:
        for table, _conflit, lignes, cle in lots:
            logger.info("  [DRY-RUN] %s : %d ligne(s)", table, len(lignes))
            stats[cle] = len(lignes)
        stats["statut"] = "DRY_RUN"
        return stats

    for table, conflit, lignes, cle in lots:
        stats[cle] = upsert(table, conflit, lignes)
        logger.info("  %s : %d ligne(s)", table, stats[cle])

    stats["statut"] = "OK"
    return stats


def dates_a_traiter(args):
    """Construit la liste des dates a ingerer selon les arguments."""
    if args.date:
        return [datetime.strptime(args.date, "%Y-%m-%d").date()]

    debut = datetime.strptime(getattr(args, "from"), "%Y-%m-%d").date()
    fin = datetime.strptime(args.to, "%Y-%m-%d").date()
    if fin < debut:
        raise ValueError("--to anterieur a --from")

    jours, courant = [], debut
    while courant <= fin:
        # Le BOC ne parait pas le week-end ; inutile de solliciter le serveur.
        if courant.weekday() < 5:
            jours.append(courant)
        courant += timedelta(days=1)
    return jours


def main():
    parseur = argparse.ArgumentParser(description="Ingestion BOC -> Supabase")
    source = parseur.add_mutually_exclusive_group(required=True)
    source.add_argument("--date", help="date de seance AAAA-MM-JJ")
    source.add_argument("--file", help="PDF local deja telecharge")
    source.add_argument("--from", dest="from", help="debut de plage AAAA-MM-JJ")
    parseur.add_argument("--to", help="fin de plage AAAA-MM-JJ (avec --from)")
    parseur.add_argument("--dry-run", action="store_true", help="simule sans ecrire")
    parseur.add_argument("--force", action="store_true",
                         help="ecrit malgre des controles en echec (deconseille)")
    args = parseur.parse_args()

    if getattr(args, "from") and not args.to:
        parseur.error("--from requiert --to")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env")
        return 1

    resultats = {}

    if args.file:
        chemin = Path(args.file).expanduser()
        if not chemin.is_file():
            logger.error("fichier introuvable : %s", chemin)
            return 1
        logger.info("--- %s ---", chemin.name)
        resultats[chemin.name] = ingerer(chemin, None, args.dry_run, args.force)
    else:
        try:
            jours = dates_a_traiter(args)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1

        logger.info("%d date(s) a traiter%s", len(jours),
                    " [DRY-RUN]" if args.dry_run else "")
        for index, jour in enumerate(jours):
            logger.info("--- %s ---", jour)
            try:
                chemin = telecharger(jour)
            except requests.RequestException as exc:
                logger.error("  echec reseau : %s", exc)
                resultats[jour.isoformat()] = {"statut": "ECHEC_RESEAU"}
                continue

            if chemin is None:
                # 404 = jour non ouvre (ADR-046), pas une anomalie.
                resultats[jour.isoformat()] = {"statut": "NON_OUVRE"}
            else:
                url = URL_TEMPLATE.format(ymd=jour.strftime("%Y%m%d"))
                resultats[jour.isoformat()] = ingerer(
                    chemin, url, args.dry_run, args.force)

            if index < len(jours) - 1:
                time.sleep(PAUSE_ENTRE_DATES)

    print("\n--- Resume ---")
    print(f"{'date':<14} {'statut':<16} {'indices':>8} {'stats':>6} "
          f"{'indic.':>7} {'legacy':>7}")
    for cle, stats in resultats.items():
        print(f"{cle:<14} {stats.get('statut', '?'):<16} "
              f"{stats.get('indices', 0):>8} {stats.get('stats', 0):>6} "
              f"{stats.get('indicateurs', 0):>7} {stats.get('legacy', 0):>7}")

    problemes = [c for c, s in resultats.items()
                 if s.get("statut") in ("CONTROLES_KO", "SCHEMA_REJETE",
                                        "ECHEC_RESEAU")]
    if problemes:
        logger.error("%d date(s) en anomalie : %s",
                     len(problemes), ", ".join(problemes))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
