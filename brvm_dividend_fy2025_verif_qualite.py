"""
brvm_dividend_fy2025_verif_qualite.py

Vérifie systématiquement, pour les 11 événements FY2025 jugés "comparables"
(recul ≥15j) dans brvm_dividend_fy2025_check.py, si la chute mesurée à l'ex-date
est fiable ou un artefact de données. Deux contrôles :

1. Prix figé anormal : combien de jours consécutifs identiques autour de
   l'ex-date, avec le volume associé (prix figé + volume non-nul = suspect).
2. Vrai dernier mouvement avant l'ex-date : au lieu de prendre J-1 strictement,
   on remonte jusqu'au dernier jour où le prix a RÉELLEMENT changé, pour ne
   pas rater un mouvement anticipatoire qui aurait eu lieu plus tôt que J-1
   (biais découvert sur ORAC : saut à J-1 réel, mais figé ensuite).

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


# Les 11 événements "comparables" identifiés dans le run précédent
EVENEMENTS = [
    ("BOABF", "2026-04-22", 397.00),
    ("BOAC", "2026-05-05", 594.53),
    ("BOAB", "2026-05-14", 585.00),
    ("ECOC", "2026-05-21", 888.00),
    ("SNTS", "2026-05-22", 1740.00),
    ("ECOC", "2026-05-22", 888.00),
    ("BOAB", "2026-05-22", 585.00),
    ("BOAS", "2026-05-29", 450.00),
    ("CABC", "2026-05-29", 152.02),
    ("BOAM", "2026-06-02", 305.04),
    ("ORAC", "2026-06-05", 800.00),
]


def main():
    companies = fetch_all("companies", {"select": "id,symbol"})
    symbol_to_id = {c["symbol"]: c["id"] for c in companies}

    print("=== Vérification qualité — 11 événements FY2025 comparables ===\n")

    resultats_fiables = []
    resultats_suspects = []

    for ticker, ex_date_str, dividende in EVENEMENTS:
        cid = symbol_to_id.get(ticker)
        if not cid:
            print(f"⚠️  {ticker} introuvable.")
            continue

        ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d").date()
        debut = (ex_date - timedelta(days=15)).isoformat()
        fin = (ex_date + timedelta(days=5)).isoformat()

        rows = fetch_all(
            "historical_data",
            {
                "select": "trade_date,price,volume",
                "company_id": f"eq.{cid}",
                "trade_date": f"gte.{debut}",
                "order": "trade_date.asc",
            },
        )
        rows = [r for r in rows if r["trade_date"][:10] <= fin]
        if not rows:
            print(f"⚠️  {ticker} {ex_date_str} : aucun prix trouvé dans la fenêtre.")
            continue

        avant_ex = [r for r in rows if r["trade_date"][:10] < ex_date_str]
        apres_ou_egal = [r for r in rows if r["trade_date"][:10] >= ex_date_str]

        if not avant_ex or not apres_ou_egal:
            print(f"⚠️  {ticker} {ex_date_str} : fenêtre avant/après incomplète.")
            continue

        prix_j0 = apres_ou_egal[0]["price"]
        prix_j_moins_1_strict = avant_ex[-1]["price"]

        # CORRECTION v2 (bug v1 identifié : la boucle se déclenchait dès la
        # moindre variation normale jour-à-jour, pas seulement sur un vrai
        # plateau). On ne remonte que si J-1 ET J-2 sont identiques (= début
        # d'un plateau d'au moins 2 jours), signe d'un mouvement anticipatoire
        # qui s'est figé tôt — comme observé sur ORAC (16975 à J-1 ET J-2).
        # Sinon, J-1 strict est gardé tel quel (cas normal de marché qui varie
        # légèrement chaque jour, ce qui est l'écrasante majorité des cas).
        prix_avant_mouvement = prix_j_moins_1_strict
        mouvement_detecte_avant_j1 = False
        if len(avant_ex) >= 2 and avant_ex[-2]["price"] == prix_j_moins_1_strict:
            idx = len(avant_ex) - 1
            while idx > 0 and avant_ex[idx]["price"] == prix_j_moins_1_strict:
                idx -= 1
            prix_avant_mouvement = avant_ex[idx]["price"]
            mouvement_detecte_avant_j1 = prix_avant_mouvement != prix_j_moins_1_strict

        fenetre_proche = [r for r in rows
                           if abs((datetime.strptime(r["trade_date"][:10], "%Y-%m-%d").date() - ex_date).days) <= 5]
        prix_set = {r["price"] for r in fenetre_proche}
        volumes_sur_plateau = [r.get("volume", 0) or 0 for r in fenetre_proche]
        plateau_suspect = (
            len(prix_set) == 1
            and len(fenetre_proche) >= 5
            and max(volumes_sur_plateau) > 0
        )

        chute_strict = prix_j_moins_1_strict - prix_j0
        chute_pct_strict = round((chute_strict / dividende) * 100, 1) if dividende else None

        chute_corrigee = prix_avant_mouvement - prix_j0
        chute_pct_corrigee = round((chute_corrigee / dividende) * 100, 1) if dividende else None

        statut = "🔴 SUSPECT (prix figé + volume actif)" if plateau_suspect else "✅ fiable"
        flag_mvt = " ⚠️ mouvement détecté avant J-1 !" if mouvement_detecte_avant_j1 else ""

        print(f"{ticker:8s} ex={ex_date_str}  div={dividende:8.2f}  "
              f"J-1={prix_j_moins_1_strict:8.2f}  J0={prix_j0:8.2f}  "
              f"chute_strict={chute_pct_strict:6.1f}%  chute_corrigee={chute_pct_corrigee:6.1f}%  "
              f"prix_distincts_fenetre±5j={len(prix_set)}  {statut}{flag_mvt}")

        chute_a_retenir = chute_pct_corrigee if mouvement_detecte_avant_j1 else chute_pct_strict

        if plateau_suspect:
            resultats_suspects.append((ticker, ex_date_str, chute_a_retenir))
        else:
            resultats_fiables.append((ticker, ex_date_str, chute_a_retenir))

    print(f"\n=== Résumé ===")
    print(f"Événements fiables    : {len(resultats_fiables)}")
    print(f"Événements suspects   : {len(resultats_suspects)} (prix figé anormalement + volume actif)")

    if resultats_fiables:
        chutes = [c for _, _, c in resultats_fiables if c is not None]
        print(f"\nMédiane chute (événements FIABLES uniquement, n={len(chutes)}) : "
              f"{statistics.median(chutes):.1f}% du dividende")
    else:
        print("\n⚠️  Aucun événement fiable — impossible de conclure sur la médiane.")

    if resultats_suspects:
        print(f"\nTickers/dates à corriger en priorité dans le pipeline de scraping :")
        for ticker, date_, _ in resultats_suspects:
            print(f"  - {ticker} ({date_})")


if __name__ == "__main__":
    main()
