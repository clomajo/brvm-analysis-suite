#!/usr/bin/env python3
"""
audit_gru_vs_naive.py -- Classe A, lecture seule, aucune ecriture DB.
Compare les previsions GRU (predictions_results) au comparateur naif
(persistance : prevision = dernier prix connu a run_date).

Seuils pre-enregistres, geles avant lecture :
  MASE = MAE_gru / MAE_naive
    <  0.85  -> valeur ajoutee (reduction >= 15%)
    0.85-1.0 -> marginal
    >= 1.0   -> GRU battu par la persistance
  Direction correcte : seuil 55%

Appariement strict : une ligne n'entre dans AUCUNE des deux jambes
si le baseline naif est indisponible.
"""
import os, sys, csv, logging, statistics
from datetime import date, timedelta
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
log = logging.getLogger("gru_audit")

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
if not KEY:
    log.error("Cle Supabase absente")
    sys.exit(1)
H = {"apikey": KEY, "Authorization": "Bearer " + KEY}
OUT = "tools/experiments/GRU_VERIF/resultats_gru_vs_naive.csv"

def fetch_all(table, params, page=1000):
    out, off = [], 0
    while True:
        p = dict(params); p["limit"] = page; p["offset"] = off
        r = requests.get(URL + "/rest/v1/" + table, headers=H, params=p, timeout=90)
        if r.status_code >= 400:
            log.error("%s -> %s %s", table, r.status_code, r.text)
            r.raise_for_status()
        b = r.json()
        out.extend(b)
        if len(b) < page:
            return out
        off += page

def d(s):
    return date.fromisoformat(str(s)[:10])

# 1. Verifications GRU
res = fetch_all("predictions_results",
                {"select": "prediction_id,company_id,ticker,run_date,prediction_date,"
                           "predicted_price,actual_price,direction_correct"})
log.info("predictions_results : %d lignes", len(res))

seen, rows = set(), []
for r in res:
    pid = r.get("prediction_id")
    if pid in seen:
        continue
    seen.add(pid)
    if r.get("actual_price") is None or r.get("predicted_price") is None:
        continue
    rows.append(r)
log.info("apres dedup + non-null : %d lignes", len(rows))

# 2. Mesure de l'ecart de couverture
tot = fetch_all("predictions", {"select": "id,prediction_date"})
echues = [p for p in tot if d(p["prediction_date"]) <= date.today()]
log.info("predictions totales=%d | echues=%d | verifiees=%d | non verifiees echues=%d",
         len(tot), len(echues), len(seen), len(echues) - len(seen))

# 3. Prix historiques
cids = sorted({r["company_id"] for r in rows})
lo = min(d(r["run_date"]) for r in rows) - timedelta(days=10)
hi = max(d(r["prediction_date"]) for r in rows) + timedelta(days=5)
hist = {}
for cid in cids:
    hd = fetch_all("historical_data",
                   {"select": "trade_date,price", "company_id": "eq." + str(cid),
                    "and": "(trade_date.gte.%s,trade_date.lte.%s)" % (lo.isoformat(), hi.isoformat()),
                    "order": "trade_date.asc"})
    hist[cid] = [(d(x["trade_date"]), x["price"]) for x in hd if x.get("price") is not None]
log.info("historique charge sur %d societes", len(hist))

def baseline(cid, run):
    """Dernier prix connu a run_date, fenetre 5 jours en arriere."""
    cand = [p for (t, p) in hist.get(cid, []) if run - timedelta(days=5) <= t <= run]
    return cand[-1] if cand else None

# 4. Appariement strict
paires, sans_baseline = [], 0
for r in rows:
    b = baseline(r["company_id"], d(r["run_date"]))
    if b is None:
        sans_baseline += 1
        continue
    act, pred = float(r["actual_price"]), float(r["predicted_price"])
    h = (d(r["prediction_date"]) - d(r["run_date"])).days
    paires.append({
        "ticker": r.get("ticker"), "run_date": r["run_date"],
        "prediction_date": r["prediction_date"], "horizon": h,
        "predicted": pred, "naive": float(b), "actual": act,
        "ae_gru": abs(pred - act), "ae_naive": abs(float(b) - act),
        "direction_correct": r.get("direction_correct"),
    })
log.info("paires retenues=%d | rejetees faute de baseline=%d", len(paires), sans_baseline)
if not paires:
    log.error("aucune paire exploitable")
    sys.exit(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(paires[0].keys()))
    w.writeheader()
    w.writerows(paires)

def bloc(nom, sub):
    if not sub:
        return
    g = [x["ae_gru"] for x in sub]
    n = [x["ae_naive"] for x in sub]
    mg, mn = statistics.mean(g), statistics.mean(n)
    mase = mg / mn if mn else float("inf")
    dirs = [x["direction_correct"] for x in sub if x["direction_correct"] is not None]
    dr = 100.0 * sum(1 for x in dirs if x) / len(dirs) if dirs else float("nan")
    print("%-16s n=%-5d MAE_gru=%9.2f MAE_naive=%9.2f MASE=%6.3f  med_gru=%8.2f med_naive=%8.2f  dir=%5.1f%% (n=%d)"
          % (nom, len(sub), mg, mn, mase, statistics.median(g), statistics.median(n), dr, len(dirs)))

print("=" * 118)
bloc("GLOBAL", paires)
print("-" * 118)
for lab, f in [("H = 1-3j", lambda h: 1 <= h <= 3), ("H = 4-7j", lambda h: 4 <= h <= 7),
               ("H = 8-14j", lambda h: 8 <= h <= 14), ("H = 15-30j", lambda h: 15 <= h <= 30),
               ("H > 30j", lambda h: h > 30)]:
    bloc(lab, [x for x in paires if f(x["horizon"])])
print("=" * 118)
print("Seuils geles : MASE < 0.85 valeur ajoutee | 0.85-1.0 marginal | >= 1.0 onglet ferme")
print("               direction >= 55%")
print("CSV -> " + OUT)
