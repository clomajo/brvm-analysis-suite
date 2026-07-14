"""
tools/stress_test_v2.py
T6 — Stress-test statistique du backtest V2 "cours cible"
Source des signaux : backtest_value.py (commit 49a64b6), même source que T5b/T9.

4 volets, chacun avec une règle d'interprétation FIGÉE dans la spec (PLAN_REMEDIATION.md
Phase 6) — le modèle exécutant applique les règles textuellement, ne les interprète pas.

Dépendances : numpy, pandas (déjà présentes). Pas de scipy (absent, confirmé 13/07/2026)
— bootstrap fait à la main avec numpy.random.
"""

import os
import statistics
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests
import numpy as np

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

PER_SECTORIEL = {
    "banque": 12.4, "agro": 10.2, "industrie": 13.2,
    "telecom": 13.3, "distribution": 16.1, "autre": 11.0,
}

SECTEURS = {
    "banque": ["BOAB", "BOABF", "BOAC", "BOAM", "BOAN", "BOAS", "BNBC", "CBIBF",
               "NSBC", "SGBC", "SIBC", "SICC", "SLBC", "UNLC", "CABC"],
    "agro": ["PALC", "SOGC", "SPHC", "SAFC", "CFAC"],
    "industrie": ["SMBC", "STAC", "STBC", "BICC", "CIEC", "ECOC", "SIVC",
                  "SEMC", "SHEC", "SCRC", "SDCC", "SDSC", "UNXC"],
    "telecom": ["ONTBF", "ORAC", "ORGT"],
    "distribution": ["ABJC", "ETIT", "FTSC", "LNBB", "NEIC", "NTLC",
                      "PRSC", "SNTS", "SOGC", "TTLC", "TTLS"],
}

EXCLUSIONS = {"NTLC", "BOAN", "BNBC", "SICC", "UNLC", "ETIT", "FTSC", "CFAC", "SIVC"}

CAP_MIN = 150e9
CAP_MAX = 500e9

FY_DATES = {
    "FY2021": "2022-04-30", "FY2022": "2023-04-30",
    "FY2023": "2024-04-30", "FY2024": "2025-04-30",
}

N_BOOTSTRAP = 10_000
RNG_SEED = 42


def get_secteur(ticker):
    for s, tickers in SECTEURS.items():
        if ticker in tickers:
            return s
    return "autre"


def fetch_all_prices():
    print("Chargement des prix historiques...")
    all_prices = {}
    rc = requests.get(f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol", headers=HEADERS)
    companies = {c["id"]: c["symbol"] for c in rc.json()}

    offset, batch = 0, 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/historical_data"
            f"?select=company_id,trade_date,price&order=trade_date.asc"
            f"&offset={offset}&limit={batch}",
            headers=HEADERS
        )
        rows = r.json()
        if not rows:
            break
        for row in rows:
            symbol = companies.get(row["company_id"])
            if symbol:
                all_prices.setdefault(symbol, {})[row["trade_date"]] = row["price"]
        offset += batch
        if len(rows) < batch:
            break
    print(f"  {len(all_prices)} tickers chargés")
    return all_prices


def fetch_fundamentals_raw():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,fiscal_year,eps,pe_ratio,roe,pb_ratio,market_cap"
        f"&eps=not.is.null&order=ticker.asc,fiscal_year.asc",
        headers=HEADERS
    )
    data = r.json()

    r2 = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,market_cap&market_cap=not.is.null",
        headers=HEADERS
    )
    cap_by_ticker = {row["ticker"]: row["market_cap"] for row in r2.json() if row["market_cap"]}

    return data, cap_by_ticker


def get_price_at_date(prices_dict, target_date_str, window=10):
    target = date.fromisoformat(target_date_str)
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta * sign)).isoformat()
            if d in prices_dict:
                return prices_dict[d], d
    return None, None


def generer_signaux(all_prices, fundamentals_raw, cap_by_ticker, roe_min, pb_max):
    filtered = {}
    for row in fundamentals_raw:
        t = row["ticker"]
        fy = row["fiscal_year"]
        if t in EXCLUSIONS:
            continue
        if not row["eps"] or row["eps"] <= 0:
            continue

        cap = cap_by_ticker.get(t)
        roe = row.get("roe")
        pb = row.get("pb_ratio")
        if not cap or not (CAP_MIN <= cap <= CAP_MAX):
            continue
        if not roe or roe < roe_min:
            continue
        if not pb or pb > pb_max:
            continue

        filtered.setdefault(t, {})[fy] = row["eps"]

    resultats = []
    for ticker, fy_eps in sorted(filtered.items()):
        prices = all_prices.get(ticker, {})
        if not prices:
            continue
        secteur = get_secteur(ticker)
        per_ref = PER_SECTORIEL.get(secteur, 11.0)

        for fy, eps in fy_eps.items():
            signal_date = FY_DATES.get(fy)
            if not signal_date:
                continue
            prix_signal, _ = get_price_at_date(prices, signal_date)
            if not prix_signal:
                continue

            cours_cible = eps * per_ref
            decote_pct = (cours_cible - prix_signal) / prix_signal * 100

            date_j90 = (date.fromisoformat(signal_date) + timedelta(days=90)).isoformat()
            prix_j90, _ = get_price_at_date(prices, date_j90)
            perf_j90 = (prix_j90 - prix_signal) / prix_signal * 100 if prix_j90 else None

            signal = "ACHAT" if decote_pct > 15 else "VENTE" if decote_pct < -15 else "NEUTRE"
            if signal != "ACHAT":
                continue

            resultats.append({
                "ticker": ticker, "fy": fy, "signal_date": signal_date,
                "decote_pct": round(decote_pct, 1),
                "perf_j90": round(perf_j90, 2) if perf_j90 is not None else None,
            })

    return resultats


def volet_bootstrap(signaux_defaut):
    vals = np.array([r["perf_j90"] for r in signaux_defaut if r["perf_j90"] is not None])
    rng = np.random.default_rng(RNG_SEED)

    medianes, moyennes = [], []
    for _ in range(N_BOOTSTRAP):
        tirage = rng.choice(vals, size=len(vals), replace=True)
        medianes.append(np.median(tirage))
        moyennes.append(np.mean(tirage))

    ic95_mediane = (np.percentile(medianes, 2.5), np.percentile(medianes, 97.5))
    ic95_moyenne = (np.percentile(moyennes, 2.5), np.percentile(moyennes, 97.5))

    borne_basse_mediane = ic95_mediane[0]
    alerte = borne_basse_mediane < 0

    return {
        "n": len(vals),
        "n_bootstrap": N_BOOTSTRAP,
        "mediane_observee": round(float(np.median(vals)), 2),
        "moyenne_observee": round(float(np.mean(vals)), 2),
        "ic95_mediane": (round(float(ic95_mediane[0]), 2), round(float(ic95_mediane[1]), 2)),
        "ic95_moyenne": (round(float(ic95_moyenne[0]), 2), round(float(ic95_moyenne[1]), 2)),
        "alerte_borne_basse_negative": alerte,
    }


def volet_walkforward(signaux_defaut):
    signaux_tries = sorted(
        [r for r in signaux_defaut if r["perf_j90"] is not None],
        key=lambda r: r["signal_date"]
    )
    n = len(signaux_tries)
    taille_tiers = n // 3
    tiers = [
        signaux_tries[0:taille_tiers],
        signaux_tries[taille_tiers:2 * taille_tiers],
        signaux_tries[2 * taille_tiers:],
    ]

    resultats_tiers = []
    instabilite = False
    for i, tier in enumerate(tiers, start=1):
        vals = [r["perf_j90"] for r in tier]
        if not vals:
            continue
        med = round(statistics.median(vals), 2)
        if med < 0:
            instabilite = True
        resultats_tiers.append({
            "tiers": i,
            "n": len(vals),
            "periode": f"{tier[0]['signal_date']} → {tier[-1]['signal_date']}",
            "mediane": med,
            "moyenne": round(statistics.mean(vals), 2),
        })

    return {"tiers": resultats_tiers, "instabilite_detectee": instabilite}


def volet_sensibilite(all_prices, fundamentals_raw, cap_by_ticker):
    grille_roe = [12, 15, 18]
    grille_pb = [2.0, 2.5, 3.0]

    resultats_grille = {}
    for roe in grille_roe:
        for pb in grille_pb:
            sigs = generer_signaux(all_prices, fundamentals_raw, cap_by_ticker, roe, pb)
            vals = [s["perf_j90"] for s in sigs if s["perf_j90"] is not None]
            resultats_grille[(roe, pb)] = {
                "n": len(sigs),
                "mediane": round(statistics.median(vals), 2) if vals else None,
            }

    overfitting_flags = []
    roe_idx = {v: i for i, v in enumerate(grille_roe)}
    pb_idx = {v: i for i, v in enumerate(grille_pb)}

    def variation_excessive(a, b):
        if a is None or b is None:
            return False
        if a == 0 and b == 0:
            return False
        base = max(abs(a), 1e-9)
        return abs(a - b) / base > 0.5

    cles = list(resultats_grille.keys())
    for (roe, pb) in cles:
        courant = resultats_grille[(roe, pb)]
        i = roe_idx[roe]
        if i + 1 < len(grille_roe):
            voisin = resultats_grille[(grille_roe[i + 1], pb)]
            if variation_excessive(courant["n"], voisin["n"]) or variation_excessive(courant["mediane"], voisin["mediane"]):
                overfitting_flags.append(f"ROE {roe}→{grille_roe[i+1]} (P/B={pb})")
        j = pb_idx[pb]
        if j + 1 < len(grille_pb):
            voisin = resultats_grille[(roe, grille_pb[j + 1])]
            if variation_excessive(courant["n"], voisin["n"]) or variation_excessive(courant["mediane"], voisin["mediane"]):
                overfitting_flags.append(f"P/B {pb}→{grille_pb[j+1]} (ROE={roe})")

    return {
        "grille": resultats_grille,
        "grille_roe": grille_roe,
        "grille_pb": grille_pb,
        "overfitting_detecte": len(overfitting_flags) > 0,
        "overfitting_flags": overfitting_flags,
    }


def volet_survivance(all_prices, fundamentals_raw, cap_by_ticker):
    fund_by_ticker = {}
    for row in fundamentals_raw:
        t = row["ticker"]
        if t not in EXCLUSIONS:
            continue
        fy = row["fiscal_year"]
        if not row["eps"] or row["eps"] <= 0:
            continue
        fund_by_ticker.setdefault(t, {})[fy] = row["eps"]

    detail = []
    n_perdants = 0
    n_total_signaux = 0

    for ticker, fy_eps in sorted(fund_by_ticker.items()):
        prices = all_prices.get(ticker, {})
        if not prices:
            detail.append({"ticker": ticker, "note": "pas de données prix"})
            continue

        secteur = get_secteur(ticker)
        per_ref = PER_SECTORIEL.get(secteur, 11.0)

        for fy, eps in fy_eps.items():
            signal_date = FY_DATES.get(fy)
            if not signal_date:
                continue
            prix_signal, _ = get_price_at_date(prices, signal_date)
            if not prix_signal:
                continue

            cours_cible = eps * per_ref
            decote_pct = (cours_cible - prix_signal) / prix_signal * 100
            if decote_pct <= 15:
                continue

            date_j90 = (date.fromisoformat(signal_date) + timedelta(days=90)).isoformat()
            prix_j90, _ = get_price_at_date(prices, date_j90)
            perf_j90 = (prix_j90 - prix_signal) / prix_signal * 100 if prix_j90 else None

            if perf_j90 is not None:
                n_total_signaux += 1
                perdant = perf_j90 < 0
                if perdant:
                    n_perdants += 1
                detail.append({
                    "ticker": ticker, "fy": fy,
                    "perf_j90_hypothetique": round(perf_j90, 2),
                    "perdant": perdant,
                })

    return {
        "n_tickers_exclus": len(EXCLUSIONS),
        "tickers_exclus": sorted(EXCLUSIONS),
        "n_signaux_hypothetiques_generes": n_total_signaux,
        "n_perdants": n_perdants,
        "detail": detail,
    }


def run():
    all_prices = fetch_all_prices()
    fundamentals_raw, cap_by_ticker = fetch_fundamentals_raw()

    signaux_defaut = generer_signaux(all_prices, fundamentals_raw, cap_by_ticker, 15.0, 2.5)

    print("=" * 70)
    print("ÉTAPE 0 — VÉRIFICATION REPRODUCTIBILITÉ (seuils par défaut)")
    print("=" * 70)
    vals_defaut = [s["perf_j90"] for s in signaux_defaut if s["perf_j90"] is not None]
    print(f"n signaux ACHAT : {len(signaux_defaut)} (attendu 25)")
    if vals_defaut:
        med = statistics.median(vals_defaut)
        print(f"médiane J+90    : {med:+.1f}% (attendu +7.8%)")
        if abs(len(signaux_defaut) - 25) > 2 or abs(med - 7.8) > 0.5:
            print("⚠️  HORS TOLÉRANCE — arrêt recommandé avant de poursuivre T6.")
        else:
            print("✅ Dans la tolérance.")
    print()

    lignes_log = []
    lignes_log.append("## T6 — Stress-test statistique V2 (cours cible)\n")
    lignes_log.append("**Date d'exécution :** 13/07/2026\n")
    lignes_log.append(
        "**Source des signaux :** identique à T5b — `backtest_value.py` (commit `49a64b6`), "
        "répliqué via `tools/stress_test_v2.py`.\n"
    )
    lignes_log.append(
        f"**Étape 0 (reproductibilité, seuils par défaut) :** n={len(signaux_defaut)} "
        f"(attendu 25), médiane J+90={statistics.median(vals_defaut):+.1f}% (attendu +7.8%).\n"
    )

    print("=" * 70)
    print("VOLET 1 — BOOTSTRAP (10 000 tirages, IC 95%)")
    print("=" * 70)
    r1 = volet_bootstrap(signaux_defaut)
    print(f"n={r1['n']} | médiane observée={r1['mediane_observee']:+.1f}% | "
          f"moyenne observée={r1['moyenne_observee']:+.1f}%")
    print(f"IC95% médiane : [{r1['ic95_mediane'][0]:+.1f}%, {r1['ic95_mediane'][1]:+.1f}%]")
    print(f"IC95% moyenne : [{r1['ic95_moyenne'][0]:+.1f}%, {r1['ic95_moyenne'][1]:+.1f}%]")

    lignes_log.append("\n### Volet 1 — Bootstrap (10 000 tirages)\n")
    lignes_log.append(f"- n = {r1['n']}, médiane observée = {r1['mediane_observee']:+.1f}%, "
                       f"moyenne observée = {r1['moyenne_observee']:+.1f}%")
    lignes_log.append(f"- IC95% médiane : [{r1['ic95_mediane'][0]:+.1f}%, {r1['ic95_mediane'][1]:+.1f}%]")
    lignes_log.append(f"- IC95% moyenne : [{r1['ic95_moyenne'][0]:+.1f}%, {r1['ic95_moyenne'][1]:+.1f}%]")

    if r1["alerte_borne_basse_negative"]:
        print("\n⚠️  RÈGLE DÉCLENCHÉE : borne basse IC95 médiane < 0.")
        msg = ("**V2 non prouvé statistiquement** — plafonner la taille de position par "
               "signal à un montant défini par Jocelyn jusqu'à n ≥ 60 signaux vérifiés.")
        print(msg)
        lignes_log.append(f"\n⚠️ **Règle appliquée :** {msg}\n")
    else:
        print("\n✅ Borne basse IC95 médiane ≥ 0 — règle non déclenchée.")
        lignes_log.append(f"\n✅ Borne basse IC95 médiane ≥ 0 — règle non déclenchée.\n")

    print(f"\n{'='*70}")
    print("VOLET 2 — WALK-FORWARD (3 tiers chronologiques)")
    print("=" * 70)
    r2 = volet_walkforward(signaux_defaut)
    lignes_log.append("\n### Volet 2 — Walk-forward (3 tiers chronologiques)\n")
    lignes_log.append(f"| Tiers | n | Période | Médiane | Moyenne |")
    lignes_log.append(f"|---|---|---|---|---|")
    for t in r2["tiers"]:
        print(f"Tiers {t['tiers']} (n={t['n']}, {t['periode']}) : "
              f"médiane={t['mediane']:+.1f}%  moyenne={t['moyenne']:+.1f}%")
        lignes_log.append(f"| {t['tiers']} | {t['n']} | {t['periode']} | {t['mediane']:+.1f}% | {t['moyenne']:+.1f}% |")

    if r2["instabilite_detectee"]:
        print("\n⚠️  RÈGLE DÉCLENCHÉE : au moins un tiers a une médiane < 0.")
        msg = "**instabilité temporelle, revalider trimestriellement.**"
        print(msg)
        lignes_log.append(f"\n⚠️ **Règle appliquée :** {msg}\n")
    else:
        print("\n✅ Tous les tiers ont une médiane ≥ 0 — règle non déclenchée.")
        lignes_log.append(f"\n✅ Tous les tiers ont une médiane ≥ 0 — règle non déclenchée.\n")

    print(f"\n{'='*70}")
    print("VOLET 3 — SENSIBILITÉ AUX SEUILS (grille ROE × P/B)")
    print("=" * 70)
    r3 = volet_sensibilite(all_prices, fundamentals_raw, cap_by_ticker)

    lignes_log.append("\n### Volet 3 — Sensibilité aux seuils (grille ROE × P/B)\n")

    header = "ROE/PB".ljust(10) + "".join(f"{pb:>18}" for pb in r3["grille_pb"])
    print(header)
    for roe in r3["grille_roe"]:
        row_print = f"{roe:<10}"
        row_log = f"| {roe} |"
        for pb in r3["grille_pb"]:
            cell = r3["grille"][(roe, pb)]
            med_str = f"{cell['mediane']:+.1f}%" if cell["mediane"] is not None else "N/A"
            row_print += f"{'n=' + str(cell['n']) + ',' + med_str:>18}"
            row_log += f" n={cell['n']}, {med_str} |"
        print(row_print)
        lignes_log.append(row_log)

    if r3["overfitting_detecte"]:
        print(f"\n⚠️  RÈGLE DÉCLENCHÉE : variation > 50% entre cases adjacentes : {r3['overfitting_flags']}")
        msg = "**seuils probablement surajustés (overfitting), ne pas resserrer davantage les critères.**"
        print(msg)
        lignes_log.append(f"\n⚠️ **Règle appliquée :** {msg} (déclencheurs : {', '.join(r3['overfitting_flags'])})\n")
    else:
        print("\n✅ Aucune variation > 50% entre cases adjacentes — règle non déclenchée.")
        lignes_log.append(f"\n✅ Aucune variation > 50% entre cases adjacentes — règle non déclenchée.\n")

    print(f"\n{'='*70}")
    print("VOLET 4 — BIAIS DE SURVIVANCE (10 tickers exclus)")
    print("=" * 70)
    r4 = volet_survivance(all_prices, fundamentals_raw, cap_by_ticker)
    print(f"Tickers exclus ({r4['n_tickers_exclus']}) : {r4['tickers_exclus']}")
    print(f"Signaux hypothétiques générés (auraient été ACHAT sans exclusion) : {r4['n_signaux_hypothetiques_generes']}")
    print(f"Dont perdants (perf_j90 < 0) : {r4['n_perdants']}")
    print("\nRapport brut — AUCUNE conclusion (interprétation réservée à Jocelyn).")

    lignes_log.append("\n### Volet 4 — Biais de survivance (10 tickers exclus)\n")
    lignes_log.append(f"- Tickers exclus ({r4['n_tickers_exclus']}) : {', '.join(r4['tickers_exclus'])}")
    lignes_log.append(f"- Signaux hypothétiques générés (auraient été ACHAT sans exclusion) : {r4['n_signaux_hypothetiques_generes']}")
    lignes_log.append(f"- Dont perdants (perf_j90 < 0) : {r4['n_perdants']}")
    if r4["detail"]:
        lignes_log.append(f"\n| Ticker | FY | Perf J+90 hypothétique | Perdant |")
        lignes_log.append(f"|---|---|---|---|")
        for d in r4["detail"]:
            if "fy" in d:
                lignes_log.append(f"| {d['ticker']} | {d['fy']} | {d['perf_j90_hypothetique']:+.1f}% | {'oui' if d['perdant'] else 'non'} |")
    lignes_log.append("\n*Rapport brut, sans conclusion — interprétation réservée à Jocelyn.*\n")

    with open("REMEDIATION_LOG_T6_append.md", "w") as f:
        f.write("\n".join(lignes_log))
        f.write("\n")

    print(f"\n{'='*70}")
    print("Extrait REMEDIATION_LOG.md généré : REMEDIATION_LOG_T6_append.md")
    print("=" * 70)


if __name__ == "__main__":
    run()
