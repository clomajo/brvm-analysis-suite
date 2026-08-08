#!/usr/bin/env python3
"""
Audit E2.6 — recalcul de l'alpha en prix pur des deux cotes.
Classe A, lecture seule, aucun acces DB, aucune ecriture hors
tools/experiments/E2_6/.

Motif: run_e2_6.py L289 reintegre le dividende au sujet
(p_end - p_start + dividende) tandis que compute_benchmark L129 reste
en prix pur (p_end - p_start). Meme asymetrie que E2.8/T5c-A.
"""
import csv
import logging
import os
import statistics
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("AUDIT_E2_6")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO_ROOT, "dividend_cycle_exploration.csv")
E26 = os.path.join(HERE, "E2_6_alpha_par_cycle.csv")
OUT = os.path.join(HERE, "E2_6_audit_alpha_pp.csv")

TOL_C1 = 0.5
SEUIL_C1_PCT = 95.0


def med(v):
    return statistics.median(v) if v else None


def pctpos(v):
    return sum(1 for x in v if x > 0) / len(v) * 100.0 if v else None


def fnum(s):
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load():
    for p in (SRC, E26):
        if not os.path.exists(p):
            log.error("Fichier introuvable: %s", p)
            sys.exit(1)
    with open(SRC, newline="", encoding="utf-8") as f:
        src = {(r["ticker"], str(r["fiscal_year"]).strip()): r
               for r in csv.DictReader(f)}
    with open(E26, newline="", encoding="utf-8") as f:
        e26 = list(csv.DictReader(f))
    log.info("Source: %d cycles | E2.6: %d cycles", len(src), len(e26))
    return src, e26


def groupe(rows, keyfn, min_n):
    g = {}
    for r in rows:
        g.setdefault(keyfn(r), []).append(r)
    out = {}
    for k, v in sorted(g.items(), key=lambda x: str(x[0])):
        if len(v) < min_n:
            continue
        pub = [r["alpha_pub"] for r in v]
        pp = [r["alpha_pp"] for r in v]
        out[k] = (len(v), med(pub), pctpos(pub), med(pp), pctpos(pp))
    return out


def main():
    src, e26 = load()
    rows, orphelins, c1_ko, anomalies = [], [], [], []

    for r in e26:
        key = (r["ticker"], str(r["fiscal_year"]).strip())
        s = src.get(key)
        if s is None:
            orphelins.append(key)
            continue
        p_a = fnum(s.get("prix_annonce"))
        p_p = fnum(s.get("prix_paiement"))
        mnt = fnum(s.get("montant"))
        rdt = fnum(r.get("rendement_cycle"))
        bench = fnum(r.get("benchmark_cycle"))
        alpha_pub = fnum(r.get("alpha_cycle"))
        if None in (p_a, p_p, mnt, rdt, bench, alpha_pub) or p_a == 0:
            orphelins.append(key)
            continue

        rdt_recalc = (p_p - p_a + mnt) / p_a * 100.0
        ecart_c1 = rdt_recalc - rdt
        contrib = mnt / p_a * 100.0
        alpha_pp = alpha_pub - contrib
        duree = fnum(r.get("duree_jours")) or 0.0
        if duree > 180:
            anomalies.append(key)
        if abs(ecart_c1) > TOL_C1:
            c1_ko.append((key, round(ecart_c1, 3)))

        rows.append({
            "ticker": r["ticker"], "fiscal_year": key[1],
            "annee_ex": (r.get("date_ex") or "")[:4] or "NA",
            "duree_jours": duree, "prix_annonce": p_a,
            "contrib_div_pts": round(contrib, 4),
            "alpha_pub": alpha_pub, "alpha_pp": round(alpha_pp, 4),
            "ecart_c1": round(ecart_c1, 4),
        })

    log.info("Apparies: %d | orphelins: %d", len(rows), len(orphelins))
    for k in orphelins:
        log.warning("Non apparie ou champ manquant: %s", k)
    if not rows:
        log.error("Aucun cycle apparie — audit impossible.")
        sys.exit(1)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log.info("Ecrit: %s (%d lignes)", OUT, len(rows))

    n = len(rows)
    ok = n - len(c1_ko)
    pct_ok = ok / n * 100.0
    pub = [r["alpha_pub"] for r in rows]
    pp = [r["alpha_pp"] for r in rows]
    contribs = [r["contrib_div_pts"] for r in rows]

    print("\n" + "=" * 72)
    print("AUDIT E2.6 — ALPHA EN PRIX PUR DES DEUX COTES")
    print("=" * 72)
    print(f"\n--- C1 : reconciliation rendement_cycle (tol +/-{TOL_C1} pt) ---")
    print(f"  Concordants: {ok}/{n} ({pct_ok:.1f}%) — seuil requis {SEUIL_C1_PCT}%")
    for k, e in c1_ko[:15]:
        print(f"    ECART {k}: {e} pts")
    if len(c1_ko) > 15:
        print(f"    ... {len(c1_ko) - 15} autres")
    if pct_ok < SEUIL_C1_PCT:
        print("\n  >>> C1 ECHOUE — sources divergentes. Aucun verdict rendu.")
        print("=" * 72)
        return

    print(f"\n--- Global (n={n}) ---")
    print(f"  contrib_div mediane : {med(contribs):+.3f} pts")
    print(f"  alpha PUBLIE        : mediane {med(pub):+.3f} | %positif {pctpos(pub):.1f}")
    print(f"  alpha PRIX PUR      : mediane {med(pp):+.3f} | %positif {pctpos(pp):.1f}")

    sains = [r for r in rows if r["duree_jours"] <= 180]
    print(f"\n--- Descriptif seul, non decisionnel : duree<=180j (n={len(sains)}) ---")
    print(f"  alpha PRIX PUR      : mediane {med([r['alpha_pp'] for r in sains]):+.3f}"
          f" | %positif {pctpos([r['alpha_pp'] for r in sains]):.1f}")
    print(f"  Anomalies duree>180j: {anomalies if anomalies else 'aucune'}")

    for titre, res in (
        ("annee civile ex-date", groupe(rows, lambda r: r["annee_ex"], 1)),
        ("ticker (n>=3)", groupe(rows, lambda r: r["ticker"], 3)),
    ):
        print(f"\n--- Par {titre} ---")
        for k, (nn, mpub, ppub, mpp, ppp) in res.items():
            print(f"  {k}: n={nn} | pub {mpub:+.2f}/{ppub:.0f}%"
                  f" | pp {mpp:+.2f}/{ppp:.0f}%")

    m, p = med(pp), pctpos(pp)
    if m >= 2.0 and p >= 55.0:
        v = "V1 — H1 TIENT (drift de prix reel, independant du coupon)"
    elif m <= 0.0 or p <= 45.0:
        v = "V2 — H1 TOMBE (alpha publie porte par l'asymetrie de benchmark)"
    else:
        v = "V3 — ZONE GRISE, non concluant"
    print(f"\n--- VERDICT: {v} ---")
    print("Rappel: le benchmark prix pur reste deprime par les detachements")
    print("des tickers de reference (fenetres avril-juin) -> ce test est")
    print("CONSERVATEUR en faveur de H1.")
    print("=" * 72)


if __name__ == "__main__":
    main()
