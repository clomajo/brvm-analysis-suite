#!/usr/bin/env python3
"""
health_check.py — Bilan quotidien du pipeline BRVM Analytics.

Objectif : détecter un run GitHub Actions qui sort en exit 0 sans avoir
rien inséré (cf. incident BACKLOG corrompu 1 mois sans détection).

Contrôles effectués pour AUJOURD'HUI (UTC) :
  - nb_prices     : historical_data.trade_date = aujourd'hui
  - nb_targets    : target_prices.calcul_date  = aujourd'hui
  - nb_decisions  : brvm_decisions.date        = aujourd'hui
  - missing_tickers : companies.symbol sans ligne historical_data
                       aujourd'hui (jointure via v_historical_prices)

Écrit un résumé Markdown dans $GITHUB_STEP_SUMMARY si disponible,
sinon dans health_report.md (exécution locale).

Exit codes :
  0 = OK, ou week-end/jour férié (BRVM fermée)
  1 = anomalie détectée (seuil non atteint) ou erreur d'infrastructure
      empêchant le calcul du bilan

ADR-004 : accès Supabase exclusivement via REST API (jamais psycopg2).
"""

import logging
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import find_dotenv, load_dotenv

# --------------------------------------------------------------------------
# Configuration / seuils
# --------------------------------------------------------------------------

MIN_PRICES = 999     # sur 47 tickers ; certains ne cotent pas chaque jour
MIN_TARGETS = 30
MIN_DECISIONS = 30

# Jours fériés BRVM 2026 — À REMPLIR PAR JOCELYN depuis le calendrier
# officiel BRVM (brvm.org). Ne jamais deviner ces dates : les fêtes
# musulmanes (Tabaski, Korité, etc.) varient chaque année et ne peuvent
# pas être calculées de façon fiable par le modèle.
# Format : liste de chaînes ISO "YYYY-MM-DD".
JOURS_FERIES_BRVM_2026 = [
    "2026-01-01",  # Jour de l'an
    "2026-03-17",  # Lendemain de la nuit du destin (*)
    "2026-03-20",  # Fete du Ramadan (*)
    "2026-04-06",  # Lundi de Paques
    "2026-05-01",  # Fete du Travail
    "2026-05-14",  # Ascension
    "2026-05-25",  # Lundi de Pentecote
    "2026-05-27",  # Tabaski (*)
    "2026-08-07",  # Independance
    "2026-08-26",  # Maouloud (*)
    "2026-12-25",  # Noel
    # (*) Dates sujettes a changement (fetes mobiles) - source brvm.org, calendrier publie 19/12/2025
]

REQUEST_TIMEOUT = 30  # secondes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("health_check")


# --------------------------------------------------------------------------
# Accès Supabase REST
# --------------------------------------------------------------------------

def get_supabase_config():
    """Charge et valide la config Supabase depuis l'environnement."""
    load_dotenv(find_dotenv(usecwd=True))

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        logger.error(
            "SUPABASE_URL et/ou SUPABASE_SERVICE_ROLE_KEY manquants dans "
            "l'environnement (.env non chargé ou incomplet)."
        )
        raise EnvironmentError("Configuration Supabase incomplète")

    base_url = supabase_url.rstrip("/") + "/rest/v1/"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    return base_url, headers


def get_exact_count(base_url, headers, table, date_column, today_str):
    """
    Compte les lignes de `table` où `date_column` = today_str, sans
    télécharger les données (Prefer: count=exact + Range: 0-0).
    """
    url = f"{base_url}{table}"
    params = {
        "select": "id",
        date_column: f"eq.{today_str}",
    }
    req_headers = dict(headers)
    req_headers["Prefer"] = "count=exact"
    req_headers["Range"] = "0-0"

    resp = requests.get(url, headers=req_headers, params=params, timeout=REQUEST_TIMEOUT)

    if resp.status_code not in (200, 206):
        logger.error(
            "Échec requête count sur %s (status %s) : %s",
            table, resp.status_code, resp.text[:500],
        )
        raise requests.HTTPError(f"Requête count échouée sur {table}")

    content_range = resp.headers.get("Content-Range")
    if not content_range or "/" not in content_range:
        logger.error(
            "Header Content-Range absent ou invalide pour %s : %r",
            table, content_range,
        )
        raise ValueError(f"Content-Range invalide pour {table}")

    total_str = content_range.split("/")[-1]
    if total_str == "*":
        logger.error("Content-Range renvoie un total inconnu ('*') pour %s", table)
        raise ValueError(f"Total inconnu pour {table}")

    return int(total_str)


def get_missing_tickers(base_url, headers, today_str):
    """
    Retourne la liste triée des companies.symbol sans ligne
    historical_data aujourd'hui, via v_historical_prices.
    """
    # Tous les tickers connus
    resp_companies = requests.get(
        f"{base_url}companies",
        headers=headers,
        params={"select": "symbol"},
        timeout=REQUEST_TIMEOUT,
    )
    if resp_companies.status_code != 200:
        logger.error(
            "Échec requête companies (status %s) : %s",
            resp_companies.status_code, resp_companies.text[:500],
        )
        raise requests.HTTPError("Requête companies échouée")

    all_symbols = {row["symbol"] for row in resp_companies.json()}

    # Tickers avec un prix aujourd'hui
    resp_prices = requests.get(
        f"{base_url}v_historical_prices",
        headers=headers,
        params={"select": "ticker", "trade_date": f"eq.{today_str}"},
        timeout=REQUEST_TIMEOUT,
    )
    if resp_prices.status_code != 200:
        logger.error(
            "Échec requête v_historical_prices (status %s) : %s",
            resp_prices.status_code, resp_prices.text[:500],
        )
        raise requests.HTTPError("Requête v_historical_prices échouée")

    present_tickers = {row["ticker"] for row in resp_prices.json()}

    missing = sorted(all_symbols - present_tickers)
    return missing


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def build_markdown_report(today_str, results, missing_tickers, note=None):
    def status_icon(value, threshold):
        return "✅" if value >= threshold else "❌"

    lines = [
        f"## Health Report — {today_str}",
        "",
    ]
    if note:
        lines.append(f"> {note}")
        lines.append("")

    lines.append("| Métrique | Valeur | Seuil | Statut |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| nb_prices | {results['nb_prices']} | {MIN_PRICES} | "
        f"{status_icon(results['nb_prices'], MIN_PRICES)} |"
    )
    lines.append(
        f"| nb_targets | {results['nb_targets']} | {MIN_TARGETS} | "
        f"{status_icon(results['nb_targets'], MIN_TARGETS)} |"
    )
    lines.append(
        f"| nb_decisions | {results['nb_decisions']} | {MIN_DECISIONS} | "
        f"{status_icon(results['nb_decisions'], MIN_DECISIONS)} |"
    )
    lines.append("")

    if missing_tickers:
        lines.append(f"**Tickers manquants aujourd'hui ({len(missing_tickers)}) :**")
        lines.append("")
        lines.append(", ".join(missing_tickers))
    else:
        lines.append("**Aucun ticker manquant aujourd'hui.**")

    lines.append("")
    return "\n".join(lines)


def write_report(markdown):
    """Écrit le résumé dans $GITHUB_STEP_SUMMARY (CI) ou health_report.md (local)."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
        logger.info("Résumé écrit dans GITHUB_STEP_SUMMARY")
    else:
        with open("health_report.md", "w", encoding="utf-8") as f:
            f.write(markdown + "\n")
        logger.info("Résumé écrit dans health_report.md (exécution locale)")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()

    # Jour férié BRVM → ne jamais échouer
    if today_str in JOURS_FERIES_BRVM_2026:
        logger.info("Jour férié BRVM (%s) — script OK sans vérification.", today_str)
        markdown = f"## Health Report — {today_str}\n\n> Jour férié BRVM — aucune vérification effectuée.\n"
        write_report(markdown)
        sys.exit(0)

    # Week-end → ne jamais échouer
    is_weekend = today.weekday() >= 5
    if is_weekend:
        logger.info("Week-end (%s) — script OK sans vérification.", today_str)
        markdown = f"## Health Report — {today_str}\n\n> Week-end — BRVM fermée, aucune vérification effectuée.\n"
        write_report(markdown)
        sys.exit(0)

    # Jour ouvré : calcul du bilan via REST API
    try:
        base_url, headers = get_supabase_config()

        nb_prices = get_exact_count(base_url, headers, "historical_data", "trade_date", today_str)
        nb_targets = get_exact_count(base_url, headers, "target_prices", "calcul_date", today_str)
        nb_decisions = get_exact_count(base_url, headers, "brvm_decisions", "date", today_str)
        missing_tickers = get_missing_tickers(base_url, headers, today_str)
    except (EnvironmentError, requests.RequestException, ValueError) as exc:
        # Erreur d'infrastructure (réseau, clé manquante, réponse invalide) :
        # on ne peut pas calculer le bilan → on échoue bruyamment.
        logger.error("Erreur d'infrastructure empêchant le calcul du bilan : %s", exc)
        markdown = (
            f"## Health Report — {today_str}\n\n"
            f"> ❌ Erreur d'infrastructure — bilan non calculé : {exc}\n"
        )
        write_report(markdown)
        sys.exit(1)

    results = {
        "nb_prices": nb_prices,
        "nb_targets": nb_targets,
        "nb_decisions": nb_decisions,
    }

    logger.info(
        "nb_prices=%s nb_targets=%s nb_decisions=%s missing_tickers=%s",
        nb_prices, nb_targets, nb_decisions, len(missing_tickers),
    )

    markdown = build_markdown_report(today_str, results, missing_tickers)
    write_report(markdown)

    threshold_failed = (
        nb_prices < MIN_PRICES
        or nb_targets < MIN_TARGETS
        or nb_decisions < MIN_DECISIONS
    )
    zero_prices_on_business_day = nb_prices == 0  # jour ouvré déjà garanti à ce stade

    if threshold_failed or zero_prices_on_business_day:
        logger.warning("Anomalie détectée — seuils non atteints ou aucune donnée insérée.")
        sys.exit(1)

    logger.info("Bilan quotidien OK — tous les seuils sont atteints.")
    sys.exit(0)


if __name__ == "__main__":
    main()
