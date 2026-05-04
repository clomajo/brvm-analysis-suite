import os, csv
import requests
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Get BRVM30 company_id
r = requests.get(
    f"{SUPABASE_URL}/rest/v1/companies?symbol=eq.BRVM30&select=id",
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
)
company_id = r.json()[0]['id']
print(f"BRVM30 company_id: {company_id}")

# Read CSV
records = []
with open('/Users/kaylam/Downloads/grid-export.csv', 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row['Date'] and row['Cours']:
            records.append({
                'company_id': company_id,
                'trade_date': row['Date'],
                'price':      float(row['Cours']),
                'volume':     0,
                'value':      0.0
            })

print(f"Records: {len(records)}")
print(f"Date range: {records[-1]['trade_date']} → {records[0]['trade_date']}")

# Insert in batches
import json
for i in range(0, len(records), 500):
    batch = records[i:i+500]
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/historical_data",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        data=json.dumps(batch)
    )
    print(f"  Batch {i//500+1}: status {r.status_code}")

print("✅ BRVM30 loaded")
