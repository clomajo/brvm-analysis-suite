"""E4.0 — V1 par horizon, liquidite, secteur, double benchmark.
Pre-enregistrement : EXPERIMENTS_LOG.md, commit 5305af4.
Classe A : lecture seule, aucune ecriture en base.
"""
import os, json, logging, statistics
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

HORIZONS = [10, 15, 20, 30, 45, 60]
TOLERANCE = 5
N_MIN = 100
BRVMC_ID = 48
SORTIE = "tools/experiments/E4_0"

SECTOR_MAP = {
    'BICC':'FINANCE','BOAB':'FINANCE','BOABF':'FINANCE','BOAC':'FINANCE',
    'BOAM':'FINANCE','BOAN':'FINANCE','BOAS':'FINANCE','CBIBF':'FINANCE',
    'ECOC':'FINANCE','LNBB':'FINANCE','NSBC':'FINANCE','ORGT':'FINANCE',
    'SAFC':'FINANCE','SGBC':'FINANCE','SIBC':'FINANCE',
    'PALC':'AGRO','SPHC':'AGRO','SICC':'AGRO','SOGC':'AGRO','SCRC':'AGRO',
}


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
    seances = {r["date_seance"] for r in get_all("boc_cote", "select=date_seance&est_droit=is.false")}
    log.info("seances BOC : %s", len(seances))

    sym2id = {c["symbol"]: c["id"] for c in get_all("companies", "select=id,symbol")}

    prix = {}
    for row in get_all("historical_data", "select=company_id,trade_date,price"):
        if row["price"] is not None:
            prix[(row["company_id"], row["trade_date"])] = float(row["price"])
    log.info("prix charges : %s", len(prix))

    decisions = get_all("brvm_decisions",
                        "select=id,ticker,signal,score,date,liquidity_tier"
                        "&date=gte.2026-04-09&date=lte.2026-09-04")
    decisions = [d for d in decisions if d["date"] in seances]
    log.info("decisions retenues (dates reelles) : %s", len(decisions))

    def prix_proche(cid, cible):
        best, ec = None, None
        for delta in range(-TOLERANCE, TOLERANCE + 1):
            d = (cible + timedelta(days=delta)).isoformat()
            if d not in seances:
                continue
            v = prix.get((cid, d))
            if v is not None and (ec is None or abs(delta) < ec):
                best, ec = v, abs(delta)
        return best

    resultats = {}

    for hz in HORIZONS:
        par_date = defaultdict(list)
        for d in decisions:
            cid = sym2id.get(d["ticker"])
            if not cid:
                continue
            sd = date.fromisoformat(d["date"])
            vd = sd + timedelta(days=hz)
            ps, pv = prix_proche(cid, sd), prix_proche(cid, vd)
            if ps is None or pv is None:
                continue
            bs, bv = prix_proche(BRVMC_ID, sd), prix_proche(BRVMC_ID, vd)
            if bs is None or bv is None:
                continue
            var = (pv - ps) / ps * 100
            var_idx = (bv - bs) / bs * 100
            s = d["signal"]
            ok = var > 0 if s == "ACHAT" else (var < 0 if s == "EVITER" else abs(var) < 5)
            par_date[d["date"]].append({
                "ticker": d["ticker"], "signal": s, "tier": d.get("liquidity_tier"),
                "secteur": SECTOR_MAP.get(d["ticker"], "OTHER"),
                "var": var, "ok": ok, "alpha_brvmc": var - var_idx,
            })

        lignes = []
        for lot in par_date.values():
            moy = sum(r["var"] for r in lot) / len(lot)
            for r in lot:
                r["alpha_cohorte"] = r["var"] - moy
            lignes += lot
        resultats[hz] = lignes
        log.info("J+%-3s : %s observations", hz, len(lignes))

    def agrege(lignes, cle=None):
        groupes = defaultdict(list)
        for r in lignes:
            groupes[(r["signal"],) + ((r[cle],) if cle else ())].append(r)
        out = []
        for k, g in sorted(groupes.items()):
            n = len(g)
            out.append({
                "cle": k, "n": n,
                "hit": 100 * sum(1 for r in g if r["ok"]) / n,
                "var": statistics.mean(r["var"] for r in g),
                "a_coh": statistics.mean(r["alpha_cohorte"] for r in g),
                "a_idx": statistics.mean(r["alpha_brvmc"] for r in g),
                "suffisant": n >= N_MIN,
            })
        return out

    def afficher(titre, rows):
        log.info("\n%s", titre)
        log.info("%-34s %6s %7s %8s %9s %9s", "cle", "n", "hit%", "var%", "a_coh", "a_idx")
        for r in rows:
            flag = "" if r["suffisant"] else "   [n<100 — non interpretable]"
            log.info("%-34s %6d %7.1f %8.2f %9.2f %9.2f%s",
                     " / ".join(str(x) for x in r["cle"]), r["n"], r["hit"],
                     r["var"], r["a_coh"], r["a_idx"], flag)

    log.info("\n" + "=" * 78)
    log.info("PAR HORIZON")
    log.info("=" * 78)
    for hz in HORIZONS:
        afficher(f"--- J+{hz}", agrege(resultats[hz]))

    log.info("\n" + "=" * 78)
    log.info("PAR LIQUIDITE (J+20)")
    log.info("=" * 78)
    afficher("", agrege(resultats[20], "tier"))

    log.info("\n" + "=" * 78)
    log.info("PAR SECTEUR (J+20)")
    log.info("=" * 78)
    afficher("", agrege(resultats[20], "secteur"))

    log.info("\n" + "=" * 78)
    log.info("CRITERE PRE-ENREGISTRE : alpha cohorte ACHAT > +1.18 ET hierarchie monotone")
    log.info("=" * 78)
    for hz in HORIZONS:
        a = {r["cle"][0]: r for r in agrege(resultats[hz])}
        if not all(s in a for s in ("ACHAT", "SURVEILLER", "EVITER")):
            log.info("J+%-3s : categories incompletes", hz)
            continue
        c1 = a["ACHAT"]["a_coh"] > 1.18
        mono_h = a["ACHAT"]["hit"] > a["SURVEILLER"]["hit"] > a["EVITER"]["hit"]
        mono_a = a["ACHAT"]["a_coh"] > a["SURVEILLER"]["a_coh"] > a["EVITER"]["a_coh"]
        n_ok = a["ACHAT"]["n"] >= N_MIN
        verdict = "MEILLEUR" if (c1 and mono_h and mono_a and n_ok) else "non"
        log.info("J+%-3s alpha_ACHAT=%+.2f (>1.18:%s) mono_hit:%s mono_alpha:%s n=%d -> %s",
                 hz, a["ACHAT"]["a_coh"], c1, mono_h, mono_a, a["ACHAT"]["n"], verdict)

    os.makedirs(SORTIE, exist_ok=True)
    with open(f"{SORTIE}/resultats.json", "w", encoding="utf-8") as f:
        json.dump({str(h): agrege(resultats[h]) for h in HORIZONS}, f,
                  ensure_ascii=False, indent=1, default=str)
    log.info("\nresultats -> %s/resultats.json", SORTIE)


if __name__ == "__main__":
    main()
