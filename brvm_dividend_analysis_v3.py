"""
BRVM Dividend Recovery Analysis v3
Joint EX_DIVIDEND (date) + DIVIDEND_HISTORY (montant) par (ticker, fiscal_year)
"""
import json, os
from collections import defaultdict
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
corps = fetch("companies", "select=id,symbol,company_name&order=symbol.asc")
comp_by_id  = {c["id"]: c["symbol"] for c in corps}
comp_by_sym = {c["symbol"]: c["id"] for c in corps}
# aussi par company_name pour matcher DIVIDEND_HISTORY
comp_by_name = {c.get("company_name","").upper(): c["symbol"] for c in corps if c.get("company_name")}
print(f"  {len(corps)} tickers")

# ---------- corporate_events ----------
print("\nChargement corporate_events...")
all_events = fetch("corporate_events", "select=*&order=event_date.asc")

by_type = defaultdict(list)
for e in all_events:
    by_type[e["event_type"]].append(e)

ex_div_list  = by_type.get("EX_DIVIDEND", [])
div_hist_list = by_type.get("DIVIDEND_HISTORY", [])
div_list     = by_type.get("DIVIDEND", [])

print(f"  EX_DIVIDEND     : {len(ex_div_list)}")
print(f"  DIVIDEND_HISTORY: {len(div_hist_list)}")
print(f"  DIVIDEND        : {len(div_list)}")

# ---------- résoudre ticker pour DIVIDEND_HISTORY ----------
def resolve_ticker(e):
    if e.get("ticker"):
        return e["ticker"]
    if e.get("company_id"):
        return comp_by_id.get(e["company_id"])
    # Tenter par company_name
    name = (e.get("company_name") or "").upper().strip()
    if name in comp_by_name:
        return comp_by_name[name]
    # Recherche partielle
    for k, v in comp_by_name.items():
        if name and name[:6] in k:
            return v
    return None

# ---------- construire index montants par (ticker, fiscal_year) ----------
# Source 1 : DIVIDEND_HISTORY (sikafinance_history) — montant en FCFA
# Source 2 : DIVIDEND (richbourse) — montant en FCFA avec yield
amount_index = {}  # (ticker, fiscal_year) -> {amount, yield_pct, source}

for e in div_hist_list + div_list:
    ticker = resolve_ticker(e)
    fy = str(e.get("fiscal_year") or "")
    amount = e.get("amount")
    if not ticker or not fy or not amount:
        continue
    key = (ticker, fy)
    # DIVIDEND (richbourse) > DIVIDEND_HISTORY (sikafinance) car plus fiable
    if key not in amount_index or e["event_type"] == "DIVIDEND":
        amount_index[key] = {
            "amount":    float(amount),
            "yield_pct": e.get("yield_pct"),
            "source":    e["event_type"]
        }

print(f"\n  Montants indexés : {len(amount_index)} (ticker, fiscal_year)")
print("  Exemples :")
for k, v in list(amount_index.items())[:8]:
    print(f"    {k} → {v}")

# ---------- construire liste finale d'événements enrichis ----------
# EX_DIVIDEND enrichi avec le montant de l'index
enriched = []
for e in ex_div_list:
    ticker = resolve_ticker(e)
    fy = str(e.get("fiscal_year") or "")
    ex_date = e.get("event_date")
    if not ticker or not ex_date:
        continue
    amt_data = amount_index.get((ticker, fy)) or amount_index.get((ticker, str(int(fy)-1) if fy.isdigit() else ""))
    enriched.append({
        "ticker":   ticker,
        "ex_date":  ex_date,
        "fy":       fy,
        "amount":   amt_data["amount"] if amt_data else 0,
        "yield_pct": amt_data["yield_pct"] if amt_data else None,
        "has_amount": amt_data is not None
    })

# Ajouter les DIVIDEND_HISTORY sans EX_DIVIDEND correspondant
# (tickers qui ont un montant mais pas de date ex-div précise)
ex_div_keys = {(e["ticker"], e["fy"]) for e in enriched}
fallback = []
for e in div_hist_list:
    ticker = resolve_ticker(e)
    fy = str(e.get("fiscal_year") or "")
    amount = e.get("amount")
    ex_date = e.get("event_date")  # date approximative (souvent 31/12)
    if not ticker or not ex_date or not amount:
        continue
    if (ticker, fy) not in ex_div_keys:
        fallback.append({
            "ticker":   ticker,
            "ex_date":  ex_date,
            "fy":       fy,
            "amount":   float(amount),
            "yield_pct": e.get("yield_pct"),
            "has_amount": True,
            "is_fallback": True
        })
        ex_div_keys.add((ticker, fy))

all_enriched = enriched + fallback
with_amount  = [e for e in all_enriched if e.get("amount", 0) > 0]
print(f"\n  Événements enrichis total : {len(all_enriched)}")
print(f"  Avec montant > 0         : {len(with_amount)}")
print("\n  Événements avec montant :")
for e in sorted(with_amount, key=lambda x: x["ex_date"], reverse=True):
    flag = " [fallback]" if e.get("is_fallback") else ""
    print(f"    {e['ticker']:8} {e['ex_date']} FY{e['fy']}  div={e['amount']:8.0f}F  yield={e['yield_pct']}%{flag}")

# ---------- chargement prix ----------
tickers_needed = list({e["ticker"] for e in with_amount} - {None})
print(f"\nChargement prix pour {len(tickers_needed)} tickers...")
prices = {}
for sym in tickers_needed:
    cid = comp_by_sym.get(sym)
    if not cid:
        continue
    rows = fetch("historical_data", f"select=trade_date,price&company_id=eq.{cid}&order=trade_date.asc")
    if rows:
        prices[sym] = {r["trade_date"]: float(r["price"]) for r in rows}

# ---------- analyse ----------
results = []
for ev in with_amount:
    ticker  = ev["ticker"]
    ex_date = ev["ex_date"]
    div     = ev["amount"]
    if ticker not in prices:
        continue

    sorted_dates = sorted(prices[ticker].keys())
    ex_idx = next((i for i, d in enumerate(sorted_dates) if d >= ex_date), None)
    if ex_idx is None or ex_idx < 3 or ex_idx >= len(sorted_dates) - 5:
        continue

    pre_price    = prices[ticker][sorted_dates[ex_idx - 1]]
    theo_ex_div  = pre_price - div
    after_dates  = sorted_dates[ex_idx: ex_idx + 120]
    after_prices = [prices[ticker][d] for d in after_dates]
    ex_price     = after_prices[0] if after_prices else None
    if not pre_price or not ex_price or theo_ex_div <= 0:
        continue

    actual_drop   = pre_price - ex_price
    overreact     = actual_drop - div
    overreact_pct = round(overreact / div * 100, 2)

    # Jours pour revenir au prix pré-ex-div (full recovery)
    days_to_fill = next((i + 1 for i, p in enumerate(after_prices) if p >= pre_price), None)

    # Jours pour revenir au prix théorique ex-div
    days_to_theo = next((i + 1 for i, p in enumerate(after_prices) if p >= theo_ex_div), None)

    # Jour où le prix est le plus bas SOUS le prix théorique ex-div (opportunité max)
    min_below, min_day = 0, 0
    for i, p in enumerate(after_prices[:30]):
        below = theo_ex_div - p
        if below > min_below:
            min_below = below
            min_day   = i + 1

    # Série de prix normalisés (base 100 = prix pré-ex-div)
    normalized = [round(p / pre_price * 100, 2) for p in after_prices[:90]]
    theo_normalized = round(theo_ex_div / pre_price * 100, 2)

    results.append({
        "ticker":          ticker,
        "ex_date":         ex_date,
        "fiscal_year":     ev["fy"],
        "dividend":        div,
        "yield_pct":       ev.get("yield_pct"),
        "pre_price":       round(pre_price, 2),
        "theo_ex_div":     round(theo_ex_div, 2),
        "theo_normalized": theo_normalized,
        "ex_price":        round(ex_price, 2),
        "actual_drop":     round(actual_drop, 2),
        "drop_vs_div_pct": round(actual_drop / div * 100, 2),
        "overreact_pct":   overreact_pct,
        "days_to_fill":    days_to_fill,
        "days_to_theo":    days_to_theo,
        "min_day":         min_day,
        "min_below_fcfa":  round(min_below, 2),
        "min_below_pct":   round(min_below / div * 100, 2) if div > 0 else 0,
        "normalized":      normalized,
        "is_fallback":     ev.get("is_fallback", False)
    })

print(f"\n{len(results)} événements analysés")

# ---------- résumé ----------
if results:
    valid = [r for r in results if r["overreact_pct"] > -200]  # exclure aberrants
    fills  = sorted([r["days_to_fill"] for r in valid if r["days_to_fill"]])
    theos  = sorted([r["days_to_theo"] for r in valid if r["days_to_theo"]])
    overs  = sorted([r["overreact_pct"] for r in valid])
    opts   = sorted([r["min_day"] for r in valid if r["min_day"]])
    med    = lambda lst: lst[len(lst)//2] if lst else None

    print(f"\n=== RÉSUMÉ ===")
    print(f"N événements analysés  : {len(results)} (dont {len(valid)} cohérents)")
    print(f"Fill médian (pré-div)  : {med(fills)} jours")
    print(f"Fill médian (théorique): {med(theos)} jours")
    print(f"Sur-réaction médiane   : {med(overs):.1f}%")
    print(f"J optimal médian       : J+{med(opts)}")

    print(f"\nDétail :")
    for r in sorted(results, key=lambda x: x["ex_date"], reverse=True):
        print(f"  {r['ticker']:8} {r['ex_date']} FY{r['fiscal_year']}  "
              f"div={r['dividend']:6.0f}F  "
              f"chute={r['actual_drop']:+6.0f}F ({r['drop_vs_div_pct']:+.0f}% du div)  "
              f"overreact={r['overreact_pct']:+6.1f}%  "
              f"fill={str(r['days_to_fill'])+'j' if r['days_to_fill'] else 'non':6}  "
              f"theo_fill={str(r['days_to_theo'])+'j' if r['days_to_theo'] else 'non':6}  "
              f"opt=J+{r['min_day']}")

# ---------- export ----------
output = {"generated_at": datetime.now().isoformat(), "events": results}
with open("brvm_dividend_results.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nFichier brvm_dividend_results.json créé ({len(results)} événements).")
