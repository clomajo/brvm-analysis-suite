import pandas as pd
import numpy as np
import openpyxl

# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_pickle('backtest_v4.pkl')
print(f"Columns with max/gain/hit: {list(df.columns[df.columns.str.contains('max|gain|hit')])}")

# ── Load BRVM index ───────────────────────────────────────────────────────────
wb = openpyxl.load_workbook('/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx')
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
index = pd.DataFrame(rows[1:], columns=['company','trade_date','open','high','low','close','volume'])
index['trade_date'] = pd.to_datetime(index['trade_date'])
index['close'] = pd.to_numeric(index['close'], errors='coerce')
index = index[['trade_date','close']].dropna().sort_values('trade_date').reset_index(drop=True)
index_lookup = index.set_index('trade_date')['close'].to_dict()
index_dates  = sorted(index_lookup.keys())

# FIX 2: Use trading days for index return (same as stock EOP)
def get_index_return_trading(signal_date, n_trading=90):
    future_dates = [d for d in index_dates if d > signal_date]
    if len(future_dates) < n_trading:
        return np.nan
    end_date    = future_dates[n_trading - 1]
    start_level = index_lookup.get(signal_date, np.nan)
    end_level   = index_lookup.get(end_date, np.nan)
    if pd.isna(start_level) or pd.isna(end_level) or start_level == 0:
        return np.nan
    return (end_level - start_level) / start_level * 100

# ── Compute end-of-period returns (trading day 90) ────────────────────────────
print("Computing end-of-period returns (90 trading days)...")
results = []
for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values
    eop_90 = []
    max_90 = []
    for i in range(len(g)):
        future = prices[i+1:i+91]
        if len(future) < 90:
            eop_90.append(np.nan)
            max_90.append(np.nan)
        else:
            base = prices[i]
            if base > 0:
                eop_90.append((future[89] - base) / base * 100)
                max_90.append((np.max(future) - base) / base * 100)
            else:
                eop_90.append(np.nan)
                max_90.append(np.nan)
    g['eop_return_90'] = eop_90
    g['max_return_90'] = max_90
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
df = df.dropna(subset=['eop_return_90'])

# FIX 2: Index return using trading days
print("Computing index returns (90 trading days)...")
df['index_eop_90'] = df['trade_date'].apply(get_index_return_trading)
df['alpha_eop_90'] = df['eop_return_90'] - df['index_eop_90']
df['year'] = df['trade_date'].dt.year
print(f"Total rows: {len(df)}")

# ═══════════════════════════════════════════════════════════════════
# TEST 1: END-OF-PERIOD vs MAXIMUM RETURN
# ═══════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST 1: END-OF-PERIOD vs MAXIMUM RETURN — HIGH CONVICTION LIQUID")
print("="*70)

hc = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['is_liquid'] == True)
].dropna(subset=['eop_return_90','max_return_90','index_eop_90']).copy()

# FIX 1: max_win using max_return_90 (not max_gain_60)
if 'hit_upside' in hc.columns:
    hc['max_win'] = hc['hit_upside'] == 1
else:
    hc['max_win'] = hc['max_return_90'] > 0

hc['eop_win']   = hc['eop_return_90'] > 0
hc['alpha_max'] = hc['max_return_90'] - hc['index_eop_90']

print(f"\n  {'Metric':<38} {'Max Return':>18} {'End-of-Period':>18}")
print(f"  {'-'*74}")
print(f"  {'Signals':<38} {len(hc):>18,} {len(hc):>18,}")
print(f"  {'Avg return':<38} {hc['max_return_90'].mean():>17.2f}% {hc['eop_return_90'].mean():>17.2f}%")
print(f"  {'% positive':<38} {hc['max_win'].mean()*100:>17.1f}% {hc['eop_win'].mean()*100:>17.1f}%")
print(f"  {'Avg alpha vs BRVM':<38} {hc['alpha_max'].mean():>17.2f}% {hc['alpha_eop_90'].mean():>17.2f}%")
print(f"  {'% beating index':<38} {(hc['alpha_max']>0).mean()*100:>17.1f}% {(hc['alpha_eop_90']>0).mean()*100:>17.1f}%")

# Risk metrics
eop_mean = hc['eop_return_90'].mean()
eop_std  = hc['eop_return_90'].std()
sharpe   = (eop_mean / eop_std) * np.sqrt(252/90) if eop_std > 0 else np.nan
max_dd   = hc['eop_return_90'].min()
calmar   = eop_mean / abs(max_dd) if max_dd < 0 else np.nan
pct_95   = np.percentile(hc['eop_return_90'], 5)

print(f"\n  {'--- Risk Metrics (EOP) ---':<38}")
print(f"  {'Sharpe ratio (annualized)':<38} {sharpe:>17.3f}")
print(f"  {'Max drawdown (worst EOP return)':<38} {max_dd:>17.2f}%")
print(f"  {'Calmar ratio':<38} {calmar:>17.3f}")
print(f"  {'5th percentile return':<38} {pct_95:>17.2f}%")
print(f"  {'Std dev of EOP returns':<38} {eop_std:>17.2f}%")

# ═══════════════════════════════════════════════════════════════════
# TEST 2: FULL UNIVERSE
# ═══════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST 2: FULL UNIVERSE — ALL ACHAT SIGNALS, ALL CONFIDENCE LEVELS")
print("="*70)

all_achat = df[df['signal_v2'] == 'ACHAT'].dropna(subset=['eop_return_90']).copy()
print(f"\n  Total ACHAT signals:    {len(all_achat):,}")
print(f"  Avg EOP return:         {all_achat['eop_return_90'].mean():.2f}%")
print(f"  % positive:             {(all_achat['eop_return_90']>0).mean()*100:.1f}%")
print(f"  Std dev:                {all_achat['eop_return_90'].std():.2f}%")

all_achat['conf_band'] = pd.cut(all_achat['confidence'],
    bins=[0,40,70,100], labels=['Low (<40)','Medium (40-70)','High (>70)'])
print(f"\n  By confidence band:")
print(all_achat.groupby('conf_band', observed=True)['eop_return_90'].agg(
    count='count',
    avg_return=lambda x: f"{x.mean():.2f}%",
    pct_positive=lambda x: f"{(x>0).mean()*100:.1f}%",
    std=lambda x: f"{x.std():.2f}%"
).to_string())

print(f"\n  By liquidity tier:")
print(all_achat.groupby('is_liquid', observed=True)['eop_return_90'].agg(
    count='count',
    avg_return=lambda x: f"{x.mean():.2f}%",
    pct_positive=lambda x: f"{(x>0).mean()*100:.1f}%"
).to_string())

# ═══════════════════════════════════════════════════════════════════
# TEST 3: OUT-OF-SAMPLE 2024–2025
# ═══════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST 3: OUT-OF-SAMPLE — 2024–2025 HELD OUT")
print("="*70)

oos = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['is_liquid'] == True) &
    (df['year'].isin([2024, 2025]))
].dropna(subset=['eop_return_90','index_eop_90']).copy()

oos['alpha'] = oos['eop_return_90'] - oos['index_eop_90']
oos_sharpe = (oos['eop_return_90'].mean() / oos['eop_return_90'].std()) * np.sqrt(252/90)

print(f"\n  Signals (2024–2025):    {len(oos):,}")
print(f"  Avg EOP return:         {oos['eop_return_90'].mean():.2f}%")
print(f"  % positive:             {(oos['eop_return_90']>0).mean()*100:.1f}%")
print(f"  Avg alpha vs BRVM:      {oos['alpha'].mean():.2f}%")
print(f"  % beating index:        {(oos['alpha']>0).mean()*100:.1f}%")
print(f"  Sharpe (annualized):    {oos_sharpe:.3f}")

print(f"\n  By year:")
for yr in [2024, 2025]:
    y = oos[oos['year']==yr]
    if len(y) > 0:
        print(f"  {yr}: {len(y):,} signals | EOP return: {y['eop_return_90'].mean():.2f}% | "
              f"% positive: {(y['eop_return_90']>0).mean()*100:.1f}% | "
              f"Alpha: {y['alpha'].mean():.2f}%")

# ═══════════════════════════════════════════════════════════════════
# TEST 4: SENSITIVITY — TREND WEIGHT
# ═══════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST 4: SENSITIVITY — TREND WEIGHT (30% / 40% / 50%)")
print("="*70)

def rescore(row, w_trend):
    w_rsi = 0.20
    w_vol = 0.25
    w_vr  = 1.0 - w_rsi - w_trend - w_vol
    rsi_s = float(row['rsi'])
    t20   = (row['price'] - row['sma20']) / row['sma20'] * 100
    t50   = (row['price'] - row['sma50']) / row['sma50'] * 100
    tr_s  = float(np.clip(50 + (t20*0.6 + t50*0.4) * 5, 0, 100))
    vc_s  = float(np.clip(row['vol_ratio'] * 50, 0, 100))
    vr_s  = float(np.clip(100 - row['atr_pct'] * 10, 0, 100))
    return np.clip(rsi_s*w_rsi + tr_s*w_trend + vc_s*w_vol + vr_s*w_vr, 0, 100)

liquid = df[df['is_liquid'] == True].copy()
print(f"\n  {'Trend weight':<15} {'HC Signals':>12} {'% Positive':>12} {'Avg Return':>12} {'Avg Alpha':>12}")
print(f"  {'-'*63}")
for w in [0.30, 0.40, 0.50]:
    liquid[f'score_w{int(w*100)}'] = liquid.apply(lambda r: rescore(r, w), axis=1)
    sig = liquid[
        (liquid[f'score_w{int(w*100)}'] >= 65) &
        (liquid['confidence'] >= 70)
    ].dropna(subset=['eop_return_90','index_eop_90'])
    if len(sig) > 0:
        alpha = sig['eop_return_90'] - sig['index_eop_90']
        print(f"  {int(w*100)}%{'':<12} {len(sig):>12,} {(sig['eop_return_90']>0).mean()*100:>11.1f}% "
              f"{sig['eop_return_90'].mean():>11.2f}% {alpha.mean():>11.2f}%")

# ═══════════════════════════════════════════════════════════════════
# TEST 5: SLIPPAGE & LIQUIDITY (realistic execution)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST 5: REALISTIC EXECUTION — SLIPPAGE & LIQUIDITY")
print("="*70)

SLIPPAGE = 0.01       # 1% entry slippage
MAX_VOL_PCT = 0.05    # max 5% of daily volume
MIN_USD = 500         # minimum position $500 USD
FCFA_TO_USD = 1/600   # approximate XOF/USD

hc2 = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['is_liquid'] == True)
].dropna(subset=['eop_return_90']).copy()

# Max position size in USD
hc2['max_position_usd'] = hc2['vol_avg20'] * MAX_VOL_PCT * hc2['price'] * FCFA_TO_USD
hc2['executable'] = hc2['max_position_usd'] >= MIN_USD

# Net return after slippage
hc2['net_eop_return'] = hc2['eop_return_90'] - (SLIPPAGE * 100 * 2)  # entry + exit

exec_signals = hc2[hc2['executable']]
non_exec     = hc2[~hc2['executable']]

print(f"\n  Total HC liquid signals:     {len(hc2):,}")
print(f"  Executable (≥$500 position): {len(exec_signals):,} ({len(exec_signals)/len(hc2)*100:.1f}%)")
print(f"  Not executable (<$500):      {len(non_exec):,} ({len(non_exec)/len(hc2)*100:.1f}%)")
print(f"\n  Executable signals after 1% slippage each way:")
print(f"  Avg net return:              {exec_signals['net_eop_return'].mean():.2f}%")
print(f"  % positive after slippage:  {(exec_signals['net_eop_return']>0).mean()*100:.1f}%")
net_sharpe = (exec_signals['net_eop_return'].mean() /
              exec_signals['net_eop_return'].std()) * np.sqrt(252/90)
print(f"  Sharpe after slippage:       {net_sharpe:.3f}")
print(f"  Avg position size (USD):     ${exec_signals['max_position_usd'].mean():,.0f}")

print(f"\n  By year (2022+, executable only):")
exec_recent = exec_signals[exec_signals['year'] >= 2022].copy()
for yr in sorted(exec_recent['year'].unique()):
    y = exec_recent[exec_recent['year']==yr]
    print(f"  {yr}: {len(y):,} signals | Net return: {y['net_eop_return'].mean():.2f}% | "
          f"% positive: {(y['net_eop_return']>0).mean()*100:.1f}%")

print("\n✅ Honest backtest v2 complete")
