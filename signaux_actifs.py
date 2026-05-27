import os, statistics
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests
from dateutil import parser as dateparser
from datetime import date, timedelta

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

AUJOURD_HUI = date(2026, 5, 27)
FENETRE_JOURS = 45

WATCHLIST = {"SOGC","SPHC","BOAS","BOABF"}
WATCHLIST_ETENDUE = {"ONTBF","TTLC","SIBC","SGBC","BOAM","SMBC","CIEC","NSBC"}

PER_SECTORIEL = {
    "banque": 12.4, "agro": 10.2, "industrie": 13.2,
    "telecom": 13.3, "distribution": 16.1, "autre": 11.0,
}
SECTEURS = {
    "banque": ["BOABF","BOAS","BOAM","BOAN","SGBC","SIBC","NSBC","CABC","CBIBF","SLBC"],
    "agro": ["SOGC","SPHC","PALC","CFAC"],
    "telecom": ["ONTBF","ORAC"],
    "industrie": ["SMBC","BICC","CIEC","SCRC","SDCC","STBC","NTLC"],
    "distribution": ["ABJC","SNTS","TTLC","TTLS","LNBB"],
}
def get_secteur(t):
    for s, tickers in SECTEURS.items():
        if t in tickers: return s
    return "autre"

# Fondamentaux
r = requests.get(
    f"{SUPABASE_URL}/rest/v1/company_fundamentals"
    f"?select=ticker,fiscal_year,roe,pb_ratio,eps,pe_ratio,market_cap"
    f"&roe=not.is.null&order=ticker.asc,fiscal_year.desc",
    headers=HEADERS
)
latest = {}
for row in r.json():
    if row["ticker"] not in latest:
        latest[row["ticker"]] = row

# Ex-dates futures
r2 = requests.get(
    f"{SUPABASE_URL}/rest/v1/company_fundamentals"
    f"?select=ticker,fiscal_year,ex_dividend_date,dividend_per_share"
    f"&ex_dividend_date=not.is.null&order=ticker.asc,fiscal_year.desc",
    headers=HEADERS
)
ex_dates = {}
for row in r2.json():
    raw = row.get("ex_dividend_date")
    if not raw or raw == "n/a": continue
    try:
        d = dateparser.parse(str(raw)).date()
        if d >= AUJOURD_HUI:
            ticker = row["ticker"]
            if ticker not in ex_dates or d < ex_dates[ticker]["date"]:
                ex_dates[ticker] = {
                    "date": d,
                    "dividende": row["dividend_per_share"],
                    "fy": row["fiscal_year"]
                }
    except:
        continue

# Prix actuels
rc = requests.get(
    f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
    headers=HEADERS
)
companies = {c["id"]: c["symbol"] for c in rc.json()}
prix_actuels = {}
r3 = requests.get(
    f"{SUPABASE_URL}/rest/v1/historical_data"
    f"?select=company_id,trade_date,price&order=trade_date.desc&limit=500",
    headers=HEADERS
)
for row in r3.json():
    sym = companies.get(row["company_id"])
    if sym and sym not in prix_actuels:
        prix_actuels[sym] = row["price"]

print("=" * 75)
print(f"SIGNAUX ACTIFS — Ex-dates dans les {FENETRE_JOURS} prochains jours")
print(f"Date : {AUJOURD_HUI}")
print("=" * 75)
print(f"\n{'Ticker':<8} {'Ex-date':<12} {'J-10':<12} {'Div':>6} {'ROE':>6} {'P/B':>6} {'Decote':>8} {'Prix':>8} Statut")
print("-" * 85)

signaux = []
for ticker, ev in sorted(ex_dates.items(), key=lambda x: x[1]["date"]):
    ex_date = ev["date"]
    jours_restants = (ex_date - AUJOURD_HUI).days
    if jours_restants > FENETRE_JOURS: continue

    j_moins_10 = ex_date - timedelta(days=10)
    jours_avant_signal = (j_moins_10 - AUJOURD_HUI).days

    fund = latest.get(ticker, {})
    roe = fund.get("roe")
    pb = fund.get("pb_ratio")
    eps = fund.get("eps")
    pe = fund.get("pe_ratio")
    prix = prix_actuels.get(ticker)
    div = ev["dividende"]

    decote = None
    if eps and eps > 0 and pe and pe > 0:
        prix_calc = eps * pe
        cible = eps * PER_SECTORIEL.get(get_secteur(ticker), 11.0)
        decote = (cible - prix_calc) / prix_calc * 100

    ok_watchlist = ticker in WATCHLIST
    ok_etendue = ticker in WATCHLIST_ETENDUE
    ok_roe = roe and roe > 15
    ok_pb = pb and pb < 2.5

    if ok_watchlist and ok_roe and ok_pb:
        statut = "SIGNAL FORT"
    elif ok_watchlist or (ok_etendue and ok_roe and ok_pb):
        statut = "A SURVEILLER"
    elif jours_avant_signal <= 0 <= jours_restants:
        statut = "FENETRE ACTIVE"
    else:
        statut = "hors filtre"

    d_str = f"{decote:.0f}%" if decote else "N/A"
    div_str = f"{div:.0f}" if div else "N/A"
    roe_str = f"{roe:.1f}" if roe else "N/A"
    pb_str = f"{pb:.2f}" if pb else "N/A"
    prix_str = f"{prix:.0f}" if prix else "N/A"

    print(f"{ticker:<8} {str(ex_date):<12} {str(j_moins_10):<12} {div_str:>6} {roe_str:>6} {pb_str:>6} {d_str:>8} {prix_str:>8} {statut}")

    if statut != "hors filtre":
        signaux.append({
            "ticker": ticker, "ex_date": ex_date,
            "j_moins_10": j_moins_10,
            "jours_avant_signal": jours_avant_signal,
            "roe": roe, "pb": pb, "decote": decote,
            "prix": prix, "div": div, "statut": statut
        })

print(f"\n=== RECAP SIGNAUX ACTIFS ({len(signaux)}) ===\n")
for s in sorted(signaux, key=lambda x: x["j_moins_10"]):
    j = s["jours_avant_signal"]
    if j > 0:
        timing = f"Acheter dans {j} jours (le {s['j_moins_10']})"
    elif j == 0:
        timing = "ACHETER AUJOURD'HUI"
    else:
        timing = f"FENETRE ACTIVE — ex-date dans {(s['ex_date']-AUJOURD_HUI).days} jours"
    print(f"  {s['ticker']:<8} | {s['ex_date']} | {timing}")
    print(f"           | ROE={s['roe']} | P/B={s['pb']} | Decote={s['decote']} | Prix={s['prix']} | Div={s['div']}")
