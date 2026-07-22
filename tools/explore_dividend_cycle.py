"""
tools/explore_dividend_cycle.py (exploration factuelle — T5c étape 0, pas de production)

Objectif : documenter de façon factuelle, sans règle de trading imposée,
comment le cours (et le volume si pertinent) évolue entre l'annonce d'un
dividende (AG) et son paiement effectif (DIVIDEND_PAYMENT), pour les 47
tickers BRVM.

Ceci N'EST PAS un backtest de stratégie. Aucune règle d'achat/vente n'est
appliquée ici — uniquement une observation factuelle de la trajectoire de
prix/volume sur la fenêtre annonce -> paiement, pour informer une décision
future (T5c) sur les règles exactes de la stratégie dividend capture.

Règles de construction des cycles (validées avec Jocelyn, 16/07/2026) :
  - date_annonce = l'AG la plus proche AVANT l'EX_DIVIDEND, dans une
    fenêtre de 20 à 45 jours (une même (ticker, fiscal_year) peut avoir
    plusieurs AG ; les AG hors de cette fenêtre sont ignorées, probablement
    des AG extraordinaires sans lien avec le dividende).
  - date_ex = EX_DIVIDEND (si plusieurs pour le même (ticker, fiscal_year),
    la première chronologiquement est retenue, l'autre flaggée comme doublon
    probable).
  - date_paiement = le DIVIDEND_PAYMENT le plus proche APRÈS date_ex.
  - montant/yield = DIVIDEND en priorité (montant précis daté), sinon
    DIVIDEND_HISTORY en fallback (montant connu mais date approximative,
    généralement 31/12).

Sortie : un CSV détaillé par cycle (un cycle = un (ticker, fiscal_year)
exploitable) + un résumé texte par ticker.
"""

import os
import csv
import statistics
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

FENETRE_AG_MIN = 5   # jours avant EX_DIVIDEND (élargi 16/07/2026 — 20j excluait des cas valides, ex. BOAB FY2025 à 14j)
FENETRE_AG_MAX = 120  # élargi 22/07/2026 — NTLC/SMBC ont un délai AG→ex de 62 à 104j


def fetch_all_tickers():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol&order=symbol.asc", headers=HEADERS)
    return [c["symbol"] for c in r.json()]


def fetch_all_events():
    """Récupère tous les corporate_events pertinents en une passe (pagination)."""
    all_rows = []
    offset, batch = 0, 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/corporate_events"
            f"?select=ticker,event_type,event_date,amount,yield_pct,fiscal_year"
            f"&event_type=in.(AG,EX_DIVIDEND,DIVIDEND_PAYMENT,DIVIDEND,DIVIDEND_HISTORY)"
            f"&ticker=not.is.null"
            f"&order=ticker.asc,event_date.asc"
            f"&offset={offset}&limit={batch}",
            headers=HEADERS
        )
        rows = r.json()
        if not rows:
            break
        all_rows.extend(rows)
        offset += batch
        if len(rows) < batch:
            break
    return all_rows


def fetch_prices(ticker):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/v_historical_prices"
        f"?select=trade_date,price,volume"
        f"&ticker=eq.{ticker}"
        f"&order=trade_date.asc",
        headers=HEADERS
    )
    rows = r.json()
    prices = {row["trade_date"]: row["price"] for row in rows if row.get("price") is not None}
    volumes = {row["trade_date"]: row.get("volume") for row in rows}
    return prices, volumes


def get_price_near(prices, target_date_str, window=10):
    target = date.fromisoformat(target_date_str)
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta * sign)).isoformat()
            if d in prices:
                return prices[d], d
    return None, None


def get_avg_volume_window(volumes, start_date_str, end_date_str):
    """Volume moyen quotidien sur la fenêtre [start, end], en ignorant les
    jours sans donnée (weekends/jours fériés/pas d'échange)."""
    start = date.fromisoformat(start_date_str)
    end = date.fromisoformat(end_date_str)
    if start > end:
        return None
    vals = []
    d = start
    while d <= end:
        v = volumes.get(d.isoformat())
        if v is not None:
            vals.append(v)
        d += timedelta(days=1)
    return round(statistics.mean(vals), 0) if vals else None


def construire_cycles(ticker, events_ticker):
    """Construit les cycles (ticker, fiscal_year) exploitables à partir des
    événements bruts d'un ticker."""
    by_type = {}
    for e in events_ticker:
        by_type.setdefault(e["event_type"], []).append(e)

    ex_divs = sorted(by_type.get("EX_DIVIDEND", []), key=lambda e: e["event_date"])
    ags = sorted(by_type.get("AG", []), key=lambda e: e["event_date"])
    payments = sorted(by_type.get("DIVIDEND_PAYMENT", []), key=lambda e: e["event_date"])
    dividends = by_type.get("DIVIDEND", [])
    dividend_history = by_type.get("DIVIDEND_HISTORY", [])

    # Dédoublonnage EX_DIVIDEND par fiscal_year : garder la première
    ex_div_par_fy = {}
    doublons = []
    for e in ex_divs:
        fy = e["fiscal_year"]
        if fy not in ex_div_par_fy:
            ex_div_par_fy[fy] = e
        else:
            doublons.append(e)

    cycles = []
    for fy, ex_div in ex_div_par_fy.items():
        date_ex = ex_div["event_date"]

        # AG la plus proche AVANT date_ex, dans la fenêtre 20-45j
        date_annonce = None
        for ag in ags:
            delta_j = (date.fromisoformat(date_ex) - date.fromisoformat(ag["event_date"])).days
            if FENETRE_AG_MIN <= delta_j <= FENETRE_AG_MAX:
                date_annonce = ag["event_date"]
                break

        candidats_ag = [
            ag["event_date"] for ag in ags
            if FENETRE_AG_MIN <= (date.fromisoformat(date_ex) - date.fromisoformat(ag["event_date"])).days <= FENETRE_AG_MAX
        ]
        date_annonce = max(candidats_ag) if candidats_ag else None

        candidats_paiement = [
            p["event_date"] for p in payments
            if p["event_date"] >= date_ex
        ]
        date_paiement = min(candidats_paiement) if candidats_paiement else None

        montant, yield_pct, source_montant = None, None, None
        for d in dividends:
            if d["fiscal_year"] == fy and d.get("amount"):
                montant, yield_pct, source_montant = d["amount"], d.get("yield_pct"), "DIVIDEND"
                break
        if montant is None:
            for d in dividend_history:
                if d["fiscal_year"] == fy and d.get("amount"):
                    montant, yield_pct, source_montant = d["amount"], d.get("yield_pct"), "DIVIDEND_HISTORY"
                    break

        cycles.append({
            "ticker": ticker,
            "fiscal_year": fy,
            "date_annonce": date_annonce,
            "date_ex": date_ex,
            "date_paiement": date_paiement,
            "montant": montant,
            "yield_pct": yield_pct,
            "source_montant": source_montant,
            "n_ex_div_doublons_ignores": len(doublons),
        })

    return cycles


def analyser_cycle(cycle, prices, volumes):
    resultat = dict(cycle)
    resultat["exploitable"] = False
    resultat["raison_non_exploitable"] = None

    if not cycle["date_annonce"]:
        resultat["raison_non_exploitable"] = f"pas d'AG trouvée dans la fenêtre {FENETRE_AG_MIN}-{FENETRE_AG_MAX}j avant EX_DIVIDEND"
        return resultat
    if not cycle["date_paiement"]:
        resultat["raison_non_exploitable"] = "pas de DIVIDEND_PAYMENT après EX_DIVIDEND"
        return resultat
    if not cycle["montant"]:
        resultat["raison_non_exploitable"] = "montant dividende introuvable (ni DIVIDEND ni DIVIDEND_HISTORY)"
        return resultat
    if not prices:
        resultat["raison_non_exploitable"] = "aucune donnée de prix pour ce ticker"
        return resultat

    prix_annonce, _ = get_price_near(prices, cycle["date_annonce"])
    prix_veille_ex, _ = get_price_near(prices, (date.fromisoformat(cycle["date_ex"]) - timedelta(days=1)).isoformat())
    prix_jour_ex, _ = get_price_near(prices, cycle["date_ex"])
    prix_paiement, _ = get_price_near(prices, cycle["date_paiement"])

    if not all([prix_annonce, prix_veille_ex, prix_jour_ex, prix_paiement]):
        resultat["raison_non_exploitable"] = "prix manquant sur une des 4 dates clés (annonce/veille-ex/ex/paiement)"
        return resultat

    resultat["prix_annonce"] = prix_annonce
    resultat["prix_veille_ex"] = prix_veille_ex
    resultat["prix_jour_ex"] = prix_jour_ex
    resultat["prix_paiement"] = prix_paiement

    resultat["variation_annonce_a_veille_ex_pct"] = round(
        (prix_veille_ex - prix_annonce) / prix_annonce * 100, 2
    )

    chute_reelle = prix_veille_ex - prix_jour_ex
    resultat["chute_reelle_fcfa"] = round(chute_reelle, 2)
    resultat["chute_reelle_pct_du_dividende"] = (
        round(chute_reelle / cycle["montant"] * 100, 1) if cycle["montant"] else None
    )

    resultat["variation_ex_a_paiement_pct"] = round(
        (prix_paiement - prix_jour_ex) / prix_jour_ex * 100, 2
    )

    resultat["variation_totale_annonce_a_paiement_pct"] = round(
        (prix_paiement - prix_annonce) / prix_annonce * 100, 2
    )

    resultat["volume_moyen_avant_annonce"] = get_avg_volume_window(
        volumes,
        (date.fromisoformat(cycle["date_annonce"]) - timedelta(days=20)).isoformat(),
        cycle["date_annonce"]
    )
    resultat["volume_moyen_annonce_a_ex"] = get_avg_volume_window(
        volumes, cycle["date_annonce"], cycle["date_ex"]
    )
    resultat["volume_moyen_ex_a_paiement"] = get_avg_volume_window(
        volumes, cycle["date_ex"], cycle["date_paiement"]
    )

    resultat["exploitable"] = True
    return resultat


def run():
    print("Chargement tickers...")
    tickers = fetch_all_tickers()
    print(f"  {len(tickers)} tickers")

    print("Chargement corporate_events...")
    all_events = fetch_all_events()
    print(f"  {len(all_events)} événements pertinents")

    events_par_ticker = {}
    for e in all_events:
        events_par_ticker.setdefault(e["ticker"], []).append(e)

    tous_cycles = []
    print("\nAnalyse par ticker...")
    for ticker in tickers:
        events_ticker = events_par_ticker.get(ticker, [])
        cycles = construire_cycles(ticker, events_ticker)

        if not cycles:
            tous_cycles.append({
                "ticker": ticker, "fiscal_year": None, "exploitable": False,
                "raison_non_exploitable": "aucun événement dividende (AG/EX_DIVIDEND) trouvé pour ce ticker",
            })
            continue

        prices, volumes = fetch_prices(ticker)
        for cycle in cycles:
            resultat = analyser_cycle(cycle, prices, volumes)
            tous_cycles.append(resultat)

    n_exploitables = sum(1 for c in tous_cycles if c.get("exploitable"))
    n_total = len(tous_cycles)
    print(f"\n{n_exploitables}/{n_total} cycles exploitables (sur {len(tickers)} tickers)")

    colonnes = [
        "ticker", "fiscal_year", "exploitable", "raison_non_exploitable",
        "date_annonce", "date_ex", "date_paiement", "montant", "yield_pct", "source_montant",
        "n_ex_div_doublons_ignores",
        "prix_annonce", "prix_veille_ex", "prix_jour_ex", "prix_paiement",
        "variation_annonce_a_veille_ex_pct", "chute_reelle_fcfa", "chute_reelle_pct_du_dividende",
        "variation_ex_a_paiement_pct", "variation_totale_annonce_a_paiement_pct",
        "volume_moyen_avant_annonce", "volume_moyen_annonce_a_ex", "volume_moyen_ex_a_paiement",
    ]
    with open("dividend_cycle_exploration.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        writer.writeheader()
        for c in tous_cycles:
            writer.writerow(c)

    with open("dividend_cycle_exploration_resume.txt", "w") as f:
        f.write("EXPLORATION FACTUELLE — CYCLE DIVIDENDE (ANNONCE -> PAIEMENT)\n")
        f.write("=" * 70 + "\n")
        f.write(f"{n_exploitables}/{n_total} cycles exploitables sur {len(tickers)} tickers\n\n")

        exploitables = [c for c in tous_cycles if c.get("exploitable")]
        if exploitables:
            var_totale = [c["variation_totale_annonce_a_paiement_pct"] for c in exploitables]
            chute_pct = [c["chute_reelle_pct_du_dividende"] for c in exploitables if c["chute_reelle_pct_du_dividende"] is not None]

            f.write(f"Variation totale annonce->paiement : médiane={statistics.median(var_totale):+.1f}%, "
                    f"moyenne={statistics.mean(var_totale):+.1f}%\n")
            if chute_pct:
                f.write(f"Chute réelle à l'ex-date (% du dividende) : médiane={statistics.median(chute_pct):.1f}%, "
                        f"moyenne={statistics.mean(chute_pct):.1f}%\n")
            f.write("\n")

        f.write("Détail par cycle exploitable :\n")
        f.write("-" * 70 + "\n")
        for c in sorted(exploitables, key=lambda x: (x["ticker"], x["fiscal_year"])):
            f.write(
                f"{c['ticker']:<8} FY{c['fiscal_year']:<6} "
                f"annonce={c['date_annonce']} ex={c['date_ex']} paiement={c['date_paiement']} "
                f"div={c['montant']}F ({c['source_montant']}) "
                f"| var_totale={c['variation_totale_annonce_a_paiement_pct']:+.1f}% "
                f"chute_ex={c['chute_reelle_pct_du_dividende']}%\n"
            )

        non_exploitables = [c for c in tous_cycles if not c.get("exploitable")]
        f.write(f"\nCycles NON exploitables ({len(non_exploitables)}) :\n")
        f.write("-" * 70 + "\n")
        for c in non_exploitables:
            fy_str = f"FY{c['fiscal_year']}" if c.get("fiscal_year") else "(aucun cycle)"
            f.write(f"{c['ticker']:<8} {fy_str:<8} — {c['raison_non_exploitable']}\n")

    print("\nFichiers générés : dividend_cycle_exploration.csv, dividend_cycle_exploration_resume.txt")


if __name__ == "__main__":
    run()
