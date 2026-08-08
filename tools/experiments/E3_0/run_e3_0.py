#!/usr/bin/env python3
"""
E3.0 - Descriptif pur-prix autour des cycles de dividende.
Tickers: SNTS, BOAC, BOAB. Classe A : lecture seule, aucune ecriture DB.
Aucun montant de dividende n'entre dans les calculs (immunise ADR-040 + asymetrie benchmark).
"""
import os, sys, csv, bisect, logging
from datetime import datetime
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("E3.0")

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not URL or not KEY:
    log.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent")
    sys.exit(1)
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
TICKERS = ["SNTS", "BOAC", "BOAB"]
TOL = 10  # jours de tolerance pour trouver une cotation

def rest_get(table, params):
    r = requests.get(f"{URL}/rest/v1/{table}", headers=HEADERS, params=params, timeout=30)
    if r.status_code >= 400:
        log.error("GET %s -> %s : %s", table, r.status_code, r.text)
        r.raise_for_status()
    return r.json()

def probe(table):
    rows = rest_get(table, {"select": "*", "limit": 1})
    cols = sorted(rows[0].keys()) if rows else []
    log.info("Colonnes %s : %s", table, cols)
    return cols

def fetch_all(table, params, page=1000):
    out, offset = [], 0
    while True:
        p = dict(params); p["limit"] = page; p["offset"] = offset
        rows = rest_get(table, p)
        out.extend(rows)
        if len(rows) < page:
            return out
        offset += page

def price_near(dates, prices, target, tol=TOL):
    i = bisect.bisect_left(dates, target)
    best = None
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(dates):
            d = abs((dates[j] - target).days)
            if d <= tol and (best is None or d < best[0]):
                best = (d, prices[j])
    return best[1] if best else None

def shift(d, n):
    return d.fromordinal(d.toordinal() + n)

def pct(a, b):
    return None if (a is None or b is None or b == 0) else round((a / b - 1) * 100, 2)

# --- 1. Schemas et resolution des tickers ---
probe("companies"); ce_cols = probe("corporate_events"); probe("historical_data")

comps = rest_get("companies", {"select": "id,symbol", "symbol": f"in.({','.join(TICKERS)})"})
if not comps:
    log.error("Aucune societe resolue pour %s", TICKERS); sys.exit(1)
log.info("Societes resolues : %s", {c["symbol"]: c["id"] for c in comps})

link = next((c for c in ("company_id", "symbol", "ticker") if c in ce_cols), None)
if link is None:
    log.error("Aucune colonne de liaison trouvee dans corporate_events"); sys.exit(1)
log.info("Colonne de liaison corporate_events : %s", link)

date_col = next((c for c in ("event_date", "date", "ex_date") if c in ce_cols), None)
type_col = next((c for c in ("event_type", "type") if c in ce_cols), None)
if not date_col or not type_col:
    log.error("Colonnes date/type introuvables dans corporate_events : %s", ce_cols); sys.exit(1)

rows_out = []
for c in comps:
    sym, cid = c["symbol"], c["id"]
    val = cid if link == "company_id" else sym

    hist = fetch_all("historical_data", {
        "select": "trade_date,price", "company_id": f"eq.{cid}", "order": "trade_date.asc"})
    series = sorted((datetime.fromisoformat(r["trade_date"][:10]).date(), float(r["price"]))
                    for r in hist if r.get("price") is not None)
    if not series:
        log.warning("%s : aucune cotation", sym); continue
    dates = [d for d, _ in series]; prices = [p for _, p in series]
    log.info("%s : %d cotations, %s -> %s", sym, len(series), dates[0], dates[-1])

    evs = fetch_all("corporate_events", {"select": "*", link: f"eq.{val}", "order": f"{date_col}.asc"})
    types = sorted({e.get(type_col) for e in evs if e.get(type_col)})
    log.info("%s : event_types presents = %s", sym, types)

    ann_type = next((t for t in types if t and ("ANNOUNC" in t.upper() or "ANNONC" in t.upper())), None)
    ann_dates = sorted(datetime.fromisoformat(e[date_col][:10]).date()
                       for e in evs if e.get(type_col) == ann_type and e.get(date_col)) if ann_type else []

    for e in evs:
        if e.get(type_col) != "EX_DIVIDEND" or not e.get(date_col):
            continue
        ex = datetime.fromisoformat(e[date_col][:10]).date()
        p_pre = price_near(dates, prices, shift(ex, -1))
        p_ex = price_near(dates, prices, ex)
        p30 = price_near(dates, prices, shift(ex, 30))
        p45 = price_near(dates, prices, shift(ex, 45))

        r = {"ticker": sym, "ex_date": ex.isoformat(),
             "decrochage_%": pct(p_ex, p_pre),
             "ex_to_30_%": pct(p30, p_ex), "ex_to_45_%": pct(p45, p_ex),
             "recup_30_vs_pre_%": pct(p30, p_pre), "recup_45_vs_pre_%": pct(p45, p_pre),
             "annonce": "", "pre45_%": "", "pre30_%": ""}

        cand = [a for a in ann_dates if 0 < (ex - a).days <= 180]
        if cand:
            a = max(cand)
            p_a = price_near(dates, prices, a)
            r.update({"annonce": a.isoformat(),
                      "pre45_%": pct(p_a, price_near(dates, prices, shift(a, -45))),
                      "pre30_%": pct(p_a, price_near(dates, prices, shift(a, -30)))})
        rows_out.append(r)

if not rows_out:
    log.error("Aucun cycle EX_DIVIDEND exploitable"); sys.exit(1)

cols = ["ticker", "ex_date", "annonce", "pre45_%", "pre30_%", "decrochage_%",
        "ex_to_30_%", "ex_to_45_%", "recup_30_vs_pre_%", "recup_45_vs_pre_%"]
out = "tools/experiments/E3_0/E3_0_resultats.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows_out)

print("\n" + " | ".join(f"{c:>18}" for c in cols))
for r in sorted(rows_out, key=lambda x: (x["ticker"], x["ex_date"])):
    print(" | ".join(f"{str(r[c]) if r[c] is not None else 'NA':>18}" for c in cols))

def med(k):
    v = sorted(x[k] for x in rows_out if isinstance(x.get(k), float))
    if not v: return "NA"
    n = len(v)
    return round(v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2, 2)

print(f"\nn cycles = {len(rows_out)}")
for k in ("decrochage_%", "ex_to_30_%", "ex_to_45_%", "recup_30_vs_pre_%", "recup_45_vs_pre_%"):
    print(f"  mediane {k:<22} = {med(k)}")
print(f"\nCSV -> {out}")
