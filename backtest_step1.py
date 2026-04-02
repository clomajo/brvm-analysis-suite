import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Load company_id → symbol map
print("Loading companies...")
res = supabase.table('companies').select('id, symbol').execute()
companies = {row['id']: row['symbol'] for row in res.data}
print(f"  {len(companies)} companies found")

# 2. Pull all historical_data in paginated batches
print("Loading historical_data (this may take a moment)...")
all_rows = []
batch_size = 1000
offset = 0

while True:
    res = (
        supabase.table('historical_data')
        .select('company_id, trade_date, price, volume, value')
        .order('trade_date')
        .range(offset, offset + batch_size - 1)
        .execute()
    )
    batch = res.data
    if not batch:
        break
    all_rows.extend(batch)
    offset += batch_size
    print(f"  Fetched {len(all_rows)} rows...", end='\r')

print(f"\n  Total rows fetched: {len(all_rows)}")

# 3. Build DataFrame
df = pd.DataFrame(all_rows)
df['symbol'] = df['company_id'].map(companies)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df = df.dropna(subset=['price', 'symbol'])
df = df.sort_values(['symbol', 'trade_date']).reset_index(drop=True)

# 4. Sanity check
print("\n── Sanity Check ──────────────────────────────────────")
print(f"  Total rows:       {len(df)}")
print(f"  Unique tickers:   {df['symbol'].nunique()}")
print(f"  Date range:       {df['trade_date'].min().date()} → {df['trade_date'].max().date()}")
print(f"  Nulls in price:   {df['price'].isna().sum()}")
print(f"  Nulls in volume:  {df['volume'].isna().sum()}")
print("\n── Sample (first 5 rows) ─────────────────────────────")
print(df.head())
print("\n── Rows per ticker (top 10) ──────────────────────────")
print(df.groupby('symbol').size().sort_values(ascending=False).head(10))
