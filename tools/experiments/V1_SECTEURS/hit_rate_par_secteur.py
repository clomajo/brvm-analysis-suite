#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V1 par secteur — le hit rate de V1 differe-t-il selon le secteur officiel ?
============================================================================
Classe A : lecture seule, aucune ecriture en base.

QUESTION
Faut-il des sous-modeles V1 differencies par secteur ? Avant de construire quoi
que ce soit, mesurer si la question a une reponse : V1 se comporte-t-il
differemment selon le secteur, de facon statistiquement distinguable ?

SEUILS PRE-ENREGISTRES (fixes le 15/08/2026, avant toute lecture de resultat)

  Metrique   : hit rate = part des signaux dont variation_pct > 0
  Signaux    : ACHAT et SURVEILLER, mesures separement
  Horizon    : J+20 (tolerance 15-25 jours calendaires)
  Comparateur: le hit rate global du meme signal, tous secteurs confondus
  Taille min : n >= 30 par secteur et par signal, sinon NON CONCLUANT

  DIVERGENT  : l'IC95 du secteur ne recoupe pas l'IC95 du global
  NON DIVERGENT : les intervalles se recoupent

  DECISION SI AUCUN SECTEUR NE DIVERGE
    La question est close. Pas de sous-modeles sectoriels : les ecarts observes
    seraient du bruit d'echantillonnage.

  DECISION SI UN OU DEUX SECTEURS DIVERGENT
    Envisager un SEUIL sectoriel (un parametre par secteur) — pas une
    reestimation des quatre ponderations par secteur, qui ferait passer le
    modele de 4 a 28 parametres sur le meme echantillon.

DEFINITION DU HIT RATE — ecart assume avec verify_decisions.py
Le script de production utilise une definition conditionnelle : variation > 0
pour ACHAT, < 0 pour EVITER, |variation| < 5 pour SURVEILLER. Comparer ces
hit rates entre signaux reviendrait a comparer des mesures differentes.

Ce test emploie donc une definition unique — variation_pct > 0 — pour ACHAT
comme pour SURVEILLER. Plus severe que la definition d'origine pour SURVEILLER,
mais c'est la seule facon d'obtenir des chiffres comparables entre secteurs et
entre signaux. Les chiffres produits ici ne sont donc PAS comparables au
65,6 % annonce pour V1.

LIMITES
  - alpha et benchmark_return sont NULL avant le 28/07/2026 (ADR-039,
    backfill jamais execute) : ce test ne mesure que le hit rate absolu, pas
    l'alpha. Dans un marche a +43 % YTD, un hit rate eleve n'est pas en soi
    une preuve de selectivite.
  - L'horizon a change de J+90 a J+20 le 07/07/2026 (ADR-038). Le filtre sur
    15-25 jours ecarte les verifications a l'ancien horizon.

Usage :
    python3 tools/experiments/V1_SECTEURS/hit_rate_par_secteur.py
"""

import math
import os
import sys
from collections import defaultdict
from datetime import datetime

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

HORIZON_MIN, HORIZON_MAX = 15, 25
N_MINIMUM = 30
SIGNAUX = ("ACHAT", "SURVEILLER")

# Nomenclature officielle BRVM, 7 secteurs (ADR-010, en vigueur 02/01/2025).
SECTEUR_OFFICIEL = {
    "Consommation de Base": ["NTLC", "PALC", "SPHC", "SICC", "STBC", "SOGC", "SLBC", "SCRC", "UNLC"],
    "Consommation Discretionnaire": ["BNBC", "CFAC", "LNBB", "NEIC", "ABJC", "PRSC", "UNXC"],
    "Energie": ["SMBC", "TTLC", "TTLS", "SHEC"],
    "Industriels": ["SDSC", "SEMC", "SIVC", "FTSC", "STAC", "CABC"],
    "Services Financiers": ["BOAB", "BOABF", "BOAC", "BOAM", "BOAN", "BOAS", "BICB", "BICC",
                            "CBIBF", "ECOC", "ETIT", "NSBC", "ORGT", "SAFC", "SGBC", "SIBC"],
    "Services Publics": ["CIEC", "SDCC"],
    "Telecommunications": ["ONTBF", "ORAC", "SNTS"],
}
TICKER_SECTEUR = {t: s for s, ts in SECTEUR_OFFICIEL.items() for t in ts}


def charger(table, params, page=1000):
    """Pagination REST complete."""
    sortie, offset = [], 0
    while True:
        reponse = requests.get(
            f"{URL}/rest/v1/{table}",
            headers={**HEADERS, "Range": f"{offset}-{offset + page - 1}"},
            params=params, timeout=60)
        reponse.raise_for_status()
        lot = reponse.json()
        if not lot:
            break
        sortie.extend(lot)
        if len(lot) < page:
            break
        offset += page
    return sortie


def wilson(succes, total, z=1.96):
    """Intervalle de confiance de Wilson pour une proportion.

    Prefere a l'approximation normale : reste valide sur petits effectifs et
    ne produit jamais de borne hors [0, 1].
    """
    if total == 0:
        return (0.0, 0.0, 0.0)
    p = succes / total
    d = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    demi = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return (p, max(0.0, centre - demi), min(1.0, centre + demi))


def disjoints(a, b):
    """Vrai si les deux intervalles (bas, haut) ne se recoupent pas."""
    return a[1] > b[2] or b[1] > a[2]


def main():
    if not URL or not KEY:
        print("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env", file=sys.stderr)
        return 1

    print("=" * 72)
    print("V1 PAR SECTEUR — seuils pre-enregistres, Classe A lecture seule")
    print("=" * 72)

    lignes = charger("brvm_decisions_results", {
        "select": "ticker,signal,signal_date,verification_date,variation_pct",
    })
    print(f"  {len(lignes)} verifications chargees")

    # Filtre d'horizon : l'historique melange J+90 (avant ADR-038) et J+20.
    retenues, hors_horizon, sans_secteur = [], 0, set()
    for r in lignes:
        try:
            d1 = datetime.strptime(r["signal_date"], "%Y-%m-%d")
            d2 = datetime.strptime(r["verification_date"], "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        jours = (d2 - d1).days
        if not (HORIZON_MIN <= jours <= HORIZON_MAX):
            hors_horizon += 1
            continue
        secteur = TICKER_SECTEUR.get(r["ticker"])
        if not secteur:
            sans_secteur.add(r["ticker"])
            continue
        if r.get("variation_pct") is None:
            continue
        retenues.append({**r, "secteur": secteur})

    print(f"  {len(retenues)} retenues a J+{HORIZON_MIN}-{HORIZON_MAX}")
    print(f"  {hors_horizon} hors horizon (ancien J+90, ADR-038)")
    if sans_secteur:
        print(f"  tickers sans secteur : {' '.join(sorted(sans_secteur))}")

    for signal in SIGNAUX:
        lot = [r for r in retenues if r["signal"] == signal]
        if not lot:
            print(f"\n  aucun signal {signal} a cet horizon")
            continue

        succes_g = sum(1 for r in lot if r["variation_pct"] > 0)
        global_ic = wilson(succes_g, len(lot))

        print()
        print("=" * 72)
        print(f"SIGNAL {signal}")
        print(f"  Global : {global_ic[0]*100:.1f}% "
              f"[{global_ic[1]*100:.1f} – {global_ic[2]*100:.1f}]  n={len(lot)}")
        print("-" * 72)
        print(f"  {'Secteur':<30} {'n':>5} {'hit':>7}  {'IC95':>16}  verdict")
        print("-" * 72)

        par_secteur = defaultdict(list)
        for r in lot:
            par_secteur[r["secteur"]].append(r)

        divergents = []
        for secteur in sorted(par_secteur, key=lambda s: -len(par_secteur[s])):
            obs = par_secteur[secteur]
            succes = sum(1 for r in obs if r["variation_pct"] > 0)
            ic = wilson(succes, len(obs))

            if len(obs) < N_MINIMUM:
                verdict = f"NON CONCLUANT (n<{N_MINIMUM})"
            elif disjoints(ic, global_ic):
                verdict = "DIVERGENT"
                divergents.append((secteur, ic[0], len(obs)))
            else:
                verdict = "non divergent"

            print(f"  {secteur:<30} {len(obs):>5} {ic[0]*100:>6.1f}% "
                  f"  [{ic[1]*100:>5.1f} – {ic[2]*100:>5.1f}]  {verdict}")

        print("-" * 72)
        if divergents:
            print(f"  {len(divergents)} secteur(s) divergent(s) :")
            for secteur, taux, n in divergents:
                sens = "au-dessus" if taux > global_ic[0] else "en dessous"
                print(f"    {secteur} — {taux*100:.1f}% {sens} du global (n={n})")
        else:
            print("  Aucun secteur divergent : les ecarts observes sont compatibles")
            print("  avec du bruit d'echantillonnage.")

    print()
    print("=" * 72)
    print("RAPPEL DES SEUILS PRE-ENREGISTRES")
    print("  Aucun divergent      -> question close, pas de sous-modeles")
    print("  Un ou deux divergents-> envisager un SEUIL sectoriel, pas une")
    print("                          reestimation des ponderations")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
