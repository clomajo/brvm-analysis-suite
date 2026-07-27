#!/usr/bin/env python3
"""
E2.7-B — Timing d'entree, detention longue
Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).

Meme mecanisme (H1, derive post-annonce) qu'E2.7-A, mais objectif different :
ici le titre est suppose detenu LONG TERME (pas de sortie liee au cycle
dividende). Question : entrer pres d'une date d'annonce de dividende
bat-il un point d'entree choisi au hasard dans l'annee, sur la meme duree
de detention ?

Grille fixee : 4 offsets d'entree (J-5, J0, J+5, J+10) x 3 durees de
detention (35j, 47j, 70j = Q1/mediane/Q3 de duree_jours sur les 89 cycles
d'E2.6). 12 combinaisons, aucune autre testee.

Univers : tous les tickers ayant au moins un cycle dividende exploitable
dans dividend_cycle_exploration.csv (memes cycles source qu'E2.6/E2.7A),
sans filtre de liquidite ni de nombre minimum de cycles supplementaire.

Calcul brut : ni frais ni IRVM (identique a E2.6/E2.7A) — cf. Interdits
specifiques d'E2.7-B dans PLAN_EXPERIMENTATION_MODELES.md.

Reference aleatoire par ticker x duree : moyenne des rendements totaux
(prix + dividende(s) captures dans la fenetre, meme logique que le
rendement de cycle) sur toutes les fenetres glissantes de cette duree
disponibles dans l'historique complet du ticker, echantillonnees tous
les 10 jours calendaires. Les dividendes sont inclus dans la reference
aleatoire pour une comparaison "detention longue" a perimetre egal
(un holder de long terme touche les dividendes qui tombent dans sa
fenetre de detention, qu'elle soit choisie autour d'une annonce ou au
hasard) — hypothese explicitee ici car non detaillee au mot pres dans
la spec, a signaler si contestee.

Ecriture strictement limitee a tools/experiments/E2_7B/ et EXPERIMENTS_LOG.md.
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
log = logging.getLogger("E2_7B")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CSV_SOURCE = os.path.join(REPO_ROOT, "dividend_cycle_exploration.csv")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_RENDEMENT = os.path.join(OUT_DIR, "E2_7B_rendement_par_combinaison.csv")
OUT_REFERENCE = os.path.join(OUT_DIR, "E2_7B_reference_aleatoire.csv")
OUT_ALPHA = os.path.join(OUT_DIR, "E2_7B_alpha_par_combinaison.csv")
LOG_MD = os.path.join(REPO_ROOT, "EXPERIMENTS_LOG.md")

ENTREE_OFFSETS = [-5, 0, 5, 10]
DUREES = [35, 47, 70]
MAX_GAP_DAYS = 5
SAMPLE_STEP_DAYS = 10
OFFSETS_PROCHES_ANNONCE = [-5, 0]  # J-5 et J0 : "l'offset le plus proche de l'annonce"


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


def build_dividend_index(source_rows):
    """ticker -> liste triee de (date_ex, montant) pour TOUS les evenements
    dividende reels (date_ex et montant presents), pas seulement les cycles
    'exploitable' — un cycle peut capturer le dividende d'une autre annee."""
    idx = {}
    for r in source_rows:
        d_ex = parse_date(r.get("date_ex"))
        montant = r.get("montant")
        if d_ex is None or not montant:
            continue
        try:
            m = float(montant)
        except ValueError:
            continue
        idx.setdefault(r["ticker"], []).append((d_ex, m))
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


def compute_entry_price(price_list, target_date, max_gap_days=MAX_GAP_DAYS):
    _, p, _ = price_at_or_before(price_list, target_date, max_gap_days)
    return p


def compute_exit_price(price_list, target_date, max_gap_days=MAX_GAP_DAYS):
    _, p, _ = price_at_or_before(price_list, target_date, max_gap_days)
    return p


def dividendes_captures(div_list, date_debut, date_fin):
    """Somme des montants de tous les evenements dividende dont date_ex
    tombe dans [date_debut, date_fin], et le nombre d'evenements captures."""
    events = [m for d, m in div_list if date_debut <= d <= date_fin]
    return sum(events), len(events)


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

    univers_tickers = sorted(set(r["ticker"] for r in exploitable_rows))
    log.info("Univers etendu (>=1 dividende exploitable): %d tickers", len(univers_tickers))

    log.info("Recuperation v_historical_prices via REST (pagination Range)...")
    price_rows = fetch_all_prices(url, key)
    price_index = build_price_index(price_rows)
    dividend_index = build_dividend_index(source_rows)
    log.info("Index prix construit: %d tickers, index dividendes: %d tickers", len(price_index), len(dividend_index))

    # --- Etape 1: rendement par cycle x offset x duree ---
    rendement_rows = []
    n_exclus_total = 0
    n_multi_dividendes = 0

    for entree_off in ENTREE_OFFSETS:
        for duree in DUREES:
            n_exclus = 0
            for r in exploitable_rows:
                ticker = r["ticker"]
                date_annonce = parse_date(r["date_annonce"])
                if not date_annonce:
                    n_exclus += 1
                    continue

                date_entree = date_annonce + timedelta(days=entree_off)
                date_sortie_calc = date_entree + timedelta(days=duree)

                plist = price_index.get(ticker, [])
                p_start = compute_entry_price(plist, date_entree)
                p_end = compute_exit_price(plist, date_sortie_calc)

                if p_start is None or p_end is None or p_start == 0:
                    n_exclus += 1
                    continue

                div_list = dividend_index.get(ticker, [])
                dividende_total, n_div = dividendes_captures(div_list, date_entree, date_sortie_calc)
                if n_div > 1:
                    n_multi_dividendes += 1

                rendement_cycle = (p_end - p_start + dividende_total) / p_start * 100.0

                rendement_rows.append({
                    "ticker": ticker,
                    "fiscal_year": r.get("fiscal_year"),
                    "offset": entree_off,
                    "duree": duree,
                    "date_entree": date_entree.isoformat(),
                    "date_sortie_calc": date_sortie_calc.isoformat(),
                    "rendement_cycle": round(rendement_cycle, 4),
                })

            n_exclus_total += n_exclus
            log.info("Combo (offset=%+d, duree=%dj): %d cycles valides, %d exclus",
                      entree_off, duree, len(exploitable_rows) - n_exclus, n_exclus)

    if n_multi_dividendes:
        log.warning("SIGNAL: %d cycles (cumules sur les 12 combinaisons) capturent plus d'un "
                    "evenement dividende dans leur fenetre — non exclus, comptabilises tel quel.",
                    n_multi_dividendes)

    fieldnames_rendement = [
        "ticker", "fiscal_year", "offset", "duree",
        "date_entree", "date_sortie_calc", "rendement_cycle",
    ]
    with open(OUT_RENDEMENT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_rendement)
        w.writeheader()
        w.writerows(rendement_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_RENDEMENT, len(rendement_rows))

    # --- Etape 2: reference aleatoire par ticker x duree ---
    reference_rows = []
    reference_lookup = {}

    for ticker in univers_tickers:
        plist = price_index.get(ticker, [])
        div_list = dividend_index.get(ticker, [])
        if not plist:
            for duree in DUREES:
                reference_rows.append({"ticker": ticker, "duree": duree, "n_fenetres": 0, "rendement_moyen": None})
                reference_lookup[(ticker, duree)] = None
            continue

        first_date = plist[0][0]
        last_date = plist[-1][0]

        for duree in DUREES:
            rets = []
            window_start = first_date
            while window_start + timedelta(days=duree) <= last_date:
                window_end = window_start + timedelta(days=duree)
                p_start = compute_entry_price(plist, window_start)
                p_end = compute_exit_price(plist, window_end)
                if p_start is not None and p_end is not None and p_start != 0:
                    dividende_total, _ = dividendes_captures(div_list, window_start, window_end)
                    rets.append((p_end - p_start + dividende_total) / p_start * 100.0)
                window_start += timedelta(days=SAMPLE_STEP_DAYS)

            rendement_moyen = round(statistics.mean(rets), 4) if rets else None
            reference_rows.append({
                "ticker": ticker, "duree": duree, "n_fenetres": len(rets), "rendement_moyen": rendement_moyen,
            })
            reference_lookup[(ticker, duree)] = rendement_moyen

    with open(OUT_REFERENCE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "duree", "n_fenetres", "rendement_moyen"])
        w.writeheader()
        w.writerows(reference_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_REFERENCE, len(reference_rows))

    # --- Etape 3: ecart par combinaison (offset x duree), fichier fusionne alpha ---
    alpha_rows = []
    for row in rendement_rows:
        ref = reference_lookup.get((row["ticker"], row["duree"]))
        if ref is None:
            continue
        ecart_cycle = round(row["rendement_cycle"] - ref, 4)
        alpha_rows.append({
            **row,
            "reference_aleatoire": ref,
            "ecart_cycle": ecart_cycle,
        })

    fieldnames_alpha = fieldnames_rendement + ["reference_aleatoire", "ecart_cycle"]
    with open(OUT_ALPHA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_alpha)
        w.writeheader()
        w.writerows(alpha_rows)
    log.info("Ecrit: %s (%d lignes)", OUT_ALPHA, len(alpha_rows))

    stats_par_combo = {}
    for entree_off in ENTREE_OFFSETS:
        for duree in DUREES:
            combo = (entree_off, duree)
            vals = [r["ecart_cycle"] for r in alpha_rows if r["offset"] == entree_off and r["duree"] == duree]
            n_battant = sum(1 for r in alpha_rows
                             if r["offset"] == entree_off and r["duree"] == duree and r["ecart_cycle"] > 0)
            stats_par_combo[combo] = {
                "n": len(vals),
                "ecart_moyen": round(statistics.mean(vals), 4) if vals else None,
                "ecart_median": round(median(vals), 4) if vals else None,
                "pct_battant": round(n_battant / len(vals) * 100.0, 1) if vals else None,
            }

    # --- Regles d'interpretation (appliquees dans l'ordre) ---
    n_positifs = sum(1 for s in stats_par_combo.values() if s["ecart_median"] is not None and s["ecart_median"] > 0)
    n_combos_pct_ge_55 = sum(1 for s in stats_par_combo.values() if s["pct_battant"] is not None and s["pct_battant"] >= 55.0)

    def offset_a_2_sur_3_durees_ge_55(offset):
        durees_ok = sum(1 for duree in DUREES if stats_par_combo[(offset, duree)]["pct_battant"] is not None
                         and stats_par_combo[(offset, duree)]["pct_battant"] >= 55.0)
        return durees_ok >= 2

    condition_offset_proche = any(offset_a_2_sur_3_durees_ge_55(o) for o in OFFSETS_PROCHES_ANNONCE)

    verdict = None
    conclusion = None

    if n_positifs >= 9 and condition_offset_proche:
        verdict = "TIMING_DIVIDENDE_CONFIRME"
        meilleures = sorted(stats_par_combo.items(),
                             key=lambda kv: (kv[1]["ecart_median"] if kv[1]["ecart_median"] is not None else -9999),
                             reverse=True)[:3]
        liste_meilleures = ", ".join(f"(offset={c[0]:+d}, duree={c[1]}j): ecart_median={s['ecart_median']}"
                                       for c, s in meilleures)
        conclusion = ("Timing d'entree autour de l'annonce de dividende ameliore le rendement vs entree "
                      "aleatoire, de facon robuste a travers les durees testees. Combinaison(s) a discuter "
                      f"avec Jocelyn : {liste_meilleures}.")
    elif n_positifs < 6 or n_combos_pct_ge_55 <= 2:
        verdict = "PAS_EFFET_TIMING"
        conclusion = ("Aucun effet de timing fiable detecte au-dela du mecanisme deja documente par E2.6. "
                      "Pour une strategie de detention longue, le moment d'entree autour d'une annonce de "
                      "dividende n'apporte pas d'avantage mesurable et robuste a travers les durees testees.")
    else:
        verdict = "CAS_LIMITE"
        conclusion = ("Resultats incoherents entre combinaisons — escalade au modele avance, "
                      "aucune conclusion ecrite.")

    # --- Rapport console ---
    print("\n" + "=" * 70)
    print("E2.7-B — RESULTATS")
    print("=" * 70)
    print(f"\nCycles exploitables source: {len(exploitable_rows)}")
    print(f"Univers etendu (tickers avec >=1 cycle exploitable): {len(univers_tickers)}")
    print(f"Cycles multi-dividendes signales (cumules sur 12 combos): {n_multi_dividendes}")
    print(f"\n--- Etape 3: tableau 4x3 (offset x duree) — n, ecart_median, %battant ---")
    label_coin = "offset\\duree"
    print(f"{label_coin:>15}", end="")
    for duree in DUREES:
        print(f"{str(duree)+'j':>28}", end="")
    print()
    for entree_off in ENTREE_OFFSETS:
        row_label = f"{entree_off:+d}"
        print(f"{row_label:>15}", end="")
        for duree in DUREES:
            s = stats_par_combo[(entree_off, duree)]
            cell = f"n={s['n']},e={s['ecart_median']},%b={s['pct_battant']}"
            print(f"{cell:>28}", end="")
        print()
    print(f"\n--- Criteres ---")
    print(f"  combinaisons avec ecart median positif: {n_positifs}/12")
    print(f"  combinaisons avec %battant>=55: {n_combos_pct_ge_55}/12")
    print(f"  offset proche annonce (J-5 ou J0) avec >=2/3 durees a %battant>=55: {condition_offset_proche}")
    print(f"\n--- VERDICT: {verdict} ---")
    print(conclusion)
    print("=" * 70)

    # --- Journalisation ---
    tableau_md = "| offset\\\\duree | " + " | ".join(f"{d}j" for d in DUREES) + " |\n"
    tableau_md += "|---|" + "---|" * len(DUREES) + "\n"
    for entree_off in ENTREE_OFFSETS:
        row = f"| {entree_off:+d} | "
        row += " | ".join(
            f"n={stats_par_combo[(entree_off, d)]['n']}, "
            f"ecart={stats_par_combo[(entree_off, d)]['ecart_median']}, "
            f"%b={stats_par_combo[(entree_off, d)]['pct_battant']}"
            for d in DUREES
        )
        row += " |\n"
        tableau_md += row

    entry = f"""

## E2.7-B — Timing d'entree, detention longue
**Date d'execution**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: {len(exploitable_rows)}
**Univers etendu**: {len(univers_tickers)} tickers (>=1 cycle dividende exploitable, sans filtre de liquidite ni de nombre minimum de cycles)
**Cycles multi-dividendes signales**: {n_multi_dividendes}

**Tableau 4x3 (offset x duree), n / ecart median / %battant par case**:

{tableau_md}
**Combinaisons avec ecart median positif**: {n_positifs}/12
**Combinaisons avec %battant>=55**: {n_combos_pct_ge_55}/12
**Offset proche annonce (J-5 ou J0) avec >=2/3 durees a %battant>=55**: {condition_offset_proche}

**VERDICT: {verdict}**
{conclusion}

**Artefacts**: `tools/experiments/E2_7B/E2_7B_rendement_par_combinaison.csv` ({len(rendement_rows)} lignes), `tools/experiments/E2_7B/E2_7B_reference_aleatoire.csv` ({len(reference_rows)} lignes), `tools/experiments/E2_7B/E2_7B_alpha_par_combinaison.csv` ({len(alpha_rows)} lignes)
"""
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Journalise dans %s", LOG_MD)


if __name__ == "__main__":
    main()
