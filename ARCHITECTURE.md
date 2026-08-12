# Architecture — BRVM Analytics

> Dernière refonte : 12/08/2026. La version précédente (28/07/2026) documentait
> 9 scripts sur les 19 réellement appelés par `brvm-analysis.yml`, citait deux
> tables inexistantes et décrivait des horizons de vérification obsolètes.
> **Ce document doit être mis à jour à chaque ajout d'étape au pipeline** — son
> obsolescence est le mécanisme qui produit les écrivains concurrents (ADR-041,
> ADR-049, trois mappings sectoriels désynchronisés).

---

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Vercel)                        │
│              brvm-analytics — React 18 + Vite 3.2.7         │
│                     App.jsx (~4600 lignes)                  │
└──────────────────────▲──────────────────────────────────────┘
                       │ REST API (VITE_SUPABASE_ANON_KEY)
┌──────────────────────┴──────────────────────────────────────┐
│                  SUPABASE (PostgreSQL)                      │
│              projet lynevvhmstpcffobwudr                    │
│                    34 tables et vues                        │
└──────────────────────▲──────────────────────────────────────┘
                       │ REST API (SUPABASE_SERVICE_ROLE_KEY)
┌──────────────────────┴──────────────────────────────────────┐
│              PIPELINE (GitHub Actions)                      │
│      brvm-analysis.yml — cron 06:00 UTC, quotidien          │
│              Python 3.11, timeout 180 min                   │
└─────────────────────────────────────────────────────────────┘
```

**Conséquence du cron à 06:00 UTC :** le pipeline ne peut ingérer que la séance
de la veille. Toutes les données affichées sont à J-1 — la home l'assume avec un
horodatage unique (ADR-045).

---

## Repos

| Repo | Rôle | Déploiement |
|---|---|---|
| `brvm-analysis-suite` | Pipeline Python | GitHub Actions |
| `brvm-analytics` | Frontend React | Vercel |

Branche active : `remediation-2026-07`. Cherry-pick vers `main` pour la prod,
jamais de commit direct sur `main`.

---

## Étapes du pipeline

Ordre réel d'exécution dans `brvm-analysis.yml`.

| Étape | Script | Fréquence | Écrit dans |
|---|---|---|---|
| 0 | `update_index.py` | quotidien | `companies` |
| 1 | `data_collector_simple.py` | quotidien | `companies`, `historical_data` |
| 1 | `scrape_boc_pdf.py` | quotidien | `company_fundamentals` |
| 1 | `scrape_indices.py` | quotidien | `companies`, `historical_data` |
| 1 | `scrape_commodities.py` | quotidien | `commodity_prices` |
| 1b | `test_pipeline.py` | lundi | — |
| 1c | `scrape_corporate_events.py` | lundi | `companies`, `corporate_events` |
| 1f | `calculate_target_price.py` | quotidien | `target_prices` |
| 1g | Fair Value V3 | quotidien | `target_prices_v3` |
| 2 | `technical_analyzer_simple.py` | quotidien | `technical_analysis` |
| 3 | `opportunity_scorer_simple.py` | quotidien | `opportunities` |
| 3b | `generate_decisions.py` | quotidien | `brvm_decisions` |
| 3c | `verify_decisions.py` | quotidien | `brvm_decisions_results` |
| 3e | `verify_predictions.py` | quotidien | `predictions_results` |
| 3d | `test_pipeline.py` | quotidien | — |
| 4 | Prédictions GRU | quotidien | `predictions` |
| 5 | `fundamental_analyzer.py` | 1er et 15 | `fundamental_analysis`, `company_fundamentals`, `company_management` |
| 6 | `report_generator.py` | 1er et 15 | fichiers .docx |
| 7 | `news_collector.py` | quotidien | `news_events` |
| V2 | `signaux_actifs.py` | lundi | — (lecture seule) |
| V2b | `scrape_market_cap.py` | 1er lundi du mois | `company_fundamentals` |
| — | `health_check.py` | quotidien | — |

**Workflows séparés :** `parse_boa_letter.yml` (bulletins BOA, cron 18:00 UTC),
`tests.yml`.

**Non branché :** `tools/ingest_boc.py` — fonctionnel, historique backfillé
jusqu'au 11/08/2026, mais aucune exécution automatique (backlog).

**Débranchés / orphelins :** `data_collector.py` (ADR-048),
`extract_fundamental_signals.py`, `prediction_analyzer.py`.

**À débrancher :** étapes 3e et 4 (GRU) — ADR-044, après retrait de l'onglet
Prévisions du frontend.

---

## Écrivains multiples — points de vigilance

Plusieurs scripts écrivent dans la même table. C'est la principale source
d'incohérences du projet.

### `company_fundamentals`

| Script | Écrit | Risque |
|---|---|---|
| `scrape_boc_pdf.py` | `pe_ratio`, `dividend_yield`, `dividend_per_share` (**net**), `ex_dividend_date` | ADR-049 |
| `scrape_market_cap.py` | `market_cap`, `shares_outstanding` | `scraped_at` figé au 27/05/2026 |
| `fundamental_analyzer.py` | champs d'analyse IA | psycopg2 direct (viole ADR-004) |
| autre écrivain | `dividend_per_share` (**brut**) | ADR-041 / ADR-049 |

**`dividend_per_share` contient du brut ou du net selon l'ordre d'exécution**, ligne
à ligne. Toute lecture de cette colonne est suspecte tant qu'ADR-049 n'est pas traité.

### Indices BRVM — quatre sources

`update_index.py`, `scrape_indices.py`, `data_collector.py` (débranché) et
`tools/ingest_boc.py` touchent tous aux valeurs d'indices, sur des tables
différentes. `boc_indices` est la seule alimentée depuis la source officielle
(Bulletin Officiel de la Cote) avec contrôles de cohérence.

### Mappings sectoriels — trois référentiels

| Source | Contenu |
|---|---|
| `calculate_target_price.py` `SECTEUR_OFFICIEL` | 7 catégories BRVM — **référence production** |
| `backtest_value.py` | 5 catégories maison |
| `companies.sector` | libellés français simplifiés |

`boc_indices` apporte un quatrième référentiel, celui de la BRVM elle-même
(7 secteurs, base 02/01/2025).

---

## Modèles

### V1 — signal composite prix/volume
`RSI×0.20 + tendance×0.40 + volume×0.25 + volatilité×0.15` → ACHAT / SURVEILLER / ÉVITER.

**Seul modèle empiriquement validé** : n=843, 65.6 % à J+20 → 81.8 % à J+90
(commit `8ef56ad`). Vérification quotidienne à J+20 (ADR-019 ; ADR-038 documente
la logique J+90 d'origine).

### V2 — cours cible
PER sectoriel × EPS + DDM. **Statistiquement non prouvé** : IC95 % bootstrap
[-1.6 %, +14.3 %], n=25. Échec de la falsification T9 (ne se différencie pas d'une
stratégie dividende naïve). T14 : 68 % des signaux concentrés sur
SERVICES_FINANCIERS. **Gelé** (phase 13).

### V3 — DDM/PE à pondération progressive
`target_prices_v3`, 34 tickers, commit `334481b`. Coexiste avec V2 sans écrasement.
7 signaux ACHAT. **Backtest de validation en attente** — pas d'affichage en home
avant validation.

### GRU / Prévisions
**Fermé définitivement** — ADR-044. MASE 1.888 (erreur ~1.9× la persistance naïve),
direction 47.9 % (sous le hasard), audit `95290c1`.

---

## Sources de données

| Source | Script | Contenu |
|---|---|---|
| brvm.org (HTML) | `data_collector_simple.py` | cours quotidiens |
| BOC PDF pages 3-4 | `scrape_boc_pdf.py` | PER, dividende net, rendement par ticker |
| BOC PDF page 1 | `tools/ingest_boc.py` | indices, agrégats, breadth, PER sectoriels |
| Yahoo Finance | `scrape_commodities.py`, `tools/backfill_commodities.py` | cacao, coton, or, brut, USD/XOF |
| BOA Capital | `parse_boa_letter.py` | bulletins hebdomadaires |
| stockanalysis.com | `scrape_market_cap.py` | capitalisation, actions en circulation |

**BOC** — `https://www.brvm.org/sites/default/files/boc_AAAAMMJJ_2.pdf`. Pattern
déterministe vérifié sur 13 dates (2023→2026), sans expiration. 404 = jour non
ouvré (ADR-046). Rupture de taxonomie au 02/01/2026 : le parser refuse les
bulletins antérieurs.

**Commodités** — 11 ans d'historique (2015-08 → 2026-08), ~2750 points par série.
`usdxof` est dérivé d'EUR/USD via la parité fixe 655.957, pas du ticker `XOFUSD=X`.
`crude` contient -37.63 au 2020-04-20 (WTI négatif) : donnée réelle, point de
levier extrême.

---

## Contraintes d'architecture (non négociables)

| Règle | ADR |
|---|---|
| Supabase via REST API uniquement, jamais psycopg2 | ADR-004 |
| Corrections de masse par SQL Editor uniquement | ADR-026 |
| `App.jsx` modifié par scripts de patch Python | ADR-002 |
| Pas de react-markdown ; Vite figé en 3.2.7 ; Node en v16.20.2 | — |
| `load_dotenv(find_dotenv(usecwd=True))`, module `logging`, pas d'`except` silencieux | — |
| `python3` explicite (le `python` du Mac mini est en Python 2) | — |

**Violations connues d'ADR-004 :** `fundamental_analyzer.py`, `report_generator.py`
(psycopg2 direct) — arbitrage en attente : migrer ou accorder une dérogation.

---

## Schéma — pièges connus

| Table / colonne | Piège |
|---|---|
| `companies.symbol` | pas `ticker`, pas `name` |
| `historical_data` | `trade_date`, `price`, `company_id` — **pas de colonne ticker**, résolution en deux temps via `companies` |
| `historical_data.value` | **colonne morte** — 14.9 % de couverture, plus alimentée. Le montant échangé se calcule `price × volume` |
| `company_fundamentals` | colonne de date = `scraped_at`, **il n'y a pas d'`updated_at`** |
| `company_fundamentals.dividend_per_share` | brut **ou** net selon l'ordre d'exécution — ADR-049 |
| `corporate_events` | `EX_DIVIDEND` (date précise, montant toujours NULL) et `DIVIDEND_HISTORY` (montants présents, `event_date` = clôture d'exercice) — jointure par `fiscal_year` |
| `DIVIDEND_HISTORY.fiscal_year` | décalé d'un an (ADR-040) — affecte 77/89 cycles exploitables |
| `brvm_decisions_results.benchmark_return` | moyenne de cohorte quotidienne issue de `verify_decisions.py`, **pas l'indice BRVM Composite** |
| `v_latest_market_data` | nom trompeur — contient `predicted_price` (prédictions) |
| `monthly_volume_avg` | moyenne **saisonnière par mois calendaire**, pas une moyenne glissante 20j |
| `new_market_indicators` | 6 colonnes ; le `INSERT` de `data_collector.py` en référence deux qui n'existent pas |
| `boc_indices` | `BRVM_PRESTIGE` (PHARE) et `BRVM-PRESTIGE` (COMPARTIMENT) sont le même indice — filtrer par `type_indice` |

---

## Contraintes connues

| Contrainte | Impact | Statut |
|---|---|---|
| Node v16.20.2 (macOS Catalina) | Mise à jour impossible | Contourné |
| Claude Code incompatible Catalina | — | GitHub Codespaces pour les tâches Classe A |
| `App.jsx` monolithique (~4600 lignes) | Maintenance difficile | Dette technique |
| Données pré-split non ajustées | Backtest BOA non fiable | Backlog DATA-05/06 |
| `shares_outstanding` non fiable post-split (stockanalysis.com) | EPS erroné, cours cible V2 aberrant | ADR-012, ADR-018 |
| `scrape_market_cap.py` — `scraped_at` figé au 27/05/2026 | `market_cap` périmé | **Incident non résolu** |
| `report_generator.py` ordonne par `id`, pas par date | Variations fausses après tout backfill | ADR-048, à corriger **avant** backfill |
| `requirements.txt` ne déclare pas `pdfminer.six` | `parse_boa_letter.py` ne devrait pas tourner en CI | Piste sur son arrêt du 30/04/2026 |
| Exclusion SNTS documentée dans SKILL.md | Jamais implémentée en code | Backlog |

---

## Sécurité

Clés en variables d'environnement (`.env` local, secrets GitHub Actions).
`SUPABASE_SERVICE_ROLE_KEY` au format `sb_secret_...` depuis la migration du
27/07/2026 (ADR-042), utilisée à la fois comme en-tête `apikey` et
`Authorization: Bearer`. Migration de `VITE_SUPABASE_ANON_KEY` vers
`sb_publishable_...` toujours en attente côté Vercel.

PAT `BRVM_5` : scopes `repo` + `workflow`. Surveiller l'expiration.
