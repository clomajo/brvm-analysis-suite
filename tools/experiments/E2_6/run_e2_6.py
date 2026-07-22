#!/usr/bin/env python3
"""
E2.6 — Identification du mecanisme dividende (H1 / H2 / H3)
Classe A — experience offline, lecture seule.

Lit dividend_cycle_exploration.csv (commit d771ece) + v_historical_prices
(REST GET, pagination Range). Calcule alpha_cycle par cycle contre un
benchmark egal-pondere (tickers exclus le ticker analyse), classe
statut_cotation_ex, produit les trois decoupes autorisees et teste les
trois sous-groupes ex ante. Applique la regle d'interpretation
textuellement et journalise dans EXPERIMENTS_LOG.md.

Ecriture strictement limitee a tools/experiments/E2_6/ et EXPERIMENTS_LOG.md.
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
log = logging.getLogger("E2_6")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CSV_SOURCE = os.path.join(REPO_ROOT, "dividend_cycle_exploration.csv")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(OUT_DIR, "E2_6_alpha_par_cycle.csv")
LOG_MD = os.path.join(REPO_ROOT, "EXPERIMENTS_LOG.md")

MAX_GAP_JOURS_OUVRES = 3  # tolerance "dernier cours <= 3 jours ouvres de la borne"


def load_env():
    load_dotenv(find_dotenv(usecwd=True))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent — erreur d'infrastructure.")
        sys.exit(1)
    return url, key


def fetch_all_prices(url, key):
    """REST GET paginee (Range par 1000) sur v_historical_prices."""
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
    """ticker -> sorted list of (date, price) pour recherche de bornes."""
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
    """
    Dernier cours <= target_date. Retourne (date_trouvee, prix, ecart_jours)
    ou (None, None, None) si aucun cours dans la fenetre.
    price_list: liste triee de (date, price) pour UN ticker.
    """
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


def price_exact(price_list, target_date):
    for d, p in price_list:
        if d == target_date:
            return p
    return None


def compute_benchmark(price_index, exclude_ticker, date_start, date_end, max_gap_ouvres=3):
    """
    Moyenne simple des rendements de tous les tickers (hors exclude_ticker)
    ayant un prix valide aux deux bornes. Prix valide = dernier cours
    <= 3 jours ouvres de la borne -> on utilise une tolerance calendaire
    large (max_gap_ouvres * 1.6 jours calendaires) car price_at_or_before
    raisonne en jours calendaires; c'est une approximation documentee.
    """
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


def classify_statut_cotation_ex(price_list, date_ex, max_gap_ouvres=3):
    """
    COTE_SANS_VARIATION / NON_COTE / COTE_AVEC_VARIATION
    selon la spec etape 2.
    """
    max_gap_cal = int(round(max_gap_ouvres * 1.6))
    p_ex = price_exact(price_list, date_ex)
    prev_date, prev_price, gap = price_at_or_before(
        price_list, date_ex - timedelta(days=1), max_gap_cal
    )

    if p_ex is None:
        return "NON_COTE"
    if prev_price is None:
        return "NON_COTE"
    if prev_price == p_ex:
        return "COTE_SANS_VARIATION"
    return "COTE_AVEC_VARIATION"


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
    skipped = []

    for r in exploitable_rows:
        ticker = r["ticker"]
        date_annonce = parse_date(r["date_annonce"])
        date_ex = parse_date(r["date_ex"])
        date_paiement = parse_date(r["date_paiement"])

        if not (date_annonce and date_paiement):
            skipped.append((ticker, r.get("fiscal_year"), "dates annonce/paiement manquantes"))
            continue

        plist = price_index.get(ticker, [])

        _, p_start, gap_start = price_at_or_before(plist, date_annonce, max_gap_days=5)
        _, p_end, gap_end = price_at_or_before(plist, date_paiement, max_gap_days=5)

        if p_start is None or p_end is None or p_start == 0:
            skipped.append((ticker, r.get("fiscal_year"), "prix annonce/paiement introuvable dans fenetre 5j"))
            continue

        dividende = float(r["montant"]) if r.get("montant") else 0.0
        rendement_cycle = (p_end - p_start + dividende) / p_start * 100.0

        benchmark_cycle, n_bench = compute_benchmark(price_index, ticker, date_annonce, date_paiement)
        if benchmark_cycle is None:
            skipped.append((ticker, r.get("fiscal_year"), "aucun benchmark calculable (0 ticker de reference)"))
            continue

        alpha_cycle = rendement_cycle - benchmark_cycle

        chute_ex_pct = None
        if r.get("chute_reelle_pct_du_dividende"):
            try:
                chute_ex_pct = float(r["chute_reelle_pct_du_dividende"])
            except ValueError:
                chute_ex_pct = None

        statut = "NON_COTE"
        if date_ex:
            statut = classify_statut_cotation_ex(plist, date_ex)
        else:
            log.info("%s %s: date_ex absente -> statut NON_COTE par defaut, conserve pour H1", ticker, r.get("fiscal_year"))

        duree_jours = (date_paiement - date_annonce).days

        output_rows.append({
            "ticker": ticker,
            "fiscal_year": r.get("fiscal_year"),
            "date_annonce": r["date_annonce"],
            "date_ex": r["date_ex"],
            "date_paiement": r["date_paiement"],
            "duree_jours": duree_jours,
            "dividende": dividende,
            "yield_pct": r.get("yield_pct"),
            "rendement_cycle": round(rendement_cycle, 4),
            "benchmark_cycle": round(benchmark_cycle, 4),
            "alpha_cycle": round(alpha_cycle, 4),
            "chute_ex_pct": chute_ex_pct,
            "statut_cotation_ex": statut,
            "n_benchmark": n_bench,
            "delai_ag_ex_jours": (date_ex - date_annonce).days if date_ex else None,
            "volume_moyen_avant_annonce": r.get("volume_moyen_avant_annonce"),
        })

    log.info("Cycles traites: %d, cycles ecartes: %d", len(output_rows), len(skipped))
    for s in skipped:
        log.warning("Ecarte: ticker=%s fy=%s raison=%s", *s)

    fieldnames = [
        "ticker", "fiscal_year", "date_annonce", "date_ex", "date_paiement",
        "duree_jours", "dividende", "yield_pct", "rendement_cycle",
        "benchmark_cycle", "alpha_cycle", "chute_ex_pct", "statut_cotation_ex",
        "n_benchmark", "delai_ag_ex_jours", "volume_moyen_avant_annonce",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(output_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_CSV, len(output_rows))

    statut_counts = {"COTE_SANS_VARIATION": 0, "NON_COTE": 0, "COTE_AVEC_VARIATION": 0}
    for row in output_rows:
        statut_counts[row["statut_cotation_ex"]] = statut_counts.get(row["statut_cotation_ex"], 0) + 1

    def cut_by(rows, keyfn, min_n=3):
        groups = {}
        for row in rows:
            k = keyfn(row)
            groups.setdefault(k, []).append(row["alpha_cycle"])
        result = {}
        under_n = []
        for k, vals in groups.items():
            if len(vals) < min_n:
                under_n.extend(vals)
                continue
            result[k] = {
                "n": len(vals),
                "alpha_median": round(median(vals), 4),
                "pct_positive": round(pct_positive(vals), 1),
            }
        if under_n:
            result["n<3 (agrege, non interprete)"] = {
                "n": len(under_n),
                "alpha_median": round(median(under_n), 4) if under_n else None,
                "pct_positive": round(pct_positive(under_n), 1) if under_n else None,
            }
        return result

    decoupe_ticker = cut_by(output_rows, lambda r: r["ticker"], min_n=3)
    decoupe_annee = cut_by(output_rows, lambda r: parse_date(r["date_ex"]).year if r["date_ex"] else "date_ex_manquante", min_n=1)

    yields_valid = [r for r in output_rows if r["yield_pct"]]
    yields_sorted = sorted(yields_valid, key=lambda r: float(r["yield_pct"]))
    n_y = len(yields_sorted)
    terciles = {"T1_bas": [], "T2_moyen": [], "T3_haut": []}
    for i, row in enumerate(yields_sorted):
        if i < n_y / 3:
            terciles["T1_bas"].append(row["alpha_cycle"])
        elif i < 2 * n_y / 3:
            terciles["T2_moyen"].append(row["alpha_cycle"])
        else:
            terciles["T3_haut"].append(row["alpha_cycle"])
    decoupe_tercile = {
        k: {"n": len(v), "alpha_median": round(median(v), 4) if v else None,
            "pct_positive": round(pct_positive(v), 1) if v else None}
        for k, v in terciles.items()
    }

    h2_pool = [r for r in output_rows if r["statut_cotation_ex"] != "NON_COTE" and r["chute_ex_pct"] is not None]

    def chute_stats(rows):
        chutes = [r["chute_ex_pct"] for r in rows]
        if not chutes:
            return {"n": 0, "chute_mediane": None, "pct_sous_30": None}
        return {
            "n": len(chutes),
            "chute_mediane": round(median(chutes), 2),
            "pct_sous_30": round(sum(1 for c in chutes if c < 30) / len(chutes) * 100, 1),
        }

    sg_a = [r for r in h2_pool if r["delai_ag_ex_jours"] is not None and r["delai_ag_ex_jours"] <= 45]

    vol_values = []
    for r in h2_pool:
        try:
            vol_values.append(float(r["volume_moyen_avant_annonce"]))
        except (TypeError, ValueError):
            pass
    vol_median = median(vol_values) if vol_values else None
    sg_c = []
    if vol_median is not None:
        for r in h2_pool:
            try:
                v = float(r["volume_moyen_avant_annonce"])
            except (TypeError, ValueError):
                continue
            if v >= vol_median:
                sg_c.append(r)

    yield_pool = [r for r in h2_pool if r["yield_pct"]]
    yield_pool_sorted = sorted(yield_pool, key=lambda r: float(r["yield_pct"]))
    n_yp = len(yield_pool_sorted)
    sg_b = yield_pool_sorted[int(round(2 * n_yp / 3)):] if n_yp else []

    subgroup_results = {
        "a_delai_ag_ex_le_45j": chute_stats(sg_a),
        "b_yield_tercile_sup": chute_stats(sg_b),
        "c_volume_ge_mediane": chute_stats(sg_c),
    }

    all_ticker_medians = [v["alpha_median"] for k, v in decoupe_ticker.items() if k != "n<3 (agrege, non interprete)"]
    alpha_global_median = median([r["alpha_cycle"] for r in output_rows])

    pct_tickers_positifs = None
    if all_ticker_medians:
        pct_tickers_positifs = sum(1 for m in all_ticker_medians if m > 0) / len(all_ticker_medians) * 100

    # Correction post-execution: la spec attend "chacune des 4 annees" -
    # l'annee en cours (2026, fragment S1 seulement) est exclue du critere
    # H1 strict pour eviter un biais de selection (seuls les cycles deja
    # payes en 2026 apparaissent dans le dataset exploitable).
    annee_courante = datetime.now().year
    annee_medians_completes = {k: v["alpha_median"] for k, v in decoupe_annee.items() if k not in ("date_ex_manquante", "n<3 (agrege, non interprete)") and k != annee_courante}
    annee_medians = annee_medians_completes
    toutes_annees_positives = all(v is not None and v > 0 for v in annee_medians.values()) if annee_medians else False
    nb_annees = len(annee_medians)

    h1_crit1 = alpha_global_median is not None and alpha_global_median >= 2.0
    h1_crit2 = pct_tickers_positifs is not None and pct_tickers_positifs >= 60.0
    h1_crit3 = toutes_annees_positives and nb_annees >= 4

    h1_criteres_echoues = sum(1 for c in (h1_crit1, h1_crit2, h1_crit3) if not c)
    h1_retenue = h1_criteres_echoues == 0

    h2_retenue = False
    h2_critere_gagnant = None
    h2_limite = False
    if not h1_retenue:
        for name, stats in subgroup_results.items():
            if stats["n"] >= 12 and stats["chute_mediane"] is not None:
                if stats["chute_mediane"] < 30:
                    h2_retenue = True
                    h2_critere_gagnant = name
                    break
                elif 30 <= stats["chute_mediane"] <= 35:
                    h2_limite = True

    cas_limite = (h1_criteres_echoues == 1) or (not h1_retenue and not h2_retenue and h2_limite)

    if h1_retenue:
        verdict = "H1"
        conclusion = ("H1 confirmee — derive post-annonce. Mecanisme candidat pour T5c : "
                      "hold annonce->paiement. Regle d'entree a cadrer avec Jocelyn.")
    elif cas_limite:
        verdict = "CAS_LIMITE"
        conclusion = ("Cas limite — H1 echoue sur un seul de ses trois criteres, ou un "
                      "sous-groupe H2 atteint n>=12 avec chute mediane entre 30 et 35%. "
                      "Escalade au modele avance, aucune conclusion ecrite.")
    elif h2_retenue:
        verdict = "H2"
        conclusion = (f"H2 confirmee sur sous-groupe [{h2_critere_gagnant}] — sous-reaction "
                      "exploitable. Critere d'eligibilite a figer en ADR avant backtest.")
    else:
        verdict = "H3"
        conclusion = ("H3 retenue — aucun mecanisme dividende identifiable. Le chiffre de "
                      "juin (93% WR) est repute non reproduit. T5c se conclut sans "
                      "backtest ; E2.4 et E2.5 restent gelees. Decision : Jocelyn.")

    print("\n" + "=" * 70)
    print("E2.6 — RESULTATS")
    print("=" * 70)
    print(f"\nCycles exploitables source: {len(exploitable_rows)}")
    print(f"Cycles traites: {len(output_rows)}")
    print(f"Cycles ecartes: {len(skipped)}")
    print(f"\n--- Etape 2: statut_cotation_ex ---")
    for k, v in statut_counts.items():
        print(f"  {k}: {v}")
    print(f"\n--- Etape 3a: decoupe par ticker (n>=3) ---")
    for k, v in sorted(decoupe_ticker.items()):
        print(f"  {k}: n={v['n']}, alpha_median={v['alpha_median']}, %positif={v['pct_positive']}")
    print(f"\n--- Etape 3b: decoupe par annee civile ex-date ---")
    for k, v in sorted(decoupe_annee.items(), key=lambda x: str(x[0])):
        print(f"  {k}: n={v['n']}, alpha_median={v['alpha_median']}, %positif={v['pct_positive']}")
    print(f"\n--- Etape 3c: decoupe par tercile de yield ---")
    for k, v in decoupe_tercile.items():
        print(f"  {k}: n={v['n']}, alpha_median={v['alpha_median']}, %positif={v['pct_positive']}")
    print(f"\n--- Etape 4: sous-groupes ex ante (H2, NON_COTE exclus) ---")
    for k, v in subgroup_results.items():
        print(f"  {k}: n={v['n']}, chute_mediane={v['chute_mediane']}, %sous_30={v['pct_sous_30']}")
    print(f"\n--- Criteres H1 ---")
    print(f"  alpha_global_median >= +2pts: {h1_crit1} (valeur={alpha_global_median})")
    print(f"  >=60% tickers alpha median positif: {h1_crit2} (valeur={pct_tickers_positifs})")
    print(f"  alpha median positif sur les {nb_annees} annees: {h1_crit3}")
    print(f"\n--- VERDICT: {verdict} ---")
    print(conclusion)
    print("=" * 70)

    entry = f"""

## E2.6 — Identification du mecanisme dividende (H1/H2/H3)
**Date d'execution**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: {len(exploitable_rows)} | **Traites**: {len(output_rows)} | **Ecartes**: {len(skipped)}

**Statut cotation ex**: COTE_SANS_VARIATION={statut_counts['COTE_SANS_VARIATION']}, NON_COTE={statut_counts['NON_COTE']}, COTE_AVEC_VARIATION={statut_counts['COTE_AVEC_VARIATION']}

**Criteres H1**:
- alpha median global >= +2pts: {h1_crit1} (valeur={alpha_global_median})
- >=60% tickers (n>=3) a alpha median positif: {h1_crit2} (valeur={pct_tickers_positifs})
- alpha median positif sur les {nb_annees} annees civiles: {h1_crit3}

**Sous-groupes ex ante (H2)**:
- delai AG->ex <= 45j: n={{subgroup_results['a_delai_ag_ex_le_45j']['n']}}, chute_mediane={{subgroup_results['a_delai_ag_ex_le_45j']['chute_mediane']}}
- yield tercile superieur: n={{subgroup_results['b_yield_tercile_sup']['n']}}, chute_mediane={{subgroup_results['b_yield_tercile_sup']['chute_mediane']}}
- volume >= mediane: n={{subgroup_results['c_volume_ge_mediane']['n']}}, chute_mediane={{subgroup_results['c_volume_ge_mediane']['chute_mediane']}}

**VERDICT: {verdict}**
{conclusion}

**Artefacts**: `tools/experiments/E2_6/E2_6_alpha_par_cycle.csv` ({len(output_rows)} lignes)
"""
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Journalise dans %s", LOG_MD)


if __name__ == "__main__":
    main()
