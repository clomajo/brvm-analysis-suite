import pandas as pd
import numpy as np
import openpyxl
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

# ── Charger le backtest ───────────────────────────────────────────────────────
print("Loading backtest data...")
df = pd.read_pickle('backtest_v4.pkl')

# ── Charger l'index BRVM ─────────────────────────────────────────────────────
wb = openpyxl.load_workbook('/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx')
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
idx = pd.DataFrame(rows[1:], columns=['company','trade_date','open','high','low','close','volume'])
idx['trade_date'] = pd.to_datetime(idx['trade_date'])
idx['close'] = pd.to_numeric(idx['close'], errors='coerce')
idx = idx[['trade_date','close']].dropna().sort_values('trade_date').set_index('trade_date')
idx_dates = sorted(idx.index)

def get_index_return(signal_date, n=90):
    future = [d for d in idx_dates if d > signal_date]
    if len(future) < n:
        return np.nan
    end_date = future[n-1]
    s = idx.loc[signal_date, 'close'] if signal_date in idx.index else np.nan
    e = idx.loc[end_date, 'close'] if end_date in idx.index else np.nan
    if pd.isna(s) or pd.isna(e) or s == 0:
        return np.nan
    return (e - s) / s * 100

# ── Calculer EOP returns ──────────────────────────────────────────────────────
print("Computing EOP returns...")
results = []
for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values
    for i in range(len(g)):
        future = prices[i+1:i+91]
        eop = (future[89] - prices[i]) / prices[i] * 100 if len(future) >= 90 and prices[i] > 0 else np.nan
        g.loc[i, 'eop_return_90'] = eop
        future60 = prices[i+1:i+61]
        eop60 = (future60[59] - prices[i]) / prices[i] * 100 if len(future60) >= 60 and prices[i] > 0 else np.nan
        g.loc[i, 'eop_return_60'] = eop60
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
df['year'] = df['trade_date'].dt.year
df['index_eop_90'] = df['trade_date'].apply(lambda d: get_index_return(d, 90))
df['index_eop_60'] = df['trade_date'].apply(lambda d: get_index_return(d, 60))
df['alpha_90'] = df['eop_return_90'] - df['index_eop_90']
df['alpha_60'] = df['eop_return_60'] - df['index_eop_60']

# ── Filtrer HC liquid ─────────────────────────────────────────────────────────
hc = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['is_liquid'] == True)
].copy()

# ── Calculer les stats par periode et window ──────────────────────────────────
def calc_stats(subset, window):
    eop_col = f'eop_return_{window}'
    alpha_col = f'alpha_{window}'
    s = subset.dropna(subset=[eop_col, alpha_col])
    if len(s) == 0:
        return None
    return {
        'signal_count': len(s),
        'win_rate': (s[eop_col] > 0).mean() * 100,
        'avg_gain': s[eop_col].mean(),
        'avg_alpha': s[alpha_col].mean(),
        'beat_index_pct': (s[alpha_col] > 0).mean() * 100,
        'hit_target_pct': (s[eop_col] > 0).mean() * 100,  # EOP positive = hit
        'avg_max_loss': s[eop_col][s[eop_col] < 0].mean() if (s[eop_col] < 0).any() else 0,
    }

updates = []

# Par année
for year in sorted(hc['year'].unique()):
    subset = hc[hc['year'] == year]
    for window in [60, 90]:
        stats = calc_stats(subset, window)
        if stats:
            updates.append({
                'period': str(year),
                'signal': 'ACHAT_HC',
                'liquidity_tier': 'liquid',
                'window_days': window,
                **stats
            })

# ALL periods
for window in [60, 90]:
    stats = calc_stats(hc, window)
    if stats:
        updates.append({
            'period': 'ALL',
            'signal': 'ACHAT_HC',
            'liquidity_tier': 'liquid',
            'window_days': window,
            **stats
        })

print(f"\nScorecard updates to write: {len(updates)}")
print(f"\nSample ALL 90d:")
all90 = [u for u in updates if u['period'] == 'ALL' and u['window_days'] == 90][0]
for k, v in all90.items():
    if isinstance(v, float):
        print(f"  {k}: {v:.2f}")
    else:
        print(f"  {k}: {v}")

# ── Mettre a jour Supabase ────────────────────────────────────────────────────
print("\nUpdating scorecard table...")
for u in updates:
    # Find existing row
    res = supabase.table('scorecard').select('id').eq('period', u['period']).eq('signal', u['signal']).eq('liquidity_tier', u['liquidity_tier']).eq('window_days', u['window_days']).execute()
    if res.data:
        row_id = res.data[0]['id']
        supabase.table('scorecard').update(u).eq('id', row_id).execute()
        print(f"  Updated {u['period']} {u['window_days']}d")
    else:
        supabase.table('scorecard').insert(u).execute()
        print(f"  Inserted {u['period']} {u['window_days']}d")

print("\n✅ Scorecard updated with honest EOP numbers")
