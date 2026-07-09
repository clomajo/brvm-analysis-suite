"""
investigate_ntlc.py — Script JETABLE (tools/)

Phase 3 — P1 : Vérification NTLC (split vs erreur de scraping)

Contexte : shares_outstanding corrigé 1 100 000 -> 22 070 400 (facteur ~20.064x).
Objectif : détecter si une discontinuité de prix ~/20 existe dans l'historique
NTLC (split réel non ajusté) ou si l'historique est continu (ancienne valeur
= pure erreur de saisie source, sans impact sur les prix).

Ce script ne prend AUCUNE décision : il produit des données brutes.
La branche de l'arbre de décision est tranchée par Jocelyn (cf. tâche T3).

Sorties :
  - tools/ntlc_report.csv  (trade_date,price,variation_pct — historique complet)
  - stdout : 3 sections (TOP 10 variations, min/max par année, corporate_events bruts)

Contraintes respectées :
  - REST-only (ADR-004), pas de psycopg2
  - load_dotenv(find_dotenv(usecwd=True))
  - logging module (INFO/WARNING/ERROR -> stderr), aucun print pour les erreurs
  - aucun except silencieux
  - script additif, ne modifie aucun script existant
"""

import csv
import logging
import os
import sys
import time
from collections import defaultdict

import requests
from dotenv import find_dotenv, load_dotenv

# --- Setup ---------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("investigate_ntlc")

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

TICKER = "NTLC"
VARIATION_THRESHOLD = 40.0  # %
PAGE_SIZE = 1000
MAX_RETRIES = 1  # règle des 3 tentatives : erreurs réseau = triage, pas de retry en boucle
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "ntlc_report.csv")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }


def _check_env():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error(
            "Variables d'environnement manquantes (SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY). Vérifier le .env — "
            "erreur d'infrastructure, intervention humaine requise."
        )
        sys.exit(1)


def fetch_paginated(endpoint, params):
    """Récupère toutes les lignes d'un endpoint REST via pagination Range."""
    all_rows = []
    offset = 0

    while True:
        range_header = f"{offset}-{offset + PAGE_SIZE - 1}"
        headers = _headers()
        headers["Range"] = range_header

        attempt = 0
        while True:
            try:
                resp = requests.get(
                    f"{SUPABASE_URL}/rest/v1/{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                break
            except requests.exceptions.RequestException as exc:
                attempt += 1
                if attempt > MAX_RETRIES:
                    logger.error(
                        "Erreur réseau persistante sur %s (offset=%d) : %s "
                        "— erreur d'infrastructure, STOP.",
                        endpoint, offset, exc,
                    )
                    sys.exit(1)
                logger.warning(
                    "Erreur réseau sur %s (offset=%d) : %s — retry dans 30s (1/%d).",
                    endpoint, offset, exc, MAX_RETRIES,
                )
                time.sleep(30)

        if resp.status_code not in (200, 206):
            logger.error(
                "Réponse inattendue de %s (offset=%d) : HTTP %d — %s",
                endpoint, offset, resp.status_code, resp.text[:500],
            )
            sys.exit(1)

        page = resp.json()
        all_rows.extend(page)
        logger.info("Page récupérée : offset=%d, lignes=%d", offset, len(page))

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows


def compute_variations(rows):
    """Calcule les variations journalières en %. rows triées par trade_date asc."""
    enriched = []
    prev_price = None
    for row in rows:
        price = row.get("price")
        trade_date = row.get("trade_date")
        if price is None or trade_date is None:
            logger.warning("Ligne incomplète ignorée pour le calcul de variation : %s", row)
            continue
        price = float(price)
        if prev_price is not None and prev_price != 0:
            variation_pct = (price - prev_price) / prev_price * 100
        else:
            variation_pct = None
        enriched.append({
            "trade_date": trade_date,
            "price": price,
            "variation_pct": variation_pct,
        })
        prev_price = price
    return enriched


def write_csv(enriched, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["trade_date", "price", "variation_pct"])
        for r in enriched:
            var = "" if r["variation_pct"] is None else f"{r['variation_pct']:.4f}"
            writer.writerow([r["trade_date"], r["price"], var])
    logger.info("CSV écrit : %s (%d lignes)", path, len(enriched))


def print_top_variations(enriched, n=10):
    dated = [r for r in enriched if r["variation_pct"] is not None]
    top = sorted(dated, key=lambda r: abs(r["variation_pct"]), reverse=True)[:n]
    print("=== SECTION 1 : TOP 10 VARIATIONS JOURNALIÈRES ===")
    for r in top:
        print(f"{r['trade_date']},{r['variation_pct']:.2f}%")
    print()
    over_threshold = [r for r in dated if abs(r["variation_pct"]) > VARIATION_THRESHOLD]
    print(f"=== VARIATIONS |%| > {VARIATION_THRESHOLD} ({len(over_threshold)} occurrences) ===")
    for r in over_threshold:
        print(f"{r['trade_date']},{r['variation_pct']:.2f}%")
    print()


def print_min_max_by_year(enriched):
    by_year = defaultdict(list)
    for r in enriched:
        year = r["trade_date"][:4]
        by_year[year].append(r["price"])
    print("=== SECTION 2 : MIN/MAX PAR ANNÉE ===")
    for year in sorted(by_year.keys()):
        prices = by_year[year]
        print(f"{year},min={min(prices)},max={max(prices)},n={len(prices)}")
    print()


def print_corporate_events(events):
    print("=== SECTION 3 : CORPORATE_EVENTS (BRUT) ===")
    if not events:
        print("(aucun événement trouvé)")
    for e in events:
        print(
            f"{e.get('event_date')},{e.get('event_type')},"
            f"{ {k: v for k, v in e.items() if k not in ('event_date', 'event_type')} }"
        )
    print()


def main():
    _check_env()

    logger.info("Récupération historique %s via v_historical_prices...", TICKER)
    history_rows = fetch_paginated(
        "v_historical_prices",
        {"ticker": f"eq.{TICKER}", "order": "trade_date.asc"},
    )
    logger.info("Total lignes historique récupérées : %d", len(history_rows))

    if not history_rows:
        logger.error(
            "Aucune donnée retournée pour %s sur v_historical_prices. "
            "Vérifier le nom de colonne (ticker) et la présence de données.",
            TICKER,
        )
        sys.exit(1)

    enriched = compute_variations(history_rows)
    write_csv(enriched, OUTPUT_CSV)

    logger.info("Récupération corporate_events pour %s...", TICKER)
    events = fetch_paginated(
        "corporate_events",
        {"ticker": f"eq.{TICKER}", "order": "event_date.asc"},
    )
    logger.info("Total événements récupérés : %d", len(events))

    print_top_variations(enriched, n=10)
    print_min_max_by_year(enriched)
    print_corporate_events(events)


if __name__ == "__main__":
    main()
