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
