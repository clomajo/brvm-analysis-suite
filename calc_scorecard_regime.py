import pandas as pd
import numpy as np
import openpyxl

df = pd.read_pickle('backtest_v4.pkl')

wb = openpyxl.load_workbook('/Users/kaylam/Downloads/Historical Data BRVM 10Y/10Y_BRVM-COMPOSITE INDEX_DATA.xlsx')
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
idx = pd.DataFrame(rows[1:], columns=['company','trade_date','open','high','low','close','volume'])
idx['trade_date'] = pd.to_datetime(idx['trade_date'])
idx['close'] = pd.to_numeric(idx['close'], errors='coerce')
idx = idx[['trade_date','close']].dropna().sort_values('trade_date').set_index('trade_date')
idx['sma50']  = idx['close'].rolling(50).mean()
idx['sma200'] = idx['close'].rolling(200).mean()
idx['regime'] = np.where((idx['close']>idx['sma50'])&(idx['close']>idx['sma200']),'BULL','BEAR')
idx_dates = sorted(idx.index)

def get_index_return(signal_date, n=90):
    future = [d for d in idx_dates if d > signal_date]
    if len(future) < n: return np.nan
    end = future[n-1]
    s = idx.loc[signal_date,'close'] if signal_date in idx.index else np.nan
    e = idx.loc[end,'close'] if end in idx.index else np.nan
    if pd.isna(s) or pd.isna(e) or s==0: return np.nan
    return (e-s)/s*100

print("Computing EOP returns...")
results = []
for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values
    eop = []
    for i in range(len(g)):
        future = prices[i+1:i+91]
        eop.append((future[89]-prices[i])/prices[i]*100 if len(future)>=90 and prices[i]>0 else np.nan)
    g['eop_return_90'] = eop
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
df['year'] = df['trade_date'].dt.year
df['regime'] = df['trade_date'].map(idx['regime'])
df['index_eop_90'] = df['trade_date'].apply(lambda d: get_index_return(d,90))
df['alpha_90'] = df['eop_return_90'] - df['index_eop_90']

hc = df[(df['signal_v2']=='ACHAT')&(df['confidence']>=70)&(df['is_liquid']==True)].dropna(subset=['eop_return_90'])

PRESTIGE = {'ECOC','NTLC','ONTBF','ORAC','PALC','SGBC','SIBC','SMBC','SNTS','SPHC','TTLC','TTLS'}
BRVM30   = {'SDSC','SIVC','BOABF','BOAB','BOAC','BOAM','BOAN','BOAS','BICB','CFAC','CIEC',
            'ECOC','ETIT','FTSC','ONTBF','ORGT','ORAC','PALC','SAFC','SPHC','SGBC','STBC',
            'SIBC','SOGC','SLBC','SNTS','SCRC','TTLC','UNXC','SHEC'}

print("\n=== PAR REGIME ===")
for regime in ['BULL','BEAR']:
    s = hc[hc['regime']==regime].dropna(subset=['alpha_90'])
    if len(s)==0: continue
    sharpe = (s['eop_return_90'].mean()/s['eop_return_90'].std())*np.sqrt(252/90)
    print(f"{regime}: {len(s):,} | {(s['eop_return_90']>0).mean()*100:.1f}% pos | "
          f"return: {s['eop_return_90'].mean():.2f}% | alpha: {s['alpha_90'].mean():.2f}% | Sharpe: {sharpe:.3f}")

print("\n=== PAR TIER (tous signaux ACHAT HC) ===")
hc2 = hc.copy()
hc2['tier'] = hc2['symbol'].apply(lambda s: 'prestige' if s in PRESTIGE else ('brvm30' if s in BRVM30 else 'illiquid'))
for tier in ['prestige','brvm30','illiquid']:
    s = hc2[hc2['tier']==tier]
    if len(s)==0: continue
    print(f"{tier:<10}: {len(s):,} | {(s['eop_return_90']>0).mean()*100:.1f}% pos | return: {s['eop_return_90'].mean():.2f}%")

print("\n=== BULL REGIME PAR TIER ===")
bull = hc2[hc2['regime']=='BULL']
for tier in ['prestige','brvm30','illiquid']:
    s = bull[bull['tier']==tier]
    if len(s)==0: continue
    sharpe = (s['eop_return_90'].mean()/s['eop_return_90'].std())*np.sqrt(252/90)
    print(f"{tier:<10}: {len(s):,} | {(s['eop_return_90']>0).mean()*100:.1f}% pos | "
          f"return: {s['eop_return_90'].mean():.2f}% | Sharpe: {sharpe:.3f}")

print("\n=== ANNUEL AVEC REGIME ===")
print(f"{'Year':<6} {'%BULL':>7} {'Signals':>8} {'%Pos':>7} {'Alpha':>8} {'Regime'}")
print('-'*55)
for yr in range(2016,2026):
    yr_data = hc[hc['year']==yr].dropna(subset=['eop_return_90','alpha_90'])
    bull_pct = float((idx[idx.index.year==yr]['regime']=='BULL').mean()*100) if yr in idx.index.year else 0
    if len(yr_data)==0: continue
    note = 'BULL' if bull_pct>=60 else ('BEAR' if bull_pct<=20 else 'MIXED')
    print(f"{yr:<6} {bull_pct:>6.0f}% {len(yr_data):>8,} {(yr_data['eop_return_90']>0).mean()*100:>6.1f}% "
          f"{yr_data['alpha_90'].mean():>7.2f}% {note}")

print("\nDone")
