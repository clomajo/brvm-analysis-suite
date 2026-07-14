# REMEDIATION_LOG.md

Journal des tâches d'exécution du plan de remédiation v1.2.
Une entrée par tâche terminée, committée à la fin de chaque tâche.

---

## T0 — Branche de travail et snapshot

- **Date d'exécution** : 2026-07-08
- **Branche** : `remediation-2026-07` (poussée vers origin)
- **Backup Supabase automatique** : ❌ Indisponible (plan Free — confirmé via Dashboard → Database → Backups → Scheduled backups)
- **Snapshot de repli** : Export CSV manuel des 3 tables à risque pour cette remédiation, via SQL Editor → Download CSV :
  - `target_prices_rows.csv` (979 lignes)
  - `company_fundamentals_rows.csv` (261 lignes)
  - `fundamental_analysis_rows.csv` (4997 lignes)
  Stockés dans `backups/2026-07-08/` (non versionné — voir .gitignore).
- **Statut** : ✅ Terminé
- **Notes** : `historical_data`, `corporate_events`, `sector_per_history` non sauvegardées — hors scope des tâches prévues dans ce cycle de remédiation.

---


## T1 — Health Check quotidien TERMINE (2026-07-09)

**Fichier :** health_check.py (racine du repo, integre au workflow brvm-analysis.yml)

**Objectif :** empecher qu'un run Actions sorte en exit 0 sans avoir rien insere
(cf. incident BACKLOG corrompu 1 mois sans detection).

**Controles :** nb_prices (seuil 35), nb_targets (seuil 30), nb_decisions (seuil 30),
missing_tickers, exemption week-end/jours feries BRVM.

**Criteres d'acceptation :**
- [x] #1 - Execution locale : exit code coherent, tableau affiche (commit 71b65af)
- [x] #2 - Run manuel workflow_dispatch : Summary GitHub Actions affiche
      correctement (run #170)
- [x] #3 - Test negatif (MIN_PRICES=999) : job echoue, comportement bruyant
      confirme (run #171, commits c28b3c0 -> bff7fa8)

**Commits :**
- 71b65af - health_check.py cree
- 7365405 - integration workflow (step "Health Check" avec if: always())
- c28b3c0 -> bff7fa8 - test negatif + restauration seuil

**Anomalie reelle detectee pendant les tests (a traiter separement, hors perimetre T1) :**
2026-07-09 : nb_targets=22 alors que seuil=30. target_prices incomplet pour
la journee. A investiguer dans calculate_target_price.py.

**Note operationnelle :** JOURS_FERIES_BRVM_2026 rempli (11 dates, source
calendrier officiel brvm.org publie 19/12/2025). 4 dates marquees (*) sujettes
a revision (fetes mobiles) - a reverifier en mars/mai/aout 2026 avant echeance.

**Extension differee (session separee) :** table Supabase pipeline_health
pour historiser les bilans (point 7 de la spec T1, non implemente).


## Suivi differe — nb_targets=22 (2026-07-09)

Anomalie detectee par le health check (voir T1 ci-dessus) : target_prices
incomplet pour la journee du 2026-07-09 (22/47 tickers, seuil=30).
Investigation NON demarree — decision de Jocelyn de differer pour suivi
ulterieur, hors session du 09/07/2026.

A investiguer : calculate_target_price.py (pourquoi seulement 22 tickers
mis a jour aujourd'hui alors que nb_prices=49 et nb_decisions=47 sont OK).

## T3 — Investigation NTLC (split vs erreur de scraping) — 09/07/2026

**Statut :** ✅ Terminé

- Script `tools/investigate_ntlc.py` exécuté, sortie brute archivée
  (`tools/ntlc_report.csv`)
- Discontinuité unique détectée : 2017-09-11 (-94.62%)
- Confirmée comme split réel via BRVM Avis N°164-2017/BRVM/DG (20:1)
- Correction SQL appliquée (361 lignes, company_id=22,
  trade_date < 2017-09-11, price = price / 20)
- Vérification post-correction : continuité de prix confirmée sur tout
  l'historique 2016-2026
- Décision consignée : ADR-032 (DECISIONS.md)
- Point ouvert (non bloquant) : écart ratio split (20) vs ratio
  shares_outstanding (20.064) — source de l'écart non investiguée

### Session clôturée — 09/07/2026

- Commit script + données : `873fce5`
- Commit documentation (ADR-032, CHANGELOG, BACKLOG) : `74064c8`
- Branche : `remediation-2026-07`
- T3 terminé, aucun blocage. Prochaine tâche à planifier : finaliser T0
  (vérification exports CSV) ou traiter les 86 lignes `[FALLBACK]` dans
  `fundamental_analysis`.

## T2a — Extraction (injection de dépendances) — 09/07/2026

**Statut :** ✅ Terminé — aucune modification de code nécessaire

**Constat (vérifié par lecture directe du code source, pas d'hypothèse) :**
Les 3 fonctions cibles de T2 (`evaluer_qualite_eps`, `check_eps_coherence`,
`_parse_date_from_titre`) reçoivent déjà toutes leurs données en paramètres
et ne font aucun accès Supabase direct dans leur corps. L'injection de
dépendances requise par T2a est déjà en place — pas de refactor à faire.

Vérification : grep de `self\.` dans le corps de `_parse_date_from_titre`
(223-273) : aucune occurrence (les 3 matches trouvés appartiennent à
`_find_all_reports`, méthode suivante).

**Décision :** passage direct à T2b (écriture des tests), sans diff de
refactor à valider puisqu'aucun refactor n'était nécessaire.

## T2b — Suite pytest (tests uniquement)

**Date :** 10/07/2026
**Commits :** f242e92, c1a740d, 07040a2, 9e00147 (branche remediation-2026-07)

**Réalisé :**
- tests/conftest.py, test_eps.py, test_parsing.py, test_health.py (24 tests)
- pytest.ini (pythonpath = .), .github/workflows/tests.yml, pytest==8.* ajouté à requirements.txt
- Cible : check_eps_coherence(), evaluer_qualite_eps(), _parse_date_from_titre(),
  logique week-end/jour férié de health_check.main()

**Incident découvert et corrigé :**
Le pattern .gitignore `test_*.py` (initialement destiné à exclure d'anciens
scripts jetables) masquait silencieusement test_eps.py, test_parsing.py et
test_health.py — seul conftest.py avait été commité (f242e92), donnant un faux
sentiment de succès local (pytest fonctionnait car les fichiers existaient sur
disque, non ignorés par pytest lui-même). Détecté via `git status` avant push
grâce à la gate de vérification systématique. Corrigé par exception ciblée
`!tests/test_*.py` (commit c1a740d), sans toucher aux autres patterns.

**Écart spec/code documenté (non corrigé, T2b = zéro modif prod) :**
check_eps_coherence() retourne (None, None) silencieusement — sans warning —
quand shares_outstanding est 0 ou None, alors que la spec T2 attendait un
warning. Comportement réel figé tel quel dans les tests. À traiter éventuellement
en T4.

**Critères d'acceptation :**
1. ✅ pytest -v local : 24/24 passed
2. ✅ Workflow GitHub Actions vert (run c1a740d puis 9e00147)
3. ✅ Test de non-régression volontaire : 4 assertions cassées (commit 07040a2)
   → CI détecte l'échec (4 failed, 20 passed) → réparé (commit 9e00147) → CI verte

## T4 — Refactor EPS (net_income/shares_outstanding) — 11/07/2026

**Statut : FAIT (scope réduit, documenté)**

- `check_eps_coherence()` : eps_recalcule devient valeur primaire de
  `company_fundamentals.eps`, eps scrapé devient cross-check (docstring mise à jour).
- Garde-fou de sanité ajouté (ratio eps_scrapé/eps_recalcule hors [0.2, 5] → pas
  de remplacement) pour éviter l'insertion de valeurs aberrantes.
- 24/24 tests pytest non-régression validés.
- **Critère d'acceptation initial (NTLC FY2024 = 822.37 FCFA) NON atteint** — cause
  racine identifiée (shares_outstanding scrapé faux, bug parse_val 'M' + split 2017
  non répercuté à la source) et documentée séparément (ADR-033, BACKLOG.md), hors
  périmètre de cette session par décision explicite.
- Validation manuelle NTLC FY2024 : eps_recalcule=16 500 000 000 (aberrant),
  garde-fou déclenché, eps_scraped=16447.64 conservé (comportement attendu).

Commits : 120008a
## T5b — Backtest net (frais) — V2 cours cible

**Date d'exécution :** 13/07/2026

**Source des signaux :** `backtest_value.py` (commit `49a64b6`), réplique via `backtest_net_value.py` (aucune modification du script source).

**Portée du calcul net :** frais de transaction uniquement. Cette stratégie (convergence prix/valeur intrinsèque) ne comptabilise pas de dividende encaissé dans son rendement mesuré — **aucun terme IRVM appliqué ici**. Ne pas confondre avec la stratégie dividend capture (BOAB/BOAC/ECOC/SMBC/NSBC/NTLC), traitée séparément en T5c.

**⚠️ Flag 1 :** courtage SGI (1.0%) non confirmé par source primaire (CREPMF ou avis d'opéré réel) — hypothèse de travail issue d'un document Scribd non-primaire (cf. ADR-034, BACKLOG.md).

**⚠️ Flag 2 :** les dividendes éventuellement versés pendant la fenêtre J+90 ne sont pas comptés dans `backtest_value.py`. Le rendement net ci-dessous est donc **conservateur** (sous-estimé) par rapport au rendement total réel (prix + dividende).

**Étape 0 (reproductibilité) :** n=25 signaux ACHAT (attendu 25), médiane J+90 brute=+7.8% (attendu +7.8%) — **dans la tolérance, validé le 13/07/2026**.

**Frais aller-retour appliqués :** 2.6% (= 2 × [0.2% BRVM + 0.1% DC/BR + 1.0% SGI non confirmé])


### Tableau comparatif (J+90, n=25 signaux ACHAT)

| Mesure | n | Médiane | Moyenne | % positifs | Pire cas |
|---|---|---|---|---|---|
| Brut | 25 | +7.8% | +6.4% | 68.0% | -27.9% |
| Net (frais 2.6% AR) | 25 | +5.2% | +3.8% | 64.0% | -30.5% |

### Sensibilité FILL_RATE

⚠️ 0.75 est le taux de fill validé pour la stratégie DIVIDEND CAPTURE (walk-forward BOAB/BOAC/ECOC/SMBC/NSBC/NTLC), PAS pour cette stratégie V2 cours cible. Grille fournie à titre informatif/sensibilité uniquement.

| FILL_RATE | n | Médiane | Moyenne | % positifs | Pire cas |
|---|---|---|---|---|---|
| 0.60 | 25 | +3.1% | +2.3% | 64.0% | -18.3% |
| 0.75 | 25 | +3.9% | +2.9% | 64.0% | -22.9% |
| 0.90 | 25 | +4.7% | +3.4% | 64.0% | -27.4% |

### Calibration seuil_liquidite (proposition)

| Ticker | volume_20j médian |
|---|---|
| BOAB | 3,171 |
| BOAC | 4,623 |
| ECOC | 1,814 |
| NSBC | 1,512 |
| NTLC | 1,772 |
| SMBC | 952 |

**Médiane des volume_20j (6 tickers) :** 1,793
**Seuil proposé (× 0.5) :** 896

*Proposition chiffrée à valider par Jocelyn — non appliquée au pipeline dans cette tâche.*

## T6 — Stress-test statistique V2 (cours cible)

**Date d'exécution :** 13/07/2026

**Source des signaux :** identique à T5b — `backtest_value.py` (commit `49a64b6`), répliqué via `tools/stress_test_v2.py`.

**Étape 0 (reproductibilité, seuils par défaut) :** n=25 (attendu 25), médiane J+90=+7.8% (attendu +7.8%).


### Volet 1 — Bootstrap (10 000 tirages)

- n = 25, médiane observée = +7.8%, moyenne observée = +6.4%
- IC95% médiane : [-1.6%, +14.3%]
- IC95% moyenne : [+1.2%, +11.4%]

⚠️ **Règle appliquée :** **V2 non prouvé statistiquement** — plafonner la taille de position par signal à un montant défini par Jocelyn jusqu'à n ≥ 60 signaux vérifiés.


### Volet 2 — Walk-forward (3 tiers chronologiques)

| Tiers | n | Période | Médiane | Moyenne |
|---|---|---|---|---|
| 1 | 8 | 2022-04-30 → 2023-04-30 | +9.8% | +7.5% |
| 2 | 8 | 2023-04-30 → 2024-04-30 | +5.2% | +3.1% |
| 3 | 9 | 2024-04-30 → 2025-04-30 | +8.4% | +8.3% |

✅ Tous les tiers ont une médiane ≥ 0 — règle non déclenchée.


### Volet 3 — Sensibilité aux seuils (grille ROE × P/B)

| ROE \ P/B | 2.0 | 2.5 | 3.0 |
|---|---|---|---|
| 12 | n=22, +7.2% | n=26, +6.9% | n=28, +6.9% |
| 15 | n=21, +8.4% | n=25, +7.8% | n=27, +7.8% |
| 18 | n=17, +8.4% | n=21, +7.8% | n=23, +7.8% |

✅ Aucune variation > 50% entre cases adjacentes — règle non déclenchée.


### Volet 4 — Biais de survivance (10 tickers exclus)

- Tickers exclus (9) : BNBC, BOAN, CFAC, ETIT, FTSC, NTLC, SICC, SIVC, UNLC
- Signaux hypothétiques générés (auraient été ACHAT sans exclusion) : 8
- Dont perdants (perf_j90 < 0) : 5

| Ticker | FY | Perf J+90 hypothétique | Perdant |
|---|---|---|---|
| BOAN | FY2021 | -9.7% | oui |
| BOAN | FY2022 | -4.2% | oui |
| BOAN | FY2023 | -12.2% | oui |
| BOAN | FY2024 | -3.5% | oui |
| NTLC | FY2021 | -10.5% | oui |
| NTLC | FY2023 | +10.1% | non |
| NTLC | FY2024 | +19.7% | non |
| SIVC | FY2023 | +14.1% | non |

*Rapport brut, sans conclusion — interprétation réservée à Jocelyn.*

