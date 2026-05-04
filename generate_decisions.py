import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import date
from brvm_classifier import BRVMClassifier

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
# ── Chargement signaux fondamentaux Mistral ───────────────────────────────────
print("Loading fundamental signals...")
fund_res = supabase.table('company_fundamentals')    .select('ticker, signal_fondamental, croissance_ca_pct, resume_fondamental')    .not_.is_('signal_fondamental', 'null')    .execute()
fund_signals = {row['ticker']: row for row in fund_res.data}
print(f"  {len(fund_signals)} fundamental signals loaded")

# ── Chargement signaux fondamentaux Mistral ───────────────────────────────────
print("Loading fundamental signals...")
fund_res = supabase.table('company_fundamentals')    .select('ticker, signal_fondamental, croissance_ca_pct, resume_fondamental')    .not_.is_('signal_fondamental', 'null')    .execute()
fund_signals = {row['ticker']: row for row in fund_res.data}
print(f"  {len(fund_signals)} fundamental signals loaded")


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

# ── Mapping pays par ticker ──────────────────────────────────────────────────
TICKER_COUNTRY = {
    # Côte d'Ivoire
    'ABJC':'CI','BICC':'CI','BNBC':'CI','BOAC':'CI','CABC':'CI','CFAC':'CI',
    'CIEC':'CI','ECOC':'CI','ETIT':'TG','FTSC':'CI','LNBB':'BJ','NEIC':'CI',
    'NSBC':'CI','NTLC':'CI','ORAC':'CI','ORGT':'TG','PALC':'CI','PRSC':'CI',
    'SAFC':'CI','SCRC':'CI','SDCC':'CI','SDSC':'CI','SEMC':'CI','SGBC':'CI',
    'SHEC':'CI','SIBC':'CI','SICC':'CI','SIVC':'CI','SLBC':'CI','SMBC':'CI',
    'SOGC':'CI','SPHC':'CI','STAC':'CI','STBC':'CI','TTLC':'CI','UNLC':'CI',
    'UNXC':'CI',
    # Sénégal
    'SNTS':'SN','TTLS':'SN',
    # Bénin
    'BOAB':'BJ',
    # Burkina Faso
    'BOABF':'BF','CBIBF':'BF','ONTBF':'BF',
    # Mali
    'BOAM':'ML',
    # Niger
    'BOAN':'NE',
    # Sénégal
    'BOAS':'SN',
}

GEO_MULTIPLIER = {
    'CI': 1.00, 'SN': 0.95, 'BJ': 0.95,
    'TG': 0.90, 'BF': 0.75, 'ML': 0.70, 'NE': 0.65
}

SECTOR_MAP = {
    # Finance
    'BICC':'FINANCE','BOAB':'FINANCE','BOABF':'FINANCE','BOAC':'FINANCE',
    'BOAM':'FINANCE','BOAN':'FINANCE','BOAS':'FINANCE','CBIBF':'FINANCE',
    'ECOC':'FINANCE','LNBB':'FINANCE','NSBC':'FINANCE','ORGT':'FINANCE',
    'SAFC':'FINANCE','SGBC':'FINANCE','SIBC':'FINANCE',
    # Agro
    'PALC':'AGRO','SPHC':'AGRO','SICC':'AGRO','SOGC':'AGRO','SCRC':'AGRO',
}

# Charger les fondamentaux depuis Supabase
print("Loading fundamentals for score_v2...")
fund_data = {}
try:
    fund_rows = supabase.table('company_fundamentals').select(
        'ticker,fiscal_year,pe_ratio,roe,revenue_growth,operating_margin,dividend_yield'
    ).eq('fiscal_year', 'FY2025').execute()
    for row in fund_rows.data:
        fund_data[row['ticker']] = row
    # Fallback to FY2024 for missing FY2025
    fund_rows_2024 = supabase.table('company_fundamentals').select(
        'ticker,fiscal_year,pe_ratio,roe,revenue_growth,operating_margin,dividend_yield'
    ).eq('fiscal_year', 'FY2024').execute()
    for row in fund_rows_2024.data:
        if row['ticker'] not in fund_data:
            fund_data[row['ticker']] = row
    print(f"  Loaded fundamentals for {len(fund_data)} tickers")
except Exception as e:
    print(f"  Warning: Could not load fundamentals: {e}")

def calc_fundamental_score(ticker):
    """
    Score fondamental 0-100 basé sur PE, ROE, croissance, marge, dividende.
    Retourne (score, mode) où mode = 'FULL'/'PARTIAL'/'NONE'
    """
    f = fund_data.get(ticker, {})
    if not f:
        return 50.0, 'NONE'

    scores = []
    weights = []

    # PE Ratio (25pts) — plus bas = mieux pour value
    pe = f.get('pe_ratio')
    if pe and pe > 0:
        if pe < 8:      pe_s = 100
        elif pe < 12:   pe_s = 80
        elif pe < 18:   pe_s = 60
        elif pe < 25:   pe_s = 40
        else:           pe_s = 20
        scores.append(pe_s); weights.append(25)

    # ROE (25pts)
    roe = f.get('roe')
    if roe:
        if roe > 25:    roe_s = 100
        elif roe > 15:  roe_s = 80
        elif roe > 10:  roe_s = 60
        elif roe > 5:   roe_s = 40
        else:           roe_s = 20
        scores.append(roe_s); weights.append(25)

    # Croissance revenue (20pts)
    rev_g = f.get('revenue_growth')
    if rev_g is not None:
        if rev_g > 15:   rev_s = 100
        elif rev_g > 8:  rev_s = 80
        elif rev_g > 3:  rev_s = 60
        elif rev_g > 0:  rev_s = 40
        else:            rev_s = 20
        scores.append(rev_s); weights.append(20)

    # Marge opérationnelle (15pts)
    margin = f.get('operating_margin')
    if margin:
        if margin > 30:    m_s = 100
        elif margin > 20:  m_s = 80
        elif margin > 10:  m_s = 60
        elif margin > 5:   m_s = 40
        else:              m_s = 20
        scores.append(m_s); weights.append(15)

    # Dividende yield (15pts)
    div = f.get('dividend_yield')
    if div:
        if div > 6:    div_s = 100
        elif div > 4:  div_s = 80
        elif div > 2:  div_s = 60
        elif div > 0:  div_s = 40
        else:          div_s = 20
        scores.append(div_s); weights.append(15)

    if not scores:
        return 50.0, 'NONE'

    total_weight = sum(weights)
    fund_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    mode = 'FULL' if total_weight >= 70 else 'PARTIAL'
    return round(fund_score, 1), mode

def calc_score_v2(symbol, tech_score):
    """
    Score v2 = (tech × ratio_tech + fund × ratio_fund) × geo_multiplier
    """
    fund_score, fund_mode = calc_fundamental_score(symbol)
    sector = SECTOR_MAP.get(symbol, 'OTHER')
    country = TICKER_COUNTRY.get(symbol, 'CI')
    geo = GEO_MULTIPLIER.get(country, 1.00)

    # Pondération selon disponibilité et secteur
    if fund_mode == 'NONE':
        ratio_tech, ratio_fund = 1.00, 0.00
    elif fund_mode == 'PARTIAL':
        ratio_tech, ratio_fund = 0.80, 0.20
    elif sector == 'FINANCE':
        ratio_tech, ratio_fund = 0.60, 0.40
    elif sector == 'AGRO':
        ratio_tech, ratio_fund = 0.80, 0.20
    else:
        ratio_tech, ratio_fund = 0.70, 0.30

    raw = (tech_score * ratio_tech + fund_score * ratio_fund) * geo

    # Malus liquidité déjà dans score technique — pas de double comptage
    return round(raw, 1), fund_score, fund_mode, geo, ratio_tech, ratio_fund

print("Generating decisions...")
decisions = []

EXCLUDE = {'BRVM30', 'BRVMC', 'BRVM_CI'}
for symbol, group in df.groupby('symbol'):
    if symbol in EXCLUDE:
        continue
    g = group.copy().reset_index(drop=True)
    if len(g) < 30:
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
    g_clean = g.dropna(subset=['rsi', 'sma20', 'atr', 'vol_ratio'])
    
    # Vérifier qu'il reste des lignes après nettoyage
    if len(g_clean) == 0:
        print(f"  Skipping {symbol} — no valid data after cleaning")
        continue

    try:
        row = g_clean.iloc[-1]
    except IndexError:
        print(f"  Skipping {symbol} — iloc[-1] failed (empty after dropna)")
        continue

    data_completeness = 'High' if len(g_clean) >= 55 else 'Medium' if len(g_clean) >= 30 else 'Low'
    tier = classifier.get_tier(symbol, date_jour)
    seuil_achat = classifier.get_seuil_achat(symbol, date_jour)
    is_eligible = (tier != 'illiquid')

    rsi_score = float(row['rsi'])
    trend_sma20 = (row['price'] - row['sma20']) / row['sma20'] * 100
    _sma50 = row['sma50'] if ('sma50' in row.index and row['sma50'] == row['sma50']) else None
    trend_sma50 = (row['price'] - _sma50) / _sma50 * 100 if _sma50 else trend_sma20
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


    # ── Signal fondamental Mistral ─────────────────────────────────────────
    fund = fund_signals.get(symbol, {})
    signal_fond = fund.get('signal_fondamental')
    croissance = fund.get('croissance_ca_pct')
    resume = fund.get('resume_fondamental')

    # Signal combiné
    if signal == 'ACHAT' and signal_fond == 'positif':
        signal_combine = 'CONVICTION FORTE'
    elif signal == 'ACHAT' and signal_fond == 'négatif':
        signal_combine = 'PRUDENCE'
    elif signal == 'ACHAT' and signal_fond == 'neutre':
        signal_combine = 'ACHAT MODÉRÉ'
    elif signal == 'SURVEILLER' and signal_fond == 'positif':
        signal_combine = 'À SURVEILLER +'
    elif signal == 'EVITER' and signal_fond == 'négatif':
        signal_combine = 'ÉVITER FORT'
    else:
        signal_combine = signal

    # ── Signal fondamental Mistral ─────────────────────────────────────────
    fund = fund_signals.get(symbol, {})
    signal_fond = fund.get('signal_fondamental')
    croissance = fund.get('croissance_ca_pct')
    resume = fund.get('resume_fondamental')

    if signal == 'ACHAT' and signal_fond == 'positif':
        signal_combine = 'CONVICTION FORTE'
    elif signal == 'ACHAT' and signal_fond in ['negatif', 'négatif']:
        signal_combine = 'PRUDENCE'
    elif signal == 'ACHAT' and signal_fond == 'neutre':
        signal_combine = 'ACHAT MODERE'
    elif signal == 'SURVEILLER' and signal_fond == 'positif':
        signal_combine = 'A SURVEILLER +'
    elif signal == 'EVITER' and signal_fond in ['negatif', 'négatif']:
        signal_combine = 'EVITER FORT'
    else:
        signal_combine = signal
    decisions.append({
        'ticker': symbol,
        'date': date_jour,
        'score': score,
        'signal': signal,
            'data_completeness': data_completeness,
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
        'market_regime': market_regime,
        'signal_fondamental': signal_fond,
        'croissance_ca_pct': croissance,
        'resume_fondamental': resume,
        'signal_combine': signal_combine,
        'signal_fondamental': signal_fond,
        'croissance_ca_pct': croissance,
        'resume_fondamental': resume,
        'signal_combine': signal_combine
    })

    # ── Score v2 (fondamental + géopolitique) ──────────────────────────────
    s_v2, f_score, f_mode, geo, r_tech, r_fund = calc_score_v2(symbol, score)
    decisions[-1]['score_v2'] = s_v2
    decisions[-1]['fundamental_score_v2'] = f_score
    decisions[-1]['fund_mode'] = f_mode
    decisions[-1]['geo_multiplier'] = geo
    decisions[-1]['ratio_tech'] = r_tech
    decisions[-1]['ratio_fund'] = r_fund

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
