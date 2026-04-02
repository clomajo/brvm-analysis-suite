import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Load data (same as step 1) ────────────────────────────────────────────────
res = supabase.table('companies').select('id, symbol').execute()
companies = {row['id']: row['symbol'] for row in res.data}

all_rows = []
offset = 0
while True:
    res = (
        supabase.table('historical_data')
        .select('company_id, trade_date, price, volume, value')
        .order('trade_date')
        .range(offset, offset + 999)
        .execute()
    )
    if not res.data:
        break
    all_rows.extend(res.data)
    offset += 1000

df = pd.DataFrame(all_rows)
df['symbol'] = df['company_id'].map(companies)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df = df.dropna(subset=['price', 'symbol'])
df = df.sort_values(['symbol', 'trade_date']).reset_index(drop=True)

# ── Indicator functions ───────────────────────────────────────────────────────
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    high = df['price'].rolling(2).max()
    low  = df['price'].rolling(2).min()
    tr   = high - low
    return tr.rolling(period).mean()

def calc_macd_signal(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd > signal  # True = bullish

# ── Compute indicators per ticker ─────────────────────────────────────────────
print("Computing indicators...")
results = []

for symbol, group in df.groupby('symbol'):
    g = group.copy().reset_index(drop=True)

    g['rsi']        = calc_rsi(g['price'])
    g['sma20']      = g['price'].rolling(20).mean()
    g['sma50']      = g['price'].rolling(50).mean()
    g['atr']        = calc_atr(g)
    g['atr_pct']    = g['atr'] / g['price'] * 100
    g['vol_avg20']  = g['volume'].rolling(20).mean()
    g['vol_ratio']  = g['volume'] / g['vol_avg20'].replace(0, np.nan)
    g['macd_bull']  = calc_macd_signal(g['price'])

    results.append(g)

df_ind = pd.concat(results).reset_index(drop=True)

# Drop rows without enough history for indicators
df_ind = df_ind.dropna(subset=['rsi', 'sma20', 'sma50', 'atr', 'vol_ratio'])
print(f"  Rows with full indicators: {len(df_ind)}")

# ── Sanity check ──────────────────────────────────────────────────────────────
print("\n── Sample indicators (SGBC, last 5 rows) ────────────────")
sample = df_ind[df_ind['symbol'] == 'SGBC'][
    ['trade_date','price','rsi','sma20','sma50','atr_pct','vol_ratio','macd_bull']
].tail(5)
print(sample.to_string(index=False))

print("\n── RSI distribution ─────────────────────────────────────")
print(df_ind['rsi'].describe().round(2))

print("\n── ATR% distribution ────────────────────────────────────")
print(df_ind['atr_pct'].describe().round(2))

# Save for next step
df_ind.to_pickle('backtest_indicators.pkl')
print("\n✅ Saved to backtest_indicators.pkl — ready for Step 3")
