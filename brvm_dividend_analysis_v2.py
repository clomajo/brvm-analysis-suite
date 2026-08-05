"""
BRVM Dividend Recovery Analysis v2
Exécuter : python3 brvm_dividend_analysis_v2.py
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

# ---------- companies ----------
print("Chargement companies...")
corps = fetch("companies", "select=id,symbol&order=symbol.asc")
comp_by_id  = {c["id"]: c["symbol"] for c in corps}
comp_by_sym = {c["symbol"]: c["id"] for c in corps}
print(f"  {len(corps)} tickers")

# ---------- corporate_events — TOUS les types dividende ----------
print("\nChargement corporate_events...")
# On prend EX_DIVIDEND en priorité (= date réelle ex-div)
# + DIVIDEND_HISTORY comme fallback
all_events = fetch("corporate_events", "select=*&order=event_date.desc")
print(f"  {len(all_events)} événements total")

# Répartition par type
from collections import defaultdict
by_type = defaultdict(list)
for e in all_events:
    by_type[e['event_type']].append(e)
for t, evs in sorted(by_type.items()):
    print(f"  {t}: {len(evs)} événements — ex: amount={evs[0].get('amount')}, yield={evs[0].get('yield_pct')}, date={evs[0].get('event_date')}")

# ---------- stratégie de sélection ----------
# EX_DIVIDEND = date ex-div officielle → priorité absolue
# DIVIDEND_HISTORY = historique → fallback si pas de EX_DIVIDEND pour ce ticker/année
ex_div_events = by_type.get('EX_DIVIDEND', [])
div_hist      = by_type.get('DIVIDEND_HISTORY', [])

print(f"\n  EX_DIVIDEND : {len(ex_div_events)}")
print(f"  DIVIDEND_HISTORY : {len(div_hist)}")
print(f"\n  Échantillon EX_DIVIDEND:")
for e in ex_div_events[:3]:
    print(f"    {e}")
print(f"\n  Échantillon DIVIDEND_HISTORY:")
for e in div_hist[:3]:
    print(f"    {e}")

# ---------- fusion : EX_DIVIDEND + DIVIDEND_HISTORY ----------
# Clé de déduplication : (ticker, fiscal_year)
selected = {}
for e in ex_div_events + div_hist:
    ticker = e.get('ticker') or comp_by_id.get(e.get('company_id'))
    year   = e.get('fiscal_year') or (e.get('event_date','')[:4])
    key    = (ticker, year)
    # EX_DIVIDEND gagne toujours sur DIVIDEND_HISTORY
    if key not in selected or e['event_type'] == 'EX_DIVIDEND':
        selected[key] = e

div_events = list(selected.values())
print(f"\n{len(div_events)} événements dividende retenus après déduplication")

# ---------- résoudre le montant ----------
# amount peut être en FCFA absolu ou en % selon la source
# On détecte : si amount < 20 pour un prix > 500, c'est probablement un yield %
# On utilise yield_pct si disponible, sinon amount
def resolve_dividend(e, pre_price):
    amount = e.get('amount')
    yield_pct = e.get('yield_pct')
    if amount and float(amount) > 0:
        # Si amount < 5% du prix → c'est probablement en FCFA et raisonnable
        # Si amount > 50% du prix → incohérent, utiliser yield_pct
        a = float(amount)
        if pre_price and a > pre_price * 0.5:
            # amount semble être en % ou incohérent
            if yield_pct:
                return round(pre_price * float(yield_pct) / 100, 2)
            return 0
        return a
    if yield_pct and pre_price:
        return round(pre_price * float(yield_pct) / 100, 2)
    return 0

# ---------- chargement prix ----------
tickers_needed = list({e.get('ticker') or comp_by_id.get(e.get('company_id')) for e in div_events} - {None})
print(f"\nChargement prix pour {len(tickers_needed)} tickers...")
prices = {}
for sym in tickers_needed:
    cid = comp_by_sym.get(sym)
    if not cid:
        continue
    rows = fetch("historical_data", f"select=trade_date,price&company_id=eq.{cid}&order=trade_date.asc")
    if rows:
        prices[sym] = {r["trade_date"]: float(r["price"]) for r in rows}
        print(f"  {sym}: {len(rows)} jours de prix")

# ---------- analyse ----------
results = []
skipped = []
for ev in div_events:
    ticker  = ev.get('ticker') or comp_by_id.get(ev.get('company_id'))
    ex_date = ev.get('event_date')
    if not ticker or not ex_date or ticker not in prices:
        skipped.append(f"{ticker} / {ex_date}: pas de prix")
        continue

    sorted_dates = sorted(prices[ticker].keys())
    # Trouver l'index de la date ex-div dans l'historique
    ex_idx = next((i for i, d in enumerate(sorted_dates) if d >= ex_date), None)
    if ex_idx is None or ex_idx < 3 or ex_idx >= len(sorted_dates) - 5:
        skipped.append(f"{ticker} / {ex_date}: ex_idx hors bornes ({ex_idx})")
        continue

    pre_price = prices[ticker][sorted_dates[ex_idx - 1]]
    div = resolve_dividend(ev, pre_price)

    theo_ex_div = pre_price - div if div > 0 else pre_price
    after_dates  = sorted_dates[ex_idx: ex_idx + 120]
    after_prices = [prices[ticker][d] for d in after_dates]
    ex_price     = after_prices[0] if after_prices else None
    if not pre_price or not ex_price:
        skipped.append(f"{ticker} / {ex_date}: prix manquant")
        continue

    actual_drop   = pre_price - ex_price
    overreact     = actual_drop - div if div > 0 else 0
    overreact_pct = round(overreact / div * 100, 2) if div > 0 else 0

    days_to_fill = next((i + 1 for i, p in enumerate(after_prices) if p >= pre_price), None)

    # Jour où le prix est le plus bas sous le prix théorique ex-div
    min_below, min_day = 0, 0
    for i, p in enumerate(after_prices[:30]):
        below = theo_ex_div - p
        if below > min_below:
            min_below = below
            min_day   = i + 1

    results.append({
        "ticker":        ticker,
        "ex_date":       ex_date,
        "fiscal_year":   ev.get('fiscal_year'),
        "event_type":    ev.get('event_type'),
        "dividend":      div,
        "yield_pct":     ev.get('yield_pct'),
        "pre_price":     round(pre_price, 2),
        "theo_ex_div":   round(theo_ex_div, 2),
        "ex_price":      round(ex_price, 2),
        "actual_drop":   round(actual_drop, 2),
        "overreact_pct": overreact_pct,
        "days_to_fill":  days_to_fill,
        "min_day":       min_day,
        "min_below_fcfa": round(min_below, 2),
        "after_prices":  [round(p, 2) for p in after_prices[:90]]
    })

print(f"\n{len(results)} événements analysés | {len(skipped)} ignorés")
for s in skipped[:10]:
    print(f"  SKIP: {s}")

# ---------- résumé ----------
if results:
    fills = sorted([r["days_to_fill"] for r in results if r["days_to_fill"]])
    overs = sorted([r["overreact_pct"] for r in results])
    opts  = sorted([r["min_day"] for r in results if r["min_day"]])
    med   = lambda lst: lst[len(lst)//2] if lst else None
    print(f"\n=== RÉSUMÉ ===")
    print(f"N événements  : {len(results)}")
    print(f"Fill médian   : {med(fills)} jours")
    print(f"Sur-réaction  : {med(overs):.1f}% (médiane)")
    print(f"J optimal     : J+{med(opts)}")
    print(f"\nDétail par événement :")
    for r in sorted(results, key=lambda x: x['ex_date'], reverse=True):
        print(f"  {r['ticker']:8} {r['ex_date']} div={r['dividend']:8.0f}F  overreact={r['overreact_pct']:+6.1f}%  fill={str(r['days_to_fill'])+'j' if r['days_to_fill'] else 'non':6}  opt=J+{r['min_day']}")

# ---------- export JSON ----------
output = {"generated_at": datetime.now().isoformat(), "events": results}
with open("brvm_dividend_results.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nFichier brvm_dividend_results.json créé — colle son contenu à Claude.")
