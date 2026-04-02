import pandas as pd
import numpy as np

# ── Load indicators from Step 2 ───────────────────────────────────────────────
df = pd.read_pickle('backtest_indicators.pkl')
print(f"Loaded {len(df)} rows")

# ── Cap ATR% outliers ─────────────────────────────────────────────────────────
df['atr_pct'] = df['atr_pct'].clip(upper=20.0)

# ── Composite score function (Phase 0 formula) ────────────────────────────────
def composite_score(row):
    # Component 1: RSI momentum (20%)
    rsi_score = float(row['rsi'])

    # Component 2: Trend strength (25%)
    trend_sma20 = (row['price'] - row['sma20']) / row['sma20'] * 100
    trend_sma50 = (row['price'] - row['sma50']) / row['sma50'] * 100
    trend_raw   = (trend_sma20 * 0.6) + (trend_sma50 * 0.4)
    trend_score = float(np.clip(50 + trend_raw * 5, 0, 100))

    # Component 3: Volume confirmation (15%)
    vol_score = float(np.clip(row['vol_ratio'] * 50, 0, 100))

    # Component 4: Volatility regime (15%) — lower ATR% = more stable = higher score
    vol_regime_score = float(np.clip(100 - (row['atr_pct'] * 10), 0, 100))

    # Component 5: No fundamentals in historical data → redistribute weight
    # Trend gets +10%, Volume gets +5% (as per Phase 0 decision)
    score = (
        rsi_score        * 0.20 +
        trend_score      * 0.35 +
        vol_score        * 0.20 +
        vol_regime_score * 0.25
    )
    return round(float(np.clip(score, 0, 100)))

# ── Apply score ───────────────────────────────────────────────────────────────
print("Computing composite scores...")
df['score'] = df.apply(composite_score, axis=1)

# ── Signal thresholds ─────────────────────────────────────────────────────────
def signal(score):
    if score >= 65:
        return 'ACHAT'
    elif score >= 40:
        return 'SURVEILLER'
    else:
        return 'EVITER'

df['signal'] = df['score'].apply(signal)

# ── Confidence score ──────────────────────────────────────────────────────────
exchange_median_vol = df['vol_avg20'].median()

def confidence_score(row):
    # Signal consistency: RSI, MACD, trend all agree?
    rsi_bull   = row['rsi'] > 50
    trend_bull = row['price'] > row['sma20']
    macd_bull  = bool(row['macd_bull'])
    agreement  = sum([rsi_bull, trend_bull, macd_bull]) / 3
    signal_consistency = agreement * 100

    # Volume liquidity vs exchange median
    liquidity = min(100, (row['vol_avg20'] / exchange_median_vol) * 100)

    # Data quality: we have full data for all rows at this point = 100%
    data_quality = 100.0

    confidence = (
        data_quality       * 0.40 +
        signal_consistency * 0.40 +
        liquidity          * 0.20
    )
    return round(float(confidence))

print("Computing confidence scores...")
df['confidence'] = df.apply(confidence_score, axis=1)

# ── ATR targets ───────────────────────────────────────────────────────────────
df['upside_target']   = (df['price'] * (1 + 2.5 * df['atr_pct'] / 100)).round(2)
df['downside_target'] = (df['price'] * (1 - 2.0 * df['atr_pct'] / 100)).round(2)
df['upside_pct']      = ((df['upside_target']   - df['price']) / df['price'] * 100).round(1)
df['downside_pct']    = ((df['price'] - df['downside_target']) / df['price'] * 100).round(1)
df['risk_reward']     = (df['upside_pct'] / df['downside_pct'].replace(0, np.nan)).round(2)

# ── Sanity check ──────────────────────────────────────────────────────────────
print("\n── Score distribution ───────────────────────────────────")
print(df['score'].describe().round(2))

print("\n── Signal breakdown ─────────────────────────────────────")
print(df['signal'].value_counts())

print("\n── Confidence distribution ──────────────────────────────")
print(df['confidence'].describe().round(2))

print("\n── Sample (SGBC last 5) ─────────────────────────────────")
sample = df[df['symbol'] == 'SGBC'][
    ['trade_date','price','score','signal','confidence','upside_pct','downside_pct','risk_reward']
].tail(5)
print(sample.to_string(index=False))

# Save for Step 4
df.to_pickle('backtest_scored.pkl')
print("\n✅ Saved to backtest_scored.pkl — ready for Step 4")
