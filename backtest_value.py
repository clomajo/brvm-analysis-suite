"""
backtest_value.py
Backtest de la stratégie value (décote vs valeur intrinsèque) sur la BRVM
Période : FY2021-FY2024
Hypothèse : un titre décoté vs PER sectoriel médian surperforme à J+60/J+90
"""

import os, statistics
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# PER médians empiriques calculés
PER_SECTORIEL = {
    "banque": 12.4,
    "agro": 10.2,
    "industrie": 13.2,
    "telecom": 13.3,
    "distribution": 16.1,
    "autre": 11.0,
}

SECTEURS = {
    "banque": ["BOAB","BOABF","BOAC","BOAM","BOAN","BOAS","BNBC","CBIBF",
               "NSBC","SGBC","SIBC","SICC","SLBC","UNLC","CABC"],
    "agro":   ["PALC","SOGC","SPHC","SAFC","CFAC"],
    "industrie": ["SMBC","STAC","STBC","BICC","CIEC","ECOC","SIVC",
                  "SEMC","SHEC","SCRC","SDCC","SDSC","UNXC"],
    "telecom": ["ONTBF","ORAC","ORGT"],
    "distribution": ["ABJC","ETIT","FTSC","LNBB","NEIC","NTLC",
                     "PRSC","SNTS","SOGC","TTLC","TTLS"],
}

# Tickers exclus — EPS non représentatif
EXCLUSIONS = {"NTLC", "BOAN", "BNBC", "SICC", "UNLC", "ETIT", "FTSC", "CFAC", "SIVC"}

def get_secteur(ticker):
    for s, tickers in SECTEURS.items():
        if ticker in tickers:
            return s
    return "autre"

def fetch_all_prices():
    """Récupère tous les prix historiques."""
    print("Chargement des prix historiques...")
    all_prices = {}
    
    # Mapping company_id → symbol
    rc = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    companies = {c["id"]: c["symbol"] for c in rc.json()}
    
    # Prix par batch
    offset = 0
    batch = 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/historical_data"
            f"?select=company_id,trade_date,price"
            f"&order=trade_date.asc"
            f"&offset={offset}&limit={batch}",
            headers=HEADERS
        )
        rows = r.json()
        if not rows:
            break
        for row in rows:
            symbol = companies.get(row["company_id"])
            if symbol:
                all_prices.setdefault(symbol, {})[row["trade_date"]] = row["price"]
        offset += batch
        if len(rows) < batch:
            break
    
    print(f"  {len(all_prices)} tickers chargés")
    return all_prices

def fetch_fundamentals_history():
    """Récupère EPS historique par ticker et année fiscale."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,fiscal_year,eps,pe_ratio"
        f"&eps=not.is.null"
        f"&order=ticker.asc,fiscal_year.asc",
        headers=HEADERS
    )
    data = r.json()
    result = {}
    for row in data:
        t = row["ticker"]
        fy = row["fiscal_year"]  # ex: FY2023
        if t not in EXCLUSIONS and row["eps"] and row["eps"] > 0:
            result.setdefault(t, {})[fy] = row["eps"]
    return result

def get_price_at_date(prices_dict, target_date_str, window=10):
    """Trouve le prix le plus proche d'une date donnée (±window jours)."""
    target = date.fromisoformat(target_date_str)
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta*sign)).isoformat()
            if d in prices_dict:
                return prices_dict[d], d
    return None, None

def run():
    all_prices = fetch_all_prices()
    fundamentals = fetch_fundamentals_history()
    
    # Dates de signal : fin de chaque année fiscale
    # FY2021 → signal au 31/12/2021, mesure J+60 et J+90
    fy_dates = {
        "FY2021": "2022-01-31",  # publication typique ~1 mois après clôture
        "FY2022": "2023-01-31",
        "FY2023": "2024-01-31",
        "FY2024": "2025-01-31",
    }

    resultats = []
    
    print("\nCalcul des signaux et performances...\n")
    
    for ticker, fy_eps in sorted(fundamentals.items()):
        prices = all_prices.get(ticker, {})
        if not prices:
            continue
        
        secteur = get_secteur(ticker)
        per_ref = PER_SECTORIEL.get(secteur, 11.0)
        
        for fy, eps in fy_eps.items():
            signal_date = fy_dates.get(fy)
            if not signal_date:
                continue
            
            # Prix au moment du signal
            prix_signal, date_reel = get_price_at_date(prices, signal_date)
            if not prix_signal:
                continue
            
            # Cours cible et décote
            cours_cible = eps * per_ref
            decote_pct = (cours_cible - prix_signal) / prix_signal * 100
            
            # Performance à J+60 et J+90
            date_j60 = (date.fromisoformat(signal_date) + timedelta(days=60)).isoformat()
            date_j90 = (date.fromisoformat(signal_date) + timedelta(days=90)).isoformat()
            
            prix_j60, _ = get_price_at_date(prices, date_j60)
            prix_j90, _ = get_price_at_date(prices, date_j90)
            
            perf_j60 = (prix_j60 - prix_signal) / prix_signal * 100 if prix_j60 else None
            perf_j90 = (prix_j90 - prix_signal) / prix_signal * 100 if prix_j90 else None
            
            signal = "ACHAT" if decote_pct > 15 else "VENTE" if decote_pct < -15 else "NEUTRE"
            
            resultats.append({
                "ticker": ticker,
                "secteur": secteur,
                "fy": fy,
                "eps": eps,
                "cours_cible": round(cours_cible, 0),
                "prix_signal": prix_signal,
                "decote_pct": round(decote_pct, 1),
                "signal": signal,
                "perf_j60": round(perf_j60, 1) if perf_j60 is not None else None,
                "perf_j90": round(perf_j90, 1) if perf_j90 is not None else None,
            })

    # Analyse par groupe signal
    print("=" * 60)
    print("RÉSULTATS BACKTEST VALUE — BRVM FY2021-FY2024")
    print("=" * 60)
    
    for signal in ["ACHAT", "NEUTRE", "VENTE"]:
        groupe = [r for r in resultats if r["signal"] == signal]
        j60 = [r["perf_j60"] for r in groupe if r["perf_j60"] is not None]
        j90 = [r["perf_j90"] for r in groupe if r["perf_j90"] is not None]
        
        if not j60:
            continue
            
        print(f"\n{signal} (n={len(groupe)}) :")
        print(f"  J+60 : médiane={round(statistics.median(j60),1)}% | moyenne={round(statistics.mean(j60),1)}% | positifs={sum(1 for x in j60 if x>0)}/{len(j60)}")
        if j90:
            print(f"  J+90 : médiane={round(statistics.median(j90),1)}% | moyenne={round(statistics.mean(j90),1)}% | positifs={sum(1 for x in j90 if x>0)}/{len(j90)}")

    # Détail par ticker
    print(f"\n{'Ticker':<8} {'FY':<7} {'Décote':>8} {'Signal':<8} {'J+60':>7} {'J+90':>7}")
    print("-" * 55)
    for r in sorted(resultats, key=lambda x: x["decote_pct"], reverse=True):
        j60 = f"{r['perf_j60']}%" if r['perf_j60'] is not None else "N/A"
        j90 = f"{r['perf_j90']}%" if r['perf_j90'] is not None else "N/A"
        flag = "🟢" if r["signal"]=="ACHAT" else "🔴" if r["signal"]=="VENTE" else "⚪"
        print(f"{flag} {r['ticker']:<6} {r['fy']:<7} {r['decote_pct']:>7}% {r['signal']:<8} {j60:>7} {j90:>7}")

    print(f"\nTotal signaux analysés : {len(resultats)}")

if __name__ == "__main__":
    run()
