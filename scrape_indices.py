#!/usr/bin/env python3
"""
scrape_indices.py — Scrape BRVMC et BRVM30 depuis bulletin officiel BRVM
"""
import os, requests, logging, re
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
BULLETIN_URL = "https://www.brvm.org/en/marche/bulletin-officiel-de-la-cote"

def get_company_id(symbol):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/companies?symbol=eq.{symbol}&select=id", headers=HEADERS)
    rows = r.json()
    return rows[0]['id'] if rows else None

def already_exists(company_id, date):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/historical_data?company_id=eq.{company_id}&trade_date=eq.{date}&select=id", headers=HEADERS)
    return len(r.json()) > 0

def save_price(company_id, date, price, exists):
    data = {"price": price, "open_price": price, "high_price": price, "low_price": price}
    if exists:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/historical_data?company_id=eq.{company_id}&trade_date=eq.{date}",
            headers={**HEADERS, "Prefer": "return=minimal"}, json=data
        )
    else:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/historical_data",
            headers={**HEADERS, "Prefer": "return=minimal"},
            json={**data, "company_id": company_id, "trade_date": date, "volume": 0, "value": 0}
        )
    return r.status_code in [200, 201, 204]

def scrape_indices():
    today = datetime.now().date().isoformat()
    r = requests.get(BULLETIN_URL, timeout=30, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    mapping = {'BRVM-C': 'BRVMC', 'BRVM-30': 'BRVM30'}
    
    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            label = tds[0].get_text(strip=True)
            if label in mapping:
                symbol = mapping[label]
                # La valeur est dans le texte du tr : ex "BRVM-C402,590,15%"
                full_text = tr.get_text(strip=True).replace(label, '')
                # Extraire premier nombre : 402,59
                nums = re.findall(r'\d+[,\.]\d+', full_text)
                if nums:
                    try:
                        price = float(nums[0].replace(',', '.'))
                        company_id = get_company_id(symbol)
                        if not company_id:
                            logging.warning(f"❌ {symbol}: company_id introuvable")
                            continue
                        exists = already_exists(company_id, today)
                        if save_price(company_id, today, price, exists):
                            action = "mis à jour" if exists else "inséré"
                            logging.info(f"✅ {symbol}: {price} {action} pour {today}")
                    except Exception as e:
                        logging.error(f"❌ {symbol}: {e}")

if __name__ == '__main__':
    scrape_indices()
