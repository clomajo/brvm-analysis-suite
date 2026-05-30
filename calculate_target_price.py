"""
calculate_target_price.py
Calcule un cours cible par ticker BRVM via méthode PER normalisé + Gordon
Produit : table target_prices (ticker, cours_cible, decote_pct, methode, date)
"""

import os
import requests
from datetime import date
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Secteurs BRVM
SECTEURS = {
    "banque": ["BOAB","BOABF","BOAC","BOAM","BOAN","BOAS","BNBC","CBIBF",
               "NSBC","SGBC","SIBC","SICC","SLBC","UNLC","BICI","CABC"],
    "agro":   ["PALC","SOGC","SPHC","SUCRIVOIRE","SAFC","CFAC"],
    "industrie": ["SMBC","STAC","STBC","BICC","CIEC","ECOC","SIVC",
                  "SEMC","SHEC","SCRC","SDCC","SDSC","UNXC"],
    "telecom": ["ONTBF","ORAC","ORGT"],
    "distribution": ["ABJC","CFAC","ETIT","FTSC","LNBB","NEIC","NTLC",
                     "PRSC","SNTS","SOGC","TTLC","TTLS"],
}

PER_SECTORIEL = {
    "banque": 10.0,
    "agro": 14.0,
    "industrie": 12.0,
    "telecom": 12.0,
    "distribution": 13.0,
    "autre": 11.0,
}

TAUX_REQUIS = 0.08  # 8% UEMOA

def get_secteur(ticker):
    for secteur, tickers in SECTEURS.items():
        if ticker in tickers:
            return secteur
    return "autre"

def fetch_fundamentals():
    """Récupère EPS moyen 3 ans + dividende le plus recent par ticker (V2-07)."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,fiscal_year,eps,dividend_per_share,pe_ratio"
        f"&eps=not.is.null&order=ticker.asc,fiscal_year.desc",
        headers={**HEADERS, "Range": "0-2999"}
    )
    data = r.json()
    # Grouper par ticker (max 3 ans)
    grouped = {}
    for row in data:
        t = row["ticker"]
        if t not in grouped:
            grouped[t] = []
        if len(grouped[t]) < 3:
            grouped[t].append(row)
    # Calculer EPS moyen + garder dividende le plus recent
    result = {}
    for ticker, rows in grouped.items():
        eps_values = [r["eps"] for r in rows if r["eps"] and abs(r["eps"]) < 1e7]
        eps_avg = round(sum(eps_values) / len(eps_values), 2) if eps_values else None
        latest = rows[0]
        result[ticker] = {
            "ticker": ticker,
            "fiscal_year": latest["fiscal_year"],
            "eps": eps_avg,
            "eps_years": len(eps_values),
            "dividend_per_share": latest["dividend_per_share"],
            "pe_ratio": latest["pe_ratio"],
        }
    return result

def fetch_prix_actuels():
    """Récupère le dernier prix connu par ticker."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=company_id,trade_date,price&order=trade_date.desc",
        headers=HEADERS
    )
    rows = r.json()
    # Récupère aussi le mapping company_id → symbol
    rc = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    companies = {c["id"]: c["symbol"] for c in rc.json()}
    
    prix = {}
    for row in rows:
        symbol = companies.get(row["company_id"])
        if symbol and symbol not in prix:
            prix[symbol] = row["price"]
    return prix

def calculer_cours_cible(ticker, eps, dividende, secteur):
    """Retourne (cours_cible, methode)."""
    per_ref = PER_SECTORIEL.get(secteur, PER_SECTORIEL["autre"])
    
    # Méthode PER
    cours_per = None
    if eps and eps > 0 and abs(eps) < 1e7:
        cours_per = eps * per_ref

    # Méthode Gordon
    cours_gordon = None
    if dividende and dividende > 0:
        cours_gordon = dividende / TAUX_REQUIS

    # Combinaison
    if cours_per and cours_gordon:
        cours_cible = 0.70 * cours_per + 0.30 * cours_gordon
        methode = "PER70+Gordon30"
    elif cours_per:
        cours_cible = cours_per
        methode = "PER100"
    elif cours_gordon:
        cours_cible = cours_gordon
        methode = "Gordon100"
    else:
        return None, None

    return round(cours_cible, 2), methode

def run():
    print("=== Calcul cours cibles BRVM ===")
    
    fundamentals = fetch_fundamentals()
    prix_actuels = fetch_prix_actuels()
    
    print(f"Tickers avec fondamentaux : {len(fundamentals)}")
    print(f"Tickers avec prix : {len(prix_actuels)}")
    
    resultats = []
    today = date.today().isoformat()

    for ticker, row in sorted(fundamentals.items()):
        eps = row.get("eps")
        dividende = row.get("dividend_per_share")
        fiscal_year = row.get("fiscal_year")
        prix_actuel = prix_actuels.get(ticker)
        secteur = get_secteur(ticker)

        cours_cible, methode = calculer_cours_cible(ticker, eps, dividende, secteur)

        if not cours_cible or not prix_actuel:
            print(f"  ⚠️  {ticker}: données insuffisantes (cours_cible={cours_cible}, prix={prix_actuel})")
            continue

        decote_pct = round((cours_cible - prix_actuel) / prix_actuel * 100, 2)
        signal = "ACHAT" if decote_pct > 15 else "VENTE" if decote_pct < -15 else "NEUTRE"

        resultats.append({
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "secteur": secteur,
            "eps": eps,
            "dividende": dividende,
            "per_ref": PER_SECTORIEL.get(secteur, 11.0),
            "cours_cible": cours_cible,
            "prix_actuel": prix_actuel,
            "decote_pct": decote_pct,
            "signal_v2": signal,
            "methode": methode,
            "calcul_date": today,
        })

        flag = "🟢" if signal == "ACHAT" else "🔴" if signal == "VENTE" else "⚪"
        n_years = row.get("eps_years", 1)
        print(f"  {flag} {ticker} ({secteur}) | EPS={eps} (moy {n_years}ans) | Cible={cours_cible} | Actuel={prix_actuel} | Décote={decote_pct}% | {signal}")

    # Tri par décote décroissante
    resultats.sort(key=lambda x: x["decote_pct"], reverse=True)
    
    print(f"\n=== Résumé ===")
    print(f"ACHAT  : {sum(1 for r in resultats if r['signal_v2']=='ACHAT')}")
    print(f"NEUTRE : {sum(1 for r in resultats if r['signal_v2']=='NEUTRE')}")
    print(f"VENTE  : {sum(1 for r in resultats if r['signal_v2']=='VENTE')}")
    
    print(f"\n=== Top 5 décotes (ACHAT) ===")
    for r in resultats[:5]:
        print(f"  {r['ticker']}: cible={r['cours_cible']} vs actuel={r['prix_actuel']} ({r['decote_pct']}%)")

    print(f"\n=== Top 5 surcotes (VENTE) ===")
    for r in resultats[-5:]:
        print(f"  {r['ticker']}: cible={r['cours_cible']} vs actuel={r['prix_actuel']} ({r['decote_pct']}%)")

    return resultats

if __name__ == "__main__":
    run()
