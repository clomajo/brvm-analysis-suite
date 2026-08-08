#!/usr/bin/env python3
"""Audit des biais de E2.8 / T5c-A. Lecture seule, aucun acces DB, aucune ecriture.

Trois partitions testees sur les artefacts deja produits :
  1. Asymetrie dividende  -> alpha recalcule en prix pur (symetrique)
  2. source_montant       -> DIVIDEND_HISTORY (ADR-040) vs DIVIDEND (saine)
  3. gap_entree_jours     -> prix d'entree anterieur a l'annonce (non executable)
"""
import csv
import logging
import os
import statistics as st
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
log = logging.getLogger("audit_e2_8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CSV_CYCLES = os.path.join(HERE, "E2_8_rotation_par_cycle.csv")
CSV_SOURCE = os.path.join(REPO, "dividend_cycle_exploration.csv")


def charger(path, label):
    if not os.path.exists(path):
        log.error("Introuvable : %s", path)
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    log.info("%s : %d lignes", label, len(rows))
    return rows


def indexer_source(rows):
    idx = {}
    for r in rows:
        if r.get("exploitable") != "True":
            continue
        idx[(r["ticker"], r["fiscal_year"])] = r
    return idx


def enrichir(cycles, idx_src):
    out, n_orphelin, n_sans_prix = [], 0, 0
    for c in cycles:
        src = idx_src.get((c["ticker"], c["fiscal_year"]))
        if src is None:
            n_orphelin += 1
            continue
        try:
            prix_annonce = float(src["prix_annonce"]) if src.get("prix_annonce") else 0.0
        except ValueError:
            prix_annonce = 0.0
        if prix_annonce <= 0:
            n_sans_prix += 1
            continue
        div = float(c["dividende_encaisse"] or 0.0)
        contrib = div / prix_annonce * 100.0
        out.append({
            "ticker": c["ticker"],
            "alpha_cycle": float(c["alpha_cycle"]),
            "contrib_div_pts": contrib,
            "alpha_prix": float(c["alpha_cycle"]) - contrib,
            "div_encaisse": div,
            "gap_entree": int(c["gap_entree_jours"] or 0),
            "source_montant": src.get("source_montant", "?"),
        })
    log.info("Apparies : %d ; orphelins : %d ; sans prix_annonce : %d", len(out), n_orphelin, n_sans_prix)
    return out


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "med": round(st.median(vals), 3),
        "moy": round(st.mean(vals), 3),
        "pct_pos": round(100.0 * sum(1 for v in vals if v > 0) / len(vals), 1),
    }


def afficher(titre, groupes, cle):
    print(f"\n--- {titre} ---")
    print(f"{'groupe':<28}{'n':>6}{'mediane':>12}{'moyenne':>12}{'%positif':>11}")
    for nom, lignes in groupes:
        s = stats([r[cle] for r in lignes])
        if s is None:
            print(f"{nom:<28}{'0':>6}{'-':>12}{'-':>12}{'-':>11}")
            continue
        print(f"{nom:<28}{s['n']:>6}{s['med']:>12}{s['moy']:>12}{s['pct_pos']:>11}")


def main():
    cycles = charger(CSV_CYCLES, "E2_8_rotation_par_cycle")
    source = charger(CSV_SOURCE, "dividend_cycle_exploration")
    data = enrichir(cycles, indexer_source(source))
    if not data:
        log.error("Aucun cycle apparie — appariement (ticker, fiscal_year) a verifier.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("AUDIT BIAIS E2.8 / T5c-A")
    print("=" * 70)

    # TEST 1 — asymetrie dividende : alpha publie vs alpha en prix pur
    afficher("TEST 1a — alpha_cycle publie (rendement total vs benchmark prix)",
             [("tous cycles", data)], "alpha_cycle")
    afficher("TEST 1b — alpha_prix recalcule (prix pur des deux cotes)",
             [("tous cycles", data)], "alpha_prix")
    contribs = [r["contrib_div_pts"] for r in data]
    s = stats(contribs)
    print(f"\nContribution mecanique du dividende : mediane {s['med']} pts, moyenne {s['moy']} pts")
    avec = [r for r in data if r["div_encaisse"] > 0]
    sans = [r for r in data if r["div_encaisse"] == 0]
    print(f"Cycles avec dividende encaisse : {len(avec)} ; sans : {len(sans)}")
    afficher("TEST 1c — groupe de controle (alpha publie)",
             [("avec dividende", avec), ("sans dividende (temoin)", sans)], "alpha_cycle")

    # TEST 2 — ADR-040
    afficher("TEST 2 — source du montant (alpha publie)",
             [("DIVIDEND_HISTORY (decalee)", [r for r in data if r["source_montant"] == "DIVIDEND_HISTORY"]),
              ("DIVIDEND (saine)", [r for r in data if r["source_montant"] == "DIVIDEND"])],
             "alpha_cycle")

    # TEST 3 — executabilite du prix d'entree
    afficher("TEST 3 — gap d'entree (alpha en prix pur)",
             [("gap = 0 j (executable)", [r for r in data if r["gap_entree"] == 0]),
              ("gap >= 1 j (pre-annonce)", [r for r in data if r["gap_entree"] >= 1])],
             "alpha_prix")
    rep = {}
    for r in data:
        rep[r["gap_entree"]] = rep.get(r["gap_entree"], 0) + 1
    print("\nRepartition gap_entree_jours :", dict(sorted(rep.items())))

    print("\n" + "=" * 70)
    print("LECTURE : TEST 1b est decisif. Si alpha_prix median reste franchement")
    print("positif, le drift post-annonce est reel -> T5c-A en production.")
    print("S'il s'effondre vers 0, l'alpha publie est une ecriture comptable")
    print("-> benchmark a reconstruire en rendement total avant toute decision.")
    print("=" * 70)


if __name__ == "__main__":
    main()
