"""
brvm_dividend_volume_h1_h2.py

Teste H1 (apprentissage du marché) vs H2 (conjoncturel à 2026) en comparant
le volume de transaction dans la fenêtre PRÉ-ex-date entre FY2025 et
FY2021-2024 (référence historique).

Logique du test :
- H1 prédit : volume pré-ex-date FY2025 > volume pré-ex-date historique
  (plus d'acheteurs se positionnent pour capturer l'inefficience —
  l'apprentissage se manifeste par plus de transactions AVANT l'ex-date,
  pas seulement par une chute plus faible à l'ex-date elle-même).
- H2 prédit : pas de différence significative de volume pré-ex-date —
  la chute plus faible viendrait d'autre chose (liquidité générale du
  marché, conditions macro), pas d'un comportement d'achat différent
  spécifiquement lié à la mécanique dividende.

Méthode : pour chaque événement (FY2025 et FY2021-2024), calculer le volume
moyen sur les 10 jours précédant l'ex-date, normalisé par le volume moyen
"normal" du titre (60 jours avant cette fenêtre, pour contrôler la liquidité
de base propre à chaque ticker). Comparer les deux distributions.

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


def volume_ratio_pre_exdate(rows_prix, ex_date):
    """
    Calcule le ratio : volume moyen [J-10, J-1] / volume moyen [J-70, J-11].
    Un ratio > 1 signifie une hausse de volume à l'approche de l'ex-date,
    par rapport au régime de liquidité "normal" du titre.
    """
    fenetre_recente = []
    fenetre_base = []
    for r in rows_prix:
        try:
            d = datetime.strptime(r["trade_date"][:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        delta = (ex_date - d).days
        vol = r.get("volume") or 0
        if 1 <= delta <= 10:
            fenetre_recente.append(vol)
        elif 11 <= delta <= 70:
            fenetre_base.append(vol)

    if not fenetre_recente or not fenetre_base:
        return None

    moy_recente = statistics.mean(fenetre_recente)
    moy_base = statistics.mean(fenetre_base)
    if moy_base == 0:
        return None
    return moy_recente / moy_base


EVENEMENTS_FY2025 = [
    ("BOABF", "2026-04-22"), ("BOAC", "2026-05-05"), ("BOAB", "2026-05-14"),
    ("SNTS", "2026-05-22"), ("BOAB", "2026-05-22"), ("BOAS", "2026-05-29"),
    ("CABC", "2026-05-29"), ("BOAM", "2026-06-02"), ("ORAC", "2026-06-05"),
]


def main():
    companies = fetch_all("companies", {"select": "id,symbol"})
    symbol_to_id = {c["symbol"]: c["id"] for c in companies}

    print("=== Test H1 vs H2 — volume pré-ex-date FY2025 vs historique (21/06/2026) ===\n")

    print("→ Chargement corporate_events pour référence historique FY2021-2024...")
    events = fetch_all("corporate_events", {"select": "ticker,company_id,event_type,event_date,fiscal_year"})
    ex_div_hist = [
        e for e in events
        if e.get("event_type") == "EX_DIVIDEND" and str(e.get("fiscal_year")) in ("2021", "2022", "2023", "2024")
    ]
    print(f"  {len(ex_div_hist)} événements EX_DIVIDEND FY2021-2024.")

    print("\n=== Ratios volume pré-ex-date — FY2025 ===\n")
    ratios_fy2025 = []
    for ticker, ex_date_str in EVENEMENTS_FY2025:
        cid = symbol_to_id.get(ticker)
        if not cid:
            continue
        ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d").date()
        debut = (ex_date - timedelta(days=75)).isoformat()
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,volume", "company_id": f"eq.{cid}", "trade_date": f"gte.{debut}"},
        )
        ratio = volume_ratio_pre_exdate(rows, ex_date)
        if ratio is not None:
            ratios_fy2025.append(ratio)
            print(f"  {ticker:8s} ex={ex_date_str}  ratio_volume={ratio:.2f}")

    print("\n=== Ratios volume pré-ex-date — FY2021-2024 (échantillon, max 40 événements) ===\n")
    ratios_hist = []
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
        debut = (ex_date - timedelta(days=75)).isoformat()
        fin = (ex_date + timedelta(days=1)).isoformat()
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,volume", "company_id": f"eq.{cid}",
             "trade_date": f"gte.{debut}"},
        )
        rows = [r for r in rows if r["trade_date"][:10] <= fin]
        ratio = volume_ratio_pre_exdate(rows, ex_date)
        if ratio is not None:
            ratios_hist.append(ratio)

    print(f"  {len(ratios_hist)} événements historiques avec ratio calculable.")

    print("\n=== Résumé comparatif ===")
    if ratios_fy2025:
        print(f"FY2025      (n={len(ratios_fy2025)}) : médiane ratio volume = {statistics.median(ratios_fy2025):.2f}")
    if ratios_hist:
        print(f"FY2021-2024 (n={len(ratios_hist)}) : médiane ratio volume = {statistics.median(ratios_hist):.2f}")

    if ratios_fy2025 and ratios_hist:
        med_25 = statistics.median(ratios_fy2025)
        med_hist = statistics.median(ratios_hist)
        print(f"\nRatio = volume moyen [J-10,J-1] / volume moyen [J-70,J-11]. >1 = sur-volume avant l'ex-date.")
        if med_25 > med_hist * 1.3:
            print(f"\n→ Le volume pré-ex-date FY2025 ({med_25:.2f}) est nettement supérieur à l'historique ({med_hist:.2f}).")
            print("  Cohérent avec H1 (apprentissage) : plus d'acheteurs se positionnent avant l'ex-date.")
        elif med_25 < med_hist * 0.8:
            print(f"\n→ Le volume pré-ex-date FY2025 ({med_25:.2f}) est plus faible que l'historique ({med_hist:.2f}).")
            print("  Ne soutient PAS H1 — la chute plus faible n'est pas due à plus d'achats anticipés.")
            print("  Plutôt cohérent avec H2 (conjoncturel/autre cause).")
        else:
            print(f"\n→ Pas de différence marquée entre FY2025 ({med_25:.2f}) et l'historique ({med_hist:.2f}).")
            print("  Ne soutient PAS clairement H1. La chute plus faible ne s'accompagne pas d'un")
            print("  changement de comportement d'achat visible dans le volume — H2 (conjoncturel,")
            print("  ou une autre cause non testée ici) reste l'explication la plus probable par défaut.")


if __name__ == "__main__":
    main()
