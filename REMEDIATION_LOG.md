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
