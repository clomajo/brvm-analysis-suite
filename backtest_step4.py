import pandas as pd
import numpy as np

# ── Load scored data ──────────────────────────────────────────────────────────
df = pd.read_pickle('backtest_scored.pkl')
print(f"Loaded {len(df)} rows")

# ── For each row, find price 30 trading days later ───────────────────────────
print("Computing 30-day forward returns per ticker...")
results = []

for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)

    # Shift price 30 rows forward (30 trading days)
    g['future_price'] = g['price'].shift(-30)
    g['future_return'] = (g['future_price'] - g['price']) / g['price'] * 100

    results.append(g)

df = pd.concat(results).reset_index(drop=True)

# Drop last 30 rows per ticker (no future data)
df = df.dropna(subset=['future_price'])
print(f"  Rows with future data: {len(df)}")

# ── Did the signal win? ───────────────────────────────────────────────────────
def is_win(row):
    if row['signal'] == 'ACHAT':
        return row['future_return'] > 0      # price went up
    elif row['signal'] == 'EVITER':
        return row['future_return'] < 0      # price went down
    else:
        return None                           # SURVEILLER not evaluated

df['win'] = df.apply(is_win, axis=1)

# ── Scorecard ─────────────────────────────────────────────────────────────────
print("\n── Overall Scorecard ────────────────────────────────────")

for sig in ['ACHAT', 'EVITER']:
    subset = df[df['signal'] == sig].dropna(subset=['win'])
    win_rate     = subset['win'].mean() * 100
    avg_return   = subset['future_return'].mean()
    med_return   = subset['future_return'].median()
    max_drawdown = subset['future_return'].min()
    count        = len(subset)
    print(f"\n  {sig} ({count} signals)")
    print(f"    Win rate:      {win_rate:.1f}%")
    print(f"    Avg return:    {avg_return:.2f}%")
    print(f"    Median return: {med_return:.2f}%")
    print(f"    Max drawdown:  {max_drawdown:.2f}%")

# ── By confidence band ────────────────────────────────────────────────────────
print("\n── ACHAT Win Rate by Confidence Band ────────────────────")
achat = df[df['signal'] == 'ACHAT'].dropna(subset=['win'])
achat['conf_band'] = pd.cut(
    achat['confidence'],
    bins=[0, 40, 70, 100],
    labels=['Low (<40)', 'Medium (40-70)', 'High (>70)']
)
print(achat.groupby('conf_band', observed=True)['win'].agg(
    count='count',
    win_rate=lambda x: f"{x.mean()*100:.1f}%"
))

# ── By year ───────────────────────────────────────────────────────────────────
print("\n── ACHAT Win Rate by Year ───────────────────────────────")
achat['year'] = achat['trade_date'].dt.year
print(achat.groupby('year')['win'].agg(
    count='count',
    win_rate=lambda x: f"{x.mean()*100:.1f}%"
).to_string())

# Save final backtest
df.to_pickle('backtest_final.pkl')
print("\n✅ Saved to backtest_final.pkl — Scorecard complete")
