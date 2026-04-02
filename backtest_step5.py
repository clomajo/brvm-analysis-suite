import pandas as pd
import numpy as np

df = pd.read_pickle('backtest_final.pkl')
MEDIAN_VOL = df['vol_avg20'].median()
print(f"Liquidity threshold: {MEDIAN_VOL:,.0f} shares/day")

# ── Sub-model definitions ─────────────────────────────────────────────────────
def score_liquid(row):
    rsi_score        = float(row['rsi'])
    trend_sma20      = (row['price'] - row['sma20']) / row['sma20'] * 100
    trend_sma50      = (row['price'] - row['sma50']) / row['sma50'] * 100
    trend_raw        = (trend_sma20 * 0.6) + (trend_sma50 * 0.4)
    trend_score      = float(np.clip(50 + trend_raw * 5, 0, 100))
    vol_score        = float(np.clip(row['vol_ratio'] * 50, 0, 100))
    vol_regime_score = float(np.clip(100 - (row['atr_pct'] * 10), 0, 100))

    # Liquid: trust trend + volume more
    score = (
        rsi_score        * 0.20 +
        trend_score      * 0.40 +
        vol_score        * 0.25 +
        vol_regime_score * 0.15
    )
    return round(float(np.clip(score, 0, 100)))

def score_illiquid(row):
    rsi_score        = float(row['rsi'])
    trend_sma20      = (row['price'] - row['sma20']) / row['sma20'] * 100
    trend_sma50      = (row['price'] - row['sma50']) / row['sma50'] * 100
    trend_raw        = (trend_sma20 * 0.6) + (trend_sma50 * 0.4)
    trend_score      = float(np.clip(50 + trend_raw * 5, 0, 100))
    vol_score        = float(np.clip(row['vol_ratio'] * 50, 0, 100))
    vol_regime_score = float(np.clip(100 - (row['atr_pct'] * 10), 0, 100))

    # Illiquid: trust stability + RSI more, volume less
    score = (
        rsi_score        * 0.30 +
        trend_score      * 0.30 +
        vol_score        * 0.10 +
        vol_regime_score * 0.30
    )
    return round(float(np.clip(score, 0, 100)))

# ── Apply sub-models ──────────────────────────────────────────────────────────
df['is_liquid']   = df['vol_avg20'] >= MEDIAN_VOL
df['score_v2']    = df.apply(
    lambda r: score_liquid(r) if r['is_liquid'] else score_illiquid(r), axis=1
)

def signal(score, is_liquid):
    if is_liquid:
        # Liquid: standard thresholds
        if score >= 65: return 'ACHAT'
        elif score >= 40: return 'SURVEILLER'
        else: return 'EVITER'
    else:
        # Illiquid: tighter — harder to get ACHAT
        if score >= 72: return 'ACHAT'
        elif score >= 45: return 'SURVEILLER'
        else: return 'EVITER'

df['signal_v2'] = df.apply(lambda r: signal(r['score_v2'], r['is_liquid']), axis=1)

# ── Backtest win/loss with new signals ───────────────────────────────────────
def is_win(row):
    if row['signal_v2'] == 'ACHAT':
        return row['future_return'] > 0
    elif row['signal_v2'] == 'EVITER':
        return row['future_return'] < 0
    else:
        return None

df['win_v2'] = df.apply(is_win, axis=1)

# ── Results ───────────────────────────────────────────────────────────────────
print("\n══ LIQUID SUB-MODEL ═════════════════════════════════════")
liquid = df[df['is_liquid']]
for sig in ['ACHAT', 'EVITER']:
    s = liquid[liquid['signal_v2'] == sig].dropna(subset=['win_v2'])
    print(f"\n  {sig} ({len(s)} signals)")
    print(f"    Win rate:      {s['win_v2'].mean()*100:.1f}%")
    print(f"    Avg return:    {s['future_return'].mean():.2f}%")
    print(f"    Median return: {s['future_return'].median():.2f}%")

print("\n── Liquid ACHAT by year ─────────────────────────────────")
achat_liq = liquid[(liquid['signal_v2']=='ACHAT')].dropna(subset=['win_v2'])
achat_liq = achat_liq.copy()
achat_liq['year'] = achat_liq['trade_date'].dt.year
print(achat_liq.groupby('year')['win_v2'].agg(
    count='count',
    win_rate=lambda x: f"{x.mean()*100:.1f}%"
).to_string())

print("\n══ ILLIQUID SUB-MODEL ═══════════════════════════════════")
illiquid = df[~df['is_liquid']]
for sig in ['ACHAT', 'EVITER']:
    s = illiquid[illiquid['signal_v2'] == sig].dropna(subset=['win_v2'])
    print(f"\n  {sig} ({len(s)} signals)")
    print(f"    Win rate:      {s['win_v2'].mean()*100:.1f}%")
    print(f"    Avg return:    {s['future_return'].mean():.2f}%")
    print(f"    Median return: {s['future_return'].median():.2f}%")

print("\n── Illiquid ACHAT by year ───────────────────────────────")
achat_illiq = illiquid[(illiquid['signal_v2']=='ACHAT')].dropna(subset=['win_v2'])
achat_illiq = achat_illiq.copy()
achat_illiq['year'] = achat_illiq['trade_date'].dt.year
print(achat_illiq.groupby('year')['win_v2'].agg(
    count='count',
    win_rate=lambda x: f"{x.mean()*100:.1f}%"
).to_string())

# ── Signal distribution comparison ───────────────────────────────────────────
print("\n── Signal distribution v2 ───────────────────────────────")
print(df.groupby(['is_liquid','signal_v2']).size().unstack(fill_value=0))

df.to_pickle('backtest_v2.pkl')
print("\n✅ Saved to backtest_v2.pkl")
