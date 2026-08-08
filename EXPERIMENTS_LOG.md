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


## T5c-A / E2.8 — Backtest strategie de rotation dediee dividend capture
**Date d'execution**: 2026-07-28 17:42
**Classe**: A (offline, lecture seule)
**Strategie**: achat/revente par cycle dividende, pas de detention longue.
Combinaison unique (entree = jour de bourse le plus proche de l'annonce,
sortie = jour de bourse le plus proche du paiement), reprise de la
reference E2.6/E2.7-A (GRILLE_ROBUSTE, aucune variante superieure trouvee).
**Univers**: etendu complet, 25 tickers avec >=1 cycle
dividende exploitable, sans filtre de liquidite ni de nombre minimum de
cycles (NTLC inclus).
**Calcul**: BRUT (ni frais ni IRVM — decision de session, sensibilite a
traiter a posteriori).
**Cycles exploitables source**: 89 ; cycles valides: 89 ; exclus: 0

**Robustesse globale**: n=89, rendement_median=9.7449%,
alpha_median=7.386 pts, %gagnants=89.9%,
%alpha_positif=79.8%

**Robustesse par ticker** (19 tickers a >=3 cycles, 6 a <3 cycles) :

| Ticker | n_cycles | rendement_median | alpha_median | %gagnants |
|---|---|---|---|---|
| FTSC | 1 | 232.863 | 220.608 | 100.0 |
| SLBC | 2 | 81.239 | 45.0366 | 100.0 |
| SPHC | 4 | 22.282 | 19.0886 | 75.0 |
| NSBC | 3 | 17.6034 | 14.9884 | 100.0 |
| PRSC | 2 | 15.605 | 14.0996 | 100.0 |
| CBIBF | 5 | 13.5169 | 13.8034 | 80.0 |
| STBC | 4 | 14.468 | 13.4319 | 100.0 |
| BOAM | 3 | 16.2 | 11.2995 | 100.0 |
| ECOC | 5 | 9.1822 | 10.7052 | 100.0 |
| BOAS | 5 | 15.0 | 10.1813 | 100.0 |
| ONTBF | 5 | 9.6415 | 8.3752 | 100.0 |
| BOAC | 5 | 8.1557 | 7.5098 | 100.0 |
| BOAB | 5 | 5.0202 | 7.2148 | 80.0 |
| ORAC | 4 | 10.7775 | 6.3416 | 100.0 |
| SNTS | 3 | 4.9051 | 5.7218 | 100.0 |
| CIEC | 4 | 6.9741 | 4.9016 | 100.0 |
| BOABF | 5 | 4.2098 | 4.2378 | 80.0 |
| SOGC | 4 | 7.4458 | 4.1348 | 75.0 |
| BOAN | 3 | 1.7149 | 4.0031 | 66.7 |
| TTLC | 4 | 5.0217 | 3.2065 | 100.0 |
| NTLC | 4 | 8.8673 | 3.1446 | 100.0 |
| CABC | 2 | 3.8589 | 1.1724 | 100.0 |
| SMBC | 2 | 6.4866 | 1.1265 | 50.0 |
| SHEC | 2 | 0.4533 | -0.0284 | 50.0 |
| CFAC | 3 | 3.2836 | -0.1445 | 66.7 |

**Artefacts**: `tools/experiments/E2_8_rotation/E2_8_rotation_par_cycle.csv` (89 lignes),
`tools/experiments/E2_8_rotation/E2_8_rotation_par_ticker.csv` (25 lignes)

---

## 31/07/2026 — Découverte : décalage d'un an sur les montants de dividendes (ADR-040)

**Portée : E2.6, E2.7-A, E2.7-B, T5c-A (E2_8_rotation), T9 volet A.**

`corporate_events.DIVIDEND_HISTORY.fiscal_year` retarde d'un an sur la convention BRVM. `dividend_cycle_exploration.csv`, qui alimente toute la chaîne d'expériences dividende, associe donc à chaque ex-date le montant de l'année suivante. **77 des 89 cycles exploitables sont affectés.**

Preuve documentaire (pas statistique) : avis officiels BRVM exercice 2025 + avis de crédit du courtier, concordants sur SNTS/BOAB/ONTBF/BOAC, contre les lignes `DIVIDEND_HISTORY` correspondantes. Détail complet dans ADR-040.

**Impact différencié :**
- *Mesure* — médiane +8.2%, moyenne +20.8% sur le montant. Soit ~+0.8 pt de rendement par cycle, contre un alpha médian T5c-A de +7.39 pts. Les chiffres publiés sont faux, la conclusion qualitative tient probablement.
- *Sélection* — `yield_pct` décalé de même. Le filtre `yield_pct >= 8%` de T9 volet A a sélectionné les trades sur le rendement de l'année suivante : look-ahead sur le choix des positions, biais orienté (63% de surestimation). Le 100% de trades positifs du volet A devient suspect, et avec lui le verdict de gel de la Phase 13.

**Ne remet pas en cause** : T6 (IC95% borne basse négative) et T14 (concentration sectorielle) sont indépendants et inchangés. V2 n'est pas réhabilité pour autant.

**Résultat négatif conservé** : `tools/diag_decalage_fiscal_year.py` (preuve tentée par la chute de prix à l'ex-date) est **invalidé** — le cours BRVM ne s'ajuste pas du montant du dividende (ONTBF : chutes de +5/−8.5/−20/+30 pour des dividendes de 145 à 288 ; ECOC et ORAC 2026 : chute nulle pour 781 et 704 FCFA). Son score 60/40 ne mesure rien et ne doit pas être cité. Script conservé pour ne pas refaire l'erreur.

**Piste ouverte par cet échec** : l'absence d'ajustement du cours à l'ex-date serait un mécanisme candidat pour expliquer le succès du dividend capture, indépendant du bug. À contrôler par les volumes (chutes à exactement 0.0 = cours possiblement figés).

**Outils** : `tools/diag_decalage_montants.py` (quantification, lecture seule, rejouable).

## 04/08/2026 — Validation réelle V1 (portefeuille Sikafinance, 5 trades) + trade dividende ONTBF hors-scope

**Contexte** : 6 achats réels exécutés via BOA Capital Securities (bordereaux, client 163163) entre 14/04 et 10/06/2026, suivis dans le portefeuille Sikafinance (portif/displayp?n=33609). Objectif : vérifier a posteriori la correspondance signal V1 ↔ décision d'achat, et calculer les rendements réels J+45/J+60/J+90 depuis `historical_data` (jointure via `company_id`, pas de colonne `symbol` directe sur `historical_data` ni sur `brvm_decisions` — colonne réelle : `ticker`).

### Validation signal → achat (5 trades V1, ONTBF exclu — voir note)

| Titre | Date opération | Signal ce jour | Score | Régime | Match ACHAT |
|---|---|---|---|---|---|
| SONATEL lot1 (SNTS) | 14/04/2026 | ACHAT | 73 | BULL | ✅ |
| SONATEL lot2 (SNTS) | 17/04/2026 | SURVEILLER | 59 | BULL | ⚠️ non exact — ACHAT la veille (04-16, score 83) et le lendemain (04-18, score 63), probable lag d'exécution |
| BOAB | 21/04/2026 | ACHAT | 74 | BULL | ✅ |
| BOAC | 21/04/2026 | ACHAT | 81 | BULL | ✅ |
| NTLC | 21/04/2026 | ACHAT | 73 | BULL | ✅ |

**4/5 correspondance exacte jour J. 1/5 (SNTS lot2) décalage d'un jour, signal ACHAT présent immédiatement avant/après — cohérent avec un lag d'exécution (bulletin veille) plutôt qu'un vrai désaccord signal/décision.**

### Résultats réels J+45 / J+60 / J+90 (depuis date d'achat réelle)

| Titre | Achat | Entry (FCFA) | J+45 | J+60 | J+90 |
|---|---|---|---|---|---|
| SONATEL lot1 | 14/04 | 28 800 | -2.08% | -1.39% | **+7.29%** |
| SONATEL lot2 | 17/04 | 27 500 | +3.45% | +3.27% | **+18.18%** |
| BOAB | 21/04 | 8 000 | +9.94% | +10.62% | +8.75% |
| BOAC | 21/04 | 8 695 | +1.67% | +7.53% | **+12.08%** |
| NESTLE CI | 21/04 | 12 480 | +4.13% | +20.23% | **+26.60%** |
| ONATEL BF* | 10/06 | 2 950 | -5.08% | n/a (09/08) | n/a (08/09) |

*ONTBF = achat dividend capture, **hors scope V1** (signal SURVEILLER ce jour, 50/BULL — non pertinent, la décision d'achat n'était pas basée sur le signal V1). Rendement -5.08% à J+45 non net du dividende perçu — à ne pas interpréter comme échec avant confirmation du montant dividende encaissé.

### Constats

- **5/5 trades V1 complétés positifs à J+90**, médiane ≈ +12%, cohérent avec le pattern multi-horizon V1 déjà documenté (hit rate croissant avec l'horizon, J+90: 81.8% sur backtest commit `8ef56ad`). Échantillon réel (n=5) trop petit pour confirmer statistiquement mais directionnellement aligné.
- **NTLC +26.60% à J+90** — meilleur performer. Notable car NTLC a un comportement contrasté en backtest (positif T5c-A rotation, négatif T5c-B long-hold) ; ce résultat buy-and-hold réel se rapproche du pattern T5c-A.
- **SNTS lot1** creuse à J+45/60 avant forte reprise à J+90 — illustre la pertinence de l'absence de stop-loss (ADR-036, illiquidité BRVM) : une sortie prématurée sur drawdown intermédiaire aurait raté le rendement final.
- **ONTBF** : rendement prix seul non interprétable sans le dividende — nécessite calcul net une fois le dividende confirmé encaissé, avant tout jugement sur la stratégie dividend capture.

### Note technique (schéma)

- `historical_data` n'a pas de colonne `symbol` — jointure via `company_id` (FK vers `companies.id`).
- `brvm_decisions` n'a pas de colonne `symbol` — la colonne réelle est `ticker`.
- Tickers bordereaux BOA (SNTS, BOAB, BOAC, NTLC, ONTBF) confirmés identiques à `companies.symbol` — pas de mapping supplémentaire nécessaire pour ce cas.

### Action en attente

- Calculer le rendement net ONTBF une fois le montant du dividende perçu confirmé.
- J+60/J+90 ONTBF à recalculer après le 09/08 et le 08/09/2026 respectivement.

## AUDIT E2.6 — Reaudit de H1 (alpha en prix pur des deux cotes)
**Date**: 2026-08-07 | **Classe**: A (offline, lecture seule, aucun acces DB)
**Motif**: E2.8/T5c-A a revele une asymetrie de benchmark. E2.6 utilise le
meme `compute_benchmark`. Verification de H1 au meme test.

**Defaut confirme**: `run_e2_6.py` L289 calcule le rendement sujet en
`(p_end - p_start + dividende) / p_start`, tandis que `compute_benchmark`
L129 reste en prix pur `(p_end - p_start) / p_start`. La fenetre
annonce->paiement contient l'ex-date par construction: les 89 cycles sont
affectes, sans exception.

**C1 (reconciliation source/E2.6)**: 88/89 concordants (98.9%), seuil 95%.
Un ecart isole: BOAM 2025 (-6.769 pts), divergence de borne de prix
(fenetre max_gap_days=5) — sans effet sur la mediane.

**Resultat (n=89)**:
| Mesure | Publie | Prix pur |
|---|---|---|
| alpha median | +7.333 | **-2.688** |
| % positif | 79.8% | **39.3%** |

contrib_div mediane = **+8.561 pts** — valeur identique a celle mesuree sur
E2.8/T5c-A. E2.6 et T5c-A ne sont pas deux resultats independants: c'est le
meme artefact compte deux fois.

**Regles pre-fixees appliquees**: V1 (median>=+2.0 ET %pos>=55) / V2
(median<=0 OU %pos<=45) / V3 sinon. **VERDICT: V2**, les deux criteres
franchis simultanement.

**Robustesse**: mediane -2.715 en excluant SLBC 2023 (duree 424j, seule
anomalie >180j); FTSC et SLBC conserves dans le primaire. 13/19 tickers
(n>=3) en mediane negative. Effondrement uniforme par annee (-8 a -12 pts
chacune); 2025 le plus degrade (pp -6.87 / 19% positif).

**Test conservateur**: le benchmark prix pur reste deprime par les
detachements des tickers de reference sur les memes fenetres avril-juin.
Le vrai alpha, avec benchmark total-return symetrique, serait plus negatif.
-2.688 est un plancher optimiste.

**Portee**: H1 (drift post-annonce) n'est pas demontre. Ceci N'ETABLIT PAS
que le drift n'existe pas — un benchmark total-return correct reste a
specifier (session distincte).

**Non teste, suspect**: E2.7-A et E2.7-B reposent sur la meme mecanique.
12/12 combinaisons positives dans chaque grille est le profil attendu d'un
terme additif quasi constant de +8.5 pts. Hypothese, pas verdict.

**Non affectes**: validation multi-horizon V1 (8ef56ad), T9, T14,
portefeuille reel — methodologies distinctes, ne passent pas par
`compute_benchmark`. T9/T14 sont des resultats negatifs; ce defaut gonfle
les performances et ne peut pas les inverser.

**Artefacts**: `tools/experiments/E2_6/audit_e2_6_alpha_pp.py`,
`tools/experiments/E2_6/E2_6_audit_alpha_pp.csv` (89 lignes)

**Suites (ordre)**: 1) auditer E2.7-A/B avant redaction ADR, pour couvrir
le perimetre reel en une fois; 2) ADR unique sur l'asymetrie
`compute_benchmark`; 3) reclasser le statut de T5c — l'entree/sortie
annonce->paiement n'a plus de support empirique.

## AUDIT E2.6 — Reaudit de H1 (alpha en prix pur des deux cotes)
**Date**: 2026-08-07 | **Classe**: A (offline, lecture seule, aucun acces DB)
**Motif**: E2.8/T5c-A a revele une asymetrie de benchmark. E2.6 utilise le
meme `compute_benchmark`. Verification de H1 au meme test.

**Defaut confirme**: `run_e2_6.py` L289 calcule le rendement sujet en
`(p_end - p_start + dividende) / p_start`, tandis que `compute_benchmark`
L129 reste en prix pur `(p_end - p_start) / p_start`. La fenetre
annonce->paiement contient l'ex-date par construction: les 89 cycles sont
affectes, sans exception.

**C1 (reconciliation source/E2.6)**: 88/89 concordants (98.9%), seuil 95%.
Un ecart isole: BOAM 2025 (-6.769 pts), divergence de borne de prix
(fenetre max_gap_days=5) — sans effet sur la mediane.

**Resultat (n=89)**:
| Mesure | Publie | Prix pur |
|---|---|---|
| alpha median | +7.333 | **-2.688** |
| % positif | 79.8% | **39.3%** |

contrib_div mediane = **+8.561 pts** — valeur identique a celle mesuree sur
E2.8/T5c-A. E2.6 et T5c-A ne sont pas deux resultats independants: c'est le
meme artefact compte deux fois.

**Regles pre-fixees appliquees**: V1 (median>=+2.0 ET %pos>=55) / V2
(median<=0 OU %pos<=45) / V3 sinon. **VERDICT: V2**, les deux criteres
franchis simultanement.

**Robustesse**: mediane -2.715 en excluant SLBC 2023 (duree 424j, seule
anomalie >180j); FTSC et SLBC conserves dans le primaire. 13/19 tickers
(n>=3) en mediane negative. Effondrement uniforme par annee (-8 a -12 pts
chacune); 2025 le plus degrade (pp -6.87 / 19% positif).

**Test conservateur**: le benchmark prix pur reste deprime par les
detachements des tickers de reference sur les memes fenetres avril-juin.
Le vrai alpha, avec benchmark total-return symetrique, serait plus negatif.
-2.688 est un plancher optimiste.

**Portee**: H1 (drift post-annonce) n'est pas demontre. Ceci N'ETABLIT PAS
que le drift n'existe pas — un benchmark total-return correct reste a
specifier (session distincte).

**Non teste, suspect**: E2.7-A et E2.7-B reposent sur la meme mecanique.
12/12 combinaisons positives dans chaque grille est le profil attendu d'un
terme additif quasi constant de +8.5 pts. Hypothese, pas verdict.

**Non affectes**: validation multi-horizon V1 (8ef56ad), T9, T14,
portefeuille reel — methodologies distinctes, ne passent pas par
`compute_benchmark`. T9/T14 sont des resultats negatifs; ce defaut gonfle
les performances et ne peut pas les inverser.

**Artefacts**: `tools/experiments/E2_6/audit_e2_6_alpha_pp.py`,
`tools/experiments/E2_6/E2_6_audit_alpha_pp.csv` (89 lignes)

**Suites (ordre)**: 1) auditer E2.7-A/B avant redaction ADR, pour couvrir
le perimetre reel en une fois; 2) ADR unique sur l'asymetrie
`compute_benchmark`; 3) reclasser le statut de T5c — l'entree/sortie
annonce->paiement n'a plus de support empirique.
