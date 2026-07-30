"""
diagnostic_concentration_sectorielle.py
-----------------------------------------
T14 — Diagnostic concentration sectorielle (15 min).

Contexte : hypothèse à vérifier — V2 serait en réalité un "long banques
UEMOA avec timing dividende".

Compte la répartition par secteur (7 catégories officielles BRVM, mapping
SECTEUR_OFFICIEL de calculate_target_price.py — PAS companies.sector qui
utilise un mapping différent/plus grossier) de :
  (a) les 25 signaux ACHAT du backtest V2 (backtest_value.py, commit 49a64b6)
  (b) les signaux ACHAT actuels de target_prices

Règle (appliquée textuellement) : si un secteur > 60% des signaux → à
noter dans DECISIONS.md.

Lecture seule REST. Aucune modification du pipeline de production.
"""

import logging
import os
import sys
from collections import Counter

from dotenv import find_dotenv, load_dotenv
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("diagnostic_concentration_sectorielle")

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Mapping EXACT repris de calculate_target_price.py (SECTEUR_OFFICIEL),
# fichier source non modifié — 7 catégories officielles BRVM.
SECTEUR_OFFICIEL = {
    # CONSOMMATION DE BASE (9)
    "NTLC": "CONSOMMATION_DE_BASE", "PALC": "CONSOMMATION_DE_BASE",
    "SPHC": "CONSOMMATION_DE_BASE", "SICC": "CONSOMMATION_DE_BASE",
    "STBC": "CONSOMMATION_DE_BASE", "SOGC": "CONSOMMATION_DE_BASE",
    "SLBC": "CONSOMMATION_DE_BASE", "SCRC": "CONSOMMATION_DE_BASE",
    "UNLC": "CONSOMMATION_DE_BASE",

    # CONSOMMATION DISCRETIONNAIRE (7)
    "BNBC": "CONSOMMATION_DISCRETIONNAIRE", "CFAC": "CONSOMMATION_DISCRETIONNAIRE",
    "LNBB": "CONSOMMATION_DISCRETIONNAIRE", "NEIC": "CONSOMMATION_DISCRETIONNAIRE",
    "ABJC": "CONSOMMATION_DISCRETIONNAIRE",
    "PRSC": "CONSOMMATION_DISCRETIONNAIRE",
    "UNXC": "CONSOMMATION_DISCRETIONNAIRE",

    # ENERGIE (4)
    "SMBC": "ENERGIE", "TTLC": "ENERGIE", "TTLS": "ENERGIE", "SHEC": "ENERGIE",

    # INDUSTRIELS (6)
    "SDSC": "INDUSTRIELS", "SEMC": "INDUSTRIELS", "SIVC": "INDUSTRIELS",
    "FTSC": "INDUSTRIELS",
    "STAC": "INDUSTRIELS",
    "CABC": "INDUSTRIELS",

    # SERVICES FINANCIERS (16)
    "BOAB": "SERVICES_FINANCIERS", "BOABF": "SERVICES_FINANCIERS",
    "BOAC": "SERVICES_FINANCIERS", "BOAM": "SERVICES_FINANCIERS",
    "BOAN": "SERVICES_FINANCIERS", "BOAS": "SERVICES_FINANCIERS",
    "BICB": "SERVICES_FINANCIERS", "BICC": "SERVICES_FINANCIERS",
    "CBIBF": "SERVICES_FINANCIERS", "ECOC": "SERVICES_FINANCIERS",
    "ETIT": "SERVICES_FINANCIERS", "NSBC": "SERVICES_FINANCIERS",
    "ORGT": "SERVICES_FINANCIERS", "SAFC": "SERVICES_FINANCIERS",
    "SGBC": "SERVICES_FINANCIERS", "SIBC": "SERVICES_FINANCIERS",

    # SERVICES PUBLICS (2)
    "CIEC": "SERVICES_PUBLICS", "SDCC": "SERVICES_PUBLICS",

    # TELECOMMUNICATIONS (3)
    "ONTBF": "TELECOMMUNICATIONS", "ORAC": "TELECOMMUNICATIONS",
    "SNTS": "TELECOMMUNICATIONS",
}

SEUIL_CONCENTRATION = 0.60  # 60%, spec T14


def print_repartition(label: str, tickers: list):
    """Affiche la répartition sectorielle d'une liste de tickers (avec doublons possibles)."""
    n = len(tickers)
    if n == 0:
        print(f"\n{label} : aucun ticker, rien à analyser.")
        return None

    compteur = Counter()
    non_mappes = []
    for t in tickers:
        secteur = SECTEUR_OFFICIEL.get(t)
        if secteur is None:
            non_mappes.append(t)
            compteur["NON_MAPPE"] += 1
        else:
            compteur[secteur] += 1

    print(f"\n{label} (n={n}) :")
    max_secteur = None
    max_pct = 0.0
    for secteur, count in compteur.most_common():
        pct = count / n * 100
        print(f"  {secteur:32} {count:3}  ({pct:5.1f}%)")
        if secteur != "NON_MAPPE" and pct > max_pct:
            max_pct = pct
            max_secteur = secteur

    if non_mappes:
        print(f"  ⚠️  Tickers non mappés (absents de SECTEUR_OFFICIEL) : {non_mappes}")

    return max_secteur, max_pct


def volet_a_backtest():
    """
    25 signaux ACHAT du backtest V2 — repris directement (mêmes tickers/FY
    que le run manuel de backtest_value.py et de tools/falsification_v2.py,
    Volet C, tous deux validés à n=25 le 28/07/2026).
    """
    signaux = [
        "NSBC", "BOAS", "NSBC", "BOAC", "BOABF", "BOAS", "NSBC", "BOAC",
        "BOABF", "ONTBF", "BOABF", "BOAC", "BOABF", "BOAB", "NSBC", "CIEC",
        "ONTBF", "BOAS", "BOAC", "SPHC", "TTLC", "SPHC", "BOAB", "SOGC", "SOGC",
    ]
    assert len(signaux) == 25, f"Attendu 25 signaux, trouvé {len(signaux)}"
    return signaux


def volet_b_target_prices():
    """Signaux ACHAT actuels de target_prices (signal_v2 = ACHAT ou équivalent)."""
    resp = (
        supabase.table("target_prices")
        .select("ticker, signal_v2, calcul_date")
        .order("calcul_date", desc=True)
        .execute()
    )

    # On prend la ligne la plus récente par ticker (calcul_date desc déjà
    # trié, donc premier ticker rencontré = le plus récent).
    latest_par_ticker = {}
    for row in resp.data:
        ticker = row["ticker"]
        if ticker not in latest_par_ticker:
            latest_par_ticker[ticker] = row

    achats = [
        ticker for ticker, row in latest_par_ticker.items()
        if row.get("signal_v2") == "ACHAT"
    ]
    logger.info(
        "Volet B : %d tickers avec target_prices, %d en signal_v2=ACHAT (dernière valeur)",
        len(latest_par_ticker), len(achats),
    )
    return achats


def main():
    logger.info("T14 — Diagnostic concentration sectorielle — démarrage")

    signaux_a = volet_a_backtest()
    max_secteur_a, max_pct_a = print_repartition(
        "Volet (a) — 25 signaux ACHAT du backtest V2", signaux_a
    )

    signaux_b = volet_b_target_prices()
    result_b = print_repartition(
        "Volet (b) — signaux ACHAT actuels de target_prices", signaux_b
    )
    max_secteur_b, max_pct_b = result_b if result_b else (None, 0.0)

    print(f"\n{'=' * 60}")
    print("VERDICT (règle appliquée textuellement, seuil 60%) :")

    for label, max_secteur, max_pct in [
        ("Volet (a) backtest", max_secteur_a, max_pct_a),
        ("Volet (b) target_prices actuel", max_secteur_b, max_pct_b),
    ]:
        if max_pct > SEUIL_CONCENTRATION * 100:
            print(
                f"  {label} : {max_secteur} = {max_pct:.1f}% > 60% → "
                f"'V2 = exposition sectorielle concentrée ; plafond "
                f"d'exposition par secteur à fixer par Jocelyn "
                f"(proposition de départ : 50% du capital alloué à V2).'"
            )
        else:
            print(
                f"  {label} : secteur max = {max_secteur} à {max_pct:.1f}% "
                f"(≤ 60%) → pas de concentration excessive selon le seuil défini."
            )
    print(f"{'=' * 60}\n")

    logger.info("T14 terminé. Résultats à coller dans DECISIONS.md si seuil dépassé.")


if __name__ == "__main__":
    main()
