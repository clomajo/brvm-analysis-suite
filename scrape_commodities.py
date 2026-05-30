#!/usr/bin/env python3
"""
scrape_commodities.py — Fetch prix commodités via Yahoo Finance → Supabase
Commodités: cocoa, palm oil, rubber, cotton, gold, crude oil, USD/XOF
"""
import os, requests, logging, json
from datetime import datetime, timedelta
import urllib3
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Mapping commodity_id → Yahoo Finance ticker
COMMODITIES = {
    "cocoa":   {"yahoo": "CC=F",  "name": "Cocoa"},
    "cotton":  {"yahoo": "CT=F",  "name": "Cotton"},
    "gold":    {"yahoo": "GC=F",  "name": "Gold"},
    "crude":   {"yahoo": "CL=F",  "name": "Crude Oil"},
    "usdxof":  {"yahoo": "XOFUSD=X", "name": "USD/XOF"},
}

def fetch_yahoo(symbol, days=365):
    """Fetch historical data depuis Yahoo Finance"""
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=days)).timestamp())
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": start,
        "period2": end,
        "interval": "1d",
        "includePrePost": "false"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            logging.warning(f"   ⚠️ Yahoo {symbol}: HTTP {r.status_code}")
            return []
        
        data = r.json()
        result = data.get('chart', {}).get('result', [])
        if not result:
            logging.warning(f"   ⚠️ Yahoo {symbol}: pas de données")
            return []
        
        timestamps = result[0].get('timestamp', [])
        closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
        
        rows = []
        for ts, price in zip(timestamps, closes):
            if price is None:
                continue
            date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            rows.append({"date": date, "price": round(float(price), 4)})
        
        return rows
    except Exception as e:
        logging.error(f"   ❌ Yahoo {symbol}: {e}")
        return []

def upsert_prices(commodity_id, rows):
    """Upsert dans Supabase"""
    if not rows:
        return 0
    
    data = [
        {
            "commodity_id": commodity_id,
            "trade_date": r["date"],
            "price": r["price"]
        }
        for r in rows
    ]
    
    # Batch par 100
    inserted = 0
    for i in range(0, len(data), 100):
        batch = data[i:i+100]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/commodity_prices?on_conflict=commodity_id,trade_date",
            headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
            json=batch
        )
        if r.status_code in [200, 201]:
            inserted += len(batch)
        else:
            logging.error(f"   ❌ Upsert erreur: {r.status_code} {r.text[:100]}")
    
    return inserted

def main():
    logging.info("="*60)
    logging.info("📦 COMMODITÉS — Fetch Yahoo Finance → Supabase")
    logging.info("="*60)
    
    # USD/XOF via Open Exchange Rates ou fallback fixe
    # Yahoo Finance ne couvre pas bien XOF
    # On utilise EURUSD + taux fixe EUR/XOF = 655.957
    
    total = 0
    for commodity_id, cfg in COMMODITIES.items():
        logging.info(f"📈 {cfg['name']} ({cfg['yahoo']})...")
        
        if commodity_id == "usdxof":
            # Calculer USD/XOF via EUR/USD
            rows_eurusd = fetch_yahoo("EURUSD=X", days=365)
            if rows_eurusd:
                # USD/XOF = EUR/XOF / EUR/USD = 655.957 / EURUSD
                rows = [{"date": r["date"], "price": round(655.957 / r["price"], 2)} for r in rows_eurusd if r["price"] > 0]
                logging.info(f"   📊 {len(rows)} jours via EUR/USD × 655.957")
            else:
                rows = []
        else:
            rows = fetch_yahoo(cfg["yahoo"], days=365)
        
        if rows:
            n = upsert_prices(commodity_id, rows)
            logging.info(f"   ✅ {n} prix insérés/mis à jour")
            total += n
        else:
            logging.warning(f"   ⚠️ Aucune donnée pour {commodity_id}")
    
    logging.info(f"\n✅ TOTAL: {total} prix insérés")

if __name__ == '__main__':
    main()
