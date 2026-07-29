"""
falsification_v2.py
--------------------
T9 — Test de falsification : V2 vs benchmarks réels.

Contexte : le vrai benchmark de V2 n'est pas le BRVMC. C'est (A) la
stratégie dividende naïve déjà validée, et (B) les recommandations BOA
déjà présentes en base. Si V2 ne bat ni l'une ni l'autre, la machinerie
de valorisation n'ajoute rien.

AUCUNE MODIFICATION DU PIPELINE DE PROD. Lecture seule REST.

Volet A — stratégie naïve dividende :
  Tickers {BOAB, BOAC, ECOC, SMBC, NSBC, NTLC}, yield >= 8% au moment de
  l'achat, achat J-19 avant ex-date (corporate_events, event_type=
  EX_DIVIDEND, FY2022-FY2025), sortie J+90, rendement = variation de
  prix + dividende.

Volet B — recommandations BOA :
  Table boa_recommendations, action=BUY, rendement J+90 depuis
  date_start. N'évalue que les recos dont la fenêtre J+90 est
  entièrement écoulée (date_start + 90j <= aujourd'hui).

Volet C — V2 :
  Réplique la logique de sélection de backtest_value.py (commit
  49a64b6, fichier source NON modifié) : décote_pct > 15% -> ACHAT,
  même horizon J+90. n attendu = 25 (confirmé par run manuel du
  28/07/2026).

Sortie : tableau comparatif A / B / C -> à coller dans REMEDIATION_LOG.md.
Règles d'interprétation appliquées textuellement, sans jugement.

Variables d'environnement requises :
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import statistics
import sys
from datetime import date, timedelta

import os
from dotenv import find_dotenv, load_dotenv
from supabase import create_client

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("falsification_v2")

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TODAY = date.today()

# ----------------------------------------------------------------------
# Volet A — Stratégie naïve dividende
# ----------------------------------------------------------------------

TICKERS_DIVIDENDE = ["BOAB", "BOAC", "ECOC", "SMBC", "NSBC", "NTLC"]
YIELD_MIN = 8.0
ENTREE_J_AVANT_EXDATE = 19
SORTIE_J = 90


def fetch_prices_for_ticker(ticker: str) -> dict:
    """Récupère tout l'historique de prix pour un ticker, indexé par date ISO."""
    co = supabase.table("companies").select("id").eq("symbol", ticker).execute()
    if not co.data:
        return {}
    company_id = co.data[0]["id"]

    prices = {}
    offset = 0
    page_size = 1000
    while True:
        resp = (
            supabase.table("historical_data")
            .select("trade_date, price")
            .eq("company_id", company_id)
            .order("trade_date", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        for row in resp.data:
            prices[row["trade_date"]] = row["price"]
        if len(resp.data) < page_size:
            break
        offset += page_size

    return prices


def get_price_near_date(prices: dict, target_date: date, window: int = 10):
    """Prix le plus proche de target_date (jour de bourse le plus proche, ±window jours)."""
    for delta in range(window + 1):
        for sign in [0, 1, -1]:
            if delta == 0 and sign != 0:
                continue
            d = (target_date + timedelta(days=delta * sign)).isoformat()
            if d in prices:
                return prices[d]
    return None


def volet_a_strategie_naive():
    logger.info("Volet A — stratégie naïve dividende — démarrage")
    resultats = []

    for ticker in TICKERS_DIVIDENDE:
        prices = fetch_prices_for_ticker(ticker)
        if not prices:
            logger.warning("Volet A : %s — pas de prix trouvés, ignoré", ticker)
            continue

        # EX_DIVIDEND porte la date précise ; DIVIDEND_HISTORY porte le
        # montant et le yield_pct. Les deux partagent fiscal_year, mais
        # PAS event_date (fin d'exercice pour DIVIDEND_HISTORY, vraie
        # ex-date pour EX_DIVIDEND). Jointure obligatoire par fiscal_year.
        resp_dates = (
            supabase.table("corporate_events")
            .select("event_date, fiscal_year")
            .eq("ticker", ticker)
            .eq("event_type", "EX_DIVIDEND")
            .execute()
        )
        resp_montants = (
            supabase.table("corporate_events")
            .select("amount, yield_pct, fiscal_year")
            .eq("ticker", ticker)
            .eq("event_type", "DIVIDEND_HISTORY")
            .execute()
        )

        montants_par_fy = {}
        for m in resp_montants.data:
            fy = str(m.get("fiscal_year", "")).strip()
            montants_par_fy[fy] = {
                "amount": m.get("amount"),
                "yield_pct": m.get("yield_pct"),
            }

        for ev in resp_dates.data:
            fy = str(ev.get("fiscal_year", "")).strip()

            try:
                fy_int = int(fy)
            except (TypeError, ValueError):
                continue
            if fy_int < 2022 or fy_int > 2025:
                continue

            montant_info = montants_par_fy.get(fy)
            if montant_info is None:
                logger.warning(
                    "Volet A : %s FY%s — aucun DIVIDEND_HISTORY correspondant "
                    "(exercice probablement pas encore clôturé), ignoré",
                    ticker, fy,
                )
                continue

            yield_pct = montant_info["yield_pct"]
            if yield_pct is None or yield_pct < YIELD_MIN:
                continue

            try:
                ex_date = date.fromisoformat(ev["event_date"])
            except (TypeError, ValueError):
                continue

            date_achat = ex_date - timedelta(days=ENTREE_J_AVANT_EXDATE)
            date_sortie = ex_date + timedelta(days=SORTIE_J)

            prix_achat = get_price_near_date(prices, date_achat)
            prix_sortie = get_price_near_date(prices, date_sortie)

            if prix_achat is None or prix_sortie is None:
                logger.warning(
                    "Volet A : %s FY%s — prix manquant (achat=%s, sortie=%s), ignoré",
                    ticker, fy, prix_achat, prix_sortie,
                )
                continue

            dividende = montant_info["amount"] or 0
            rendement = (
                (prix_sortie - prix_achat + dividende) / prix_achat * 100
            )

            resultats.append({
                "ticker": ticker,
                "fiscal_year": fy,
                "ex_date": ex_date.isoformat(),
                "date_achat": date_achat.isoformat(),
                "date_sortie": date_sortie.isoformat(),
                "prix_achat": prix_achat,
                "prix_sortie": prix_sortie,
                "dividende": dividende,
                "yield_pct": yield_pct,
                "rendement_pct": round(rendement, 2),
            })

    logger.info("Volet A — %d trades reconstitués", len(resultats))
    return resultats


# ----------------------------------------------------------------------
# Volet B — Recommandations BOA
# ----------------------------------------------------------------------

def volet_b_recos_boa():
    logger.info("Volet B — recommandations BOA — démarrage")
    resultats = []

    resp = (
        supabase.table("boa_recommendations")
        .select("ticker, date_start, action, cours_act")
        .eq("action", "BUY")
        .execute()
    )

    for reco in resp.data:
        try:
            date_start = date.fromisoformat(reco["date_start"])
        except (TypeError, ValueError):
            continue

        date_j90 = date_start + timedelta(days=SORTIE_J)
        if date_j90 > TODAY:
            # Fenêtre J+90 pas entièrement écoulée — exclu (spec T9)
            continue

        ticker = reco["ticker"]
        prices = fetch_prices_for_ticker(ticker)
        if not prices:
            logger.warning("Volet B : %s — pas de prix trouvés, ignoré", ticker)
            continue

        prix_achat = get_price_near_date(prices, date_start)
        prix_sortie = get_price_near_date(prices, date_j90)

        if prix_achat is None or prix_sortie is None:
            logger.warning(
                "Volet B : %s (%s) — prix manquant, ignoré",
                ticker, reco["date_start"],
            )
            continue

        rendement = (prix_sortie - prix_achat) / prix_achat * 100

        resultats.append({
            "ticker": ticker,
            "date_start": reco["date_start"],
            "date_j90": date_j90.isoformat(),
            "prix_achat": prix_achat,
            "prix_sortie": prix_sortie,
            "rendement_pct": round(rendement, 2),
        })

    logger.info("Volet B — %d recos évaluables (fenêtre J+90 écoulée)", len(resultats))
    return resultats


# ----------------------------------------------------------------------
# Volet C — V2 (réplique la logique de backtest_value.py, commit 49a64b6)
# ----------------------------------------------------------------------

# Constantes répliquées EXACTEMENT depuis backtest_value.py (commit 49a64b6)
CAP_MIN = 150_000_000_000
CAP_MAX = 500_000_000_000
ROE_MIN = 15.0
PB_MAX = 2.5
DECOTE_SEUIL_ACHAT = 15.0

PER_SECTORIEL = {
    "banque": 12.4,
    "agro": 10.2,
    "industrie": 13.2,
    "telecom": 13.3,
    "distribution": 16.1,
    "autre": 11.0,
}

SECTEURS = {
    "banque": ["BOAB", "BOABF", "BOAC", "BOAM", "BOAN", "BOAS", "BNBC", "CBIBF",
               "NSBC", "SGBC", "SIBC", "SICC", "SLBC", "UNLC", "CABC"],
    "agro": ["PALC", "SOGC", "SPHC", "SAFC", "CFAC"],
    "industrie": ["SMBC", "STAC", "STBC", "BICC", "CIEC", "ECOC", "SIVC",
                  "SEMC", "SHEC", "SCRC", "SDCC", "SDSC", "UNXC"],
    "telecom": ["ONTBF", "ORAC", "ORGT"],
    "distribution": ["ABJC", "ETIT", "FTSC", "LNBB", "NEIC", "NTLC",
                      "PRSC", "SNTS", "SOGC", "TTLC", "TTLS"],
}

# Tickers exclus — EPS non représentatif (réplique EXCLUSIONS de backtest_value.py)
EXCLUSIONS_V2 = {"NTLC", "BOAN", "BNBC", "SICC", "UNLC", "ETIT", "FTSC", "CFAC", "SIVC"}

FY_DATES = {
    "FY2021": "2022-04-30",
    "FY2022": "2023-04-30",
    "FY2023": "2024-04-30",
    "FY2024": "2025-04-30",
}


def fetch_all_prices_v2():
    """Reprend fetch_all_prices() de backtest_value.py — tous tickers, toutes dates."""
    resp = (
        supabase.table("companies").select("id, symbol").execute()
    )
    companies = {c["id"]: c["symbol"] for c in resp.data}

    all_prices = {}
    offset = 0
    page_size = 1000
    while True:
        r = (
            supabase.table("historical_data")
            .select("company_id, trade_date, price")
            .order("trade_date", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not r.data:
            break
        for row in r.data:
            ticker = companies.get(row["company_id"])
            if not ticker:
                continue
            all_prices.setdefault(ticker, {})[row["trade_date"]] = row["price"]
        if len(r.data) < page_size:
            break
        offset += page_size

    return all_prices


def fetch_fundamentals_history_v2():
    """Reprend fetch_fundamentals_history() de backtest_value.py."""
    resp = (
        supabase.table("company_fundamentals")
        .select("ticker, fiscal_year, eps, roe, pb_ratio")
        .execute()
    )
    fundamentals = {}
    for row in resp.data:
        ticker = row["ticker"]
        fy = row["fiscal_year"]
        eps = row.get("eps")
        if eps is None:
            continue
        fundamentals.setdefault(ticker, {})[fy] = {
            "eps": eps,
            "roe": row.get("roe"),
            "pb_ratio": row.get("pb_ratio"),
        }
    return fundamentals


def fetch_market_cap_by_ticker():
    """
    Réplique EXACTEMENT backtest_value.py : market_cap n'est peuplé que pour
    FY2025 (l'année courante) — on récupère UN SEUL market_cap par ticker,
    pas un market_cap par fiscal_year, et on l'applique à tout l'historique
    du ticker (c'est le comportement de l'original, cf. commentaire source
    "market_cap actuel par ticker (FY2025 = seule annee peuplee)").
    """
    resp = (
        supabase.table("company_fundamentals")
        .select("ticker, market_cap")
        .not_.is_("market_cap", "null")
        .execute()
    )
    cap_by_ticker = {}
    for row in resp.data:
        if row["market_cap"]:
            cap_by_ticker[row["ticker"]] = row["market_cap"]
    return cap_by_ticker


def get_secteur_v2(ticker: str) -> str:
    """Réplique exactement get_secteur() de backtest_value.py."""
    for s, tickers in SECTEURS.items():
        if ticker in tickers:
            return s
    return "autre"


def get_price_at_date_v2(prices_dict: dict, target_date_str: str, window: int = 10):
    target = date.fromisoformat(target_date_str)
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta * sign)).isoformat()
            if d in prices_dict:
                return prices_dict[d]
    return None


def volet_c_v2():
    logger.info("Volet C — V2 (réplique backtest_value.py, commit 49a64b6) — démarrage")

    all_prices = fetch_all_prices_v2()
    fundamentals = fetch_fundamentals_history_v2()
    cap_by_ticker = fetch_market_cap_by_ticker()

    resultats = []

    for ticker, fy_data in sorted(fundamentals.items()):
        if ticker in EXCLUSIONS_V2:
            continue

        prices = all_prices.get(ticker, {})
        if not prices:
            continue

        cap = cap_by_ticker.get(ticker)
        if not cap or not (CAP_MIN <= cap <= CAP_MAX):
            continue

        for fy, data in fy_data.items():
            signal_date = FY_DATES.get(fy)
            if not signal_date:
                continue

            roe = data.get("roe")
            pb = data.get("pb_ratio")
            # Réplique EXACTEMENT backtest_value.py : exclut si roe manquant/faible
            # OU pb manquant/trop élevé. roe == ROE_MIN et pb == PB_MAX PASSENT
            # (bornes larges dans l'original : "roe < ROE_MIN" et "pb > PB_MAX").
            if not roe or roe < ROE_MIN:
                continue
            if not pb or pb > PB_MAX:
                continue

            eps = data["eps"]
            prix_signal = get_price_at_date_v2(prices, signal_date)
            if not prix_signal:
                continue

            secteur = get_secteur_v2(ticker)
            per_ref = PER_SECTORIEL.get(secteur, 11.0)
            cours_cible = eps * per_ref
            decote_pct = (cours_cible - prix_signal) / prix_signal * 100

            if decote_pct <= DECOTE_SEUIL_ACHAT:
                continue  # on ne garde que le groupe ACHAT

            date_j90 = (date.fromisoformat(signal_date) + timedelta(days=90)).isoformat()
            prix_j90 = get_price_at_date_v2(prices, date_j90)
            if prix_j90 is None:
                continue

            perf_j90 = (prix_j90 - prix_signal) / prix_signal * 100

            resultats.append({
                "ticker": ticker,
                "fy": fy,
                "decote_pct": round(decote_pct, 1),
                "rendement_pct": round(perf_j90, 2),
            })

    logger.info("Volet C — %d signaux ACHAT (attendu : 25)", len(resultats))
    return resultats


# ----------------------------------------------------------------------
# Comparaison et règles d'interprétation (textuelles, cf. PLAN_REMEDIATION T9)
# ----------------------------------------------------------------------

def summarize(label: str, rendements: list):
    if not rendements:
        return {"label": label, "n": 0, "mediane": None, "moyenne": None,
                "pct_positifs": None, "pire_cas": None}
    n = len(rendements)
    mediane = round(statistics.median(rendements), 2)
    moyenne = round(statistics.mean(rendements), 2)
    pct_positifs = round(sum(1 for r in rendements if r > 0) / n * 100, 1)
    pire_cas = round(min(rendements), 2)
    return {
        "label": label, "n": n, "mediane": mediane, "moyenne": moyenne,
        "pct_positifs": pct_positifs, "pire_cas": pire_cas,
    }


def print_summary_table(summaries: list):
    print(f"\n{'Volet':<12} {'n':>4} {'Médiane':>10} {'Moyenne':>10} "
          f"{'%Positifs':>10} {'Pire cas':>10}")
    print("-" * 60)
    for s in summaries:
        if s["n"] == 0:
            print(f"{s['label']:<12} {'0':>4}  (aucune donnée exploitable)")
            continue
        print(f"{s['label']:<12} {s['n']:>4} {s['mediane']:>9}% {s['moyenne']:>9}% "
              f"{s['pct_positifs']:>9}% {s['pire_cas']:>9}%")


def apply_interpretation_rule(summary_a, summary_c):
    """Applique textuellement les règles d'interprétation du plan T9."""
    if summary_a["n"] == 0 or summary_c["n"] == 0:
        return ("ESCALADE — données insuffisantes sur au moins un volet "
                "(A ou C), aucune conclusion possible.")

    mediane_a = summary_a["mediane"]
    mediane_c = summary_c["mediane"]
    pct_a = summary_a["pct_positifs"]
    pct_c = summary_c["pct_positifs"]

    if mediane_c <= mediane_a and pct_c <= pct_a:
        return ("V2 non différencié de la stratégie naïve — GELER la "
                "Phase 13, envisager la simplification du pipeline.")

    if mediane_c > mediane_a + 2:
        # condition additionnelle : médiane C > médiane B (à vérifier séparément
        # par l'appelant, cf. main())
        return ("CONDITION PARTIELLE remplie (médiane C > médiane A + 2 pts) "
                "— vérifier aussi médiane C > médiane B avant de conclure "
                "'edge valorisation confirmé'.")

    return "ESCALADE — cas intermédiaire, aucune conclusion possible."


def main():
    logger.info("T9 — Test de falsification V2 — démarrage")

    resultats_a = volet_a_strategie_naive()
    resultats_b = volet_b_recos_boa()
    resultats_c = volet_c_v2()

    rendements_a = [r["rendement_pct"] for r in resultats_a]
    rendements_b = [r["rendement_pct"] for r in resultats_b]
    rendements_c = [r["rendement_pct"] for r in resultats_c]

    summary_a = summarize("A (naïve)", rendements_a)
    summary_b = summarize("B (BOA)", rendements_b)
    summary_c = summarize("C (V2)", rendements_c)

    print_summary_table([summary_a, summary_b, summary_c])

    verdict = apply_interpretation_rule(summary_a, summary_c)

    # Vérification complète de la règle "edge confirmé" (nécessite aussi C > B)
    if summary_c["n"] > 0 and summary_b["n"] > 0 and summary_a["n"] > 0:
        if (summary_c["mediane"] > summary_a["mediane"] + 2
                and summary_c["mediane"] > summary_b["mediane"]):
            verdict = ("EDGE VALORISATION CONFIRMÉ — Phase 13 débloquée "
                       "(médiane C > médiane A + 2 pts ET médiane C > médiane B).")
        elif summary_c["mediane"] <= summary_a["mediane"] and summary_c["pct_positifs"] <= summary_a["pct_positifs"]:
            verdict = ("V2 NON DIFFÉRENCIÉ de la stratégie naïve — GELER la "
                       "Phase 13, envisager la simplification du pipeline.")
        else:
            verdict = "ESCALADE — cas intermédiaire, aucune conclusion possible."

    print(f"\n{'=' * 60}")
    print("VERDICT (règle d'interprétation appliquée textuellement) :")
    print(verdict)
    print(f"{'=' * 60}\n")

    logger.info("T9 terminé. Résultats à coller dans REMEDIATION_LOG.md")


if __name__ == "__main__":
    main()
