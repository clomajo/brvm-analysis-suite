#!/usr/bin/env python3
"""
T5c-A — Backtest strategie de rotation dediee dividend capture
Classe A — experience offline, lecture seule. Gate : E2.6 (H1 confirmee) +
E2.7-A (GRILLE_ROBUSTE, commit 4c44c75) qui a valide la fenetre de reference
(entree = jour de bourse le plus proche de l'annonce, sortie = jour de
bourse le plus proche du paiement) comme choix raisonnable, sans variante
superieure identifiee.

Strategie testee : achat pour le cycle dividende (entree pres de l'annonce,
sortie au paiement), puis revente immediate — PAS de detention longue.
Combinaison unique (entree_offset=0, sortie_offset=0), reprise telle quelle
de la reference E2.6/E2.7-A. Aucune grille, aucune variante non listee ici
(anti-overfitting, cf. Interdits Classe A).

Univers : etendu complet — tous les tickers de dividend_cycle_exploration.csv
avec au moins un cycle "exploitable" (>=1 dividende documente sur la fenetre
~2022-2026 couverte par la source), sans filtre de liquidite ni de nombre
minimum de cycles. NTLC inclus explicitement (pas d'exclusion malgre un
alpha median negatif deja signale en E2.7-B).

Calcul BRUT : ni frais de transaction ni IRVM — decision de session
(27/07/2026 -> 28/07/2026), a traiter en analyse de sensibilite a posteriori,
pas en prerequis de cette experience.

Logique de recherche du "jour de bourse le plus proche" (prix au dernier
cours connu a <= max_gap_days avant la date cible) reprise a l'identique
d'E2.7-A/E2.7-B.

Ecriture strictement limitee a tools/experiments/E2_8_rotation/ et
EXPERIMENTS_LOG.md.
"""
import csv
import logging
import os
import statistics
import sys
from datetime import datetime

import requests
from dotenv import find_dotenv, load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("E2_8_rotation")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CSV_SOURCE = os.path.join(REPO_ROOT, "dividend_cycle_exploration.csv")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PAR_CYCLE = os.path.join(OUT_DIR, "E2_8_rotation_par_cycle.csv")
OUT_PAR_TICKER = os.path.join(OUT_DIR, "E2_8_rotation_par_ticker.csv")
LOG_MD = os.path.join(REPO_ROOT, "EXPERIMENTS_LOG.md")

ENTREE_OFFSET = 0  # jour de bourse le plus proche de l'annonce
SORTIE_OFFSET = 0  # jour de bourse le plus proche du paiement
MAX_GAP_DAYS = 5   # tolerance de recherche du jour de bourse le plus proche (identique E2.7-A/B)
MAX_GAP_OUVRES_BENCHMARK = 3  # identique E2.7-A


def load_env():
    load_dotenv(find_dotenv(usecwd=True))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent — erreur d'infrastructure.")
        sys.exit(1)
    return url, key


def fetch_all_prices(url, key):
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    all_rows = []
    offset = 0
    page = 1000
    while True:
        range_header = {**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"}
        resp = requests.get(
            f"{url}/rest/v1/v_historical_prices?select=ticker,trade_date,price&order=ticker,trade_date",
            headers=range_header,
            timeout=30,
        )
        if resp.status_code not in (200, 206):
            log.error("Echec REST v_historical_prices: status=%s body=%s", resp.status_code, resp.text[:300])
            sys.exit(1)
        batch = resp.json()
        all_rows.extend(batch)
        log.info("Recupere %d lignes (offset=%d, total=%d)", len(batch), offset, len(all_rows))
        if len(batch) < page:
            break
        offset += page
    return all_rows


def build_price_index(rows):
    idx = {}
    for r in rows:
        try:
            d = datetime.strptime(r["trade_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if r.get("price") is None:
            continue
        idx.setdefault(r["ticker"], []).append((d, float(r["price"])))
    for t in idx:
        idx[t].sort(key=lambda x: x[0])
    return idx


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def price_at_or_before(price_list, target_date, max_gap_days=None):
    best = None
    for d, p in price_list:
        if d <= target_date:
            best = (d, p)
        else:
            break
    if best is None:
        return None, None, None
    gap = (target_date - best[0]).days
    if max_gap_days is not None and gap > max_gap_days:
        return None, None, None
    return best[0], best[1], gap


def compute_benchmark(price_index, exclude_ticker, date_start, date_end, max_gap_ouvres=MAX_GAP_OUVRES_BENCHMARK):
    max_gap_cal = int(round(max_gap_ouvres * 1.6))
    rets = []
    for ticker, plist in price_index.items():
        if ticker == exclude_ticker:
            continue
        _, p_start, _ = price_at_or_before(plist, date_start, max_gap_cal)
        _, p_end, _ = price_at_or_before(plist, date_end, max_gap_cal)
        if p_start is None or p_end is None or p_start == 0:
            continue
        rets.append((p_end - p_start) / p_start * 100.0)
    if not rets:
        return None, 0
    return statistics.mean(rets), len(rets)


def median(values):
    return statistics.median(values) if values else None


def pct_positive(values):
    if not values:
        return None
    return sum(1 for v in values if v > 0) / len(values) * 100.0


def main():
    url, key = load_env()

    if not os.path.exists(CSV_SOURCE):
        log.error("Fichier source introuvable: %s — erreur d'infrastructure.", CSV_SOURCE)
        sys.exit(1)

    with open(CSV_SOURCE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)

    exploitable_rows = [r for r in source_rows if r.get("exploitable") == "True"]
    univers_tickers = sorted(set(r["ticker"] for r in exploitable_rows))
    log.info("Cycles source: %d total, %d exploitables", len(source_rows), len(exploitable_rows))
    log.info("Univers etendu complet (>=1 cycle exploitable, sans filtre): %d tickers", len(univers_tickers))
    log.info("NTLC inclus: %s", "NTLC" in univers_tickers)

    log.info("Recuperation v_historical_prices via REST (pagination Range)...")
    price_rows = fetch_all_prices(url, key)
    price_index = build_price_index(price_rows)
    log.info("Index prix construit: %d tickers", len(price_index))

    output_rows = []
    n_exclus = 0

    for r in exploitable_rows:
        ticker = r["ticker"]
        date_annonce = parse_date(r["date_annonce"])
        date_paiement = parse_date(r["date_paiement"])

        if not (date_annonce and date_paiement):
            n_exclus += 1
            continue

        date_entree_cible = date_annonce  # ENTREE_OFFSET = 0
        date_sortie_cible = date_paiement  # SORTIE_OFFSET = 0

        if date_sortie_cible <= date_entree_cible:
            n_exclus += 1
            continue

        plist = price_index.get(ticker, [])
        date_entree, p_start, gap_entree = price_at_or_before(plist, date_entree_cible, max_gap_days=MAX_GAP_DAYS)
        date_sortie, p_end, gap_sortie = price_at_or_before(plist, date_sortie_cible, max_gap_days=MAX_GAP_DAYS)

        if p_start is None or p_end is None or p_start == 0:
            n_exclus += 1
            continue

        dividende = float(r["montant"]) if r.get("montant") else 0.0
        date_ex = parse_date(r["date_ex"])
        dividende_encaisse = dividende if (date_ex and date_entree <= date_ex <= date_sortie) else 0.0

        rendement_cycle = (p_end - p_start + dividende_encaisse) / p_start * 100.0

        benchmark_cycle, n_bench = compute_benchmark(price_index, ticker, date_entree, date_sortie)
        if benchmark_cycle is None:
            n_exclus += 1
            continue

        alpha_cycle = rendement_cycle - benchmark_cycle

        output_rows.append({
            "ticker": ticker,
            "fiscal_year": r.get("fiscal_year"),
            "date_annonce": date_annonce.isoformat(),
            "date_paiement": date_paiement.isoformat(),
            "date_entree": date_entree.isoformat(),
            "date_sortie": date_sortie.isoformat(),
            "gap_entree_jours": gap_entree,
            "gap_sortie_jours": gap_sortie,
            "dividende_encaisse": dividende_encaisse,
            "rendement_cycle": round(rendement_cycle, 4),
            "benchmark_cycle": round(benchmark_cycle, 4),
            "alpha_cycle": round(alpha_cycle, 4),
        })

    log.info("Cycles valides: %d, exclus: %d", len(output_rows), n_exclus)

    fieldnames_cycle = [
        "ticker", "fiscal_year", "date_annonce", "date_paiement",
        "date_entree", "date_sortie", "gap_entree_jours", "gap_sortie_jours",
        "dividende_encaisse", "rendement_cycle", "benchmark_cycle", "alpha_cycle",
    ]
    with open(OUT_PAR_CYCLE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_cycle)
        w.writeheader()
        w.writerows(output_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_PAR_CYCLE, len(output_rows))

    # --- Robustesse globale ---
    rendements = [r["rendement_cycle"] for r in output_rows]
    alphas = [r["alpha_cycle"] for r in output_rows]

    stats_globales = {
        "n_cycles": len(output_rows),
        "rendement_median": round(median(rendements), 4) if rendements else None,
        "rendement_moyen": round(statistics.mean(rendements), 4) if rendements else None,
        "alpha_median": round(median(alphas), 4) if alphas else None,
        "alpha_moyen": round(statistics.mean(alphas), 4) if alphas else None,
        "pct_gagnants": round(pct_positive(rendements), 1) if rendements else None,
        "pct_alpha_positif": round(pct_positive(alphas), 1) if alphas else None,
    }

    # --- Robustesse par ticker ---
    par_ticker_rows = []
    for ticker in univers_tickers:
        vals_r = [r["rendement_cycle"] for r in output_rows if r["ticker"] == ticker]
        vals_a = [r["alpha_cycle"] for r in output_rows if r["ticker"] == ticker]
        par_ticker_rows.append({
            "ticker": ticker,
            "n_cycles": len(vals_r),
            "rendement_median": round(median(vals_r), 4) if vals_r else None,
            "alpha_median": round(median(vals_a), 4) if vals_a else None,
            "pct_gagnants": round(pct_positive(vals_r), 1) if vals_r else None,
        })
    par_ticker_rows.sort(key=lambda x: (x["alpha_median"] if x["alpha_median"] is not None else -9999), reverse=True)

    with open(OUT_PAR_TICKER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "n_cycles", "rendement_median", "alpha_median", "pct_gagnants"])
        w.writeheader()
        w.writerows(par_ticker_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_PAR_TICKER, len(par_ticker_rows))

    tickers_robustes = [row for row in par_ticker_rows if row["n_cycles"] >= 3]
    tickers_peu_robustes = [row for row in par_ticker_rows if row["n_cycles"] < 3]

    # --- Rapport console ---
    print("\n" + "=" * 70)
    print("T5c-A / E2.8 — BACKTEST ROTATION DIVIDEND CAPTURE — RESULTATS")
    print("=" * 70)
    print(f"\nCycles exploitables source: {len(exploitable_rows)}")
    print(f"Univers etendu complet: {len(univers_tickers)} tickers (NTLC inclus)")
    print(f"Cycles valides: {len(output_rows)}, exclus: {n_exclus}")
    print("\n--- Robustesse globale (n, rendement/alpha median, %gagnants) ---")
    for k, v in stats_globales.items():
        print(f"  {k}: {v}")
    print("\n--- Robustesse par ticker ---")
    print(f"{'Ticker':<8}{'n_cycles':>10}{'rendement_med':>16}{'alpha_med':>12}{'%gagnants':>12}")
    for row in par_ticker_rows:
        print(f"{row['ticker']:<8}{row['n_cycles']:>10}{str(row['rendement_median']):>16}"
              f"{str(row['alpha_median']):>12}{str(row['pct_gagnants']):>12}")
    print(f"\nTickers robustes (>=3 cycles): {len(tickers_robustes)}")
    print(f"Tickers peu robustes (<3 cycles): {len(tickers_peu_robustes)}")
    print("=" * 70)

    # --- Journalisation ---
    tableau_md = "| Ticker | n_cycles | rendement_median | alpha_median | %gagnants |\n"
    tableau_md += "|---|---|---|---|---|\n"
    for row in par_ticker_rows:
        tableau_md += (f"| {row['ticker']} | {row['n_cycles']} | {row['rendement_median']} | "
                        f"{row['alpha_median']} | {row['pct_gagnants']} |\n")

    entry = f"""

## T5c-A / E2.8 — Backtest strategie de rotation dediee dividend capture
**Date d'execution**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Classe**: A (offline, lecture seule)
**Strategie**: achat/revente par cycle dividende, pas de detention longue.
Combinaison unique (entree = jour de bourse le plus proche de l'annonce,
sortie = jour de bourse le plus proche du paiement), reprise de la
reference E2.6/E2.7-A (GRILLE_ROBUSTE, aucune variante superieure trouvee).
**Univers**: etendu complet, {len(univers_tickers)} tickers avec >=1 cycle
dividende exploitable, sans filtre de liquidite ni de nombre minimum de
cycles (NTLC inclus).
**Calcul**: BRUT (ni frais ni IRVM — decision de session, sensibilite a
traiter a posteriori).
**Cycles exploitables source**: {len(exploitable_rows)} ; cycles valides: {len(output_rows)} ; exclus: {n_exclus}

**Robustesse globale**: n={stats_globales['n_cycles']}, rendement_median={stats_globales['rendement_median']}%,
alpha_median={stats_globales['alpha_median']} pts, %gagnants={stats_globales['pct_gagnants']}%,
%alpha_positif={stats_globales['pct_alpha_positif']}%

**Robustesse par ticker** ({len(tickers_robustes)} tickers a >=3 cycles, {len(tickers_peu_robustes)} a <3 cycles) :

{tableau_md}
**Artefacts**: `tools/experiments/E2_8_rotation/E2_8_rotation_par_cycle.csv` ({len(output_rows)} lignes),
`tools/experiments/E2_8_rotation/E2_8_rotation_par_ticker.csv` ({len(par_ticker_rows)} lignes)
"""
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Journalise dans %s", LOG_MD)


if __name__ == "__main__":
    main()
