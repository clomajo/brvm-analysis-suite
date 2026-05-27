
import os, requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv("SUPABASE_URL","").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

def fetch(table, params=None):
    res, off = [], 0
    while True:
        p = {"limit":1000,"offset":off}
        if params: p.update(params)
        r = requests.get(f"{URL}/rest/v1/{table}", headers=H, params=p, timeout=30)
        b = r.json()
        if not b: break
        res.extend(b); off += len(b)
        if len(b)<1000: break
    return res

boa = pd.DataFrame(fetch("boa_recommendations",{"select":"ticker,date_start,action,cours_act,potential","order":"date_start.asc"}))
companies = {r["id"]:r["symbol"] for r in fetch("companies",{"select":"id,symbol"})}
prices = pd.DataFrame(fetch("historical_data",{"select":"company_id,trade_date,price","order":"trade_date.asc"}))
prices["ticker"] = prices["company_id"].map(companies)
prices["trade_date"] = pd.to_datetime(prices["trade_date"])
prices["price"] = pd.to_numeric(prices["price"],errors="coerce")
lookup = {t:g.sort_values("trade_date").reset_index(drop=True) for t,g in prices.groupby("ticker")}

def prix_futur(ticker, ref, jours):
    if ticker not in lookup: return None
    df = lookup[ticker]
    sub = df[df["trade_date"] >= pd.Timestamp(ref)+pd.to_timedelta(jours,unit="D")]
    return sub.iloc[0]["price"] if not sub.empty else None

boa["date_start"] = pd.to_datetime(boa["date_start"])
boa["cours_act"] = pd.to_numeric(boa["cours_act"],errors="coerce")
boa["potential"] = pd.to_numeric(boa["potential"],errors="coerce")

rows = []
for _, r in boa.iterrows():
    p0 = r["cours_act"]
    if not p0: continue
    for h in [10,20,30]:
        p1 = prix_futur(r["ticker"], r["date_start"], h)
        if p1 is None: continue
        chg = (p1-p0)/p0
        if abs(chg)>0.5: continue
        rows.append({"ticker":r["ticker"],"action":r["action"],
                     "potential":r["potential"],"chg":chg*100,"h":h})

df = pd.DataFrame(rows)
print("="*55)
print("BOA — Le potentiel predit-il la direction reelle ?")
print("="*55)
print(f"{'Horizon':<10} {'HR BUY':>8} {'HR SELL':>9} {'N BUY':>7} {'N SELL':>8}")
print("-"*55)
for h in [10,20,30]:
    s = df[df["h"]==h]
    buy = s[s["action"]=="BUY"]
    sell = s[s["action"]=="SELL"]
    hr_b = (buy["chg"]>0).mean()*100 if len(buy) else 0
    hr_s = (sell["chg"]<0).mean()*100 if len(sell) else 0
    print(f"J+{h:<8} {hr_b:>7.1f}% {hr_s:>8.1f}% {len(buy):>7} {len(sell):>8}")

print()
print("="*55)
print("Par niveau de potentiel BOA (J+20)")
print("="*55)
s20 = df[df["h"]==20].copy()
s20["bucket"] = pd.cut(s20["potential"],
    bins=[-100,-20,-10,0,10,20,100],
    labels=["<-20","-20/-10","-10/0","0/10","10/20",">20"])
print(f"{'Potentiel BOA':<15} {'HR reel':>8} {'N':>5} {'Interpretation':>20}")
print("-"*52)
for b in ["<-20","-20/-10","-10/0","0/10","10/20",">20"]:
    g = s20[s20["bucket"]==b]
    if len(g)<3: continue
    hr = (g["chg"]>0).mean()*100
    interp = "hausse reelle" if hr>55 else ("baisse reelle" if hr<45 else "neutre")
    print(f"{b:<15} {hr:>7.1f}% {len(g):>5}   {interp}")
