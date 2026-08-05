"""
BRVM Dividend Recovery Analysis
Exécuter : python3 brvm_dividend_analysis.py
Résultat  : brvm_dividend_results.json  (à coller dans le widget)
"""

import json, os
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPA_URL = os.environ.get("SUPABASE_URL", "https://lynevvhmstpcffobwudr.supabase.co")
SUPA_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--break-system-packages", "-q"])
    import requests

H = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

def fetch(table, params=""):
    url = f"{SUPA_URL}/rest/v1/{table}?{params}"
    r = requests.get(url, headers=H)
    r.raise_for_status()
    return r.json()

print("Chargement companies...")
corps = fetch("companies", "select=id,symbol&order=symbol.asc")
comp_by_id   = {c["id"]: c["symbol"] for c in corps}
comp_by_sym  = {c["symbol"]: c["id"] for c in corps}
print(f"  {len(corps)} tickers")

print("Chargement corporate_events...")
events = fetch("corporate_events", "select=*&order=event_date.desc")
print(f"  {len(events)} événements")
if events:
    print(f"  Colonnes : {list(events[0].keys())}")
    types = list({e.get('event_type','?') for e in events})
    print(f"  Types    : {types}")

# ---------- détection dynamique des colonnes ----------
sample = events[0] if events else {}
cols = list(sample.keys())

def find_col(candidates):
    for c in candidates:
        if c in cols: return c
    return None

ticker_col = find_col(['ticker','symbol','code'])
amount_col = find_col(['amount','montant','dividende','valeur','dividend'])
type_col   = find_col(['event_type','type','categorie'])
date_col   = find_col(['event_date','ex_date','date','ex_dividend_date'])
cid_col    = find_col(['company_id'])  # fallback

print(f"\n  ticker_col={ticker_col}, amount_col={amount_col}, type_col={type_col}, date_col={date_col}, cid_col={cid_col}")

# Résoudre le ticker
def get_ticker(e):
    if ticker_col and e.get(ticker_col):
        return e[ticker_col]
    if cid_col and e.get(cid_col):
        return comp_by_id.get(e[cid_col])
    return None

div_events = [e for e in events if (e.get(type_col,'') or '').upper() in ('DIVIDENDE','DIVIDEND','DIV','D')]
print(f"\n{len(div_events)} événements dividende filtrés")

# ---------- chargement prix ----------
tickers_needed = list({get_ticker(e) for e in div_events if get_ticker(e)})
print(f"Chargement prix pour {len(tickers_needed)} tickers...")
prices = {}
for sym in tickers_needed:
    cid = comp_by_sym.get(sym)
    if not cid:
        continue
    rows = fetch("historical_data", f"select=trade_date,price&company_id=eq.{cid}&order=trade_date.asc")
    prices[sym] = {r["trade_date"]: float(r["price"]) for r in rows}
    print(f"  {sym}: {len(rows)} jours")

# ---------- analyse ----------
results = []
for ev in div_events:
    ticker  = get_ticker(ev)
    ex_date = ev.get(date_col)
    div     = float(ev.get(amount_col) or 0)
    if not ticker or not ex_date or ticker not in prices:
        continue

    sorted_dates = sorted(prices[ticker].keys())
    ex_idx = next((i for i, d in enumerate(sorted_dates) if d >= ex_date), None)
    if ex_idx is None or ex_idx < 2 or ex_idx >= len(sorted_dates) - 5:
        continue

    pre_price   = prices[ticker][sorted_dates[ex_idx - 1]]
    theo_ex_div = pre_price - div if div > 0 else pre_price * 0.96
    after_dates = sorted_dates[ex_idx: ex_idx + 120]
    after_prices = [prices[ticker][d] for d in after_dates]
    ex_price    = after_prices[0] if after_prices else None
    if not pre_price or not ex_price:
        continue

    actual_drop  = pre_price - ex_price
    overreact    = actual_drop - div if div > 0 else 0
    overreact_pct = round(overreact / div * 100, 2) if div > 0 else 0

    days_to_fill = next((i + 1 for i, p in enumerate(after_prices) if p >= pre_price), None)

    min_below, min_day = 0, 0
    for i, p in enumerate(after_prices[:30]):
        below = theo_ex_div - p
        if below > min_below:
            min_below = below
            min_day = i + 1

    results.append({
        "ticker":        ticker,
        "ex_date":       ex_date,
        "dividend":      div,
        "pre_price":     round(pre_price, 2),
        "theo_ex_div":   round(theo_ex_div, 2),
        "ex_price":      round(ex_price, 2),
        "actual_drop":   round(actual_drop, 2),
        "overreact_pct": overreact_pct,
        "days_to_fill":  days_to_fill,
        "min_day":       min_day,
        "after_prices":  [round(p, 2) for p in after_prices[:90]]
    })

print(f"\n{len(results)} événements analysés avec succès")

# ---------- export ----------
output = {
    "generated_at": datetime.now().isoformat(),
    "events": results
}
with open("brvm_dividend_results.json", "w") as f:
    json.dump(output, f, indent=2)

print("\nFichier brvm_dividend_results.json créé.")
print("Colle son contenu dans le widget Claude pour visualiser l'analyse.")

# Afficher un résumé rapide
if results:
    fills = sorted([r["days_to_fill"] for r in results if r["days_to_fill"]])
    overs = sorted([r["overreact_pct"] for r in results])
    opts  = sorted([r["min_day"] for r in results if r["min_day"]])
    med = lambda lst: lst[len(lst)//2] if lst else None
    print(f"\n=== RÉSUMÉ ===")
    print(f"N événements  : {len(results)}")
    print(f"Fill médian   : {med(fills)} jours")
    print(f"Sur-réaction  : {med(overs):.1f}% (médiane)")
    print(f"J optimal     : J+{med(opts)}")
