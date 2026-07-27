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


## T7 — Centralisation config/params.py

**Date d'exécution :** 13/07/2026

**Fichier créé :** `config/params.py` (+ `config/__init__.py`) — `TAUX_ACTUALISATION = 0.08`, `POIDS_PER = 0.70`, `POIDS_DIVIDENDE = 0.30`.

**Fichier modifié :** `calculate_target_price.py` uniquement (script confirmé actif en prod — seul appelant dans `.github/workflows/brvm-analysis.yml:117`). Diff minimal : `TAUX_REQUIS` devient un alias de `TAUX_ACTUALISATION` importé ; `0.70`/`0.30` remplacés par `POIDS_PER`/`POIDS_DIVIDENDE` dans `calculer_cours_cible()`.

### Inventaire préalable (grep `0\.08\|0\.70\|0\.30`, hors venv)

| Fichier | Ligne | Contexte | Statut |
|---|---|---|---|
| `calculate_target_price.py` | 96 | `TAUX_REQUIS = 0.08` | **Modifié (T7)** |
| `calculate_target_price.py` | 291 | `cours_cible = 0.70 * cours_per + 0.30 * cours_gordon` | **Modifié (T7)** |
| `calculate_target_price_v3.py` | 278 | `marge = 0.15 if qualite >= 3 else 0.30` | Hors périmètre — voir note ci-dessous |
| `calculate_target_price_v3 (1).py` | 224, 261 | `rdt_cible = 0.08`, `marge = 0.15 if qualite >= 3 else 0.30` | Hors périmètre — voir note ci-dessous |
| `generate_decisions.py` | 112, 234, 293 | poids scoring technique (TG/BF/ML/NE, ratio_tech/ratio_fund, rsi/trend/vol) | → BACKLOG |
| `generate_decisions_backup.py` | 105-106 | poids scoring (backup, non actif) | → BACKLOG |
| `opportunity_scorer.py` | 52 | `WEIGHT_FUND = 0.30` | → BACKLOG |
| `opportunity_scorer_all.py` | 26 | `WEIGHT_FUND = 0.30` | → BACKLOG |
| `opportunity_scorer_v2.py` | 25 | `WEIGHT_FUND = 0.30` | → BACKLOG |
| `report_generator.py` | 1144, 1147 | `risk_score += vol_score * 0.30` | → BACKLOG |
| `backtest_honest_v2.py` | 196 | grille de test `[0.30, 0.40, 0.50]` | → BACKLOG (script de backtest, pas de prod) |
| `backtest_step5.py` | 38-41 | poids scoring (rsi/trend/vol_regime) | → BACKLOG (script de backtest, pas de prod) |

**Note — `calculate_target_price_v3.py` / `calculate_target_price_v3 (1).py` :** vérifiés non actifs. Absents de `.github/workflows/*.yml` (seul `calculate_target_price.py` y est appelé). `calculate_target_price_v3.py` n'a qu'un commit (`78ff24a`, session du 04/06/2026) et n'est importé par aucun autre script. `"calculate_target_price_v3 (1).py"` (avec espace et suffixe `(1)`) n'a aucun historique git — doublon local probable. Les deux sont laissés inchangés dans cette tâche ; leur suppression ou clarification est un item BACKLOG distinct, pas un item T7.

**Occurrences dans `opportunity_scorer*.py`, `generate_decisions*.py`, `report_generator.py`, `backtest_*.py` :** ce sont des pondérations de scoring technique/fondamental (V1, backtests), sans rapport avec le modèle cours cible V2 ciblé par T7. Match grep purement numérique (mêmes valeurs 0.30/0.70 réutilisées pour d'autres pondérations). Non modifiées — reportées en BACKLOG.md comme demandé par la spec.

### Test de non-régression

`tools/test_t7_nonregression.py` (jetable, non committé — capturé par `.gitignore` `test_*.py`) : `calculer_cours_cible()` testée en isolation (fonction pure) sur 5 cas couvrant les 3 branches (PER+Gordon, PER seul, Gordon seul, cas nul), comparant l'ancien calcul (constantes en dur) et le nouveau (constantes importées de `config/params.py`).

| Ticker témoin | Cas | Avant | Après | Écart |
|---|---|---|---|---|
| SONATEL | PER+Gordon | 18435.0 | 18435.0 | 0.0 |
| ECOBANK | PER seul | 3100.0 | 3100.0 | 0.0 |
| NESTLE_CI | Gordon seul | 1500.0 | 1500.0 | 0.0 |
| XYZTEST | ni l'un ni l'autre (None) | None | None | — |
| BOAC | PER+Gordon | 993.35 | 993.35 | ~1.1e-13 (bruit flottant, non significatif) |

✅ **Résultat : 5/5 cas identiques au centime — non-régression confirmée.**

### Rafraîchissement PER sectoriels

**Écart avec la spec d'origine :** la spec T7 (Phase 7 du plan v1.2) demande une comparaison aux 5 anciennes catégories du skill (Banque 12.4x, Agro 10.2x, Industrie 13.2x, Telecom 13.3x, Distribution 16.1x). Cette nomenclature a été remplacée par les 7 catégories officielles BRVM depuis la migration du 20/06/2026 (cf. docstring `calculate_target_price.py`, ADR-010) — la comparaison telle que spécifiée n'est plus applicable telle quelle.

`update_sector_per.py` est un script de **saisie interactive manuelle** (prompts `input()` par secteur, source = Tableau de Bord BOA du jour) — non exécuté dans cette tâche (pas de Tableau de Bord du jour disponible en session).

À la place : lecture directe de l'état actuel de `sector_per_history` (7 catégories officielles) :

| Secteur | P/E 2024 | Date de relevé |
|---|---|---|
| CONSOMMATION_DE_BASE | 6.5 | 2026-06-21 |
| CONSOMMATION_DISCRETIONNAIRE | 10.0 | 2026-06-21 |
| ENERGIE | 5.1 | 2026-06-21 |
| INDUSTRIELS | 3.5 | 2026-06-21 |
| SERVICES_FINANCIERS | 14.7 | 2026-06-21 |
| SERVICES_PUBLICS | 6.0 | 2026-06-21 |
| TELECOMMUNICATIONS | 14.7 | 2026-06-21 |

Ces 7 valeurs sont identiques à `PER_FALLBACK` dans `calculate_target_price.py` — aucun écart entre la source vivante et le fallback à ce jour. Dernier relevé : **21/06/2026**, soit >3 semaines — prochaine saisie mensuelle à prévoir prochainement par Jocelyn via `update_sector_per.py`.

### Critères d'acceptation

- ✅ `cours_cible` identiques avant/après (5 cas testés, écarts sous le centime)
- ✅ Écarts PER documentés (aucun écart : source vivante = fallback à ce jour ; nomenclature spec obsolète notée)
- ✅ Aucune autre modification que `calculate_target_price.py` + création `config/params.py`

## T8 — Audit factuel des providers IA (DeepSeek, Gemini, Mistral)

**Date d'exécution :** 13/07/2026

**Statut :** Audit uniquement, zéro modification de code — conforme à la spec.

**Sortie :** `docs/audit_ai_providers.csv` — 7 lignes (colonnes exactes imposées par la spec, `cout_estime_mensuel` laissé vide pour Jocelyn).

### Méthode

1. `grep -rln -i "deepseek\|gemini\|mistral"` sur tout le repo (hors venv) → 13 fichiers matchant.
2. Croisement avec `.github/workflows/*.yml` pour distinguer scripts actifs en prod vs scripts de test/diagnostic/orphelins.
3. Inspection ligne par ligne des scripts actifs (fonctions, modèles, `max_tokens`, table cible).

### Scripts actifs en production avec appel IA (2 confirmés)

- **`fundamental_analyzer.py`** — appelé `.github/workflows/brvm-analysis.yml:208`. Rotation DeepSeek → Gemini → Mistral (s'arrête au premier succès). Écrit dans `fundamental_analysis` (upsert par `report_url`).
- **`report_generator.py`** — appelé `.github/workflows/brvm-analysis.yml:230`. Même architecture de rotation. Écrit dans `report_summary` + `report_company_analysis`.

Les deux sont déclenchés par le même garde-fou de cadence dans le YAML (commande shell, pas dans le script Python) : `if [ "$DOM" = "01" ] || [ "$DOM" = "15" ]` — bi-hebdomadaire, cohérent avec ADR-021.

**Précision sur l'ordre de rotation :** DeepSeek est le provider **primaire** (tenté en premier), Mistral le **dernier recours** — pas l'inverse. L'ARCHITECTURE.md ("AI Fondamentaux : Mistral AI") laisse entendre que Mistral est principal ; en pratique DeepSeek répond en premier dans l'immense majorité des cas si sa clé API est valide. À corriger dans ARCHITECTURE.md si Jocelyn le souhaite (hors périmètre T8).

### Script consommateur (pas appelant) : `generate_decisions.py`

Ne fait aucun appel API IA. Lit `company_fundamentals.signal_fondamental` (déjà calculé en amont) via REST (`supabase.table('company_fundamentals')...`). Exclu du CSV comme "appelant" — mentionné ici pour traçabilité de la chaîne de données.

### Découverte — script orphelin actif niveau coût : `extract_fundamental_signals.py`

Appelle Mistral (`mistral-small-latest`, différent de `mistral-large-latest` utilisé ailleurs) et **peuple `company_fundamentals.signal_fondamental`** — la colonne lue ensuite par `generate_decisions.py`. **N'apparaît dans aucun workflow YAML** (`.github/workflows/*.yml`) — absent de tout déclenchement automatique confirmé. Dernier commit (`a8145ec`, message "45 tickers Mistral signals... FY2025 fix") suggère une exécution manuelle ponctuelle, pas un job récurrent.

Conséquence pratique : le signal fondamental consommé par `generate_decisions.py` (donc par `brvm_decisions`, donc potentiellement par des décisions ACHAT/SURVEILLER/EVITER affichées) dépend d'un script qui n'a **aucune garantie de rafraîchissement automatique**. Si `extract_fundamental_signals.py` n'est pas relancé manuellement, `signal_fondamental` reste figé à sa dernière exécution connue sans qu'aucune alerte ne le signale (pas de couverture par `health_check.py`, qui ne vérifie que `historical_data`/`target_prices`/`brvm_decisions`).

Item détaillé porté en BACKLOG.md — voir "[T8] extract_fundamental_signals.py".

### Découverte — violation ADR-004 sur 2 scripts actifs

`fundamental_analyzer.py` et `report_generator.py` utilisent tous deux `import psycopg2` et des connexions directes (`conn.commit()`, `cur.execute(...)`) pour écrire en base, en violation du garde-fou non-négociable ADR-004 ("Supabase : REST API uniquement... JAMAIS psycopg2"). Ce n'est pas un point relevé dans les tâches précédentes (T0-T7) et représente un écart structurel sur deux scripts de production actifs, pas des scripts jetables.

Item détaillé porté en BACKLOG.md — voir "[T8] Violation ADR-004".

### Critères d'acceptation

- ✅ `docs/audit_ai_providers.csv` produit avec les colonnes exactes imposées
- ✅ `cout_estime_mensuel` laissé à Jocelyn (nb appels/mois × tokens estimés fournis en `frequence_appels`/`max_tokens`, à croiser avec les tarifs providers)
- ✅ Zéro modification de code — audit uniquement

## Vérification multi-horizon du signal ACHAT V1 (J+20 à J+90)

**Date d'exécution :** 18/07/2026

**Contexte :** `verify_decisions.py` ne vérifie officiellement qu'à J+20 (changé depuis J+90 le 30/05/2026, commit `07f46c6`, justifié à l'époque par l'ADR-019 original — "90 jours croise trop d'événements exogènes qui masquent le signal initial"). Cet ADR a depuis été écrasé par une collision de numérotation le 28/06/2026 (un autre sujet a réutilisé le numéro ADR-019) — sa justification originale reste consultable dans l'historique git (`git log -p -- DECISIONS.md`) mais a disparu de la version courante de `DECISIONS.md`. Item BACKLOG à créer séparément pour restaurer cet ADR sous un nouveau numéro.

Face à la question de savoir si le signal V1 reste bon au-delà de J+20, un calcul ad hoc a été fait directement depuis `historical_data` (pas depuis `brvm_decisions_results`, qui ne couvre que J+20/21/30/43 par construction du script existant), pour tous les signaux ACHAT ayant atteint chaque horizon en âge à la date du calcul.

### Méthode

- Source des signaux : `brvm_decisions` filtré sur `signal = 'ACHAT'` (1305 signaux au total, depuis le 03/04/2026)
- Prix : `historical_data`, recherche du prix le plus proche (fenêtre ±7 jours) à la date du signal et à `date_signal + horizon`
- "Correct" = variation de prix strictement positive (`variation_pct > 0`) entre la date du signal et la date cible
- Un signal n'est inclus dans un horizon que si son âge réel (aujourd'hui − date du signal) est ≥ à cet horizon

### Résultats

| Horizon | n | Hit rate | Médiane | Moyenne |
|---|---|---|---|---|
| J+20 (vérifié par `verify_decisions.py`, table `brvm_decisions_results`) | 843 | 65.6% | +3.6% | +5.6% |
| J+30 (calcul ad hoc) | 768 | 68.2% | +5.4% | +7.3% |
| J+45 (calcul ad hoc) | 484 | 69.2% | +8.7% | +11.9% |
| J+60 (calcul ad hoc) | 306 | 66.0% | +6.2% | +12.7% |
| J+90 (calcul ad hoc) | 132 | **81.8%** | **+11.4%** | **+24.0%** |

Pour référence, sur les mêmes 2712 lignes de `brvm_decisions_results` (majoritairement J+20/21/30/43), la ventilation par type de signal :

| Signal | n | % correct | Médiane var% | Moyenne var% |
|---|---|---|---|---|
| ACHAT | 843 | 65.6% | +3.6% | +5.6% |
| SURVEILLER | 1608 | 49.0% | +2.2% | +3.6% |
| EVITER | 261 | 46.0% | +3.0% | +2.7% |

### Lecture

Le signal ACHAT montre un hit rate croissant avec l'horizon (65.6% à J+20 → 81.8% à J+90), avec une médiane et une moyenne également croissantes. C'est le résultat le plus solide obtenu à ce jour sur l'ensemble des vérifications de performance menées sur le projet (T6 sur V2 cours cible : IC95% incluant 0 sur n=25 ; dividend capture : pas de source committée, cf. T5c) :
- Échantillon nettement plus large (843 à 132 selon l'horizon, contre 25-26 pour V2/dividend capture)
- Progression cohérente avec l'horizon, pas un point isolé

**Réserve méthodologique :** l'échantillon à J+90 (n=132) ne couvre que les signaux les plus anciens (avril-mai 2026) — une fenêtre calendaire plus étroite que J+20 (avril-juillet). Si le marché BRVM a connu une tendance haussière particulièrement marquée sur cette période spécifique, une partie du hit rate élevé à J+90 pourrait refléter ce momentum général plutôt que la seule qualité du signal — le même biais de confusion identifié aujourd'hui pour le groupe BOA et SNTS (mouvements de marché communs indépendants du signal testé). Aucun contrôle pour ce facteur n'a été fait dans ce calcul ad hoc.

**Ce calcul est ad hoc et non committé comme script de production.** Si ces résultats doivent être présentés formellement (ex. à des clients potentiels), une tâche dédiée devrait committer ce script dans `tools/`, avec la même rigueur que T6 (bootstrap, walk-forward, contrôle du facteur de tendance de marché générale sur la période).
[coller le contenu ci-dessous]
