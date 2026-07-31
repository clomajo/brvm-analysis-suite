#!/usr/bin/env python3
"""Diagnostic : decalage d'un an de DIVIDEND_HISTORY.fiscal_year.

Lecture seule (lit le CSV local, ne touche ni la base ni le CSV).

PREUVE DU DECALAGE (documentaire, pas statistique) : le meme montant
apparait deux fois dans dividend_cycle_exploration.csv, sur deux ex-dates
distantes d'un an, via deux sources differentes.

  ticker  ligne DIVIDEND_HISTORY      ligne DIVIDEND (sikafinance)
  SNTS    1740.0  ex 2025-05-20       1740.0   ex 2026-05-22
  BOAB     585.0  ex 2025-05-30        585.0   ex 2026-05-14
  ONTBF    145.0  ex 2025-07-17        145.32  ex 2026-06-12
  BOAC     595.0  ex 2025-05-16        594.53  ex 2026-05-05

La colonne de droite est corroboree par les avis BRVM (N-111 SONATEL,
N-121 BOA BENIN, N-137 ONATEL, exercice 2025) ET par les avis de credit
du courtier (17 400 recu le 29/05/2026 pour 10 SNTS, 2 925 pour 5 BOAB,
2 325 pour 16 ONTBF, 5 945 pour 10 BOAC). Le dividende de 2026 est donc
attribue a l'ex-date de 2025 par les lignes DIVIDEND_HISTORY.

CONSEQUENCE : look-ahead d'un an sur le montant ET sur yield_pct — ce
dernier servant de filtre de selection dans falsification_v2.py (T9
volet A, seuil yield >= 8%), le biais porte aussi sur le CHOIX des trades,
pas seulement sur leur mesure.

Ce script quantifie l'ampleur du biais. Il ne corrige rien.
"""
import csv
import logging
import os
import statistics as st
import sys
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CSV_SOURCE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "dividend_cycle_exploration.csv")


def charger(path):
    if not os.path.exists(path):
        logging.error("CSV introuvable : %s", path)
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)
                if r["exploitable"] == "True" and r["montant"]]


def indexer(rows):
    """ticker -> {fiscal_year: ligne}."""
    idx = defaultdict(dict)
    for r in rows:
        try:
            idx[r["ticker"]][int(r["fiscal_year"])] = r
        except (TypeError, ValueError):
            continue
    return idx


def analyser(idx):
    """Pour chaque ligne DIVIDEND_HISTORY, le montant correct est celui de FY-1."""
    ecarts, cas_graves = [], []
    n_hist = n_sain = n_perdu = 0
    for ticker, par_fy in idx.items():
        for fy, r in sorted(par_fy.items()):
            if r["source_montant"] != "DIVIDEND_HISTORY":
                n_sain += 1
                continue
            n_hist += 1
            prec = par_fy.get(fy - 1)
            if not prec or prec["source_montant"] != "DIVIDEND_HISTORY":
                n_perdu += 1
                continue
            actuel = float(r["montant"])
            correct = float(prec["montant"])
            err = 100.0 * (actuel - correct) / correct
            ecarts.append(err)
            if abs(err) >= 50.0:
                cas_graves.append((ticker, fy, r["date_ex"], actuel, correct, err))
    return ecarts, cas_graves, n_hist, n_sain, n_perdu


def main():
    rows = charger(CSV_SOURCE)
    idx = indexer(rows)
    ecarts, cas_graves, n_hist, n_sain, n_perdu = analyser(idx)

    logging.info("Cycles exploitables : %d", len(rows))
    logging.info("  source DIVIDEND_HISTORY (decalee) : %d", n_hist)
    logging.info("  source DIVIDEND (saine)           : %d", n_sain)
    logging.info("  non corrigeables (plus ancien cycle du ticker) : %d", n_perdu)

    if not ecarts:
        logging.warning("Aucun ecart calculable.")
        return

    print(f"\nErreur relative sur le montant du dividende (n={len(ecarts)}) :")
    print(f"  mediane          = {st.median(ecarts):+.1f}%")
    print(f"  moyenne          = {st.mean(ecarts):+.1f}%")
    print(f"  cycles surestimes= {100*sum(1 for e in ecarts if e > 0)/len(ecarts):.0f}%")
    print(f"  min / max        = {min(ecarts):+.1f}% / {max(ecarts):+.1f}%")

    print(f"\nCas graves (|erreur| >= 50%) : {len(cas_graves)}")
    for t, fy, exd, a, c, e in sorted(cas_graves, key=lambda z: -abs(z[5]))[:15]:
        print(f"  {t:6} FY{fy} ex={exd:11} utilise={a:9.2f} correct={c:9.2f} ({e:+.1f}%)")

    print("\nLecture : le dividende pesant ~8-15% du prix (yield_pct), une erreur")
    print("mediane de +8% sur le montant vaut ~+0.8 pt sur le rendement d'un cycle,")
    print("a comparer a l'alpha median T5c-A de +7.39 pts. L'erreur de MESURE est")
    print("donc moderee ; l'erreur de SELECTION (filtre yield_pct dans T9 volet A)")
    print("est le probleme principal — les trades ont ete choisis sur le rendement")
    print("de l'annee suivante.")


if __name__ == "__main__":
    main()
