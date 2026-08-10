# -*- coding: utf-8 -*-
"""
backtest_v3.py — Validation du modele Fair Value V3
====================================================
Classe A : read-only, aucune ecriture en base.

SEUILS PRE-ENREGISTRES (fixes avant execution, 09/08/2026) :
  - Metrique : hit rate (variation prix > 0) + mediane de variation
  - Horizons : J+30, J+60, J+90
  - Comparateur : memes metriques sur les PASSER, meme date, meme univers
  - SUCCES : ACHAT depasse PASSER d'au moins 10 pts de hit rate a J+90
  - ECHEC  : ecart nul ou negatif a J+90

LIMITE ASSUMEE : company_fundamentals contient les valeurs COURANTES, pas
leur etat a la date rejouee. Le backtest mesure donc "la formule selectionne-
t-elle des titres qui montent", pas "V3 aurait-il eu raison en temps reel".
Meme limite que backtest_value.py sur V2.
"""

import os
import sys
import statistics
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from dotenv import load_dotenv, find_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import calculate_target_price_v3 as v3

load_dotenv(find_dotenv(usecwd=True))
U = os.environ["SUPABASE_URL"]
K = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": K, "Authorization": f"Bearer {K}"}

HORIZONS = [30, 60, 90]
TOLERANCE_JOURS = 7


def get_all(table, params, page=5000):
    out, offset = [], 0
    while True:
        r = requests.get(f"{U}/rest/v1/{table}",
                         headers={**H, "Range": f"{offset}-{offset+page-1}"},
                         params=params, timeout=60)
        r.raise_for_status()
        lot = r.json()
        if not lot:
            break
        out.extend(lot)
        if len(lot) < page:
            break
        offset += page
    return out


def main():
    print("=" * 70)
    print("BACKTEST V3 — seuils pre-enregistres, Classe A read-only")
    print("=" * 70)

    companies = get_all("companies", {"select": "id,symbol"})
    sym_to_id = {c["symbol"]: c["id"] for c in companies}
    id_to_sym = {c["id"]: c["symbol"] for c in companies}

    # Prix par (ticker, date)
    hist = get_all("historical_data", {"select": "company_id,trade_date,price",
                                       "order": "trade_date.asc"})
    prix = {}
    for r in hist:
        s = id_to_sym.get(r["company_id"])
        if s and r.get("price"):
            prix[(s, r["trade_date"])] = r["price"]
    print(f"  {len(prix)} points de prix charges")

    def prix_proche(ticker, jour):
        d0 = datetime.fromisoformat(jour)
        for delta in range(TOLERANCE_JOURS + 1):
            for signe in (0, -1, 1):
                d = (d0 + timedelta(days=signe * delta)).date().isoformat()
                if (ticker, d) in prix:
                    return prix[(ticker, d)]
        return None

    # Semaines BOA disponibles
    boa = get_all("boa_recommendations",
                  {"select": "week_label,date_end,ticker,rendement",
                   "order": "date_end.asc"})
    par_semaine = defaultdict(dict)
    date_semaine = {}
    for r in boa:
        wl = r["week_label"]
        date_semaine[wl] = r["date_end"]
        if r.get("ticker") and r.get("rendement"):
            par_semaine[wl][r["ticker"]] = r

    aujourdhui = datetime.now().date()
    semaines = sorted(par_semaine, key=lambda w: date_semaine[w])
    print(f"  {len(semaines)} semaines BOA disponibles\n")

    # Donnees statiques du modele
    fundamentals = get_all("company_fundamentals", {"select": "*"})
    fund_by_ticker = {}
    for f in fundamentals:
        if f["fiscal_year"] == "FY2025" and (f.get("eps") or f.get("dividend_per_share")):
            fund_by_ticker[f["ticker"]] = f
    for f in fundamentals:
        t = f["ticker"]
        if t not in fund_by_ticker and f["fiscal_year"] == "FY2024" \
           and (f.get("eps") or f.get("dividend_per_share")):
            fund_by_ticker[t] = f

    hist_div = v3.build_historique_dividendes()
    rdt_hist = v3.build_rendements_historiques(id_to_sym)

    resultats = defaultdict(lambda: defaultdict(list))
    n_signaux = defaultdict(int)

    for wl in semaines:
        d_sem = date_semaine[wl]
        age = (aujourdhui - datetime.fromisoformat(d_sem).date()).days
        boa_sem = par_semaine[wl]

        for ticker, fund in fund_by_ticker.items():
            cid = sym_to_id.get(ticker)
            if not cid:
                continue
            p0 = prix_proche(ticker, d_sem)
            if not p0:
                continue

            hist_local = [{"company_id": cid, "trade_date": d_sem,
                           "price": p0, "volume": 0}]
            res = v3.fair_value_v3(ticker, fund, hist_local, cid, boa_sem,
                                   hist_div, rdt_hist)
            sig = res.get("signal_v3")
            if sig not in ("ACHAT", "SURVEILLER", "PASSER"):
                continue
            n_signaux[sig] += 1

            for h in HORIZONS:
                if age < h:
                    continue
                d_cible = (datetime.fromisoformat(d_sem)
                           + timedelta(days=h)).date().isoformat()
                p1 = prix_proche(ticker, d_cible)
                if not p1:
                    continue
                resultats[sig][h].append((p1 - p0) / p0 * 100)

    print(f"Signaux generes : {dict(n_signaux)}\n")
    print(f"{'Signal':<12}{'Horizon':>9}{'n':>7}{'hit rate':>11}{'mediane':>10}")
    print("-" * 70)
    stats = {}
    for sig in ("ACHAT", "SURVEILLER", "PASSER"):
        for h in HORIZONS:
            v = resultats[sig][h]
            if not v:
                continue
            hr = sum(1 for x in v if x > 0) / len(v) * 100
            md = statistics.median(v)
            stats[(sig, h)] = (len(v), hr, md)
            print(f"{sig:<12}J+{h:<7}{len(v):>7}{hr:>10.1f}%{md:>9.1f}%")

    print("\n" + "=" * 70)
    print("VERDICT (seuils pre-enregistres)")
    a = stats.get(("ACHAT", 90))
    p = stats.get(("PASSER", 90))
    if not a or not p:
        print("  INCONCLUSIF — donnees insuffisantes a J+90")
    else:
        ecart = a[1] - p[1]
        print(f"  ACHAT J+90  : hit {a[1]:.1f}% (n={a[0]}), mediane {a[2]:+.1f}%")
        print(f"  PASSER J+90 : hit {p[1]:.1f}% (n={p[0]}), mediane {p[2]:+.1f}%")
        print(f"  Ecart       : {ecart:+.1f} pts")
        if ecart >= 10:
            print("  -> SUCCES : ecart >= 10 pts")
        elif ecart > 0:
            print("  -> NON CONCLUANT : ecart positif mais < 10 pts")
        else:
            print("  -> ECHEC : ecart nul ou negatif")
    print("=" * 70)


if __name__ == "__main__":
    main()
