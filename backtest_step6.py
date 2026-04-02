import pandas as pd
import numpy as np

df = pd.read_pickle('backtest_v2.pkl')
MEDIAN_VOL = df['vol_avg20'].median()

# ── Build 60-day forward window per ticker ────────────────────────────────────
print("Computing 60-day forward windows...")
results = []

for symbol, group in df.groupby('symbol'):
    g = group.copy().sort_values('trade_date').reset_index(drop=True)
    prices = g['price'].values

    max_gain_60    = []
    max_loss_60    = []
    hit_upside     = []
    hit_downside   = []

    for i in range(len(g)):
        window = prices[i+1:i+61]  # next 60 trading days
        if len(window) < 10:
            max_gain_60.append(np.nan)
            max_loss_60.append(np.nan)
            hit_upside.append(np.nan)
            hit_downside.append(np.nan)
            continue

        base        = prices[i]
        peak        = (np.max(window) - base) / base * 100
        trough      = (np.min(window) - base) / base * 100
        up_target   = float(g.iloc[i]['upside_target'])
        down_target = float(g.iloc[i]['downside_target'])

        max_gain_60.append(peak)
        max_loss_60.append(trough)
        hit_upside.append(int(np.max(window) >= up_target))
        hit_downside.append(int(np.min(window) <= down_target))

    g['max_gain_60']  = max_gain_60
    g['max_loss_60']  = max_loss_60
    g['hit_upside']   = hit_upside
    g['hit_downside'] = hit_downside
    results.append(g)

df = pd.concat(results).reset_index(drop=True)
df = df.dropna(subset=['max_gain_60'])
print(f"  Rows with 60-day window: {len(df)}")

# ── Analysis 1: ATR target hit rate by signal ─────────────────────────────────
print("\n══ ATR TARGET HIT RATE (60 days) ════════════════════════")
for sig in ['ACHAT', 'SURVEILLER', 'EVITER']:
    s = df[df['signal_v2'] == sig]
    upside_hit   = s['hit_upside'].mean() * 100
    downside_hit = s['hit_downside'].mean() * 100
    avg_max_gain = s['max_gain_60'].mean()
    avg_max_loss = s['max_loss_60'].mean()
    print(f"\n  {sig} ({len(s):,} signals)")
    print(f"    Hit upside target:   {upside_hit:.1f}%")
    print(f"    Hit downside target: {downside_hit:.1f}%")
    print(f"    Avg max gain (60d):  +{avg_max_gain:.2f}%")
    print(f"    Avg max loss (60d):  {avg_max_loss:.2f}%")

# ── Analysis 2: High conviction signals ───────────────────────────────────────
print("\n══ HIGH CONVICTION ACHAT (score≥65, confidence≥70) ══════")
hc = df[(df['signal_v2']=='ACHAT') & (df['confidence']>=70)]
print(f"  Signals: {len(hc):,}")
print(f"  Hit upside target:   {hc['hit_upside'].mean()*100:.1f}%")
print(f"  Avg max gain (60d):  +{hc['max_gain_60'].mean():.2f}%")
print(f"  Avg max loss (60d):  {hc['max_loss_60'].mean():.2f}%")
print(f"  Win rate (30d):      {hc['win_v2'].mean()*100:.1f}%")

print("\n── High conviction by year ──────────────────────────────")
hc = hc.copy()
hc['year'] = hc['trade_date'].dt.year
print(hc.groupby('year').agg(
    count=('win_v2','count'),
    win_rate_30d=('win_v2', lambda x: f"{x.mean()*100:.1f}%"),
    hit_upside=('hit_upside', lambda x: f"{x.mean()*100:.1f}%"),
    avg_max_gain=('max_gain_60', lambda x: f"+{x.mean():.2f}%")
).to_string())

# ── Analysis 3: Liquid high conviction recent ─────────────────────────────────
print("\n══ LIQUID + HIGH CONVICTION + 2022+ ═════════════════════")
recent_hc = df[
    (df['signal_v2']=='ACHAT') &
    (df['confidence']>=70) &
    (df['is_liquid']==True) &
    (df['trade_date'].dt.year >= 2022)
].copy()
print(f"  Signals: {len(recent_hc):,}")
print(f"  Hit upside target:   {recent_hc['hit_upside'].mean()*100:.1f}%")
print(f"  Avg max gain (60d):  +{recent_hc['max_gain_60'].mean():.2f}%")
print(f"  Avg max loss (60d):  {recent_hc['max_loss_60'].mean():.2f}%")
recent_hc['year'] = recent_hc['trade_date'].dt.year
print(recent_hc.groupby('year').agg(
    count=('win_v2','count'),
    hit_upside=('hit_upside', lambda x: f"{x.mean()*100:.1f}%"),
    avg_max_gain=('max_gain_60', lambda x: f"+{x.mean():.2f}%")
).to_string())

df.to_pickle('backtest_v3.pkl')
print("\n✅ Saved to backtest_v3.pkl")
