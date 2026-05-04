import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import date

load_dotenv()
supabase = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)

MEDIAN_VOL = 1277  # exchange median from backtest

# ── Load companies ────────────────────────────────────────────────────────────
res = supabase.table('companies').select('id, symbol').execute()
companies = {row['id']: row['symbol'] for row in res.data}

# ── Load last 90 days of historical data ─────────────────────────────────────
print("Loading recent historical data...")
all_rows = []
offset = 0
while True:
    res = (
        supabase.table('historical_data')
        .select('company_id, trade_date, price, volume')
        .order('trade_date', desc=True)
        .range(offset, offset + 999)
        .execute()
    )
    if not res.data:
        break
    all_rows.extend(res.data)
    offset += 1000
    if offset >= 6000:  # ~90 days × 47 tickers = ~4230 rows, 6000 is safe
        break

df = pd.DataFrame(all_rows)
df['symbol']     = df['company_id'].map(companies)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df['price']      = pd.to_numeric(df['price'], errors='coerce')
df['volume']     = pd.to_numeric(df['volume'], errors='coerce')
df = df.dropna(subset=['price', 'symbol'])
df = df.sort_values(['symbol', 'trade_date']).reset_index(drop=True)
print(f"  Loaded {len(df)} rows for {df['symbol'].nunique()} tickers")

# ── Indicator functions ───────────────────────────────────────────────────────
def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = -delta.clip(upper=0).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(series, period=14):
    high = series.rolling(2).max()
    low  = series.rolling(2).min()
    return (high - low).rolling(period).mean()

def calc_macd_bull(series):
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd > signal

# ── Generate one decision per ticker ─────────────────────────────────────────
print("Generating decisions...")
decisions = []
today = date.today().isoformat()

for symbol, group in df.groupby('symbol'):
    g = group.copy().reset_index(drop=True)
    if len(g) < 55:  # need at least 55 rows for SMA50 + buffer
        print(f"  Skipping {symbol} — insufficient data ({len(g)} rows)")
        continue

    g['rsi']       = calc_rsi(g['price'])
    g['sma20']     = g['price'].rolling(20).mean()
    g['sma50']     = g['price'].rolling(50).mean()
    g['atr']       = calc_atr(g['price'])
    g['atr_pct']   = (g['atr'] / g['price'] * 100).clip(upper=20.0)
    g['vol_avg20'] = g['volume'].rolling(20).mean()
    g['vol_ratio'] = g['volume'] / g['vol_avg20'].replace(0, np.nan)
    g['macd_bull'] = calc_macd_bull(g['price'])

    row = g.dropna(subset=['rsi','sma20','sma50','atr','vol_ratio']).iloc[-1]

    is_liquid = float(row['vol_avg20']) >= MEDIAN_VOL

    # ── Composite score ───────────────────────────────────────────────────────
    rsi_score        = float(row['rsi'])
    trend_sma20      = (row['price'] - row['sma20']) / row['sma20'] * 100
    trend_sma50      = (row['price'] - row['sma50']) / row['sma50'] * 100
    trend_raw        = (trend_sma20 * 0.6) + (trend_sma50 * 0.4)
    trend_score      = float(np.clip(50 + trend_raw * 5, 0, 100))
    vol_score        = float(np.clip(row['vol_ratio'] * 50, 0, 100))
    vol_regime_score = float(np.clip(100 - (row['atr_pct'] * 10), 0, 100))

    if is_liquid:
        score = (rsi_score*0.20 + trend_score*0.40 +
                 vol_score*0.25 + vol_regime_score*0.15)
    else:
        score = (rsi_score*0.30 + trend_score*0.30 +
                 vol_score*0.10 + vol_regime_score*0.30)
    score = int(np.clip(round(score), 0, 100))

    # ── Signal ────────────────────────────────────────────────────────────────
    if is_liquid:
        signal = 'ACHAT' if score >= 65 else ('SURVEILLER' if score >= 40 else 'EVITER')
    else:
        signal = 'ACHAT' if score >= 72 else ('SURVEILLER' if score >= 45 else 'EVITER')

    # ── Confidence ────────────────────────────────────────────────────────────
    rsi_bull   = float(row['rsi']) > 50
    trend_bull = float(row['price']) > float(row['sma20'])
    macd_bull  = bool(row['macd_bull'])
    consistency = sum([rsi_bull, trend_bull, macd_bull]) / 3 * 100
    liquidity_score = min(100, float(row['vol_avg20']) / MEDIAN_VOL * 100)
    confidence = round(100*0.40 + consistency*0.40 + liquidity_score*0.20)

    if confidence >= 70:
        conf_label = 'Confiance élevée'
    elif confidence >= 40:
        conf_label = 'Confiance modérée'
    else:
        conf_label = 'Signal faible'

    # ── ATR targets ───────────────────────────────────────────────────────────
    close        = float(row['price'])
    atr_pct      = float(row['atr_pct']) / 100
    upside       = round(close * (1 + 2.5 * atr_pct), 2)
    downside     = round(close * (1 - 2.0 * atr_pct), 2)
    upside_pct   = round((upside - close) / close * 100, 1)
    downside_pct = round((close - downside) / close * 100, 1)
    risk_reward  = round(upside_pct / downside_pct, 2) if downside_pct > 0 else None

    decisions.append({
        'ticker':           symbol,
        'date':             today,
        'score':            score,
        'signal':           signal,
        'liquidity_tier':   'liquid' if is_liquid else 'illiquid',
        'confidence':       confidence,
        'confidence_label': conf_label,
        'upside_target':    upside,
        'downside_target':  downside,
        'upside_pct':       upside_pct,
        'downside_pct':     downside_pct,
        'risk_reward':      risk_reward,
        'data_completeness':'High'
    })

print(f"  {len(decisions)} decisions generated")

# ── Preview ───────────────────────────────────────────────────────────────────
preview = pd.DataFrame(decisions).sort_values('score', ascending=False)
print("\n── Top 10 ACHAT signals today ───────────────────────────")
print(preview[preview['signal']=='ACHAT'][
    ['ticker','score','signal','liquidity_tier','confidence','upside_pct','downside_pct','risk_reward']
].head(10).to_string(index=False))

print("\n── Signal breakdown ─────────────────────────────────────")
print(preview['signal'].value_counts())

# ── Insert into Supabase ──────────────────────────────────────────────────────
print("\nInserting into brvm_decisions...")
# Upsert — safe to run daily, won't duplicate
res = (
    supabase.table('brvm_decisions')
    .upsert(decisions, on_conflict='ticker,date')
    .execute()
)
print(f"✅ {len(decisions)} decisions inserted for {today}")
