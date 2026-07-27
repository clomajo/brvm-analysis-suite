#!/usr/bin/env python3
"""
E2.7-A — Grille entree/sortie, rotation dediee
Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).

Teste 12 combinaisons (4 offsets d'entree x 3 offsets de sortie) sur les
89 cycles dividende exploitables. Mesure l'alpha_cycle vs benchmark pour
chaque combinaison, compare a la reference E2.6 (J0, paiement), applique
la regle d'interpretation textuellement.

Ecriture strictement limitee a tools/experiments/E2_7A/ et EXPERIMENTS_LOG.md.
"""
import csv
import logging
import os
import statistics
import sys
from datetime import datetime, timedelta

import requests
from dotenv import find_dotenv, load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("E2_7A")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CSV_SOURCE = os.path.join(REPO_ROOT, "dividend_cycle_exploration.csv")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(OUT_DIR, "E2_7A_alpha_par_combinaison.csv")
LOG_MD = os.path.join(REPO_ROOT, "EXPERIMENTS_LOG.md")

ENTREE_OFFSETS = [-5, 0, 5, 10]
SORTIE_OFFSETS = [-5, 0, 5]
REFERENCE_COMBO = (0, 0)  # (entree_offset, sortie_offset) = fenetre E2.6


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


def compute_benchmark(price_index, exclude_ticker, date_start, date_end, max_gap_ouvres=3):
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
    log.info("Cycles source: %d total, %d exploitables", len(source_rows), len(exploitable_rows))

    log.info("Recuperation v_historical_prices via REST (pagination Range)...")
    price_rows = fetch_all_prices(url, key)
    price_index = build_price_index(price_rows)
    log.info("Index prix construit: %d tickers", len(price_index))

    output_rows = []
    exclusions_par_combo = {}

    for entree_off in ENTREE_OFFSETS:
        for sortie_off in SORTIE_OFFSETS:
            combo = (entree_off, sortie_off)
            n_exclus = 0

            for r in exploitable_rows:
                ticker = r["ticker"]
                date_annonce = parse_date(r["date_annonce"])
                date_paiement = parse_date(r["date_paiement"])

                if not (date_annonce and date_paiement):
                    n_exclus += 1
                    continue

                date_entree = date_annonce + timedelta(days=entree_off)
                date_sortie = date_paiement + timedelta(days=sortie_off)

                if date_sortie <= date_entree:
                    n_exclus += 1
                    continue

                plist = price_index.get(ticker, [])
                _, p_start, _ = price_at_or_before(plist, date_entree, max_gap_days=5)
                _, p_end, _ = price_at_or_before(plist, date_sortie, max_gap_days=5)

                if p_start is None or p_end is None or p_start == 0:
                    n_exclus += 1
                    continue

                dividende = float(r["montant"]) if r.get("montant") else 0.0
                # Le dividende n'est inclus que s'il est encaisse dans [date_entree, date_sortie]
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
                    "entree_offset": entree_off,
                    "sortie_offset": sortie_off,
                    "date_entree": date_entree.isoformat(),
                    "date_sortie": date_sortie.isoformat(),
                    "rendement_cycle": round(rendement_cycle, 4),
                    "benchmark_cycle": round(benchmark_cycle, 4),
                    "alpha_cycle": round(alpha_cycle, 4),
                })

            exclusions_par_combo[combo] = n_exclus
            log.info("Combo (entree=%+d, sortie=%+d): %d cycles valides, %d exclus",
                      entree_off, sortie_off, len(exploitable_rows) - n_exclus, n_exclus)

    fieldnames = [
        "ticker", "fiscal_year", "entree_offset", "sortie_offset",
        "date_entree", "date_sortie", "rendement_cycle", "benchmark_cycle", "alpha_cycle",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(output_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_CSV, len(output_rows))

    # --- Etape 2: robustesse par combinaison ---
    stats_par_combo = {}
    for entree_off in ENTREE_OFFSETS:
        for sortie_off in SORTIE_OFFSETS:
            combo = (entree_off, sortie_off)
            vals = [r["alpha_cycle"] for r in output_rows if r["entree_offset"] == entree_off and r["sortie_offset"] == sortie_off]
            stats_par_combo[combo] = {
                "n": len(vals),
                "alpha_median": round(median(vals), 4) if vals else None,
                "pct_positive": round(pct_positive(vals), 1) if vals else None,
            }

    # --- Etape 3: comparaison a la reference ---
    ref_stats = stats_par_combo[REFERENCE_COMBO]
    ranking = sorted(stats_par_combo.items(), key=lambda kv: (kv[1]["alpha_median"] if kv[1]["alpha_median"] is not None else -9999), reverse=True)
    rank_of_ref = next(i for i, (combo, _) in enumerate(ranking) if combo == REFERENCE_COMBO)
    tercile_size = len(ranking) / 3
    ref_in_top_tercile = rank_of_ref < tercile_size

    ecarts = {}
    for combo, stats in stats_par_combo.items():
        if combo == REFERENCE_COMBO or stats["alpha_median"] is None or ref_stats["alpha_median"] is None:
            continue
        ecarts[combo] = round(stats["alpha_median"] - ref_stats["alpha_median"], 4)

    # --- Regle d'interpretation ---
    n_positifs = sum(1 for s in stats_par_combo.values() if s["alpha_median"] is not None and s["alpha_median"] > 0)

    grille_robuste = n_positifs >= 9 and ref_in_top_tercile

    verdict = None
    conclusion = None
    combo_dominante = None

    if grille_robuste:
        verdict = "GRILLE_ROBUSTE"
        conclusion = ("Grille robuste. La fenetre E2.6 (annonce->paiement) est un choix "
                      "raisonnable, pas une coincidence. Pas de changement de regle recommande.")
    else:
        candidates = [(combo, ecart) for combo, ecart in ecarts.items() if ecart >= 3.0 and stats_par_combo[combo]["n"] >= 15]
        if len(candidates) == 1:
            combo_dominante, ecart_dom = candidates[0]
            verdict = "AMELIORATION_LOCALISEE"
            conclusion = (f"Combinaison {combo_dominante} preferable a la reference E2.6 de {ecart_dom} points "
                          f"(n={stats_par_combo[combo_dominante]['n']}). A considerer pour la regle d'entree/sortie, "
                          "decision Jocelyn. Prudence : une seule experience, pas de validation croisee out-of-sample.")
        else:
            verdict = "GRILLE_INSTABLE"
            conclusion = ("Grille instable — aucune combinaison ne domine clairement. Signal probablement "
                          "bruite sur n=89 cycles bruts repartis en 12 cases. Escalade au modele avance, "
                          "aucune conclusion ecrite sur le choix entree/sortie.")

    # --- Rapport console ---
    print("\n" + "=" * 70)
    print("E2.7-A — RESULTATS")
    print("=" * 70)
    print(f"\nCycles exploitables source: {len(exploitable_rows)}")
    print(f"\n--- Etape 2: tableau 4x3 (entree x sortie) ---")
    label_coin = "entree\\sortie"
    print(f"{label_coin:>15}", end="")
    for sortie_off in SORTIE_OFFSETS:
        col_label = f"{sortie_off:+d}"
        print(f"{col_label:>20}", end="")
    print()
    for entree_off in ENTREE_OFFSETS:
        row_label = f"{entree_off:+d}"
        print(f"{row_label:>15}", end="")
        for sortie_off in SORTIE_OFFSETS:
            s = stats_par_combo[(entree_off, sortie_off)]
            cell = f"n={s['n']},a={s['alpha_median']}"
            print(f"{cell:>20}", end="")
        print()
    print(f"\n--- Etape 3: ecarts vs reference (J0, paiement) ---")
    print(f"Reference: n={ref_stats['n']}, alpha_median={ref_stats['alpha_median']}, rang={rank_of_ref+1}/{len(ranking)}, top_tercile={ref_in_top_tercile}")
    for combo, ecart in sorted(ecarts.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {combo}: ecart={ecart:+.4f} pts (n={stats_par_combo[combo]['n']})")
    print(f"\n--- Criteres ---")
    print(f"  combinaisons positives: {n_positifs}/12")
    print(f"  reference dans tercile superieur: {ref_in_top_tercile} (rang {rank_of_ref+1})")
    print(f"\n--- VERDICT: {verdict} ---")
    print(conclusion)
    print("=" * 70)

    # --- Journalisation ---
    tableau_md = "| entree\\\\sortie | " + " | ".join(f"{s:+d}" for s in SORTIE_OFFSETS) + " |\n"
    tableau_md += "|---|" + "---|" * len(SORTIE_OFFSETS) + "\n"
    for entree_off in ENTREE_OFFSETS:
        row = f"| {entree_off:+d} | "
        row += " | ".join(f"n={stats_par_combo[(entree_off, s)]['n']}, α={stats_par_combo[(entree_off, s)]['alpha_median']}" for s in SORTIE_OFFSETS)
        row += " |\n"
        tableau_md += row

    entry = f"""

## E2.7-A — Grille entree/sortie, rotation dediee
**Date d'execution**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: {len(exploitable_rows)}

**Tableau 4x3 (entree x sortie), n et alpha median par case**:

{tableau_md}
**Reference (J0, paiement)**: n={ref_stats['n']}, alpha_median={ref_stats['alpha_median']}, rang={rank_of_ref+1}/12, top_tercile={ref_in_top_tercile}

**Combinaisons positives**: {n_positifs}/12

**VERDICT: {verdict}**
{conclusion}

**Artefacts**: `tools/experiments/E2_7A/E2_7A_alpha_par_combinaison.csv` ({len(output_rows)} lignes)
"""
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Journalise dans %s", LOG_MD)


if __name__ == "__main__":
    main()
