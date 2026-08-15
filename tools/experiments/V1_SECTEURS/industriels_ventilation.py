#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Industriels — effet de composition ou effet secteur ?
=====================================================
Classe A : lecture seule, aucune ecriture en base.

CONTEXTE
hit_rate_par_secteur.py (15/08/2026) etablit que le secteur Industriels diverge
du global sur les deux signaux, avec des intervalles de confiance disjoints :

  ACHAT       38.6 % (n=88)  contre 63.6 % global
  SURVEILLER  42.0 % (n=224) contre 64.6 % global

38.6 % de reussite sur des signaux d'achat, c'est sous le hasard — dans un
marche ou le BRVM Composite gagne 43.9 % depuis janvier.

QUESTION
Avant d'en conclure quoi que ce soit sur le secteur, verifier deux hypotheses
concurrentes :

  H1 — effet de composition : un ou deux titres portent tout le deficit, et le
       "secteur" n'est qu'une etiquette sur un probleme individuel.
  H2 — effet de periode : les signaux se concentrent sur quelques semaines
       defavorables, l'ecart est conjoncturel.

Si H1 ou H2 explique l'ecart, il n'y a pas de conclusion sectorielle a tirer.

Ce script ne teste aucun seuil : il decrit. Les seuils pre-enregistres portaient
sur la divergence sectorielle, deja tranchee.

Usage :
    python3 tools/experiments/V1_SECTEURS/industriels_ventilation.py
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
INDUSTRIELS = ["SDSC", "SEMC", "SIVC", "FTSC", "STAC", "CABC"]
SIGNAUX = ("ACHAT", "SURVEILLER")


def charger(table, params, page=1000):
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
    if total == 0:
        return (0.0, 0.0, 0.0)
    p = succes / total
    d = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    demi = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return (p, max(0.0, centre - demi), min(1.0, centre + demi))


def mediane(valeurs):
    if not valeurs:
        return None
    tri = sorted(valeurs)
    n = len(tri)
    return tri[n // 2] if n % 2 else (tri[n // 2 - 1] + tri[n // 2]) / 2


def main():
    if not URL or not KEY:
        print("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env", file=sys.stderr)
        return 1

    print("=" * 74)
    print("INDUSTRIELS — effet de composition ou effet secteur ?")
    print("=" * 74)

    brut = charger("brvm_decisions_results", {
        "select": "ticker,signal,signal_date,verification_date,variation_pct,score",
    })

    lignes = []
    for r in brut:
        if r["ticker"] not in INDUSTRIELS:
            continue
        try:
            d1 = datetime.strptime(r["signal_date"], "%Y-%m-%d")
            d2 = datetime.strptime(r["verification_date"], "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        if not (HORIZON_MIN <= (d2 - d1).days <= HORIZON_MAX):
            continue
        if r.get("variation_pct") is None:
            continue
        lignes.append({**r, "mois": r["signal_date"][:7]})

    print(f"  {len(lignes)} verifications Industriels a J+{HORIZON_MIN}-{HORIZON_MAX}")

    # ── H1 : ventilation par ticker ──────────────────────────────────────────
    for signal in SIGNAUX:
        lot = [r for r in lignes if r["signal"] == signal]
        if not lot:
            continue

        succes_tot = sum(1 for r in lot if r["variation_pct"] > 0)
        ic_tot = wilson(succes_tot, len(lot))

        print()
        print("=" * 74)
        print(f"H1 — PAR TICKER · signal {signal}")
        print(f"  Secteur : {ic_tot[0]*100:.1f}% (n={len(lot)})")
        print("-" * 74)
        print(f"  {'Ticker':<8} {'n':>5} {'hit':>7}  {'IC95':>16}  "
              f"{'med.var':>9}  {'score med':>9}")
        print("-" * 74)

        par_ticker = defaultdict(list)
        for r in lot:
            par_ticker[r["ticker"]].append(r)

        for ticker in sorted(par_ticker, key=lambda t: -len(par_ticker[t])):
            obs = par_ticker[ticker]
            succes = sum(1 for r in obs if r["variation_pct"] > 0)
            ic = wilson(succes, len(obs))
            med = mediane([r["variation_pct"] for r in obs])
            sc = mediane([r["score"] for r in obs if r.get("score") is not None])
            print(f"  {ticker:<8} {len(obs):>5} {ic[0]*100:>6.1f}% "
                  f"  [{ic[1]*100:>5.1f} – {ic[2]*100:>5.1f}]  "
                  f"{med:>8.2f}%  {sc if sc is not None else '—':>9}")

        # Test de retrait : le secteur remonte-t-il sans son pire contributeur ?
        print("-" * 74)
        print("  Retrait d'un ticker a la fois :")
        for ticker in sorted(par_ticker):
            reste = [r for r in lot if r["ticker"] != ticker]
            if not reste:
                continue
            s = sum(1 for r in reste if r["variation_pct"] > 0)
            ic = wilson(s, len(reste))
            ecart = (ic[0] - ic_tot[0]) * 100
            print(f"    sans {ticker:<8} {ic[0]*100:>5.1f}% (n={len(reste):>3})  "
                  f"{ecart:+.1f} pt")

    # ── H2 : ventilation par mois ────────────────────────────────────────────
    print()
    print("=" * 74)
    print("H2 — PAR MOIS · tous signaux ACHAT et SURVEILLER confondus")
    print("-" * 74)
    print(f"  {'Mois':<10} {'n':>5} {'hit':>7}  {'med.var':>9}")
    print("-" * 74)

    par_mois = defaultdict(list)
    for r in lignes:
        if r["signal"] in SIGNAUX:
            par_mois[r["mois"]].append(r)

    for mois in sorted(par_mois):
        obs = par_mois[mois]
        succes = sum(1 for r in obs if r["variation_pct"] > 0)
        med = mediane([r["variation_pct"] for r in obs])
        print(f"  {mois:<10} {len(obs):>5} {succes/len(obs)*100:>6.1f}%  {med:>8.2f}%")

    print()
    print("=" * 74)
    print("LECTURE")
    print("  H1 retenue si un ticker concentre le deficit et que son retrait")
    print("     ramene le secteur pres du global (63-65 %).")
    print("  H2 retenue si le deficit se concentre sur un ou deux mois.")
    print("  Ni l'une ni l'autre -> le deficit est reparti, effet sectoriel.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
