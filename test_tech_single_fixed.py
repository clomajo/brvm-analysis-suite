#!/usr/bin/env python3
"""
Test technical analyzer for a single company
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

# Get historical data
end_date = datetime.now().date()
start_date = end_date - timedelta(days=200)

res = supabase.table('historical_data') \
    .select('trade_date, price') \
    .eq('company_id', company_id) \
    .gte('trade_date', start_date.isoformat()) \
    .lte('trade_date', end_date.isoformat()) \
    .order('trade_date', asc=True) \
    .execute()

print(f"Got {len(res.data)} rows of historical data")

if len(res.data) < 50:
    print("Not enough data!")
    sys.exit(1)

# Create DataFrame
df = pd.DataFrame(res.data)
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

# Get latest historical_data_id
res = supabase.table('historical_data') \
    .select('id') \
    .eq('company_id', company_id) \
    .order('trade_date', asc=False) \
    .limit(1) \
    .execute()

historical_id = res.data[0]['id']
print(f"Historical ID: {historical_id}")

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
