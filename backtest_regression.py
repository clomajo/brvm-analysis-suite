# backtest_regression.py
# Rejoue le score V1 sur 10 ans et teste chaque composante
import os, sys, requests
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

try:
    import statsmodels.api as sm
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler
    HAS_ML = True
except ImportError:
    print("pip install scikit-learn statsmodels --break-system-packages")
    HAS_ML = False

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL","").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
HORIZONS = [5, 10, 20, 30]
EXCLUDED = ["ONTBF","SICC","CFAC","SAFC","BRVMC","BRVM30","BRVM_CI"]
MEDIAN_VOL = 1277

def fetch_all(table, params=None):
    results, offset = [], 0
    while True:
        p = {"limit": 1000, "offset": offset}
        if params: p.update(params)
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=p, timeout=30)
        if r.status_code not in (200,206):
            print(f"ERREUR {table}: {r.status_code} {r.text[:150]}")
            break
        batch = r.json()
        if not batch: break
        results.extend(batch)
        offset += len(batch)
        if len(batch) < 1000: break
    return results

def fetch_companies():
    print("Chargement companies...")
    rows = fetch_all("companies", {"select":"id,symbol"})
    return {r["id"]: r["symbol"] for r in rows}

def fetch_prices(companies):
    print("Chargement historical_data (10 ans)...")
    rows = fetch_all("historical_data", {"select":"company_id,trade_date,price,volume","order":"trade_date.asc"})
    df = pd.DataFrame(rows)
    df["ticker"] = df["company_id"].map(companies)
    df = df.dropna(subset=["ticker"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["price"])
    print(f"  {len(df)} lignes pour {df['ticker'].nunique()} tickers")
    return df

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd_bull(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return (macd > signal).astype(int)

def calc_atr_pct(series, period=14):
    high = series.rolling(2).max()
    low = series.rolling(2).min()
    atr = (high - low).rolling(period).mean()
    return (atr / series * 100).clip(upper=20.0)

def compute_brvmc_regime(prices_df):
    print("  Calcul regime BULL/BEAR BRVMC...")
    brvmc = prices_df[prices_df["ticker"]=="BRVMC"].copy().sort_values("trade_date")
    if brvmc.empty:
        print("  BRVMC absent — regime BULL par defaut")
        return {}
    brvmc["sma50"]  = brvmc["price"].rolling(50).mean()
    brvmc["sma200"] = brvmc["price"].rolling(200).mean()
    brvmc["regime"] = np.where(
        (brvmc["price"] > brvmc["sma50"]) & (brvmc["price"] > brvmc["sma200"]),
        "BULL", "BEAR"
    )
    return dict(zip(brvmc["trade_date"], brvmc["regime"]))

def regime_at(regime_map, date):
    dates = sorted(regime_map.keys())
    past = [d for d in dates if d <= date]
    if not past: return "BULL"
    return regime_map[past[-1]]

def generate_signals(df, regime_map):
    print("Calcul des signaux sur 10 ans (peut prendre 2-3 minutes)...")
    all_signals = []
    tickers = [t for t in df["ticker"].unique() if t not in EXCLUDED]
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        if i % 10 == 0:
            print(f"  {i}/{total} tickers traites...")
        g = df[df["ticker"]==ticker].copy().sort_values("trade_date").reset_index(drop=True)
        if len(g) < 55:
            continue

        g["rsi"]         = calc_rsi(g["price"])
        g["sma20"]       = g["price"].rolling(20).mean()
        g["sma50"]       = g["price"].rolling(50).mean()
        g["atr_pct"]     = calc_atr_pct(g["price"])
        g["vol_avg20"]   = g["volume"].rolling(20).mean()
        g["vol_ratio"]   = g["volume"] / g["vol_avg20"].replace(0, np.nan)
        g["macd_bull"]   = calc_macd_bull(g["price"])

        g = g.dropna(subset=["rsi","sma20","atr_pct","vol_ratio"]).reset_index(drop=True)

        # Calculer composantes et signaux pour chaque jour
        for idx in range(len(g)):
            row = g.iloc[idx]
            date = row["trade_date"]

            rsi_score    = float(row["rsi"])
            trend_sma20  = (row["price"] - row["sma20"]) / row["sma20"] * 100
            sma50        = row["sma50"] if pd.notna(row["sma50"]) else row["sma20"]
            trend_sma50  = (row["price"] - sma50) / sma50 * 100
            trend_raw    = trend_sma20*0.6 + trend_sma50*0.4
            trend_score  = float(np.clip(50 + trend_raw*5, 0, 100))
            vol_score    = float(np.clip(row["vol_ratio"]*50, 0, 100))
            vol_regime   = float(np.clip(100 - row["atr_pct"]*10, 0, 100))
            liq_score    = min(100, float(row["vol_avg20"]) / MEDIAN_VOL * 100)
            macd         = int(row["macd_bull"])

            # Score V1 complet
            score_v1     = int(np.clip(round(rsi_score*0.20 + trend_score*0.40 + vol_score*0.25 + vol_regime*0.15), 0, 100))

            # Scores alternatifs (pour test ablation)
            score_no_trend = int(np.clip(round(rsi_score*0.27 + vol_score*0.40 + vol_regime*0.33), 0, 100))
            score_rsi_only = int(np.clip(round(rsi_score), 0, 100))
            score_trend_only = int(np.clip(round(trend_score), 0, 100))
            score_liq_trend = int(np.clip(round(trend_score*0.50 + liq_score*0.50), 0, 100))

            # Regime
            regime = regime_at(regime_map, date)
            regime_bull = 1 if regime == "BULL" else 0

            # Signal V1
            if score_v1 >= 65 and regime == "BULL":
                signal = "ACHAT"
            elif score_v1 < 30:
                signal = "EVITER"
            else:
                continue  # SURVEILLER — exclu de l'analyse

            # Prix futur
            future_prices = {}
            for h in HORIZONS:
                future_rows = g[g.index > idx].head(h)
                future_prices[h] = future_rows.iloc[-1]["price"] if len(future_rows) == h else None

            p0 = row["price"]
            if p0 <= 0: continue

            row_data = {
                "ticker": ticker,
                "date": date,
                "signal": signal,
                "price": p0,
                "regime_bull": regime_bull,
                "rsi_score": round(rsi_score, 1),
                "trend_score": round(trend_score, 1),
                "vol_score": round(vol_score, 1),
                "vol_regime": round(vol_regime, 1),
                "liq_score": round(liq_score, 1),
                "macd": macd,
                "score_v1": score_v1,
                "score_no_trend": score_no_trend,
                "score_rsi_only": score_rsi_only,
                "score_trend_only": score_trend_only,
                "score_liq_trend": score_liq_trend,
            }

            for h in HORIZONS:
                p1 = future_prices[h]
                if p1 is None or p0 == 0:
                    row_data[f"cj{h}"] = None
                    continue
                chg = (p1 - p0) / p0
                if abs(chg) > 0.5:
                    row_data[f"cj{h}"] = None
                    continue
                if signal == "ACHAT":
                    row_data[f"cj{h}"] = 1 if chg > 0 else 0
                else:
                    row_data[f"cj{h}"] = 1 if chg < 0 else 0

            all_signals.append(row_data)

    df_out = pd.DataFrame(all_signals)
    print(f"  {len(df_out)} signaux generes")
    return df_out

def compare_scores(df):
    print("\n" + "="*70)
    print("COMPARAISON DES SCORES — HIT RATE PAR HORIZON")
    print("="*70)

    score_cols = ["score_v1","score_no_trend","score_rsi_only","score_trend_only","score_liq_trend"]
    labels = {
        "score_v1":         "V1 complet  (rsi*20+trend*40+vol*25+vol_reg*15)",
        "score_no_trend":   "Sans trend  (rsi*27+vol*40+vol_reg*33)",
        "score_rsi_only":   "RSI seul",
        "score_trend_only": "Trend seul",
        "score_liq_trend":  "Liq+Trend   (trend*50+liq*50)",
    }

    for h in HORIZONS:
        col = f"cj{h}"
        print(f"\nJ+{h}")
        print(f"  {'Score':<45} {'HR':>6}  {'N':>6}  {'AUC':>6}")
        print(f"  {'-'*62}")
        for sc in score_cols:
            sub = df[[sc, col]].dropna()
            if len(sub) < 30:
                print(f"  {labels[sc]:<45} {'N/A':>6}  {len(sub):>6}")
                continue
            hr = round(sub[col].mean()*100, 1)
            auc = None
            try:
                Xs = StandardScaler().fit_transform(sub[[sc]].values)
                lr = LogisticRegression(max_iter=200, random_state=42)
                lr.fit(Xs, sub[col].values)
                auc = round(roc_auc_score(sub[col].values, lr.predict_proba(Xs)[:,1]), 3)
            except: pass
            flag = " <-- MEILLEUR" if auc and auc == max([0]+[auc]) else ""
            print(f"  {labels[sc]:<45} {str(hr)+'%':>6}  {len(sub):>6}  {str(auc) if auc else 'N/A':>6}")

def regression_composantes(df, h=10):
    print("\n" + "="*70)
    print(f"REGRESSION LOGISTIQUE — COMPOSANTES INDIVIDUELLES (J+{h})")
    print("="*70)
    col = f"cj{h}"
    feats = ["rsi_score","trend_score","vol_score","vol_regime","liq_score","macd","regime_bull"]
    sub = df[feats+[col]].dropna()
    if len(sub) < 50:
        print(f"Trop peu de donnees ({len(sub)})")
        return
    print(f"N = {len(sub)} signaux")
    X = sub[feats].values; y = sub[col].values
    Xs = StandardScaler().fit_transform(X)
    try:
        res = sm.Logit(y, sm.add_constant(Xs)).fit(disp=False, maxiter=300)
        names = ["const"]+feats
        print(f"\n  {'Variable':<20} {'Coeff':>8}  {'p-val':>8}  Statut")
        print(f"  {'-'*50}")
        for name, coef, pval in zip(names, res.params, res.pvalues):
            if name == "const": continue
            status = "SIGNAL" if pval<=0.05 else ("suspect" if pval<=0.10 else "BRUIT")
            print(f"  {name:<20} {coef:>+8.4f}  {pval:>8.4f}  {status}")
        print(f"\n  AIC={round(res.aic,2)}  Pseudo-R2={round(res.prsquared,4)}")
    except Exception as e:
        print(f"Erreur regression: {e}")

def hit_rate_by_regime(df):
    print("\n" + "="*70)
    print("HIT RATE PAR REGIME BULL/BEAR")
    print("="*70)
    for regime, label in [(1,"BULL"),(0,"BEAR")]:
        sub = df[df["regime_bull"]==regime]
        print(f"\n  {label} ({len(sub)} signaux)")
        for h in HORIZONS:
            col = f"cj{h}"
            n = sub[col].notna().sum()
            hr = round(sub[col].mean()*100,1) if n>0 else None
            print(f"    J+{h}: {str(hr)+'%' if hr else 'N/A':>8}  (n={n})")

def main():
    print("="*70)
    print("BRVM Analytics — Backtest Regression 10 ans")
    print(datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("="*70)
    if not HAS_ML: sys.exit(1)

    companies = fetch_companies()
    prices_df = fetch_prices(companies)

    print("\nCalcul regime BRVMC...")
    regime_map = compute_brvmc_regime(prices_df)

    signals_df = generate_signals(prices_df, regime_map)

    if signals_df.empty:
        print("Aucun signal genere — verifier les donnees")
        sys.exit(1)

    print(f"\nDataset backtest:")
    print(f"  ACHAT  : {(signals_df['signal']=='ACHAT').sum()}")
    print(f"  EVITER : {(signals_df['signal']=='EVITER').sum()}")
    print(f"  Tickers: {signals_df['ticker'].nunique()}")
    print(f"  Periode: {signals_df['date'].min().date()} -> {signals_df['date'].max().date()}")
    for h in HORIZONS:
        n = signals_df[f"cj{h}"].notna().sum()
        print(f"  J+{h}: {n} verifiables")

    compare_scores(signals_df)
    regression_composantes(signals_df, h=10)
    hit_rate_by_regime(signals_df)

    signals_df.to_csv("backtest_10ans.csv", index=False)
    print("\nbacktest_10ans.csv sauvegarde")
    print("Termine.")

if __name__=="__main__":
    main()
