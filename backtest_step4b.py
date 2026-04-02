import pandas as pd
import numpy as np

df = pd.read_pickle('backtest_final.pkl')

# Filter: only stocks with meaningful volume (above exchange median)
median_vol = df['vol_avg20'].median()
df_liquid = df[df['vol_avg20'] >= median_vol]

print(f"Liquid rows: {len(df_liquid)} (vs {len(df)} total)")
print(f"Exchange median vol_avg20: {median_vol:,.0f}")

for sig in ['ACHAT', 'EVITER']:
    subset = df_liquid[df_liquid['signal'] == sig].dropna(subset=['win'])
    win_rate   = subset['win'].mean() * 100
    avg_return = subset['future_return'].mean()
    count      = len(subset)
    print(f"\n  {sig} liquid only ({count} signals)")
    print(f"    Win rate:   {win_rate:.1f}%")
    print(f"    Avg return: {avg_return:.2f}%")

# Also check: recent years only (2022+) liquid only
print("\n── ACHAT liquid, 2022+ by year ──────────────────────────")
achat_recent = df_liquid[
    (df_liquid['signal'] == 'ACHAT') &
    (df_liquid['trade_date'].dt.year >= 2022)
].dropna(subset=['win'])
achat_recent['year'] = achat_recent['trade_date'].dt.year
print(achat_recent.groupby('year')['win'].agg(
    count='count',
    win_rate=lambda x: f"{x.mean()*100:.1f}%"
).to_string())
