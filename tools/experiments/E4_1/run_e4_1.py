"""E4.1 — volet sectoriel d'E4.0 avec SECTEUR_OFFICIEL complet (47 tickers).
Pre-enregistrement : EXPERIMENTS_LOG.md, commit d8df413.
Classe A : lecture seule, aucune ecriture en base.
"""
import os, sys, json, math, logging, statistics
from datetime import date, timedelta
from collections import defaultdict
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)
load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

sys.path.insert(0, os.getcwd())
from calculate_target_price import SECTEUR_OFFICIEL

HORIZON, TOLERANCE, N_MIN, BRVMC_ID = 20, 5, 100, 48
SORTIE = "tools/experiments/E4_1"


def get_all(table, qs):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}?{qs}&order=id.asc&limit=1000&offset={off}",
                         headers=H, timeout=120)
        if r.status_code >= 400:
            log.error("%s: %s", table, r.text[:400])
        r.raise_for_status()
        b = r.json(); out += b
        if len(b) < 1000:
            return out
        off += 1000


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    p, z = k / n, 1.96
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    m = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0.0, c-m), min(1.0, c+m))


def stats(rows):
    n = len(rows)
    if n == 0:
        return None
    k = sum(1 for r in rows if r["var"] > 0)
    lo, hi = wilson(k, n)
    return {
        "n": n, "hit": round(k/n*100, 1), "ic95": [round(lo*100,1), round(hi*100,1)],
        "variation": round(statistics.mean(r["var"] for r in rows), 2),
        "a_coh": round(statistics.mean(r["a_coh"] for r in rows), 2),
        "a_brvmc": round(statistics.mean(r["a_brvmc"] for r in rows), 2),
        "interpretable": n >= N_MIN,
    }


def main():
    seances = sorted({r["date_seance"] for r in get_all(
        "boc_cote", "select=date_seance&est_droit=is.false")})
    seances_set = set(seances)
    log.info("seances BOC: %s", len(seances))

    prix = defaultdict(dict)
    for r in get_all("historical_data", "select=company_id,trade_date,price"):
        if r["price"]:
            prix[r["company_id"]][r["trade_date"]] = float(r["price"])
    log.info("prix chargees: %s societes", len(prix))

    co = get_all("companies", "select=id,symbol")
    sym = {c["id"]: c["symbol"] for c in co}

    def prix_proche(cid, d0):
        for delta in range(0, TOLERANCE+1):
            for s in ((1, -1) if delta else (1,)):
                d = (d0 + timedelta(days=delta*s)).isoformat()
                if d in seances_set and d in prix.get(cid, {}):
                    return prix[cid][d]
        return None

    dec = get_all("brvm_decisions",
                  "select=id,ticker,signal,date,liquidity_tier")
    log.info("decisions: %s", len(dec))

    par_date = defaultdict(list)
    ign = defaultdict(int)
    for d in dec:
        if d["date"] not in seances_set:
            ign["date_fictive"] += 1; continue
        cid = next((i for i, s in sym.items() if s == d["ticker"]), None)
        if cid is None:
            ign["company"] += 1; continue
        sd = date.fromisoformat(d["date"])
        vd = sd + timedelta(days=HORIZON)
        ps, pv = prix_proche(cid, sd), prix_proche(cid, vd)
        if ps is None or pv is None:
            ign["prix"] += 1; continue
        bs, bv = prix_proche(BRVMC_ID, sd), prix_proche(BRVMC_ID, vd)
        if bs is None or bv is None:
            ign["brvmc"] += 1; continue
        par_date[d["date"]].append({
            "ticker": d["ticker"], "signal": d["signal"],
            "tier": d.get("liquidity_tier"),
            "secteur": SECTEUR_OFFICIEL.get(d["ticker"], "AUTRE"),
            "var": (pv-ps)/ps*100, "b_var": (bv-bs)/bs*100,
        })
    log.info("ignores: %s", dict(ign))

    rows = []
    for dt, lot in par_date.items():
        bench = statistics.mean(r["var"] for r in lot)
        for r in lot:
            r["a_coh"] = r["var"] - bench
            r["a_brvmc"] = r["var"] - r["b_var"]
        rows += lot
    log.info("observations: %s sur %s dates\n", len(rows), len(par_date))

    out = {"horizon": HORIZON, "n_total": len(rows), "global": {}, "secteur": {},
           "secteur_x_tier": {}}

    for sig in ("ACHAT", "SURVEILLER", "EVITER"):
        sub = [r for r in rows if r["signal"] == sig]
        out["global"][sig] = stats(sub)

    for sig in ("ACHAT", "SURVEILLER", "EVITER"):
        g = out["global"][sig]
        print(f"\n=== {sig} — global n={g['n']} hit={g['hit']}% "
              f"IC95={g['ic95']} a_coh={g['a_coh']:+.2f}")
        print(f"{'secteur':<30} {'n':>5} {'hit':>7} {'IC95':>15} "
              f"{'a_coh':>8} {'a_brvmc':>9}  div")
        for sec in sorted(set(SECTEUR_OFFICIEL.values())):
            s = stats([r for r in rows if r["signal"] == sig and r["secteur"] == sec])
            if not s:
                continue
            out["secteur"].setdefault(sig, {})[sec] = s
            div = "—"
            if s["interpretable"]:
                div = "DIV" if (s["ic95"][1] < g["ic95"][0] or
                                s["ic95"][0] > g["ic95"][1]) else "non"
            flag = "" if s["interpretable"] else "  (n<100)"
            print(f"{sec:<30} {s['n']:>5} {s['hit']:>6.1f}% "
                  f"{str(s['ic95']):>15} {s['a_coh']:>+8.2f} "
                  f"{s['a_brvmc']:>+9.2f}  {div}{flag}")

    print("\n=== ACHAT — secteur x liquidity_tier")
    print(f"{'secteur':<30} {'tier':<10} {'n':>5} {'hit':>7} {'a_coh':>8}")
    for sec in sorted(set(SECTEUR_OFFICIEL.values())):
        for tier in ("liquid", "illiquid", "prestige"):
            s = stats([r for r in rows if r["signal"] == "ACHAT"
                       and r["secteur"] == sec and r["tier"] == tier])
            if not s:
                continue
            out["secteur_x_tier"].setdefault(sec, {})[tier] = s
            flag = "" if s["interpretable"] else "  (n<100)"
            print(f"{sec:<30} {tier:<10} {s['n']:>5} {s['hit']:>6.1f}% "
                  f"{s['a_coh']:>+8.2f}{flag}")

    os.makedirs(SORTIE, exist_ok=True)
    with open(f"{SORTIE}/resultats.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n-> {SORTIE}/resultats.json")


if __name__ == "__main__":
    main()
