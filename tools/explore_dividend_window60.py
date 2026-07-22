"""
tools/explore_dividend_window60.py (exploration factuelle — T5c étape 0, pas de production)

Objectif : documenter factuellement, sans règle de trading, comment le cours
et le volume échangé évoluent sur une fenêtre symétrique de ±60 jours
calendaires autour de la date de PAIEMENT du dividende (DIVIDEND_PAYMENT),
pour chaque cycle (ticker, fiscal_year) exploitable sur les 47 tickers BRVM.

Changement d'approche (16/07/2026) par rapport à explore_dividend_cycle.py :
ancrage sur une seule date fiable (paiement) plutôt que sur l'AG, qui
introduisait une fenêtre de tolérance arbitraire et excluait ~50% des cycles.

Ceci N'EST PAS un backtest de stratégie. Aucune règle d'achat/vente n'est
appliquée ici.

Sorties :
  - dividend_window60_series.csv : une ligne par (ticker, fiscal_year, jour
    relatif J-60..J+60), avec prix et volume si disponibles ce jour-là.
  - dividend_window60_stats.csv : une ligne par (ticker, fiscal_year), avec
    des statistiques agrégées (prix moyen avant/après, volume moyen
    avant/après, variation totale, etc.)
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

FENETRE_JOURS = 60  # ±60 jours calendaires autour du paiement


def fetch_all_tickers():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol&order=symbol.asc", headers=HEADERS)
    return [c["symbol"] for c in r.json()]


def fetch_all_events():
    all_rows = []
    offset, batch = 0, 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/corporate_events"
            f"?select=ticker,event_type,event_date,amount,yield_pct,fiscal_year"
            f"&event_type=in.(EX_DIVIDEND,DIVIDEND_PAYMENT,DIVIDEND,DIVIDEND_HISTORY)"
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


def construire_cycles_paiement(ticker, events_ticker):
    by_type = {}
    for e in events_ticker:
        by_type.setdefault(e["event_type"], []).append(e)

    payments = sorted(by_type.get("DIVIDEND_PAYMENT", []), key=lambda e: e["event_date"])
    ex_divs = by_type.get("EX_DIVIDEND", [])
    dividends = by_type.get("DIVIDEND", [])
    dividend_history = by_type.get("DIVIDEND_HISTORY", [])

    cycles = []
    fy_dejavu = set()
    for p in payments:
        fy = p["fiscal_year"]
        if fy in fy_dejavu:
            continue
        fy_dejavu.add(fy)

        date_ex = None
        for e in ex_divs:
            if e["fiscal_year"] == fy:
                date_ex = e["event_date"]
                break

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
            "date_paiement": p["event_date"],
            "date_ex": date_ex,
            "montant": montant,
            "yield_pct": yield_pct,
            "source_montant": source_montant,
        })

    return cycles


def get_price_volume_at(prices, volumes, d_str):
    return prices.get(d_str), volumes.get(d_str)


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

    series_rows = []
    stats_rows = []

    print("\nAnalyse par ticker...")
    for ticker in tickers:
        events_ticker = events_par_ticker.get(ticker, [])
        cycles = construire_cycles_paiement(ticker, events_ticker)

        if not cycles:
            stats_rows.append({
                "ticker": ticker, "fiscal_year": None, "exploitable": False,
                "raison_non_exploitable": "aucun DIVIDEND_PAYMENT trouvé pour ce ticker",
            })
            continue

        prices, volumes = fetch_prices(ticker)
        if not prices:
            for cycle in cycles:
                stats_rows.append({
                    **cycle, "exploitable": False,
                    "raison_non_exploitable": "aucune donnée de prix pour ce ticker",
                })
            continue

        for cycle in cycles:
            date_paiement = date.fromisoformat(cycle["date_paiement"])
            prix_j = {}
            vol_j = {}
            n_jours_avec_prix = 0

            for offset in range(-FENETRE_JOURS, FENETRE_JOURS + 1):
                d = date_paiement + timedelta(days=offset)
                d_str = d.isoformat()
                prix, vol = get_price_volume_at(prices, volumes, d_str)

                series_rows.append({
                    "ticker": ticker,
                    "fiscal_year": cycle["fiscal_year"],
                    "date_paiement_ref": cycle["date_paiement"],
                    "jour_relatif": offset,
                    "date": d_str,
                    "prix": prix,
                    "volume": vol,
                })

                if prix is not None:
                    prix_j[offset] = prix
                    n_jours_avec_prix += 1
                if vol is not None:
                    vol_j[offset] = vol

            if n_jours_avec_prix < 20:
                stats_rows.append({
                    **cycle, "exploitable": False,
                    "raison_non_exploitable": f"seulement {n_jours_avec_prix} jours avec prix sur la fenêtre ±{FENETRE_JOURS}j",
                })
                continue

            prix_avant = [v for k, v in prix_j.items() if k < 0]
            prix_apres = [v for k, v in prix_j.items() if k > 0]
            vol_avant = [v for k, v in vol_j.items() if k < 0]
            vol_apres = [v for k, v in vol_j.items() if k > 0]

            prix_j0 = prix_j.get(0)
            prix_j_moins_1 = prix_j.get(-1)
            prix_debut_fenetre = prix_j.get(min(prix_j.keys())) if prix_j else None
            prix_fin_fenetre = prix_j.get(max(prix_j.keys())) if prix_j else None

            stats_rows.append({
                **cycle,
                "exploitable": True,
                "raison_non_exploitable": None,
                "n_jours_avec_prix": n_jours_avec_prix,
                "prix_moyen_avant": round(statistics.mean(prix_avant), 2) if prix_avant else None,
                "prix_moyen_apres": round(statistics.mean(prix_apres), 2) if prix_apres else None,
                "prix_debut_fenetre_j_moins_60": prix_debut_fenetre,
                "prix_fin_fenetre_j_plus_60": prix_fin_fenetre,
                "prix_veille_paiement_j_moins_1": prix_j_moins_1,
                "prix_jour_paiement_j0": prix_j0,
                "variation_totale_pct": (
                    round((prix_fin_fenetre - prix_debut_fenetre) / prix_debut_fenetre * 100, 2)
                    if prix_debut_fenetre and prix_fin_fenetre else None
                ),
                "variation_avant_pct": (
                    round((prix_j_moins_1 - prix_debut_fenetre) / prix_debut_fenetre * 100, 2)
                    if prix_debut_fenetre and prix_j_moins_1 else None
                ),
                "variation_apres_pct": (
                    round((prix_fin_fenetre - prix_j0) / prix_j0 * 100, 2)
                    if prix_j0 and prix_fin_fenetre else None
                ),
                "volume_moyen_avant": round(statistics.mean(vol_avant), 0) if vol_avant else None,
                "volume_moyen_apres": round(statistics.mean(vol_apres), 0) if vol_apres else None,
                "ratio_volume_apres_sur_avant": (
                    round(statistics.mean(vol_apres) / statistics.mean(vol_avant), 2)
                    if vol_avant and vol_apres and statistics.mean(vol_avant) > 0 else None
                ),
            })

    n_exploitables = sum(1 for c in stats_rows if c.get("exploitable"))
    n_total = len(stats_rows)
    print(f"\n{n_exploitables}/{n_total} cycles exploitables (sur {len(tickers)} tickers)")

    colonnes_serie = ["ticker", "fiscal_year", "date_paiement_ref", "jour_relatif", "date", "prix", "volume"]
    with open("dividend_window60_series.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=colonnes_serie, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(series_rows)

    colonnes_stats = [
        "ticker", "fiscal_year", "exploitable", "raison_non_exploitable",
        "date_paiement", "date_ex", "montant", "yield_pct", "source_montant",
        "n_jours_avec_prix",
        "prix_debut_fenetre_j_moins_60", "prix_veille_paiement_j_moins_1",
        "prix_jour_paiement_j0", "prix_fin_fenetre_j_plus_60",
        "prix_moyen_avant", "prix_moyen_apres",
        "variation_totale_pct", "variation_avant_pct", "variation_apres_pct",
        "volume_moyen_avant", "volume_moyen_apres", "ratio_volume_apres_sur_avant",
    ]
    with open("dividend_window60_stats.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=colonnes_stats, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(stats_rows)

    exploitables = [c for c in stats_rows if c.get("exploitable")]
    with open("dividend_window60_resume.txt", "w") as f:
        f.write("EXPLORATION FACTUELLE — FENÊTRE ±60J AUTOUR DU PAIEMENT DE DIVIDENDE\n")
        f.write("=" * 70 + "\n")
        f.write(f"{n_exploitables}/{n_total} cycles exploitables sur {len(tickers)} tickers\n\n")

        if exploitables:
            var_totale = [c["variation_totale_pct"] for c in exploitables if c["variation_totale_pct"] is not None]
            var_avant = [c["variation_avant_pct"] for c in exploitables if c["variation_avant_pct"] is not None]
            var_apres = [c["variation_apres_pct"] for c in exploitables if c["variation_apres_pct"] is not None]
            ratios_vol = [c["ratio_volume_apres_sur_avant"] for c in exploitables if c["ratio_volume_apres_sur_avant"] is not None]

            f.write(f"Variation totale (J-60 à J+60)  : médiane={statistics.median(var_totale):+.1f}%, moyenne={statistics.mean(var_totale):+.1f}% (n={len(var_totale)})\n")
            f.write(f"Variation avant (J-60 à J-1)     : médiane={statistics.median(var_avant):+.1f}%, moyenne={statistics.mean(var_avant):+.1f}% (n={len(var_avant)})\n")
            f.write(f"Variation après (J0 à J+60)      : médiane={statistics.median(var_apres):+.1f}%, moyenne={statistics.mean(var_apres):+.1f}% (n={len(var_apres)})\n")
            if ratios_vol:
                f.write(f"Ratio volume après/avant          : médiane={statistics.median(ratios_vol):.2f}x, moyenne={statistics.mean(ratios_vol):.2f}x (n={len(ratios_vol)})\n")
            f.write("\n")

        f.write("Détail par cycle exploitable :\n")
        f.write("-" * 70 + "\n")
        for c in sorted(exploitables, key=lambda x: (x["ticker"], x["fiscal_year"])):
            va = f"{c['variation_avant_pct']:+.1f}%" if c['variation_avant_pct'] is not None else "N/A"
            vp = f"{c['variation_apres_pct']:+.1f}%" if c['variation_apres_pct'] is not None else "N/A"
            vt = f"{c['variation_totale_pct']:+.1f}%" if c['variation_totale_pct'] is not None else "N/A"
            rv = f"{c['ratio_volume_apres_sur_avant']:.2f}x" if c['ratio_volume_apres_sur_avant'] is not None else "N/A"
            f.write(
                f"{c['ticker']:<8} FY{c['fiscal_year']:<6} paiement={c['date_paiement']} "
                f"div={c['montant']}F ({c['source_montant']}) "
                f"| avant={va} après={vp} total={vt} vol_ratio={rv}\n"
            )

        non_exploitables = [c for c in stats_rows if not c.get("exploitable")]
        f.write(f"\nCycles NON exploitables ({len(non_exploitables)}) :\n")
        f.write("-" * 70 + "\n")
        for c in non_exploitables:
            fy_str = f"FY{c['fiscal_year']}" if c.get("fiscal_year") else "(aucun cycle)"
            f.write(f"{c['ticker']:<8} {fy_str:<8} — {c['raison_non_exploitable']}\n")

    print("\nFichiers générés :")
    print("  dividend_window60_series.csv  (série jour-par-jour)")
    print("  dividend_window60_stats.csv   (stats agrégées)")
    print("  dividend_window60_resume.txt  (résumé lisible)")


if __name__ == "__main__":
    run()
