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

print('BRVM regime by year:')
print(idx.groupby(idx.index.year)['regime'].apply(lambda x: f"{(x=='BULL').mean()*100:.0f}% BULL days").to_string())

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

def rescore_directional(row):
    rsi_s = float(row['rsi'])
    t20 = (row['price']-row['sma20'])/row['sma20']*100
    t50 = (row['price']-row['sma50'])/row['sma50']*100
    tr_s = float(np.clip(50+(t20*0.6+t50*0.4)*5, 0, 100))
    direction = 1 if row['price'] > row['sma20'] else -1
    vc_s = float(np.clip(50+direction*25*(row['vol_ratio']-1)*2, 0, 100))
    vr_s = float(np.clip(100-row['atr_pct']*10, 0, 100))
    return float(np.clip(rsi_s*0.20+tr_s*0.40+vc_s*0.25+vr_s*0.15, 0, 100))

print('\nRescoring with directional volume...')
liq = df[df['is_liquid']==True].copy()
liq['score_fixed'] = liq.apply(rescore_directional, axis=1)
liq['signal_fixed'] = np.where(liq['score_fixed']>=65,'ACHAT','OTHER')

hc_orig = df[(df['signal_v2']=='ACHAT')&(df['confidence']>=70)&(df['is_liquid']==True)].dropna(subset=['eop_return_90'])
hc_fixed = liq[(liq['signal_fixed']=='ACHAT')&(liq['confidence']>=70)].dropna(subset=['eop_return_90'])

print('\n=== ORIGINAL vs FIXED VOLUME (HC Liquid EOP) ===')
print(f"{'Year':<6} {'Orig %pos':>10} {'Fixed %pos':>11} {'Orig n':>8} {'Fixed n':>8}")
print('-'*45)
for yr in range(2016,2026):
    o = hc_orig[hc_orig['year']==yr]['eop_return_90']
    f = hc_fixed[hc_fixed['year']==yr]['eop_return_90']
    if len(o)>0 or len(f)>0:
        op = f"{(o>0).mean()*100:.1f}%" if len(o)>0 else 'N/A'
        fp = f"{(f>0).mean()*100:.1f}%" if len(f)>0 else 'N/A'
        print(f"{yr:<6} {op:>10} {fp:>11} {len(o):>8,} {len(f):>8,}")

print(f"\nOverall original: {(hc_orig['eop_return_90']>0).mean()*100:.1f}% ({len(hc_orig):,} signals)")
print(f"Overall fixed:    {(hc_fixed['eop_return_90']>0).mean()*100:.1f}% ({len(hc_fixed):,} signals)")

bull_fixed = hc_fixed[hc_fixed['regime']=='BULL'].dropna(subset=['eop_return_90'])
print(f"\n=== BULL REGIME + FIXED VOLUME ===")
print(f"Signals: {len(bull_fixed):,}")
print(f"Overall % positive: {(bull_fixed['eop_return_90']>0).mean()*100:.1f}%")
for yr in range(2016,2026):
    y = bull_fixed[bull_fixed['year']==yr]
    if len(y)>5:
        print(f"  {yr}: {(y['eop_return_90']>0).mean()*100:.1f}% ({len(y)} signals)")

print('\n=== PROBLEM TICKERS 2018-2019: ORIG vs FIXED ===')
for t in ['SICC','CABC','BOAS','BOAC','SGBC','SOGC','CIEC','ONTBF']:
    o = hc_orig[(hc_orig['symbol']==t)&(hc_orig['year'].isin([2018,2019]))]['eop_return_90']
    f = hc_fixed[(hc_fixed['symbol']==t)&(hc_fixed['year'].isin([2018,2019]))]['eop_return_90']
    r = hc_fixed[(hc_fixed['symbol']==t)&(hc_fixed['year'].isin([2024,2025]))]['eop_return_90']
    op = f"{(o>0).mean()*100:.0f}%" if len(o)>0 else "N/A"
    fp = f"{(f>0).mean()*100:.0f}%" if len(f)>0 else "N/A"
    rp = f"{(r>0).mean()*100:.0f}%" if len(r)>0 else "N/A"
    print(f"{t:<8} 18-19 orig:{op} fixed:{fp} | 24-25:{rp} ({len(r)} sig)")

print('\nDone')
