import pandas as pd
import numpy as np
import openpyxl

# ── Load index ────────────────────────────────────────────────────────────────
wb = openpyxl.load_workbook('/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx')
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
index = pd.DataFrame(rows[1:], columns=['company','trade_date','open','high','low','close','volume'])
index['trade_date'] = pd.to_datetime(index['trade_date'])
index['close'] = pd.to_numeric(index['close'], errors='coerce')
index = index[['trade_date','close']].dropna().sort_values('trade_date').reset_index(drop=True)
index_lookup = index.set_index('trade_date')['close'].to_dict()
index_dates  = sorted(index_lookup.keys())

# ── Load stock data ───────────────────────────────────────────────────────────
df = pd.read_pickle('backtest_v3.pkl')

# ── Build 90-day forward window ───────────────────────────────────────────────
print("Computing 90-day forward windows per ticker...")
results = []

for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values

    max_gain_90 = []
    max_loss_90 = []
    hit_up_90   = []

    for i in range(len(g)):
        window = prices[i+1:i+91]
        if len(window) < 10:
            max_gain_90.append(np.nan)
            max_loss_90.append(np.nan)
            hit_up_90.append(np.nan)
            continue
        base       = prices[i]
        peak       = (np.max(window) - base) / base * 100
        trough     = (np.min(window) - base) / base * 100
        up_target  = float(g.iloc[i]['upside_target'])
        max_gain_90.append(peak)
        max_loss_90.append(trough)
        hit_up_90.append(int(np.max(window) >= up_target))

    g['max_gain_90'] = max_gain_90
    g['max_loss_90'] = max_loss_90
    g['hit_up_90']   = hit_up_90
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
df = df.dropna(subset=['max_gain_90'])
print(f"  Rows with 90-day window: {len(df)}")

# ── Index return over 90 days ─────────────────────────────────────────────────
def get_index_return_90d(signal_date):
    future_dates = [d for d in index_dates if d > signal_date]
    if len(future_dates) < 10:
        return np.nan
    end_date    = future_dates[min(89, len(future_dates)-1)]
    start_level = index_lookup.get(signal_date, np.nan)
    end_level   = index_lookup.get(end_date, np.nan)
    if pd.isna(start_level) or pd.isna(end_level) or start_level == 0:
        return np.nan
    return (end_level - start_level) / start_level * 100

# ── Compare 60d vs 90d side by side ──────────────────────────────────────────
print("\n══ 60d vs 90d COMPARISON — HIGH CONVICTION LIQUID ═══════")
hc = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['is_liquid'] == True)
].copy()

hc['index_ret_90d'] = hc['trade_date'].apply(get_index_return_90d)
hc['alpha_90d']     = hc['max_gain_90'] - hc['index_ret_90d']
hc["index_ret_60d"] = hc["trade_date"].apply(lambda d: (lambda f: (index_lookup.get(sorted([x for x in index_dates if x > d])[ min(59,len([x for x in index_dates if x > d])-1)], float("nan")) - index_lookup.get(d, float("nan"))) / index_lookup.get(d, 1) * 100 if len([x for x in index_dates if x > d]) >= 10 else float("nan"))(None))nhc["alpha_60d"] = hc["max_gain_60"] - hc["index_ret_60d"]nhc = hc.dropna(subset=["index_ret_90d", "max_gain_90", "index_ret_60d"])

print(f"\n  {'Metric':<30} {'60 days':>10} {'90 days':>10}")
print(f"  {'-'*50}")
print(f"  {'Signals':<30} {len(hc):>10,} {len(hc):>10,}")
print(f"  {'Avg stock max gain':<30} {hc['max_gain_60'].mean():>+9.2f}% {hc['max_gain_90'].mean():>+9.2f}%")
print(f"  {'Avg index return':<30} {hc['index_ret_60d'].mean():>+9.2f}% {hc['index_ret_90d'].mean():>+9.2f}%")
print(f"  {'Avg alpha':<30} {hc['alpha_60d'].mean():>+9.2f}% {hc['alpha_90d'].mean():>+9.2f}%")
print(f"  {'% beat index':<30} {(hc['alpha_60d']>0).mean()*100:>9.1f}% {(hc['alpha_90d']>0).mean()*100:>9.1f}%")
print(f"  {'ATR target hit rate':<30} {hc['hit_upside'].mean()*100:>9.1f}% {hc['hit_up_90'].mean()*100:>9.1f}%")

# ── By year 2022+ ─────────────────────────────────────────────────────────────
print(f"\n── By year (2022+) ──────────────────────────────────────")
hc_recent = hc[hc['trade_date'].dt.year >= 2022].copy()
hc_recent['year'] = hc_recent['trade_date'].dt.year
print(hc_recent.groupby('year').agg(
    count      =('alpha_90d','count'),
    gain_60d   =('max_gain_60',   lambda x: f"+{x.mean():.2f}%"),
    gain_90d   =('max_gain_90',   lambda x: f"+{x.mean():.2f}%"),
    alpha_60d  =('alpha_60d',     lambda x: f"+{x.mean():.2f}%"),
    alpha_90d  =('alpha_90d',     lambda x: f"+{x.mean():.2f}%"),
    beat_60d   =('alpha_60d',     lambda x: f"{(x>0).mean()*100:.1f}%"),
    beat_90d   =('alpha_90d',     lambda x: f"{(x>0).mean()*100:.1f}%"),
    hit_90d    =('hit_up_90',     lambda x: f"{x.mean()*100:.1f}%")
).to_string())

# ── ÉVITER 90d ────────────────────────────────────────────────────────────────
print(f"\n══ ÉVITER: 60d vs 90d MAX LOSS ══════════════════════════")
ev = df[df['signal_v2'] == 'EVITER'].copy()
ev = ev.dropna(subset=['max_loss_60', 'max_loss_90'])
print(f"  Avg max loss 60d: {ev['max_loss_60'].mean():.2f}%")
print(f"  Avg max loss 90d: {ev['max_loss_90'].mean():.2f}%")

print("\n✅ 60d vs 90d comparison complete")
