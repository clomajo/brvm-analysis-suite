"""
backtest_dividend.py
Analyse du comportement du cours autour du détachement de dividende
Fenêtres : J-30, J-10, J0, J+10, J+30, J+60, J+90
"""

import os, statistics
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests
from dateutil import parser as dateparser

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# Dates fiables = 2023 à aujourd'hui seulement
DATE_MIN = date(2023, 1, 1)
DATE_MAX = date(2026, 5, 27)

def parse_date(s):
    if not s or s == "n/a": return None
    try:
        d = dateparser.parse(str(s)).date()
        if DATE_MIN <= d <= DATE_MAX:
            return d
        return None
    except:
        return None

def get_price_at_date(prices, target, window=15):
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta*sign)).isoformat()
            if d in prices:
                return prices[d], d
    return None, None

# Chargement prix
print("Chargement prix historiques...")
rc = requests.get(
    f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
    headers=HEADERS
)
companies = {c["id"]: c["symbol"] for c in rc.json()}

all_prices = {}
offset = 0
while True:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=company_id,trade_date,price"
        f"&order=trade_date.asc&offset={offset}&limit=1000",
        headers=HEADERS
    )
    rows = r.json()
    if not rows: break
    for row in rows:
        sym = companies.get(row["company_id"])
        if sym:
            all_prices.setdefault(sym, {})[row["trade_date"]] = row["price"]
    offset += 1000
    if len(rows) < 1000: break

print(f"  {len(all_prices)} tickers chargés")

# Chargement ex_dividend_date
r = requests.get(
    f"{SUPABASE_URL}/rest/v1/company_fundamentals"
    f"?select=ticker,fiscal_year,ex_dividend_date,dividend_per_share"
    f"&ex_dividend_date=not.is.null"
    f"&order=ex_dividend_date.desc",
    headers=HEADERS
)
evenements = []
for row in r.json():
    d = parse_date(row["ex_dividend_date"])
    if not d: continue
    ticker = row["ticker"]
    prices = all_prices.get(ticker, {})
    if not prices: continue
    evenements.append({
        "ticker": ticker,
        "fy": row["fiscal_year"],
        "ex_div": d,
        "dividende": row["dividend_per_share"],
        "prices": prices,
    })

print(f"  {len(evenements)} événements détachement fiables (2023-2026)\n")

# Calcul des performances autour du détachement
HORIZONS = {
    "J-30": -30, "J-10": -10,
    "J+10": 10, "J+30": 30,
    "J+60": 60, "J+90": 90,
}

resultats = []
for ev in evenements:
    ticker = ev["ticker"]
    ex_div = ev["ex_div"]
    prices = ev["prices"]

    # Prix au jour du détachement (J0)
    prix_j0, date_j0 = get_price_at_date(prices, ex_div)
    if not prix_j0: continue

    row = {
        "ticker": ticker,
        "fy": ev["fy"],
        "ex_div": ex_div.isoformat(),
        "dividende": ev["dividende"],
        "prix_j0": prix_j0,
        "rdt_dividende": round(ev["dividende"] / prix_j0 * 100, 2) if ev["dividende"] else None,
    }

    for label, delta in HORIZONS.items():
        target = ex_div + timedelta(days=delta)
        prix, _ = get_price_at_date(prices, target)
        if prix:
            perf = round((prix - prix_j0) / prix_j0 * 100, 2)
            row[label] = perf
        else:
            row[label] = None

    resultats.append(row)

# Analyse statistique
print("=" * 70)
print("COMPORTEMENT DU COURS AUTOUR DU DÉTACHEMENT DE DIVIDENDE")
print("=" * 70)

print(f"\n{'Horizon':<8} {'n':>4} {'Médiane':>9} {'Moyenne':>9} {'% positifs':>12} {'% >+5%':>8}")
print("-" * 55)

for label in HORIZONS.keys():
    vals = [r[label] for r in resultats if r[label] is not None]
    if not vals: continue
    med = statistics.median(vals)
    moy = statistics.mean(vals)
    pct_pos = sum(1 for v in vals if v > 0) / len(vals) * 100
    pct_5 = sum(1 for v in vals if v > 5) / len(vals) * 100
    print(f"{label:<8} {len(vals):>4} {med:>8.1f}% {moy:>8.1f}% {pct_pos:>11.0f}% {pct_5:>7.0f}%")

# Séparation avant/après
print("\n=== Avant vs Après détachement ===")
avant = [r["J-30"] for r in resultats if r.get("J-30") is not None]
apres_30 = [r["J+30"] for r in resultats if r.get("J+30") is not None]
apres_90 = [r["J+90"] for r in resultats if r.get("J+90") is not None]

print(f"  J-30 (anticipation) : médiane={statistics.median(avant):.1f}%")
print(f"  J+30 (réaction)     : médiane={statistics.median(apres_30):.1f}%")
print(f"  J+90 (tendance)     : médiane={statistics.median(apres_90):.1f}%")

# Détail par ticker
print(f"\n{'Ticker':<8} {'FY':<8} {'Ex-div':<12} {'Div':>6} {'Rdt%':>6} {'J-30':>7} {'J-10':>7} {'J+10':>7} {'J+30':>7} {'J+60':>7} {'J+90':>7}")
print("-" * 80)
for r in sorted(resultats, key=lambda x: x["ex_div"], reverse=True):
    def fmt(v): return f"{v:.1f}%" if v is not None else "N/A"
    div = f"{r['dividende']:.0f}" if r['dividende'] else "N/A"
    rdt = f"{r['rdt_dividende']:.1f}%" if r['rdt_dividende'] else "N/A"
    print(f"{r['ticker']:<8} {r['fy']:<8} {r['ex_div']:<12} {div:>6} {rdt:>6} "
          f"{fmt(r.get('J-30')):>7} {fmt(r.get('J-10')):>7} "
          f"{fmt(r.get('J+10')):>7} {fmt(r.get('J+30')):>7} "
          f"{fmt(r.get('J+60')):>7} {fmt(r.get('J+90')):>7}")

print(f"\nTotal événements analysés : {len(resultats)}")
