"""
brvm_dividend_prix_h1_h2.py

Complète le test H1 (apprentissage) vs H2 (conjoncturel) en ajoutant l'angle
PRIX, en plus du volume déjà testé dans brvm_dividend_volume_h1_h2.py.

Logique complémentaire :
- H1 peut se manifester par une hausse de PRIX avant l'ex-date plus marquée
  qu'avant (les acheteurs paient plus cher pour capturer le dividende, même
  sans hausse de volume détectable) — pas seulement par plus de volume.
- On mesure : variation de prix [J-10, J-1] / écart-type des variations
  quotidiennes du titre sur les 70 jours précédents (= un "z-score" de la
  montée pré-ex-date, qui contrôle la volatilité propre à chaque titre).

Croisement avec le test volume déjà fait :
  Volume↑ + Prix↑  → H1 fortement soutenue (apprentissage net)
  Volume= + Prix↑  → H1 partiellement soutenue (prix monte sans plus de volume)
  Volume↑ + Prix=  → ambigu (plus d'échanges mais pas plus chers)
  Volume= + Prix=  → H1 non soutenue, H2 ou autre cause par défaut

Prérequis : SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans le .env du projet.
"""

import os
import requests
import statistics
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://lynevvhmstpcffobwudr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def fetch_all(table, params, range_size=1000):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    all_rows = []
    offset = 0
    while True:
        headers = dict(HEADERS)
        headers["Range"] = f"{offset}-{offset + range_size - 1}"
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        rows = resp.json()
        all_rows.extend(rows)
        if len(rows) < range_size:
            break
        offset += range_size
    return all_rows


def zscore_montee_pre_exdate(rows_prix, ex_date):
    """
    Calcule un z-score de la montée de prix dans [J-10, J-1] :
    (variation_pct_sur_10j) / (écart-type des variations quotidiennes sur
    les 70 jours précédant cette fenêtre).
    Un z-score élevé = montée anormalement forte vs la volatilité habituelle
    du titre, pas juste "le marché monte en général".
    """
    par_date = {}
    for r in rows_prix:
        try:
            d = datetime.strptime(r["trade_date"][:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        par_date[d] = r["price"]

    dates_triees = sorted(par_date.keys())

    # Prix à J-10 et J-1 (ou les plus proches disponibles)
    cible_j10 = ex_date - timedelta(days=10)
    cible_j1 = ex_date - timedelta(days=1)

    dates_avant_j10 = [d for d in dates_triees if d <= cible_j10]
    dates_avant_j1 = [d for d in dates_triees if d <= cible_j1]
    if not dates_avant_j10 or not dates_avant_j1:
        return None

    prix_j10 = par_date[dates_avant_j10[-1]]
    prix_j1 = par_date[dates_avant_j1[-1]]
    if not prix_j10 or prix_j10 == 0:
        return None

    variation_pct_10j = (prix_j1 - prix_j10) / prix_j10 * 100

    # Volatilité de référence : écart-type des variations quotidiennes sur
    # la fenêtre [J-80, J-11] (avant la fenêtre pré-ex-date elle-même)
    dates_base = [d for d in dates_triees if (ex_date - d).days >= 11 and (ex_date - d).days <= 80]
    variations_quotidiennes = []
    for i in range(1, len(dates_base)):
        p0 = par_date[dates_base[i - 1]]
        p1 = par_date[dates_base[i]]
        if p0 and p0 != 0:
            variations_quotidiennes.append((p1 - p0) / p0 * 100)

    if len(variations_quotidiennes) < 5:
        return None

    ecart_type = statistics.stdev(variations_quotidiennes)
    if ecart_type == 0:
        return None

    return variation_pct_10j / ecart_type


EVENEMENTS_FY2025 = [
    ("BOABF", "2026-04-22"), ("BOAC", "2026-05-05"), ("BOAB", "2026-05-14"),
    ("SNTS", "2026-05-22"), ("BOAB", "2026-05-22"), ("BOAS", "2026-05-29"),
    ("CABC", "2026-05-29"), ("BOAM", "2026-06-02"), ("ORAC", "2026-06-05"),
]


def main():
    companies = fetch_all("companies", {"select": "id,symbol"})
    symbol_to_id = {c["symbol"]: c["id"] for c in companies}

    print("=== Test H1 vs H2 (angle PRIX) — montée pré-ex-date FY2025 vs historique ===\n")

    print("→ Chargement corporate_events pour référence historique FY2021-2024...")
    events = fetch_all("corporate_events", {"select": "ticker,company_id,event_type,event_date,fiscal_year"})
    ex_div_hist = [
        e for e in events
        if e.get("event_type") == "EX_DIVIDEND" and str(e.get("fiscal_year")) in ("2021", "2022", "2023", "2024")
    ]
    print(f"  {len(ex_div_hist)} événements EX_DIVIDEND FY2021-2024.")

    print("\n=== Z-scores montée prix pré-ex-date — FY2025 ===\n")
    zscores_fy2025 = []
    for ticker, ex_date_str in EVENEMENTS_FY2025:
        cid = symbol_to_id.get(ticker)
        if not cid:
            continue
        ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d").date()
        debut = (ex_date - timedelta(days=85)).isoformat()
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,price", "company_id": f"eq.{cid}", "trade_date": f"gte.{debut}"},
        )
        z = zscore_montee_pre_exdate(rows, ex_date)
        if z is not None:
            zscores_fy2025.append(z)
            print(f"  {ticker:8s} ex={ex_date_str}  z_score_montee={z:.2f}")

    print("\n=== Z-scores montée prix pré-ex-date — FY2021-2024 (échantillon, max 40) ===\n")
    zscores_hist = []
    for e in ex_div_hist[:40]:
        ticker = e.get("ticker")
        cid = e.get("company_id")
        ex_date_str = e.get("event_date")
        if not ticker or not cid or not ex_date_str:
            continue
        try:
            ex_date = datetime.strptime(ex_date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        debut = (ex_date - timedelta(days=85)).isoformat()
        fin = (ex_date + timedelta(days=1)).isoformat()
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,price", "company_id": f"eq.{cid}", "trade_date": f"gte.{debut}"},
        )
        rows = [r for r in rows if r["trade_date"][:10] <= fin]
        z = zscore_montee_pre_exdate(rows, ex_date)
        if z is not None:
            zscores_hist.append(z)

    print(f"  {len(zscores_hist)} événements historiques avec z-score calculable.")

    print("\n=== Résumé comparatif (PRIX) ===")
    if zscores_fy2025:
        print(f"FY2025      (n={len(zscores_fy2025)}) : médiane z-score montée = {statistics.median(zscores_fy2025):.2f}")
    if zscores_hist:
        print(f"FY2021-2024 (n={len(zscores_hist)}) : médiane z-score montée = {statistics.median(zscores_hist):.2f}")

    if zscores_fy2025 and zscores_hist:
        med_25 = statistics.median(zscores_fy2025)
        med_hist = statistics.median(zscores_hist)
        diff = med_25 - med_hist
        print(f"\nZ-score = montée de prix [J-10,J-1] normalisée par la volatilité habituelle du titre.")
        if diff > 0.3:
            print(f"\n→ La montée pré-ex-date est plus marquée en FY2025 ({med_25:.2f}) qu'historiquement ({med_hist:.2f}).")
            print("  Soutient H1 sur l'angle PRIX : le marché paie plus cher avant l'ex-date.")
        elif diff < -0.3:
            print(f"\n→ La montée pré-ex-date est MOINS marquée en FY2025 ({med_25:.2f}) qu'historiquement ({med_hist:.2f}).")
            print("  Ne soutient pas H1 sur l'angle PRIX non plus.")
        else:
            print(f"\n→ Pas de différence marquée sur l'angle PRIX non plus ({med_25:.2f} vs {med_hist:.2f}).")
            print("  Combiné au test volume (déjà non concluant pour H1), aucun des deux angles")
            print("  testés ne montre de signe d'apprentissage du marché. H2 (conjoncturel) ou une")
            print("  cause non testée ici devient l'explication par défaut la plus crédible.")


if __name__ == "__main__":
    main()
