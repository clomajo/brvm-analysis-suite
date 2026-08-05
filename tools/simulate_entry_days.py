#!/usr/bin/env python3
"""
D1 — Simulation des jours d'entrée fixes post-détachement dividende.

Classe A : lecture seule, aucune écriture en base.

Question : quel jour d'entrée FIXE (J+0 à J+15) après détachement maximise
le rendement ? Distinct de `min_day` de brvm_dividend_analysis_v3b.py, qui
est un optimum a posteriori non exploitable ex ante.

Spécification validée (session 03-04/08/2026) :
  - Entrée : clôture du jour J+N (cotation suivante si jour non coté)
  - Sorties : (a) fill du cours pré-détachement, (b) J+30 fixe
  - Rendement en prix seul (le dividende n'est pas touché par un acheteur
    post-détachement) ; la sur-réaction est mesurée vs prix ex-div théorique
  - Alpha = rendement titre − rendement BRVMC sur la MÊME fenêtre calendaire
  - Univers séparés : dividend capture (6 tickers) vs autres
  - Brut : ni frais ni IRVM (protocole brut-first, sensibilité à faire a posteriori)
  - Sans fill : sortie forcée à J+90, comptée (ne PAS exclure — biaiserait
    l'échantillon vers les événements favorables)

RÉSERVES MÉTHODOLOGIQUES (cf. SESSION_2026-08-03_DIVIDENDE.md) :
  - Les 99 événements ne sont pas indépendants (~30 tickers, groupement
    temporel : plusieurs détachements peuvent partager un même contexte de marché)
  - 16 jours d'entrée testés sur 99 observations = risque de sur-ajustement.
    Un "meilleur jour" ressortira mécaniquement, signal ou non.
  - Ceci est une EXPLORATION, pas une validation. Un walk-forward
    (calibration 2016-2022 / validation 2023-2026) reste nécessaire.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("D1")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env")

HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

UNIVERS_DIVIDEND_CAPTURE = {"BOAB", "BOAC", "ECOC", "SMBC", "NSBC", "NTLC"}
BRVMC_COMPANY_ID = 48
JOURS_ENTREE = range(0, 16)
HORIZON_FIXE = 30
HORIZON_MAX = 90
INPUT_JSON = "brvm_dividend_results.json"


def fetch_all(table, params):
    """Pagination REST Supabase (limite 1000 lignes par requête)."""
    rows, offset = [], 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}&limit=1000&offset={offset}"
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def charger_series_prix():
    """Retourne {ticker: {date_iso: price}} et {date_iso: price} pour le BRVMC."""
    log.info("Chargement de companies...")
    companies = fetch_all("companies", "select=id,symbol")
    id_to_symbol = {c["id"]: c["symbol"] for c in companies}

    log.info("Chargement de historical_data (peut prendre 1-2 min)...")
    rows = fetch_all(
        "historical_data",
        "select=company_id,trade_date,price&order=trade_date.asc",
    )
    log.info("%d lignes de prix chargées", len(rows))

    prix = defaultdict(dict)
    brvmc = {}
    for row in rows:
        if row["price"] is None:
            continue
        if row["company_id"] == BRVMC_COMPANY_ID:
            brvmc[row["trade_date"]] = row["price"]
            continue
        symbol = id_to_symbol.get(row["company_id"])
        if symbol:
            prix[symbol][row["trade_date"]] = row["price"]

    log.info("BRVMC : %d séances", len(brvmc))
    return prix, brvmc


def serie_ordonnee(serie, depuis, jusqu_a_n_jours):
    """Liste [(date, prix)] triée, à partir de `depuis` (incluse), bornée en jours calendaires."""
    d0 = datetime.fromisoformat(depuis)
    fin = d0 + timedelta(days=jusqu_a_n_jours)
    out = []
    for date_str, p in serie.items():
        d = datetime.fromisoformat(date_str)
        if d0 <= d <= fin:
            out.append((date_str, p))
    out.sort(key=lambda x: x[0])
    return out


def charger_evenements():
    """Charge le JSON de v3b et applique le filtrage validé."""
    with open(INPUT_JSON) as f:
        events = json.load(f)["events"]

    total = len(events)
    filtres, exclus = [], defaultdict(int)

    for e in events:
        if e.get("actual_drop") == 0:
            exclus["cours inchangé (absence de cotation)"] += 1
            continue
        if e["ex_date"].endswith("12-31"):
            exclus["ex_date = fin d'exercice fiscal"] += 1
            continue
        filtres.append(e)

    log.info("Événements : %d bruts → %d retenus", total, len(filtres))
    for motif, n in sorted(exclus.items()):
        log.info("  exclus (%d) : %s", n, motif)

    return filtres


def rendement_benchmark(brvmc, date_debut, date_fin):
    """Rendement BRVMC entre deux dates. Prend la cotation disponible la plus proche."""
    dispo = sorted(brvmc.keys())
    d_in = next((d for d in dispo if d >= date_debut), None)
    d_out = next((d for d in dispo if d >= date_fin), None)
    if not d_in or not d_out or brvmc[d_in] == 0:
        return None
    if d_in == d_out:
        return None  # fenêtre nulle : alpha non défini
    return (brvmc[d_out] - brvmc[d_in]) / brvmc[d_in] * 100


def simuler_evenement(ev, serie_ticker, brvmc, jour_entree):
    """
    Simule une entrée à J+`jour_entree` après ex_date.
    Retourne un dict avec les deux règles de sortie, ou None si non simulable.
    """
    ex_date = ev["ex_date"]
    pre_price = ev["pre_price"]

    fenetre = serie_ordonnee(serie_ticker, ex_date, HORIZON_MAX + 15)
    if len(fenetre) < 2:
        return None

    # Jour d'entrée : la cotation d'index `jour_entree` après ex_date.
    # Si le jour calendaire n'est pas coté, on prend la cotation suivante
    # disponible (comportement voulu sur marché illiquide).
    if jour_entree >= len(fenetre):
        return None
    date_entree, prix_entree = fenetre[jour_entree]
    if not prix_entree or prix_entree <= 0:
        return None

    apres = fenetre[jour_entree:]

    # --- Sortie (a) : fill du cours pré-détachement ---
    date_fill, prix_fill, jours_fill, fill_atteint = None, None, None, False
    for i, (d, p) in enumerate(apres):
        if p >= pre_price:
            date_fill, prix_fill, jours_fill, fill_atteint = d, p, i, True
            break
    if not fill_atteint:
        date_fill, prix_fill = apres[-1]
        jours_fill = len(apres) - 1

    # --- Sortie (b) : horizon fixe J+30 après l'entrée ---
    idx_fixe = min(HORIZON_FIXE, len(apres) - 1)
    date_fixe, prix_fixe = apres[idx_fixe]

    res = {
        "ticker": ev["ticker"],
        "ex_date": ex_date,
        "jour_entree": jour_entree,
        "date_entree": date_entree,
        "prix_entree": prix_entree,
        "fill_atteint": fill_atteint,
    }

    for cle, (date_sortie, prix_sortie) in (
        ("fill", (date_fill, prix_fill)),
        ("fixe", (date_fixe, prix_fixe)),
    ):
        rdt = (prix_sortie - prix_entree) / prix_entree * 100
        bench = rendement_benchmark(brvmc, date_entree, date_sortie)
        res[f"rdt_{cle}"] = round(rdt, 2)
        res[f"alpha_{cle}"] = round(rdt - bench, 2) if bench is not None else None
        res[f"jours_{cle}"] = (
            datetime.fromisoformat(date_sortie) - datetime.fromisoformat(date_entree)
        ).days

    return res


def mediane(valeurs):
    v = sorted(x for x in valeurs if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def agreger(resultats, cle):
    """Statistiques pour une règle de sortie donnée ('fill' ou 'fixe')."""
    rdts = [r[f"rdt_{cle}"] for r in resultats]
    alphas = [r[f"alpha_{cle}"] for r in resultats if r[f"alpha_{cle}"] is not None]
    if not rdts:
        return None
    return {
        "n": len(rdts),
        "n_alpha": len(alphas),
        "rdt_median": round(mediane(rdts), 2),
        "alpha_median": round(mediane(alphas), 2) if alphas else None,
        "pct_alpha_positif": round(100 * sum(1 for a in alphas if a > 0) / len(alphas), 1)
        if alphas
        else None,
        "jours_median": mediane([r[f"jours_{cle}"] for r in resultats]),
    }


def afficher_tableau(titre, par_jour, cle):
    print(f"\n{titre} — sortie « {cle} »")
    print(f"{'J entrée':>9} {'n':>5} {'rdt méd':>9} {'alpha méd':>10} "
          f"{'% alpha>0':>10} {'jours méd':>10}")
    print("-" * 58)
    for j in sorted(par_jour):
        s = par_jour[j].get(cle)
        if not s:
            continue
        print(f"{'J+' + str(j):>9} {s['n']:>5} {s['rdt_median']:>9.2f} "
              f"{(s['alpha_median'] if s['alpha_median'] is not None else 0):>10.2f} "
              f"{(s['pct_alpha_positif'] or 0):>9.1f}% {s['jours_median']:>10.0f}")


def main():
    log.info("=== D1 — simulation des jours d'entrée fixes ===")
    log.info("EXPLORATION, pas validation. Brut (ni frais ni IRVM).")

    evenements = charger_evenements()
    prix, brvmc = charger_series_prix()

    groupes = {
        "UNIVERS DIVIDEND CAPTURE": [
            e for e in evenements if e["ticker"] in UNIVERS_DIVIDEND_CAPTURE
        ],
        "AUTRES TICKERS": [
            e for e in evenements if e["ticker"] not in UNIVERS_DIVIDEND_CAPTURE
        ],
    }

    export = {}

    for nom, evs in groupes.items():
        log.info("%s : %d événements", nom, len(evs))
        par_jour = {}
        non_simulables = defaultdict(int)

        for j in JOURS_ENTREE:
            resultats = []
            for ev in evs:
                serie = prix.get(ev["ticker"])
                if not serie:
                    non_simulables[f"J+{j} : pas de série prix"] += 1
                    continue
                r = simuler_evenement(ev, serie, brvmc, j)
                if r is None:
                    non_simulables[f"J+{j} : fenêtre insuffisante"] += 1
                    continue
                resultats.append(r)

            par_jour[j] = {
                "fill": agreger(resultats, "fill"),
                "fixe": agreger(resultats, "fixe"),
                "n_sans_fill": sum(1 for r in resultats if not r["fill_atteint"]),
            }

        for cle in ("fill", "fixe"):
            afficher_tableau(nom, par_jour, cle)

        sans_fill = par_jour[0]["n_sans_fill"]
        print(f"\n  Événements sans fill atteint (entrée J+0) : {sans_fill} "
              f"— sortis à J+{HORIZON_MAX}, non exclus")

        if non_simulables:
            print("  Non simulables :")
            for motif, n in sorted(non_simulables.items()):
                print(f"    {n:>4}  {motif}")

        export[nom] = par_jour

    sortie = "d1_entry_days_results.json"
    with open(sortie, "w") as f:
        json.dump(
            {"generated_at": datetime.now().isoformat(), "resultats": export},
            f,
            indent=2,
        )
    log.info("Écrit : %s", sortie)

    print("\n" + "=" * 58)
    print("RAPPEL — ne pas traiter ces chiffres comme une preuve :")
    print("  · 16 jours testés sur ~99 obs → un « meilleur jour » ressort")
    print("    mécaniquement, signal ou non (sur-ajustement)")
    print("  · observations non indépendantes (~30 tickers, groupement temporel)")
    print("  · walk-forward requis avant toute mise en production")
    print("=" * 58)


if __name__ == "__main__":
    main()
