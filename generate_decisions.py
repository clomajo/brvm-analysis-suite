import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import date
from brvm_classifier import BRVMClassifier

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

classifier = BRVMClassifier()
date_jour = date.today().isoformat()
CLASSIFICATION_VERSION = 'v1_officielle_20260401'

res = supabase.table('companies').select('id, symbol').execute()
companies = {row['id']: row['symbol'] for row in res.data}

print("Loading recent historical data (200 rows per ticker)...")
all_rows = []
company_ids = list(companies.keys())
for cid in company_ids:
    res = supabase.table('historical_data').select('company_id, trade_date, price, volume').eq('company_id', cid).order('trade_date', desc=True).limit(200).execute()
    if res.data:
        all_rows.extend(res.data)

df = pd.DataFrame(all_rows)
df['symbol'] = df['company_id'].map(companies)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df = df.dropna(subset=['price', 'symbol'])
df = df.sort_values(['symbol', 'trade_date']).reset_index(drop=True)
print(f"Loaded {len(df)} rows for {df['symbol'].nunique()} tickers")

# ── Calcul du regime de marche (BULL/BEAR) ────────────────────────────────────
def compute_market_regime(df, brvmc_id):
    brvmc = df[df['company_id'] == brvmc_id].copy().sort_values('trade_date').reset_index(drop=True)
    if len(brvmc) < 50:
        return 'UNKNOWN'
    prices = brvmc['price'].values
    sma50  = prices[-50:].mean()
    sma200 = prices[-200:].mean() if len(prices) >= 200 else prices.mean()
    current = prices[-1]
    if current > sma50 and current > sma200:
        return 'BULL'
    else:
        return 'BEAR'

brvmc_company = [cid for cid, sym in companies.items() if sym == 'BRVMC']
brvmc_id = brvmc_company[0] if brvmc_company else None
market_regime = compute_market_regime(df, brvmc_id) if brvmc_id else 'UNKNOWN'
print(f"Market regime: {market_regime}")

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(series, period=14):
    high = series.rolling(2).max()
    low = series.rolling(2).min()
    return (high - low).rolling(period).mean()

def calc_macd_bull(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd > signal

print("Generating decisions...")
decisions = []

for symbol, group in df.groupby('symbol'):
    g = group.copy().reset_index(drop=True)
    if len(g) < 55:
        print(f"  Skipping {symbol} — insufficient data ({len(g)} rows)")
        continue

    g['rsi'] = calc_rsi(g['price'])
    g['sma20'] = g['price'].rolling(20).mean()
    g['sma50'] = g['price'].rolling(50).mean()
    g['atr'] = calc_atr(g['price'])
    g['atr_pct'] = (g['atr'] / g['price'] * 100).clip(upper=20.0)
    g['vol_avg20'] = g['volume'].rolling(20).mean()
    g['vol_ratio'] = g['volume'] / g['vol_avg20'].replace(0, np.nan)
    g['macd_bull'] = calc_macd_bull(g['price'])

    # Supprimer les lignes avec des valeurs manquantes
    g_clean = g.dropna(subset=['rsi', 'sma20', 'sma50', 'atr', 'vol_ratio'])
    
    # Vérifier qu'il reste des lignes après nettoyage
    if len(g_clean) == 0:
        print(f"  Skipping {symbol} — no valid data after cleaning")
        continue

    try:
        row = g_clean.iloc[-1]
    except IndexError:
        print(f"  Skipping {symbol} — iloc[-1] failed (empty after dropna)")
        continue

    tier = classifier.get_tier(symbol, date_jour)
    seuil_achat = classifier.get_seuil_achat(symbol, date_jour)
    is_eligible = (tier != 'illiquid')

    rsi_score = float(row['rsi'])
    trend_sma20 = (row['price'] - row['sma20']) / row['sma20'] * 100
    trend_sma50 = (row['price'] - row['sma50']) / row['sma50'] * 100
    trend_raw = (trend_sma20 * 0.6) + (trend_sma50 * 0.4)
    trend_score = float(np.clip(50 + trend_raw * 5, 0, 100))
    vol_score = float(np.clip(row['vol_ratio'] * 50, 0, 100))
    vol_regime_score = float(np.clip(100 - (row['atr_pct'] * 10), 0, 100))

    if is_eligible:
        score = (rsi_score*0.20 + trend_score*0.40 + vol_score*0.25 + vol_regime_score*0.15)
    else:
        score = (rsi_score*0.30 + trend_score*0.30 + vol_score*0.10 + vol_regime_score*0.30)
    score = int(np.clip(round(score), 0, 100))

    if is_eligible:
        if score >= seuil_achat and market_regime != "BEAR":
            signal = 'ACHAT'
        elif score >= 40:
            signal = 'SURVEILLER'
        else:
            signal = 'EVITER'
    else:
        if score >= 72:
            signal = 'SURVEILLER'
        elif score >= 45:
            signal = 'SURVEILLER'
        else:
            signal = 'EVITER'

    rsi_bull = float(row['rsi']) > 50
    trend_bull = float(row['price']) > float(row['sma20'])
    macd_bull = bool(row['macd_bull'])
    consistency = sum([rsi_bull, trend_bull, macd_bull]) / 3 * 100
    MEDIAN_VOL = 1277
    liquidity_score = min(100, float(row['vol_avg20']) / MEDIAN_VOL * 100)
    confidence = round(100*0.40 + consistency*0.40 + liquidity_score*0.20)
    conf_label = 'Confiance élevée' if confidence >= 70 else ('Confiance modérée' if confidence >= 40 else 'Signal faible')

    close = float(row['price'])
    atr_pct = float(row['atr_pct']) / 100
    upside = round(close * (1 + 2.5 * atr_pct), 2)
    downside = round(close * (1 - 2.0 * atr_pct), 2)
    upside_pct = round((upside - close) / close * 100, 1)
    downside_pct = round((close - downside) / close * 100, 1)
    risk_reward = round(upside_pct / downside_pct, 2) if downside_pct > 0 else None

    decisions.append({
        'ticker': symbol,
        'date': date_jour,
        'score': score,
        'signal': signal,
        'liquidity_tier': tier,
        'confidence': confidence,
        'confidence_label': conf_label,
        'upside_target': upside,
        'downside_target': downside,
        'upside_pct': upside_pct,
        'downside_pct': downside_pct,
        'risk_reward': risk_reward,
        'data_completeness': 'High',
        'seuil_applique': seuil_achat if is_eligible else None,
        'classification_version': CLASSIFICATION_VERSION,
        'market_regime': market_regime
    })

print(f"{len(decisions)} decisions generated")

if len(decisions) > 0:
    preview = pd.DataFrame(decisions).sort_values('score', ascending=False)
    print("\nSignal breakdown:")
    print(preview['signal'].value_counts())
    print("\nTier breakdown:")
    print(preview['liquidity_tier'].value_counts())

    print("\nInserting into brvm_decisions...")
    supabase.table('brvm_decisions').upsert(decisions, on_conflict='ticker,date').execute()
    print(f"✅ {len(decisions)} decisions inserted for {date_jour} (version: {CLASSIFICATION_VERSION})")
else:
    print("⚠️ No decisions generated")
