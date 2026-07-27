# EXPERIMENTS_LOG - statuts des experiences E1/E2

## E2.6 — Identification du mecanisme dividende (H1/H2/H3)
**Date d'execution**: 2026-07-22 16:46
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: 89 | **Traites**: 89 | **Ecartes**: 0

**Statut cotation ex**: COTE_SANS_VARIATION=5, NON_COTE=0, COTE_AVEC_VARIATION=84

**Criteres H1**:
- alpha median global >= +2pts: True (valeur=7.3331)
- >=60% tickers (n>=3) a alpha median positif: True (valeur=94.73684210526315)
- alpha median positif sur les 4 annees civiles: True

**Sous-groupes ex ante (H2)**:
- delai AG->ex <= 45j: n=48, chute_mediane=10.85
- yield tercile superieur: n=30, chute_mediane=28.1
- volume >= mediane: n=45, chute_mediane=10.0

**VERDICT: H1**
H1 confirmee — derive post-annonce. Mecanisme candidat pour T5c : hold annonce->paiement. Regle d'entree a cadrer avec Jocelyn.

**Artefacts**: `tools/experiments/E2_6/E2_6_alpha_par_cycle.csv` (89 lignes)


## E2.7-A — Grille entree/sortie, rotation dediee
**Date d'execution**: 2026-07-27 16:39
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: 89

**Tableau 4x3 (entree x sortie), n et alpha median par case**:

| entree\\sortie | -5 | +0 | +5 |
|---|---|---|---|
| -5 | n=89, α=2.9561 | n=89, α=7.4852 | n=89, α=6.1095 |
| +0 | n=89, α=3.3758 | n=89, α=7.3331 | n=89, α=5.3603 |
| +5 | n=88, α=2.2289 | n=89, α=5.6113 | n=89, α=4.4859 |
| +10 | n=87, α=2.4656 | n=88, α=5.9071 | n=89, α=3.8474 |

**Reference (J0, paiement)**: n=89, alpha_median=7.3331, rang=2/12, top_tercile=True

**Combinaisons positives**: 12/12

**VERDICT: GRILLE_ROBUSTE**
Grille robuste. La fenetre E2.6 (annonce->paiement) est un choix raisonnable, pas une coincidence. Pas de changement de regle recommande.

**Artefacts**: `tools/experiments/E2_7A/E2_7A_alpha_par_combinaison.csv` (1064 lignes)
