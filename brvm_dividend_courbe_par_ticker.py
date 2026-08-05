"""
brvm_dividend_courbe_par_ticker.py

Construit, pour chaque événement FY2025, la courbe jour-par-jour du z-score
de prix dans la fenêtre [J-30, J-1] avant l'ex-date — pour visualiser à
partir de quel jour le marché commence à intégrer le dividende, ticker par
ticker, plutôt qu'une seule réponse moyenne agrégée.

LIMITE IMPORTANTE (à garder en tête en lisant les résultats) :
La plupart des tickers n'ont qu'1 SEUL événement FY2025 disponible à ce jour.
Une courbe sur 1 événement est DESCRIPTIVE (ce qui s'est passé cette fois),
pas un signal statistiquement validé sur le rythme propre du ticker — il
faudra plusieurs saisons (FY2026, FY2027...) pour confirmer si le rythme
observé est stable et spécifique au ticker, ou juste du bruit d'un seul cas.

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


def courbe_jour_par_jour(rows_prix, ex_date, jours_max=30):
    """
    Pour chaque jour J-N (N de jours_max à 1), calcule :
    - le prix à ce jour
    - la variation % depuis J-jours_max (référence = début de fenêtre)
    - normalisée par la volatilité habituelle (écart-type des variations
      quotidiennes sur les 70 jours précédant la fenêtre [J-jours_max-70, J-jours_max])
    Retourne une liste de (jours_avant_exdate, variation_pct, z_score).
    """
    par_date = {}
    for r in rows_prix:
        try:
            d = datetime.strptime(r["trade_date"][:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        par_date[d] = r["price"]

    dates_triees = sorted(par_date.keys())

    cible_debut = ex_date - timedelta(days=jours_max)
    dates_ref = [d for d in dates_triees if d <= cible_debut]
    if not dates_ref:
        return []
    prix_ref = par_date[dates_ref[-1]]
    if not prix_ref or prix_ref == 0:
        return []

    dates_base = [d for d in dates_triees
                  if (ex_date - d).days >= jours_max and (ex_date - d).days <= jours_max + 70]
    variations_base = []
    for i in range(1, len(dates_base)):
        p0 = par_date[dates_base[i - 1]]
        p1 = par_date[dates_base[i]]
        if p0 and p0 != 0:
            variations_base.append((p1 - p0) / p0 * 100)

    ecart_type = statistics.stdev(variations_base) if len(variations_base) >= 5 else None

    courbe = []
    for n in range(jours_max, 0, -1):
        cible = ex_date - timedelta(days=n)
        dates_dispo = [d for d in dates_triees if d <= cible]
        if not dates_dispo:
            continue
        prix_n = par_date[dates_dispo[-1]]
        variation_pct = (prix_n - prix_ref) / prix_ref * 100
        z = (variation_pct / ecart_type) if ecart_type and ecart_type != 0 else None
        courbe.append((n, round(variation_pct, 2), round(z, 2) if z is not None else None))

    return courbe


EVENEMENTS_FY2025 = [
    ("BOAB", "2026-05-14"),
    ("BOAC", "2026-05-05"),
    ("ECOC", "2026-05-21"),
    ("SNTS", "2026-05-22"),
    ("BOAS", "2026-05-29"),
    ("CABC", "2026-05-29"),
    ("BOAM", "2026-06-02"),
    ("ORAC", "2026-06-05"),
]


def main():
    companies = fetch_all("companies", {"select": "id,symbol"})
    symbol_to_id = {c["symbol"]: c["id"] for c in companies}

    print("=== Courbes jour-par-jour — montée pré-ex-date par ticker (FY2025) ===")
    print("⚠️  Rappel : 1 seul événement par ticker = DESCRIPTIF, pas un signal validé.\n")

    for ticker, ex_date_str in EVENEMENTS_FY2025:
        cid = symbol_to_id.get(ticker)
        if not cid:
            print(f"⚠️  {ticker} introuvable.\n")
            continue

        ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d").date()
        debut = (ex_date - timedelta(days=105)).isoformat()
        rows = fetch_all(
            "historical_data",
            {"select": "trade_date,price", "company_id": f"eq.{cid}", "trade_date": f"gte.{debut}"},
        )
        courbe = courbe_jour_par_jour(rows, ex_date, jours_max=30)

        if not courbe:
            print(f"{ticker} — pas assez de données pour construire la courbe.\n")
            continue

        print(f"=== {ticker} (ex-date {ex_date_str}) ===")
        print(f"  {'J-N':>5}  {'var%':>8}  {'z-score':>8}")
        for n, var_pct, z in courbe:
            marqueur = ""
            if z is not None and abs(z) >= 1.5:
                marqueur = "  ← décollage notable"
            print(f"  J-{n:<3}  {var_pct:>7.2f}%  {str(z):>8}{marqueur}")
        print()


if __name__ == "__main__":
    main()
