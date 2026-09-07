"""Re-verification des signaux V1 sur prix corriges (ADR-052 amdt 6).

Logique de calcul recopiee a l'identique de verify_decisions.py :
  - fenetre de verification J+20 en jours calendaires (ADR-019)
  - tolerance +/-5 jours pour trouver un prix (get_price_at_date)
  - memes regles de signal_correct
  - benchmark_return = moyenne des variation_pct de la cohorte du jour

Trois differences, toutes assumees et documentees :
  1. boucle sur toutes les dates de signal au lieu de la seule date J-20
  2. verification_date derivee de signal_date (+20j), non de date.today()
  3. ecrit dans brvm_decisions_results_v2, jamais dans la table de production

Lecture seule sur historical_data, brvm_decisions, companies.
"""
import os, logging, argparse
from datetime import date, timedelta
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

WINDOW = 20          # jours calendaires, ADR-019 — inchange
TOLERANCE = 5        # +/-5 jours, inchange
CIBLE = "brvm_decisions_results_v2"


def get_all(table, qs):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}?{qs}&order=id.asc&limit=1000&offset={off}",
                         headers=H, timeout=120)
        if r.status_code >= 400:
            log.error("%s: %s", table, r.text[:400])
        r.raise_for_status()
        b = r.json()
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debut", default="2026-04-09")
    ap.add_argument("--fin", default="2026-09-04")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    comps = get_all("companies", "select=id,symbol")
    sym2id = {c["symbol"]: c["id"] for c in comps}
    log.info("companies: %s", len(comps))

    prix = {}
    for row in get_all("historical_data", "select=company_id,trade_date,price"):
        if row["price"] is None:
            continue
        prix[(row["company_id"], row["trade_date"])] = float(row["price"])

    # Seances reelles = celles du BOC (source de verite), bornees a la fenetre.
    seances = {r["date_seance"] for r in get_all(
        "boc_cote", "select=date_seance&est_droit=is.false")}
    log.info("prix charges: %s | seances BOC: %s", len(prix), len(seances))

    decisions = get_all("brvm_decisions",
                        f"select=id,ticker,signal,score,date"
                        f"&date=gte.{a.debut}&date=lte.{a.fin}")
    log.info("decisions dans la fenetre: %s", len(decisions))

    reelles = {d["date"] for d in decisions} & seances
    fictives = {d["date"] for d in decisions} - seances
    log.info("dates de signal avec seance reelle: %s | sans seance: %s",
             len(reelles), len(fictives))
    if fictives:
        log.info("dates ecartees (amdt 6): %s", sorted(fictives)[:10])

    def prix_proche(cid, cible):
        best, ecart = None, None
        for delta in range(-TOLERANCE, TOLERANCE + 1):
            d = (cible + timedelta(days=delta)).isoformat()
            v = prix.get((cid, d))
            if v is not None and (ecart is None or abs(delta) < ecart):
                best, ecart = v, abs(delta)
        return best

    par_date = {}
    ignores = {"date_fictive": 0, "company": 0, "prix_signal": 0, "prix_verif": 0}

    for d in decisions:
        if d["date"] in fictives:
            ignores["date_fictive"] += 1
            continue
        cid = sym2id.get(d["ticker"])
        if not cid:
            ignores["company"] += 1
            continue
        sd = date.fromisoformat(d["date"])
        vd = sd + timedelta(days=WINDOW)

        ps = prix_proche(cid, sd)
        if ps is None:
            ignores["prix_signal"] += 1
            continue
        pv = prix_proche(cid, vd)
        if pv is None:
            ignores["prix_verif"] += 1
            continue

        var = round((pv - ps) / ps * 100, 2)
        s = d["signal"]
        if s in ("BUY", "ACHAT", "ACHETER"):
            ok = var > 0
        elif s in ("SELL", "VENTE", "VENDRE", "ÉVITER"):
            ok = var < 0
        else:
            ok = abs(var) < 5

        par_date.setdefault(d["date"], []).append({
            "decision_id": d["id"], "ticker": d["ticker"], "signal": s,
            "score": d["score"], "signal_date": d["date"],
            "verification_date": vd.isoformat(),
            "prix_signal": ps, "prix_verification": pv,
            "variation_pct": var, "signal_correct": ok,
        })

    log.info("ignores: %s", ignores)

    results = []
    for dt, lot in par_date.items():
        bench = round(sum(r["variation_pct"] for r in lot) / len(lot), 2)
        for r in lot:
            r["benchmark_return"] = bench
            r["alpha"] = round(r["variation_pct"] - bench, 2)
        results += lot

    log.info("resultats calcules: %s sur %s dates", len(results), len(par_date))
    if results:
        ok = sum(1 for r in results if r["signal_correct"])
        log.info("hit rate global: %s/%s = %.1f%%", ok, len(results), ok / len(results) * 100)
        for sig in ("ACHAT", "SURVEILLER", "EVITER"):
            sub = [r for r in results if r["signal"] == sig]
            if sub:
                k = sum(1 for r in sub if r["signal_correct"])
                log.info("  %-12s %s/%s = %.1f%%", sig, k, len(sub), k / len(sub) * 100)

    if a.dry_run:
        log.info("\nDRY RUN — aucune ecriture")
        return

    for i in range(0, len(results), 500):
        lot = results[i:i + 500]
        r = requests.post(f"{URL}/rest/v1/{CIBLE}",
                          headers={**H, "Content-Type": "application/json",
                                   "Prefer": "return=minimal"},
                          json=lot, timeout=120)
        if r.status_code >= 400:
            log.error("lot %s: %s", i, r.text[:500])
            r.raise_for_status()
        log.info("lot %s-%s insere", i, i + len(lot))
    log.info("TERMINE — %s lignes dans %s", len(results), CIBLE)


if __name__ == "__main__":
    main()
