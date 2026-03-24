#!/usr/bin/env python3
"""
Test technical analyzer for a single company - with correct Supabase syntax
"""

import os
import sys
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Testing technical analyzer for SGBC...")

# Get SGBC company_id
res = supabase.table('companies').select('id').eq('symbol', 'SGBC').execute()
if not res.data:
    print("SGBC not found!")
    sys.exit(1)

company_id = res.data[0]['id']
print(f"Company ID: {company_id}")

# Get historical data - without order first
end_date = datetime.now().date()
start_date = end_date - timedelta(days=200)

res = supabase.table('historical_data') \
    .select('trade_date, price') \
    .eq('company_id', company_id) \
    .gte('trade_date', start_date.isoformat()) \
    .lte('trade_date', end_date.isoformat()) \
    .execute()

print(f"Got {len(res.data)} rows of historical data")

if len(res.data) < 50:
    print("Not enough data!")
    sys.exit(1)

# Sort in pandas
df = pd.DataFrame(res.data)
df = df.sort_values('trade_date')
df = df.rename(columns={'price': 'close'})
df['close'] = pd.to_numeric(df['close'])

# Calculate RSI
def calculate_rsi(prices, period=14):
    deltas = prices.diff()
    gain = deltas.where(deltas > 0, 0)
    loss = -deltas.where(deltas < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

rsi = calculate_rsi(df['close'])
print(f"Calculated RSI: {rsi}")

# Get latest historical_data_id - without order
res = supabase.table('historical_data') \
    .select('id, trade_date') \
    .eq('company_id', company_id) \
    .execute()

# Sort in Python to get latest
if res.data:
    latest = max(res.data, key=lambda x: x['trade_date'])
    historical_id = latest['id']
    print(f"Latest date: {latest['trade_date']}")
    print(f"Historical ID: {historical_id}")
else:
    print("No historical data found!")
    sys.exit(1)

# Save to technical_analysis
data = {
    'historical_data_id': historical_id,
    'rsi': float(rsi),
}

try:
    supabase.table('technical_analysis').insert(data).execute()
    print("✅ Saved to technical_analysis!")
    print(f"RSI value: {rsi}")
except Exception as e:
    print(f"Error saving: {e}")
