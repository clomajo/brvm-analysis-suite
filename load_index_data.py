import os
import openpyxl
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

load_dotenv()
s = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)

# ── 1. Add BRVMC to companies ─────────────────────────────────────────────────
print("Adding index tickers to companies...")
res = s.table('companies').upsert([
    {'id': 48, 'symbol': 'BRVMC',  'name': 'BRVM Composite Index'},
    {'id': 49, 'symbol': 'BRVM30', 'name': 'BRVM 30 Index'},
], on_conflict='id').execute()
print(f"  Done: {[(r['id'], r['symbol']) for r in res.data]}")

# ── 2. Load BRVMC historical data from Excel ──────────────────────────────────
print("Loading BRVMC data from Excel...")
wb = openpyxl.load_workbook('/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx')
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
print(f"  Columns: {rows[0]}")
print(f"  Total rows: {len(rows)-1}")
print(f"  Sample: {rows[1]}")

# Columns: Company, Date, Open, High, Low, Close, Volume
records = []
for row in rows[1:]:
    company, date, open_, high, low, close, volume = row
    if not date or not close:
        continue
    # Parse date
    if isinstance(date, str):
        try:
            trade_date = datetime.strptime(date, '%Y-%m-%d').date().isoformat()
        except:
            continue
    else:
        trade_date = date.isoformat() if hasattr(date, 'isoformat') else str(date)

    records.append({
        'company_id': 48,  # BRVMC
        'trade_date': trade_date,
        'price':      float(close),
        'volume':     int(volume) if volume else 0,
        'value':      0.0
    })

print(f"  Valid records: {len(records)}")
print(f"  Date range: {records[-1]['trade_date']} → {records[0]['trade_date']}")

# ── 3. Insert in batches ──────────────────────────────────────────────────────
print("Inserting into historical_data...")
batch_size = 500
for i in range(0, len(records), batch_size):
    batch = records[i:i+batch_size]
    s.table('historical_data').upsert(
        batch, on_conflict='company_id,trade_date'
    ).execute()
    print(f"  Inserted {min(i+batch_size, len(records))}/{len(records)}")

print(f"✅ BRVMC data loaded — {len(records)} rows")
