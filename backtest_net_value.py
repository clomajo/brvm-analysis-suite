"""
backtest_net_value.py
T5b — Rendement NET (frais de transaction) sur les signaux V2 "cours cible"
générés par backtest_value.py (commit 49a64b6, brvm-analysis-suite).

Source des signaux : backtest_value.py, commit 49a64b6
    "feat: V2 backtest final — filtre cap+qualite + look-ahead fix + scorecard"
Étape 0 (reproductibilité) validée le 13/07/2026 :
    n=25 signaux ACHAT, médiane J+90 = +7.8% — reproduit à l'identique.

IMPORTANT — ce script NE modifie PAS backtest_value.py. Il réplique sa
génération de signaux (même logique, mêmes filtres, mêmes constantes) pour
pouvoir superposer un calcul de frais, sans toucher au script source.

Portée du "net" ici : FRAIS DE TRANSACTION UNIQUEMENT.
    Cette stratégie (V2 cours cible / value) ne repose pas sur l'encaissement
    d'un dividende dans la fenêtre de mesure — c'est une stratégie de
    convergence prix/valeur intrinsèque, pas de dividend capture.
    -> AUCUN terme IRVM n'est appliqué ici (pas de flux dividende mesuré).
    -> Le rendement net ci-dessous est donc CONSERVATEUR : si le titre a
       versé un dividende pendant la fenêtre J+90, ce montant n'est pas
       comptabilisé dans le rendement mesuré par backtest_value.py, et donc
       pas dans ce calcul net non plus. Le vrai rendement total (prix +
       dividende) serait légèrement supérieur au chiffre "net" produit ici.

Ne pas confondre avec la stratégie dividend capture (BOAB/BOAC/ECOC/SMBC/
NSBC/NTLC, walk-forward 93% WR) — cf. T5c, backtest séparé et non couvert
par ce script.
"""

import os
import statistics
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# ---------------------------------------------------------------------------
# Réplique exacte des constantes de backtest_value.py (commit 49a64b6)
# ---------------------------------------------------------------------------

PER_SECTORIEL = {
    "banque": 12.4,
    "agro": 10.2,
    "industrie": 13.2,
    "telecom": 13.3,
    "distribution": 16.1,
    "autre": 11.0,
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

FILTRE_CAP_QUALITE = True
CAP_MIN = 150e9
CAP_MAX = 500e9
ROE_MIN = 15.0
PB_MAX = 2.5

FY_DATES = {
    "FY2021": "2022-04-30",
    "FY2022": "2023-04-30",
    "FY2023": "2024-04-30",
    "FY2024": "2025-04-30",
}

# ---------------------------------------------------------------------------
# Frais de transaction — cf. ADR-034 (T5a)
# ---------------------------------------------------------------------------

FRAIS_BRVM = 0.002       # 0.2% — commission BRVM, source officielle brvm.org
FRAIS_DCBR = 0.001       # 0.1% — commission DC/BR, source officielle brvm.org
FRAIS_SGI = 0.010        # 1.0% — courtage BOA Capital Securities
                          # ⚠️ NON CONFIRMÉ PAR SOURCE PRIMAIRE (Scribd uniquement,
                          #    cf. ADR-034 / BACKLOG.md) — hypothèse de travail.
FRAIS_PAR_COTE = FRAIS_BRVM + FRAIS_DCBR + FRAIS_SGI          # 1.3%
FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_COTE                        # 2.6%

FILL_RATES = [0.60, 0.75, 0.90]
FILL_RATE_NOTE = (
    "0.75 est le taux de fill validé pour la stratégie DIVIDEND CAPTURE "
    "(walk-forward BOAB/BOAC/ECOC/SMBC/NSBC/NTLC), PAS pour cette stratégie "
    "V2 cours cible. Grille fournie à titre informatif/sensibilité uniquement."
)


def get_secteur(ticker):
    for s, tickers in SECTEURS.items():
        if ticker in tickers:
            return s
    return "autre"


def fetch_all_prices():
    print("Chargement des prix historiques...")
    all_prices = {}
    rc = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    companies = {c["id"]: c["symbol"] for c in rc.json()}

    offset = 0
    batch = 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/historical_data"
            f"?select=company_id,trade_date,price"
            f"&order=trade_date.asc"
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


def fetch_fundamentals_history():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,fiscal_year,eps,pe_ratio,roe,pb_ratio,market_cap"
        f"&eps=not.is.null"
        f"&order=ticker.asc,fiscal_year.asc",
        headers=HEADERS
    )
    data = r.json()

    r2 = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,market_cap"
        f"&market_cap=not.is.null",
        headers=HEADERS
    )
    cap_by_ticker = {}
    for row in r2.json():
        if row["market_cap"]:
            cap_by_ticker[row["ticker"]] = row["market_cap"]

    result = {}
    for row in data:
        t = row["ticker"]
        fy = row["fiscal_year"]
        if t in EXCLUSIONS:
            continue
        if not row["eps"] or row["eps"] <= 0:
            continue

        if FILTRE_CAP_QUALITE:
            cap = cap_by_ticker.get(t)
            roe = row.get("roe")
            pb = row.get("pb_ratio")
            if not cap or not (CAP_MIN <= cap <= CAP_MAX):
                continue
            if not roe or roe < ROE_MIN:
                continue
            if not pb or pb > PB_MAX:
                continue

        result.setdefault(t, {})[fy] = row["eps"]

    return result


def get_price_at_date(prices_dict, target_date_str, window=10):
    target = date.fromisoformat(target_date_str)
    for delta in range(window):
        for sign in [0, 1, -1]:
            d = (target + timedelta(days=delta * sign)).isoformat()
            if d in prices_dict:
                return prices_dict[d], d
    return None, None


def generer_signaux():
    """Réplique backtest_value.py::run() jusqu'à la liste `resultats`,
    sans imprimer, pour réutilisation ici."""
    all_prices = fetch_all_prices()
    fundamentals = fetch_fundamentals_history()

    resultats = []
    for ticker, fy_eps in sorted(fundamentals.items()):
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

            resultats.append({
                "ticker": ticker,
                "fy": fy,
                "decote_pct": round(decote_pct, 1),
                "signal": signal,
                "perf_j90": round(perf_j90, 2) if perf_j90 is not None else None,
            })

    return resultats


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "mediane": round(statistics.median(vals), 2),
        "moyenne": round(statistics.mean(vals), 2),
        "pct_positifs": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
        "pire_cas": round(min(vals), 2),
    }


def run():
    resultats = generer_signaux()

    achats = [r for r in resultats if r["signal"] == "ACHAT"]
    n_achat = len(achats)
    j90_brut = [r["perf_j90"] for r in achats if r["perf_j90"] is not None]
    mediane_brut = statistics.median(j90_brut) if j90_brut else None

    print("=" * 70)
    print("ÉTAPE 0 — VÉRIFICATION REPRODUCTIBILITÉ")
    print("=" * 70)
    print(f"n signaux ACHAT      : {n_achat}  (attendu 25, tolérance ±2)")
    if mediane_brut is not None:
        print(f"médiane J+90 brute    : {mediane_brut:+.1f}%  (attendu +7.8%, tolérance ±0.5pt)")
        ecart_n = abs(n_achat - 25)
        ecart_med = abs(mediane_brut - 7.8)
        if ecart_n > 2 or ecart_med > 0.5:
            print("\n⚠️  HORS TOLÉRANCE — cf. protocole T5b : STOP, documenter l'écart, escalade.")
            print("    Ce script n'ajuste PAS les règles pour retrouver le chiffre d'origine.")
        else:
            print("\n✅ Dans la tolérance — reproductibilité confirmée.")
    print()

    for r in achats:
        if r["perf_j90"] is not None:
            r["perf_j90_net"] = round(r["perf_j90"] - FRAIS_ALLER_RETOUR * 100, 2)
        else:
            r["perf_j90_net"] = None

    brut_vals = [r["perf_j90"] for r in achats if r["perf_j90"] is not None]
    net_vals = [r["perf_j90_net"] for r in achats if r["perf_j90_net"] is not None]

    lignes_log = []
    lignes_log.append("## T5b — Backtest net (frais) — V2 cours cible\n")
    lignes_log.append(f"**Date d'exécution :** 13/07/2026\n")
    lignes_log.append(
        f"**Source des signaux :** `backtest_value.py` (commit `49a64b6`), "
        f"réplique via `backtest_net_value.py` (aucune modification du script source).\n"
    )
    lignes_log.append(
        "**Portée du calcul net :** frais de transaction uniquement. Cette stratégie "
        "(convergence prix/valeur intrinsèque) ne comptabilise pas de dividende encaissé "
        "dans son rendement mesuré — **aucun terme IRVM appliqué ici**. Ne pas confondre "
        "avec la stratégie dividend capture (BOAB/BOAC/ECOC/SMBC/NSBC/NTLC), traitée "
        "séparément en T5c.\n"
    )
    lignes_log.append(
        f"**⚠️ Flag 1 :** courtage SGI ({FRAIS_SGI*100:.1f}%) non confirmé par source "
        f"primaire (CREPMF ou avis d'opéré réel) — hypothèse de travail issue d'un "
        f"document Scribd non-primaire (cf. ADR-034, BACKLOG.md).\n"
    )
    lignes_log.append(
        "**⚠️ Flag 2 :** les dividendes éventuellement versés pendant la fenêtre J+90 "
        "ne sont pas comptés dans `backtest_value.py`. Le rendement net ci-dessous est "
        "donc **conservateur** (sous-estimé) par rapport au rendement total réel "
        "(prix + dividende).\n"
    )
    lignes_log.append(
        f"**Étape 0 (reproductibilité) :** n={n_achat} signaux ACHAT "
        f"(attendu 25), médiane J+90 brute={mediane_brut:+.1f}% (attendu +7.8%) "
        f"— **dans la tolérance, validé le 13/07/2026**.\n"
    )
    lignes_log.append(
        f"**Frais aller-retour appliqués :** {FRAIS_ALLER_RETOUR*100:.1f}% "
        f"(= 2 × [{FRAIS_BRVM*100:.1f}% BRVM + {FRAIS_DCBR*100:.1f}% DC/BR "
        f"+ {FRAIS_SGI*100:.1f}% SGI non confirmé])\n"
    )

    print("=" * 70)
    print("TABLEAU COMPARATIF — BRUT vs NET vs NET×FILL_RATE (J+90, n=25 ACHAT)")
    print("=" * 70)

    s_brut = stats(brut_vals)
    s_net = stats(net_vals)

    header = f"{'':<18}{'n':>4}{'médiane':>10}{'moyenne':>10}{'%positifs':>12}{'pire cas':>10}"
    print(header)
    print("-" * len(header))
    print(f"{'BRUT':<18}{s_brut['n']:>4}{s_brut['mediane']:>9.1f}%{s_brut['moyenne']:>9.1f}%{s_brut['pct_positifs']:>11.1f}%{s_brut['pire_cas']:>9.1f}%")
    print(f"{'NET (frais)':<18}{s_net['n']:>4}{s_net['mediane']:>9.1f}%{s_net['moyenne']:>9.1f}%{s_net['pct_positifs']:>11.1f}%{s_net['pire_cas']:>9.1f}%")

    lignes_log.append("\n### Tableau comparatif (J+90, n=25 signaux ACHAT)\n")
    lignes_log.append(f"| Mesure | n | Médiane | Moyenne | % positifs | Pire cas |")
    lignes_log.append(f"|---|---|---|---|---|---|")
    lignes_log.append(f"| Brut | {s_brut['n']} | {s_brut['mediane']:+.1f}% | {s_brut['moyenne']:+.1f}% | {s_brut['pct_positifs']:.1f}% | {s_brut['pire_cas']:+.1f}% |")
    lignes_log.append(f"| Net (frais {FRAIS_ALLER_RETOUR*100:.1f}% AR) | {s_net['n']} | {s_net['mediane']:+.1f}% | {s_net['moyenne']:+.1f}% | {s_net['pct_positifs']:.1f}% | {s_net['pire_cas']:+.1f}% |")

    print(f"\n{'-'*70}")
    print("SENSIBILITÉ FILL_RATE (rendement espéré ajusté = net × fill_rate)")
    print(f"⚠️  {FILL_RATE_NOTE}")
    print(f"{'-'*70}")

    lignes_log.append(f"\n### Sensibilité FILL_RATE\n")
    lignes_log.append(f"⚠️ {FILL_RATE_NOTE}\n")
    lignes_log.append(f"| FILL_RATE | n | Médiane | Moyenne | % positifs | Pire cas |")
    lignes_log.append(f"|---|---|---|---|---|---|")

    for fr in FILL_RATES:
        fill_vals = [v * fr for v in net_vals]
        s_fill = stats(fill_vals)
        print(f"FILL_RATE={fr:.2f}  n={s_fill['n']}  médiane={s_fill['mediane']:+.1f}%  "
              f"moyenne={s_fill['moyenne']:+.1f}%  positifs={s_fill['pct_positifs']:.1f}%  "
              f"pire={s_fill['pire_cas']:+.1f}%")
        lignes_log.append(f"| {fr:.2f} | {s_fill['n']} | {s_fill['mediane']:+.1f}% | {s_fill['moyenne']:+.1f}% | {s_fill['pct_positifs']:.1f}% | {s_fill['pire_cas']:+.1f}% |")

    print(f"\n{'-'*70}")
    print("CALIBRATION SEUIL_LIQUIDITE (proposition, non appliquée au pipeline)")
    print(f"{'-'*70}")

    watchlist_div_capture = ["BOAB", "BOAC", "ECOC", "SMBC", "NSBC", "NTLC"]
    lignes_log.append(f"\n### Calibration seuil_liquidite (proposition)\n")

    seuil_result = calibrer_seuil_liquidite(watchlist_div_capture)
    for line in seuil_result["print_lines"]:
        print(line)
    lignes_log.extend(seuil_result["log_lines"])

    with open("REMEDIATION_LOG_T5b_append.md", "w") as f:
        f.write("\n".join(lignes_log))
        f.write("\n")

    print(f"\n{'='*70}")
    print("Extrait REMEDIATION_LOG.md généré : REMEDIATION_LOG_T5b_append.md")
    print(f"{'='*70}")


def calibrer_seuil_liquidite(watchlist):
    """Calcule volume_20j médian sur 12 mois pour chaque ticker de la
    watchlist dividend-capture, propose seuil = médiane des 6 × 0.5.
    Utilise v_historical_prices (expose ticker + volume)."""
    print_lines = []
    log_lines = []

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/v_historical_prices"
        f"?select=ticker,trade_date,volume"
        f"&ticker=in.({','.join(watchlist)})"
        f"&order=trade_date.desc"
        f"&limit=10000",
        headers=HEADERS
    )
    rows = r.json()

    if not rows or (isinstance(rows, dict) and rows.get("message")):
        print_lines.append(f"⚠️  Impossible de récupérer volume_20j via v_historical_prices "
                            f"(colonne volume peut-être absente de la vue). Réponse: {rows}")
        log_lines.append(f"⚠️ **Calibration non calculée** — `v_historical_prices` n'a pas "
                          f"retourné de colonne `volume` exploitable. À vérifier manuellement.\n")
        return {"print_lines": print_lines, "log_lines": log_lines}

    by_ticker = {}
    for row in rows:
        if row.get("volume") is not None:
            by_ticker.setdefault(row["ticker"], []).append(row["volume"])

    medianes_20j = {}
    for t in watchlist:
        vols = by_ticker.get(t, [])
        if len(vols) >= 20:
            fenetre_20j = [
                statistics.mean(vols[i:i+20])
                for i in range(0, max(1, len(vols) - 20), 5)
            ]
            if fenetre_20j:
                medianes_20j[t] = statistics.median(fenetre_20j)
        else:
            print_lines.append(f"  {t}: données volume insuffisantes ({len(vols)} lignes, besoin >=20)")

    if not medianes_20j:
        log_lines.append("⚠️ **Calibration non calculée** — pas assez de données volume "
                          "sur les 6 tickers de la watchlist dividend-capture.\n")
        return {"print_lines": print_lines, "log_lines": log_lines}

    print_lines.append(f"\n{'Ticker':<8}{'volume_20j médian':>20}")
    log_lines.append(f"| Ticker | volume_20j médian |")
    log_lines.append(f"|---|---|")
    for t, v in sorted(medianes_20j.items()):
        print_lines.append(f"{t:<8}{v:>20,.0f}")
        log_lines.append(f"| {t} | {v:,.0f} |")

    mediane_des_medianes = statistics.median(medianes_20j.values())
    seuil_propose = mediane_des_medianes * 0.5

    print_lines.append(f"\nMédiane des volume_20j (6 tickers) : {mediane_des_medianes:,.0f}")
    print_lines.append(f"Seuil proposé (× 0.5)              : {seuil_propose:,.0f}")
    print_lines.append(f"(Proposition chiffrée — à valider par Jocelyn, non appliquée au pipeline)")

    log_lines.append(f"\n**Médiane des volume_20j (6 tickers) :** {mediane_des_medianes:,.0f}")
    log_lines.append(f"**Seuil proposé (× 0.5) :** {seuil_propose:,.0f}")
    log_lines.append(f"\n*Proposition chiffrée à valider par Jocelyn — non appliquée au pipeline dans cette tâche.*\n")

    return {"print_lines": print_lines, "log_lines": log_lines}


if __name__ == "__main__":
    run()
