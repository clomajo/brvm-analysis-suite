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


## E2.7-B — Timing d'entree, detention longue
**Date d'execution**: 2026-07-27 22:37
**Classe**: A (offline, lecture seule)
**Cycles exploitables source**: 89
**Univers etendu**: 25 tickers (>=1 cycle dividende exploitable, sans filtre de liquidite ni de nombre minimum de cycles)
**Cycles multi-dividendes signales**: 0

**Tableau 4x3 (offset x duree), n / ecart median / %battant par case**:

| offset\\duree | 35j | 47j | 70j |
|---|---|---|---|
| -5 | n=89, ecart=2.7128, %b=60.7 | n=88, ecart=3.4535, %b=67.0 | n=88, ecart=4.6346, %b=62.5 |
| +0 | n=89, ecart=3.1252, %b=69.7 | n=88, ecart=4.5691, %b=63.6 | n=88, ecart=4.4201, %b=64.8 |
| +5 | n=88, ecart=2.9528, %b=69.3 | n=88, ecart=3.6191, %b=67.0 | n=88, ecart=5.7289, %b=67.0 |
| +10 | n=88, ecart=3.3159, %b=72.7 | n=88, ecart=3.617, %b=65.9 | n=87, ecart=5.6769, %b=67.8 |

**Combinaisons avec ecart median positif**: 12/12
**Combinaisons avec %battant>=55**: 12/12
**Offset proche annonce (J-5 ou J0) avec >=2/3 durees a %battant>=55**: True

**VERDICT: TIMING_DIVIDENDE_CONFIRME**
Timing d'entree autour de l'annonce de dividende ameliore le rendement vs entree aleatoire, de facon robuste a travers les durees testees. Combinaison(s) a discuter avec Jocelyn : (offset=+5, duree=70j): ecart_median=5.7289, (offset=+10, duree=70j): ecart_median=5.6769, (offset=-5, duree=70j): ecart_median=4.6346.

**Artefacts**: `tools/experiments/E2_7B/E2_7B_rendement_par_combinaison.csv` (1057 lignes), `tools/experiments/E2_7B/E2_7B_reference_aleatoire.csv` (75 lignes), `tools/experiments/E2_7B/E2_7B_alpha_par_combinaison.csv` (1057 lignes)

### E2.7-B — Complement : robustesse par ticker (hors grille, hors verdict)

Lecture de `E2_7B_alpha_par_combinaison.csv` agregee par ticker (tous
offsets/durees confondus) pour distinguer les tickers a faible n_cycles
(peu robuste) de ceux a n_cycles eleve. Ne modifie pas le verdict
TIMING_DIVIDENDE_CONFIRME ci-dessus (base sur la grille 4x3, n~87-89 par
case), fournit un contexte complementaire.

**Tickers robustes (>=3 cycles dividende exploitables, 19 tickers)**:

| Ticker | n_cycles | Ecart median | %gagnants |
|---|---|---|---|
| NSBC | 3 | +14.24 | 97.2% |
| BOAM | 3 | +12.43 | 94.4% |
| SPHC | 4 | +7.55 | 62.5% |
| ONTBF | 5 | +7.41 | 85.0% |
| ORAC | 4 | +7.35 | 91.5% |
| ECOC | 5 | +6.89 | 80.0% |
| BOAS | 5 | +6.54 | 88.3% |
| BOAC | 5 | +6.19 | 85.0% |
| SNTS | 3 | +3.96 | 86.1% |
| CBIBF | 5 | +2.14 | 56.7% |
| TTLC | 4 | +2.08 | 56.2% |
| CIEC | 4 | +1.66 | 60.5% |
| BOAB | 5 | +1.38 | 60.0% |
| BOABF | 5 | +0.71 | 56.7% |
| STBC | 4 | -0.60 | 47.9% |
| BOAN | 3 | -0.94 | 44.4% |
| CFAC | 3 | -1.29 | 36.1% |
| SOGC | 4 | -3.31 | 41.7% |
| NTLC | 4 | -4.63 | 22.9% |

**Tickers peu robustes (<3 cycles, 6 tickers)**:

| Ticker | n_cycles | Ecart median | %gagnants |
|---|---|---|---|
| PRSC | 2 | +9.66 | 100.0% |
| CABC | 2 | +5.28 | 66.7% |
| FTSC | 1 | +3.47 | 91.7% |
| SHEC | 2 | +2.61 | 62.5% |
| SLBC | 2 | +0.77 | 50.0% |
| SMBC | 2 | -0.27 | 50.0% |

**Point de vigilance**: les deux meilleurs scores agreges (NSBC +14.2,
BOAM +12.4) reposent sur seulement 3 cycles chacun — a traiter avec
prudence, pas comme piliers du verdict global. Les resultats les plus
solides viennent des tickers a 4-5 cycles (ONTBF, ORAC, ECOC, BOAS,
BOAC), globalement positifs ; NTLC (5 cycles, -4.63) est la principale
exception negative robuste.
