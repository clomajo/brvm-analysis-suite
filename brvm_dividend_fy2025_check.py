"""
brvm_dividend_fy2025_check.py

Reprend l'analyse du 06/06/2026 (où 4/7 événements FY2025 avaient moins de
15 jours de recul) avec les données disponibles au 21/06/2026 — deux semaines
de recul supplémentaire — pour trancher entre les deux hypothèses posées :

  H1 — Le marché a appris : l'inefficience structurelle (chute ~48% du div
       historiquement) se referme progressivement. La stratégie devient
       moins rentable avec le temps.
  H2 — C'est conjoncturel à 2026 (liquidité, flux institutionnels). La chute
       observée à ~2% en FY2025 est temporaire, pas une tendance durable.

Méthode :
1. Recharger tous les événements FY2025 (EX_DIVIDEND + DIVIDEND_HISTORY joints
   par ticker/fiscal_year, comme dans v3b).
2. Pour chaque événement, calculer la chute réelle vs chute théorique (= div),
   uniquement si on a au moins J+15 de recul (sinon donnée non comparable).
3. Comparer la distribution FY2025 (mise à jour) à la distribution FY2021-2024
   (référence déjà établie : médiane ~48%).
4. Test simple : la chute FY2025 reste-t-elle anormalement basse (~2%) avec
   plus de recul, ou se rapproche-t-elle progressivement de l'historique
   (signe qu'elle n'était pas encore stabilisée le 06/06) ?

Prérequis : SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans le .env du projet.
Lancer depuis ~/Desktop/brvm-analysis-suite.
"""

import os
import requests
import statistics
from datetime import date, datetime, timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://lynevvhmstpcffobwudr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    raise SystemExit("SUPABASE_SERVICE_ROLE_KEY introuvable dans le .env.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

MIN_JOURS_RECUL = 15  # seuil minimum pour qu'un événement soit comparable


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


def main():
    print("=== Vérification hypothèse FY2025 — chute à l'ex-date (21/06/2026) ===\n")

    print("→ Chargement companies...")
    companies = fetch_all("companies", {"select": "id,symbol"})
    id_to_symbol = {c["id"]: c["symbol"] for c in companies}
    print(f"  {len(companies)} tickers.")

    print("\n→ Chargement corporate_events...")
    events = fetch_all("corporate_events", {"select": "*"})
    print(f"  {len(events)} événements total.")

    ex_div = [e for e in events if e.get("event_type") == "EX_DIVIDEND"]
    div_hist = [e for e in events if e.get("event_type") == "DIVIDEND_HISTORY"]
    div_richbourse = [e for e in events if e.get("event_type") == "DIVIDEND"]
    print(f"  EX_DIVIDEND: {len(ex_div)}  |  DIVIDEND_HISTORY: {len(div_hist)}  |  DIVIDEND (richbourse): {len(div_richbourse)}")

    # Index montant par (ticker, fiscal_year). Deux sources possibles :
    # DIVIDEND_HISTORY (sikafinance) et DIVIDEND (richbourse) — DIVIDEND prioritaire
    # si les deux existent (source jugée plus fiable, cf. session du 06/06/2026).
    montant_par_cle = {}
    for e in div_hist:
        ticker = e.get("ticker") or id_to_symbol.get(e.get("company_id"))
        fy = e.get("fiscal_year")
        amount = e.get("amount")
        if ticker and fy and amount:
            montant_par_cle[(ticker, str(fy))] = amount
    for e in div_richbourse:  # écrase DIVIDEND_HISTORY si présent — source prioritaire
        ticker = e.get("ticker") or id_to_symbol.get(e.get("company_id"))
        fy = e.get("fiscal_year")
        amount = e.get("amount")
        if ticker and fy and amount:
            montant_par_cle[(ticker, str(fy))] = amount

    # Joindre EX_DIVIDEND (date précise) avec le montant
    evenements_complets = []
    for e in ex_div:
        ticker = e.get("ticker") or id_to_symbol.get(e.get("company_id"))
        fy = e.get("fiscal_year")
        if not ticker or not fy:
            continue
        montant = montant_par_cle.get((ticker, str(fy))) or e.get("amount")
        if not montant:
            continue
        evenements_complets.append({
            "ticker": ticker,
            "fiscal_year": str(fy),
            "ex_date": e.get("event_date"),
            "dividend": montant,
        })

    print(f"\n  {len(evenements_complets)} événements avec montant exploitable.")

    today = date.today()
    fy2025_events = [e for e in evenements_complets if e["fiscal_year"] == "2025"]
    print(f"  dont {len(fy2025_events)} en FY2025.")

    if not fy2025_events:
        print("\n⚠️  Aucun événement FY2025 trouvé avec montant. Arrêt.")
        return

    print("\n→ Chargement des prix pour les tickers FY2025 concernés...")
    tickers_fy2025 = list({e["ticker"] for e in fy2025_events})
    company_ids = {s: cid for cid, s in id_to_symbol.items() if s in tickers_fy2025}

    prix_par_ticker = {}
    for ticker in tickers_fy2025:
        cid = company_ids.get(ticker)
        if not cid:
            continue
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,price", "company_id": f"eq.{cid}", "order": "trade_date.asc"},
        )
        prix_par_ticker[ticker] = {r["trade_date"]: r["price"] for r in rows}
        print(f"  {ticker}: {len(rows)} jours de prix")

    print("\n=== Analyse événement par événement (FY2025) ===\n")
    chutes_pct = []
    chutes_pct_avec_recul = []

    for evt in sorted(fy2025_events, key=lambda e: e["ex_date"]):
        ticker = evt["ticker"]
        ex_date_str = evt["ex_date"]
        dividende = evt["dividend"]
        prix = prix_par_ticker.get(ticker, {})

        if not ex_date_str or not prix:
            continue

        try:
            ex_date = datetime.strptime(ex_date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue

        jours_recul = (today - ex_date).days

        dates_disponibles = sorted(prix.keys())
        prix_j_moins_1 = None
        prix_j_0 = None
        for d in dates_disponibles:
            d_obj = datetime.strptime(d[:10], "%Y-%m-%d").date()
            if d_obj < ex_date:
                prix_j_moins_1 = prix[d]
            elif d_obj >= ex_date and prix_j_0 is None:
                prix_j_0 = prix[d]

        if not prix_j_moins_1 or not prix_j_0:
            print(f"  ⚠️  {ticker} FY2025 (ex={ex_date_str}) : prix J-1/J0 introuvables, ignoré.")
            continue

        chute_reelle = prix_j_moins_1 - prix_j_0
        chute_pct_du_div = round((chute_reelle / dividende) * 100, 1) if dividende else None

        statut_recul = f"J+{jours_recul}" if jours_recul >= 0 else "pas encore atteint"
        comparable = jours_recul >= MIN_JOURS_RECUL

        print(f"  {ticker:8s} ex={ex_date_str}  div={dividende:8.2f}  "
              f"J-1={prix_j_moins_1:8.2f}  J0={prix_j_0:8.2f}  "
              f"chute={chute_pct_du_div:6.1f}% du div  recul={statut_recul}  "
              f"{'✅ comparable' if comparable else '⚠️  recul insuffisant'}")

        if chute_pct_du_div is not None:
            chutes_pct.append(chute_pct_du_div)
            if comparable:
                chutes_pct_avec_recul.append(chute_pct_du_div)

    print("\n=== Résumé ===")
    if chutes_pct:
        print(f"Tous événements FY2025 (n={len(chutes_pct)}) : "
              f"médiane chute = {statistics.median(chutes_pct):.1f}% du dividende")
    if chutes_pct_avec_recul:
        print(f"Événements avec recul ≥{MIN_JOURS_RECUL}j (n={len(chutes_pct_avec_recul)}) : "
              f"médiane chute = {statistics.median(chutes_pct_avec_recul):.1f}% du dividende")
    else:
        print(f"⚠️  Aucun événement FY2025 n'a encore {MIN_JOURS_RECUL} jours de recul.")

    print(f"\nRéférence historique FY2021-2024 (établie le 05-06/06/2026) : médiane ~48%")
    print(f"Observation FY2025 au 06/06/2026 (recul insuffisant à l'époque) : médiane ~2%")

    if chutes_pct_avec_recul:
        mediane_actuelle = statistics.median(chutes_pct_avec_recul)
        if mediane_actuelle < 15:
            print(f"\n→ La chute FY2025 reste anormalement basse ({mediane_actuelle:.1f}%) même avec plus de recul.")
            print("  Cohérent avec H1 (apprentissage du marché) ou H2 (conjoncturel) — ne distingue pas encore les deux.")
            print("  Il faudra comparer avec FY2026 (dès avril 2027) pour voir si ça persiste.")
        elif mediane_actuelle < 35:
            print(f"\n→ La chute FY2025 se rapproche progressivement de l'historique ({mediane_actuelle:.1f}%).")
            print("  Possible que le chiffre du 06/06 (~2%) était un artefact de manque de recul, pas une vraie tendance.")
        else:
            print(f"\n→ La chute FY2025 a fortement convergé vers l'historique ({mediane_actuelle:.1f}%).")
            print("  Le chiffre du 06/06 était très probablement un artefact de données incomplètes (H2 invalidée pour 'apprentissage').")


if __name__ == "__main__":
    main()
