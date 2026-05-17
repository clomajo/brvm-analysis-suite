import os, re, requests, urllib3, json
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def supabase_upsert(table, data):
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

print("Fetching BRVM index values...")
r = requests.get('https://www.brvm.org/en/cours-actions/0', verify=False, timeout=15)
text = BeautifulSoup(r.text, 'html.parser').get_text()

# Format: 'BRVM-C406,950,13%' / 'BRVM-30191,950,32%' / 'BRVM-PRES158,770,67%'
def extract(text, pattern):
    m = re.search(pattern, text)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None

brvmc_val  = extract(text, r'BRVM-C(\d{3,4},\d{2})')
brvm30_val = extract(text, r'BRVM-30(\d{3,4},\d{2})')

print(f"  BRVMC:  {brvmc_val}")
print(f"  BRVM30: {brvm30_val}")

today = date.today().isoformat()

r = requests.get(
    f"{SUPABASE_URL}/rest/v1/companies?symbol=in.(BRVMC,BRVM30)&select=id,symbol",
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
)
r_data = r.json()
print(f"  DEBUG - Response status: {r.status_code}")
print(f"  DEBUG - Response data: {r_data}")
if isinstance(r_data, list) and len(r_data) > 0:
    companies = {c['symbol']: c['id'] for c in r_data}
else:
    companies = {}
print(f"  Company IDs: {companies}")

records = []
if brvmc_val and 'BRVMC' in companies:
    records.append({'company_id': companies['BRVMC'], 'trade_date': today, 'price': brvmc_val, 'volume': 0, 'value': 0.0})
if brvm30_val and 'BRVM30' in companies:
    records.append({'company_id': companies['BRVM30'], 'trade_date': today, 'price': brvm30_val, 'volume': 0, 'value': 0.0})

if records:
    status = supabase_upsert('historical_data', records)
    print(f"  Upsert status: {status}")
    print(f"✅ Index updated — BRVMC={brvmc_val}, BRVM30={brvm30_val} for {today}")
else:
    print("❌ No data to insert")
