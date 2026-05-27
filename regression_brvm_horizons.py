# v2 colonnes reelles
import os, sys, requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    import statsmodels.api as sm
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, roc_curve
    from sklearn.preprocessing import StandardScaler
    HAS_ML = True
except ImportError:
    HAS_ML = False

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL","").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
HORIZONS = [5, 10, 20, 30, 60, 90]
EXCLUDED = ["ONTBF","SICC","CFAC","SAFC"]
SEP = "-"*70

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

def fetch_decisions():
    print("Chargement brvm_decisions...")
    rows = fetch_all("brvm_decisions", {"select":"id,ticker,date,score,signal,liquidity_tier,confidence,market_regime","order":"date.asc"})
    df = pd.DataFrame(rows)
    print(f"  {len(df)} signaux")
    return df

def fetch_companies():
    print("Chargement companies...")
    rows = fetch_all("companies", {"select":"id,symbol"})
    return pd.DataFrame(rows)

def fetch_prices():
    print("Chargement historical_data...")
    rows = fetch_all("historical_data", {"select":"company_id,trade_date,price,volume","order":"trade_date.asc"})
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    print(f"  {len(df)} lignes")
    return df

def build_lookup(prices_df, comp_df):
    ticker_map = dict(zip(comp_df["id"], comp_df["symbol"]))
    df = prices_df.copy()
    df["ticker"] = df["company_id"].map(ticker_map)
    df = df.dropna(subset=["ticker"])
    return {t: g.sort_values("trade_date").reset_index(drop=True) for t,g in df.groupby("ticker")}

def price_at(lookup, ticker, ref_date, fwd=True):
    if ticker not in lookup: return None
    df = lookup[ticker]
    sub = df[df["trade_date"] >= ref_date] if fwd else df[df["trade_date"] <= ref_date]
    if sub.empty: return None
    return sub.iloc[0]["price"] if fwd else sub.iloc[-1]["price"]

def vol_20d(lookup, ticker, ref_date):
    if ticker not in lookup: return 0.0
    df = lookup[ticker]
    win = df[df["trade_date"] < ref_date].tail(20)
    return win["volume"].mean() if not win.empty else 0.0

def correct(signal, p0, p1):
    if not signal or signal=="SURVEILLER" or p0 is None or p1 is None or p0==0: return None
    chg = (p1-p0)/p0
    if abs(chg)>0.5: return None
    if signal=="ACHAT": return 1 if chg>0 else 0
    if signal=="EVITER": return 1 if chg<0 else 0
    return None

def build_dataset(dec_df, pri_df, com_df):
    print("Construction dataset...")
    df = dec_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[~df["ticker"].isin(EXCLUDED)]
    df = df[df["signal"]!="SURVEILLER"]
    for c in ["score","confidence"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["regime_bull"]  = (df["market_regime"]=="BULL").astype(int)
    df["liq_prestige"] = (df["liquidity_tier"]=="prestige").astype(int)
    df["liq_illiquid"] = (df["liquidity_tier"]=="illiquid").astype(int)
    lookup = build_lookup(pri_df, com_df)
    print("  Volumes et prix signal...")
    df["vol_20d"]      = df.apply(lambda r: vol_20d(lookup,r["ticker"],r["date"]), axis=1)
    df["price_signal"] = df.apply(lambda r: price_at(lookup,r["ticker"],r["date"],fwd=False), axis=1)
    for h in HORIZONS:
        print(f"  J+{h}...")
        tgt = df["date"] + pd.to_timedelta(h, unit="D")
        df[f"pj{h}"] = [price_at(lookup,row.ticker,td,fwd=True) for row,td in zip(df.itertuples(index=False),tgt)]
        df[f"cj{h}"] = df.apply(lambda r,h=h: correct(r["signal"],r["price_signal"],r[f"pj{h}"]), axis=1)
    print(f"  {len(df)} signaux")
    return df, lookup

def get_features(df):
    cands = ["score","confidence","regime_bull","liq_prestige","liq_illiquid"]
    return [c for c in cands if c in df.columns and df[c].notna().sum()/max(len(df),1)>0.5]

def run_reg(df, h, feats):
    col = f"cj{h}"
    sub = df[feats+[col]].dropna()
    n = len(sub)
    hr = round(sub[col].mean()*100,1) if n>0 else 0
    if n<30: return {"horizon":h,"n":n,"hit_rate":hr,"note":f"trop peu ({n})"}
    X = sub[feats].values; y = sub[col].values
    Xs = StandardScaler().fit_transform(X)
    coefs,pvals,aic,pr2,auc = {},{},None,None,None
    try:
        res = sm.Logit(y, sm.add_constant(Xs)).fit(disp=False,maxiter=300)
        names = ["const"]+feats
        coefs = {k:round(v,4) for k,v in zip(names,res.params) if k!="const"}
        pvals = {k:round(v,4) for k,v in zip(names,res.pvalues) if k!="const"}
        aic = round(res.aic,2); pr2 = round(res.prsquared,4)
    except Exception as e: print(f"  statsmodels J+{h}: {e}")
    try:
        lr = LogisticRegression(max_iter=500,random_state=42); lr.fit(Xs,y)
        auc = round(roc_auc_score(y,lr.predict_proba(Xs)[:,1]),4)
    except: pass
    ablation = {}
    for drop in feats:
        red = [c for c in feats if c!=drop]
        if not red: continue
        Xr = StandardScaler().fit_transform(sub[red].values)
        try:
            r2 = sm.Logit(y,sm.add_constant(Xr)).fit(disp=False,maxiter=300)
            ablation[drop] = round(r2.aic-aic,2) if aic else None
        except: ablation[drop] = None
    return {"horizon":h,"n":n,"hit_rate":hr,"auc":auc,"aic":aic,"pseudo_r2":pr2,"coefs":coefs,"pvals":pvals,"ablation":ablation}

def tag(p, d):
    if p is None: return "?"
    if p>0.10 and d is not None and d<-2: return "BRUIT confirme"
    if p>0.10: return f"Suspect p={p:.2f}"
    if p<=0.05: return "Signal p<=5%"
    return "Ambigu"

def analyze_liq(df, feats):
    print("Analyse liquidite...")
    thr = df["vol_20d"].quantile(0.40)
    dliq = df[df["vol_20d"]>=thr]
    res = {}
    for h in HORIZONS:
        col = f"cj{h}"
        a = df[feats+[col]].dropna(); l = dliq[feats+[col]].dropna()
        ha = a[col].mean()*100 if len(a)>0 else None
        hl = l[col].mean()*100 if len(l)>0 else None
        res[h] = {"n_all":len(a),"n_liq":len(l),"hr_all":round(ha,1) if ha else None,"hr_liq":round(hl,1) if hl else None,"delta":round(hl-ha,1) if ha and hl else None}
    return res

def opt_thresh(df, h=10):
    col = f"cj{h}"; sub = df[["score",col]].dropna()
    if len(sub)<30: return {"note":f"trop peu ({len(sub)})"}
    fpr,tpr,thr = roc_curve(sub[col],sub["score"])
    auc = roc_auc_score(sub[col],sub["score"])
    idx = np.argmax(tpr-fpr); opt = round(float(thr[idx]),1)
    return {"horizon":h,"auc":round(auc,4),"seuil_optimal":opt,"n_signaux_65":int((sub["score"]>=65).sum()),"n_signaux_opt":int((sub["score"]>=opt).sum())}

def print_all(results, feats, liq, thresh):
    print("="*70)
    print("HIT RATE PAR HORIZON")
    print("="*70)
    print(f"{'Horizon':<10}{'N':<8}{'Hit rate':<12}{'AUC':<10}{'Pseudo-R2':<12}AIC")
    print(SEP)
    for r in results:
        print(f"J+{r['horizon']:<8}{r['n']:<8}{str(r['hit_rate'])+'%':<12}{str(r.get('auc','?')):<10}{str(r.get('pseudo_r2','?')):<12}{r.get('aic','?')}  {r.get('note','')}")
    for r in results:
        if "coefs" not in r: continue
        print(f"\n{SEP}\nJ+{r['horizon']} Coefficients\n{SEP}")
        print(f"{'Variable':<28}{'Coeff':>8}  {'p-val':>8}  {'dAIC':>7}  Statut")
        for f in feats:
            c=r["coefs"].get(f); p=r["pvals"].get(f); d=r.get("ablation",{}).get(f)
            print(f"{f:<28}{str(round(c,4)) if c is not None else 'N/A':>8}  {str(p) if p is not None else 'N/A':>8}  {str(d) if d is not None else 'N/A':>7}  {tag(p,d)}")
    print("="*70)
    print("LIQUIDITE filtre vs additif")
    print("="*70)
    print(f"{'Horizon':<10}{'N tous':<9}{'N liq':<9}{'HR tous':<10}{'HR liq':<10}{'dAHR':<8}Verdict")
    print(SEP)
    for h,r in liq.items():
        d=r["delta"]; ds=f"{d:+.1f}%" if d is not None else "N/A"
        flag="FILTRE UTILE" if d and d>1.5 else ("FILTRE NUL" if d and d<-1.5 else "neutre")
        print(f"J+{h:<8}{r['n_all']:<9}{r['n_liq']:<9}{str(r['hr_all'])+'%':<10}{str(r['hr_liq'])+'%':<10}{ds:<8}{flag}")
    print("="*70)
    print("SEUIL OPTIMAL")
    print("="*70)
    if "note" in thresh:
        print(thresh["note"])
    else:
        print(f"Horizon J+{thresh['horizon']} | AUC={thresh['auc']}")
        print(f"Seuil actuel  : 65  ({thresh['n_signaux_65']} signaux ACHAT)")
        print(f"Seuil optimal : {thresh['seuil_optimal']}  ({thresh['n_signaux_opt']} signaux ACHAT)")
        d = thresh["seuil_optimal"]-65
        print(f"Ecart : {d:+.1f} pts -> {'AJUSTEMENT RECOMMANDE post-degel' if abs(d)>3 else 'seuil 65 OK'}")

def main():
    print("="*70)
    print("BRVM Analytics Regression Multi-Horizons v2")
    print(datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("="*70)
    if not HAS_ML: sys.exit(1)
    dec=fetch_decisions(); com=fetch_companies(); pri=fetch_prices()
    if dec.empty or pri.empty: print("ERREUR donnees"); sys.exit(1)
    ds,_=build_dataset(dec,pri,com)
    print(f"ACHAT={(ds['signal']=='ACHAT').sum()} EVITER={(ds['signal']=='EVITER').sum()} tickers={ds['ticker'].nunique()}")
    print(f"Periode: {ds['date'].min().date()} -> {ds['date'].max().date()}")
    for h in HORIZONS:
        n=ds[f"cj{h}"].notna().sum()
        print(f"  J+{h}: {n} verifiables ({n/len(ds)*100:.0f}%)")
    feats=get_features(ds)
    print(f"Features: {feats}")
    results=[]
    for h in HORIZONS:
        print(f"Regression J+{h}...", end=" ", flush=True)
        r=run_reg(ds,h,feats); results.append(r)
        print(f"HR={r.get('hit_rate','?')}% n={r.get('n','?')}")
    liq=analyze_liq(ds,feats)
    thr=opt_thresh(ds,h=10)
    print_all(results,feats,liq,thr)
    cols=["ticker","date","signal","score","market_regime","liquidity_tier","confidence","regime_bull","vol_20d","price_signal"]+[f"cj{h}" for h in HORIZONS]
    cols=[c for c in cols if c in ds.columns]
    ds[cols].to_csv("regression_dataset.csv",index=False)
    print("regression_dataset.csv sauvegarde")
    print("Termine.")

if __name__=="__main__":
    main()
