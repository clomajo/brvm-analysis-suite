import os
import pandas as pd
import numpy as np
import openpyxl
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)

# ── Load base data ────────────────────────────────────────────────────────────
df = pd.read_pickle('/Users/kaylam/Desktop/brvm-analysis-suite/backtest_v4.pkl')
print(f"Loaded {len(df)} rows")

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

def get_index_return_nd(signal_date, n):
    future_dates = [d for d in index_dates if d > signal_date]
    if len(future_dates) < 10:
        return np.nan
    end_date    = future_dates[min(n-1, len(future_dates)-1)]
    start_level = index_lookup.get(signal_date, np.nan)
    end_level   = index_lookup.get(end_date, np.nan)
    if pd.isna(start_level) or pd.isna(end_level) or start_level == 0:
        return np.nan
    return (end_level - start_level) / start_level * 100

# ── Compute 90d forward windows per ticker ────────────────────────────────────
print("Computing 90d forward windows...")
results = []
for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values
    max_gain_90, max_loss_90, hit_up_90 = [], [], []
    for i in range(len(g)):
        window = prices[i+1:i+91]
        if len(window) < 10:
            max_gain_90.append(np.nan)
            max_loss_90.append(np.nan)
            hit_up_90.append(np.nan)
            continue
        base = prices[i]
        max_gain_90.append((np.max(window) - base) / base * 100)
        max_loss_90.append((np.min(window) - base) / base * 100)
        hit_up_90.append(int(np.max(window) >= float(g.iloc[i]['upside_target'])))
    g['max_gain_90'] = max_gain_90
    g['max_loss_90'] = max_loss_90
    g['hit_up_90']   = hit_up_90
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
print(f"  90d windows computed")

# ── Compute index returns ─────────────────────────────────────────────────────
print("Computing index returns (60d + 90d)...")
df['index_ret_60d'] = df['trade_date'].apply(lambda d: get_index_return_nd(d, 60))
df['index_ret_90d'] = df['trade_date'].apply(lambda d: get_index_return_nd(d, 90))
print(f"  Index returns computed")

df['year'] = df['trade_date'].dt.year
rows_out = []

def add_row(subset, period, signal, tier, window):
    if len(subset) == 0:
        return
    gain_col = f'max_gain_{window}'
    loss_col = f'max_loss_{window}'
    idx_col  = f'index_ret_{window}d'
    hit_col  = 'hit_upside' if window == 60 else 'hit_up_90'

    s = subset.dropna(subset=[gain_col])
    if len(s) == 0:
        return

    is_achat = signal in ['ACHAT', 'ACHAT_HC']
    win_rate = float(s['win_v2'].dropna().mean() * 100) if is_achat else None
    hit_rate = float(s[hit_col].dropna().mean() * 100) if is_achat else None

    avg_alpha = None
    beat_pct  = None
    s2 = s.dropna(subset=[idx_col])
    if len(s2) > 0:
        alpha     = s2[gain_col] - s2[idx_col]
        avg_alpha = float(alpha.mean())
        beat_pct  = float((alpha > 0).mean() * 100)

    rows_out.append({
        'period':         period,
        'signal':         signal,
        'liquidity_tier': tier,
        'window_days':    window,
        'signal_count':   len(s),
        'win_rate':       win_rate,
        'avg_gain':       float(s[gain_col].mean()),
        'avg_alpha':      avg_alpha,
        'beat_index_pct': beat_pct,
        'hit_target_pct': hit_rate,
        'avg_max_loss':   float(s[loss_col].mean()) if loss_col in s.columns else None,
    })

# ── Build all combinations ────────────────────────────────────────────────────
for window in [60, 90]:
    for signal in ['ACHAT', 'EVITER']:
        for tier, mask in [
            ('all',      df['signal_v2'] == signal),
            ('liquid',   (df['signal_v2'] == signal) & (df['is_liquid'] == True)),
            ('illiquid', (df['signal_v2'] == signal) & (df['is_liquid'] == False)),
        ]:
            subset = df[mask]
            add_row(subset, 'ALL', signal, tier, window)
            for year in sorted(df['year'].unique()):
                add_row(subset[subset['year'] == year], str(year), signal, tier, window)

    # High conviction liquid
    hc = df[
        (df['signal_v2'] == 'ACHAT') &
        (df['confidence'] >= 70) &
        (df['is_liquid'] == True)
    ]
    add_row(hc, 'ALL', 'ACHAT_HC', 'liquid', window)
    for year in sorted(df['year'].unique()):
        add_row(hc[hc['year'] == year], str(year), 'ACHAT_HC', 'liquid', window)

print(f"Generated {len(rows_out)} scorecard rows")

# ── Clean NaN → None ──────────────────────────────────────────────────────────
clean = []
for r in rows_out:
    clean.append({k: (None if isinstance(v, float) and np.isnan(v) else v)
                  for k, v in r.items()})

# ── Upsert to Supabase ────────────────────────────────────────────────────────
for i in range(0, len(clean), 100):
    batch = clean[i:i+100]
    supabase.table('scorecard').upsert(
        batch, on_conflict='period,signal,liquidity_tier,window_days'
    ).execute()
    print(f"  Upserted {min(i+100, len(clean))}/{len(clean)}")

print(f"✅ Scorecard loaded — {len(clean)} rows in Supabase")
