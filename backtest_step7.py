import pandas as pd
import numpy as np
import openpyxl

# ── Load real BRVMC index ─────────────────────────────────────────────────────
print("Loading BRVM Composite index...")

# Copy the file first: drag it from Downloads to brvm-analysis-suite folder
# OR load directly from Downloads
wb = openpyxl.load_workbook(
    '/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx'
)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
index = pd.DataFrame(rows[1:], columns=['company','trade_date','open','high','low','close','volume'])
index['trade_date'] = pd.to_datetime(index['trade_date'])
index['close'] = pd.to_numeric(index['close'], errors='coerce')
index = index[['trade_date','close']].dropna().sort_values('trade_date').reset_index(drop=True)
print(f"  Index rows: {len(index)}")
print(f"  Date range: {index['trade_date'].min().date()} → {index['trade_date'].max().date()}")

# ── Load backtest data ────────────────────────────────────────────────────────
df = pd.read_pickle('backtest_v3.pkl')

# ── Build date → index level lookup ──────────────────────────────────────────
index_lookup = index.set_index('trade_date')['close'].to_dict()
index_dates  = sorted(index_lookup.keys())

def get_index_return_60d(signal_date):
    future_dates = [d for d in index_dates if d > signal_date]
    if len(future_dates) < 10:
        return np.nan
    end_date    = future_dates[min(59, len(future_dates)-1)]
    start_level = index_lookup.get(signal_date, np.nan)
    end_level   = index_lookup.get(end_date, np.nan)
    if pd.isna(start_level) or pd.isna(end_level) or start_level == 0:
        return np.nan
    return (end_level - start_level) / start_level * 100

# ── ACHAT signals vs index ────────────────────────────────────────────────────
print("Computing alpha for ACHAT signals...")
achat = df[df['signal_v2'] == 'ACHAT'].copy()
achat['index_ret_60d'] = achat['trade_date'].apply(get_index_return_60d)
achat['alpha_60d']     = achat['max_gain_60'] - achat['index_ret_60d']
achat = achat.dropna(subset=['index_ret_60d'])

print(f"\n══ ALL ACHAT vs BRVM COMPOSITE INDEX (60d) ══════════════")
print(f"  Signals:               {len(achat):,}")
print(f"  Avg stock max gain:    +{achat['max_gain_60'].mean():.2f}%")
print(f"  Avg index return:      +{achat['index_ret_60d'].mean():.2f}%")
print(f"  Avg alpha:             +{achat['alpha_60d'].mean():.2f}%")
print(f"  % signals beat index:  {(achat['alpha_60d'] > 0).mean()*100:.1f}%")

# ── High conviction liquid 2022+ ──────────────────────────────────────────────
print(f"\n══ HIGH CONVICTION LIQUID 2022+ vs INDEX ════════════════")
hc = achat[
    (achat['confidence'] >= 70) &
    (achat['is_liquid'] == True) &
    (achat['trade_date'].dt.year >= 2022)
].copy()
print(f"  Signals:               {len(hc):,}")
print(f"  Avg stock max gain:    +{hc['max_gain_60'].mean():.2f}%")
print(f"  Avg index return:      +{hc['index_ret_60d'].mean():.2f}%")
print(f"  Avg alpha:             +{hc['alpha_60d'].mean():.2f}%")
print(f"  % signals beat index:  {(hc['alpha_60d'] > 0).mean()*100:.1f}%")

print(f"\n── By year ──────────────────────────────────────────────")
hc['year'] = hc['trade_date'].dt.year
print(hc.groupby('year').agg(
    count=('alpha_60d','count'),
    stock_gain=('max_gain_60',  lambda x: f"+{x.mean():.2f}%"),
    index_ret =('index_ret_60d',lambda x: f"+{x.mean():.2f}%"),
    alpha     =('alpha_60d',    lambda x: f"+{x.mean():.2f}%"),
    beat_index=('alpha_60d',    lambda x: f"{(x>0).mean()*100:.1f}%")
).to_string())

# ── ÉVITER: protection vs index ───────────────────────────────────────────────
print(f"\n══ ÉVITER: CAPITAL PROTECTION vs INDEX ══════════════════")
eviter = df[df['signal_v2'] == 'EVITER'].copy()
eviter['index_ret_60d'] = eviter['trade_date'].apply(get_index_return_60d)
eviter = eviter.dropna(subset=['index_ret_60d'])
eviter['protected'] = eviter['max_loss_60'] > eviter['index_ret_60d']
print(f"  Signals:               {len(eviter):,}")
print(f"  Avg stock max loss:    {eviter['max_loss_60'].mean():.2f}%")
print(f"  Avg index return:      +{eviter['index_ret_60d'].mean():.2f}%")
print(f"  % where avoiding stock beat holding index: {eviter['protected'].mean()*100:.1f}%")

df.to_pickle('backtest_v4.pkl')
print("\n✅ Saved to backtest_v4.pkl")
