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
