#!/usr/bin/env python3
"""T16-backfill — Verification du retro-remplissage alpha/benchmark_return.

Lecture seule. Ne modifie rien : l'ecriture est faite par backfill_alpha.sql
via le SQL Editor (ADR-026). Ce script controle le resultat.

Controles : couverture, invariant moyenne(alpha)==0 par cohorte,
correspondance avec les lignes de production non retouchees.
"""
import logging
import os
import sys
from collections import defaultdict

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TABLE = "brvm_decisions_results"
DATE_PROD = "2026-07-28"
TOLERANCE = 0.01


def get_env():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logging.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env")
        sys.exit(1)
    return url.rstrip("/"), key


def fetch_all(url, key):
    """Recupere toutes les lignes par pages de 1000 (limite REST Supabase)."""
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows, offset, page = [], 0, 1000
    while True:
        r = requests.get(
            f"{url}/rest/v1/{TABLE}",
            headers={**headers, "Range": f"{offset}-{offset + page - 1}"},
            params={"select": "*", "order": "id"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def controle_couverture(rows):
    nulls = sum(1 for r in rows if r.get("alpha") is None)
    total = len(rows)
    couverture = 100.0 * (total - nulls) / total if total else 0.0
    logging.info("Couverture : %d/%d = %.2f%% (NULL restants : %d)",
                 total - nulls, total, couverture, nulls)
    return couverture >= 95.0


def controle_invariant(rows):
    """La moyenne des alpha d'une cohorte doit valoir 0 (residu d'arrondi pres)."""
    cohortes = defaultdict(list)
    for r in rows:
        if r.get("alpha") is not None:
            cohortes[(r["signal_date"], r["verification_date"])].append(r["alpha"])
    ecart_max = 0.0
    for cle, alphas in cohortes.items():
        ecart = abs(sum(alphas) / len(alphas))
        ecart_max = max(ecart_max, ecart)
    logging.info("Invariant : %d cohortes, ecart max a zero = %.6f",
                 len(cohortes), ecart_max)
    return ecart_max < TOLERANCE


def controle_prod(rows):
    """Confronte la formule aux lignes ecrites par verify_decisions.py."""
    prod = [r for r in rows if r["verification_date"] == DATE_PROD]
    if not prod:
        logging.warning("Aucune ligne de production au %s : controle ignore", DATE_PROD)
        return True
    br = round(sum(r["variation_pct"] for r in prod) / len(prod), 2)
    divergences = 0
    for r in prod:
        attendu = round(r["variation_pct"] - br, 2)
        if abs(r["alpha"] - attendu) > TOLERANCE or abs(r["benchmark_return"] - br) > TOLERANCE:
            divergences += 1
    logging.info("Production (%s) : n=%d, benchmark recalcule=%.2f, divergences=%d",
                 DATE_PROD, len(prod), br, divergences)
    return divergences == 0


def main():
    url, key = get_env()
    rows = fetch_all(url, key)
    logging.info("%d lignes recuperees depuis %s", len(rows), TABLE)
    resultats = {
        "couverture": controle_couverture(rows),
        "invariant": controle_invariant(rows),
        "production": controle_prod(rows),
    }
    for nom, ok in resultats.items():
        logging.info("%-12s : %s", nom, "OK" if ok else "ECHEC")
    if not all(resultats.values()):
        sys.exit(1)
    logging.info("T16-backfill conforme.")


if __name__ == "__main__":
    main()
