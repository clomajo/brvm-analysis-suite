import os
import re
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def supabase_upsert(table, data):
    import json
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        data=json.dumps(data)
    )
    return r.status_code

# ── Scrape BRVM website ───────────────────────────────────────────────────────
print("Fetching BRVM index values...")
r = requests.get('https://www.brvm.org/en/cours-actions/0', verify=False, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')
text = soup.get_text()

# Extract: 409,620,23% pattern → value=409.62
def extract_index(text, start_hint):
    idx = text.find(start_hint)
    if idx < 0:
        return None
    chunk = text[idx:idx+30].replace(' ', '')
    # Match number like 409,62 or 191,90
    match = re.search(r'(\d{2,4},\d{2})', chunk)
    if match:
        return float(match.group(1).replace(',', '.'))
    return None

brvmc_val  = extract_index(text, '409')
brvm30_val = extract_index(text, 'BRVM-30')

# Fallback: search more broadly
if not brvmc_val:
    match = re.search(r'(\d{3},\d{2})0,\d+%\s*BRVM-30', text)
    if match:
        brvmc_val = float(match.group(1).replace(',', '.'))

if not brvm30_val:
    match = re.search(r'BRVM-30(\d{3},\d{2})', text)
    if match:
        brvm30_val = float(match.group(1).replace(',', '.'))

print(f"  BRVMC:  {brvmc_val}")
print(f"  BRVM30: {brvm30_val}")

today = date.today().isoformat()

# ── Get company IDs ───────────────────────────────────────────────────────────
r = requests.get(
    f"{SUPABASE_URL}/rest/v1/companies?symbol=in.(BRVMC,BRVM30)&select=id,symbol",
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
)
companies = {c['symbol']: c['id'] for c in r.json()}
print(f"  Company IDs: {companies}")

# ── Upsert into historical_data ───────────────────────────────────────────────
records = []
if brvmc_val and 'BRVMC' in companies:
    records.append({
        'company_id': companies['BRVMC'],
        'trade_date': today,
        'price':      brvmc_val,
        'volume':     0,
        'value':      0.0
    })
if brvm30_val and 'BRVM30' in companies:
    records.append({
        'company_id': companies['BRVM30'],
        'trade_date': today,
        'price':      brvm30_val,
        'volume':     0,
        'value':      0.0
    })

if records:
    status = supabase_upsert('historical_data', records)
    print(f"  Upsert status: {status}")
    print(f"✅ Index updated — BRVMC={brvmc_val}, BRVM30={brvm30_val} for {today}")
else:
    print("❌ No data to insert")
