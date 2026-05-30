# Architecture — BRVM Analytics

## Vue d'ensemble

BRVM Analytics est une plateforme B2B SaaS d'analyse quantitative de la BRVM
(Bourse Régionale des Valeurs Mobilières), couvrant 47 tickers sur 8 pays UEMOA.

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Vercel)                       │
│              brvm-analytics.vercel.app                      │
│         React 18 + Vite 3.2.7 — App.jsx (~3500 lignes)     │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API (Supabase)
┌──────────────────────▼──────────────────────────────────────┐
│                   SUPABASE (PostgreSQL)                     │
│              lynevvhmstpcffobwudr.supabase.co               │
│                                                             │
│  Tables principales:                                        │
│  • companies          — 47 tickers BRVM                     │
│  • historical_data    — 92 714+ lignes de prix              │
│  • brvm_decisions     — signaux ACHAT/SURVEILLER/EVITER     │
│  • brvm_decisions_results — vérifications live (dès 07/26)  │
│  • fundamental_analysis   — analyses Mistral par ticker     │
│  • technical_indicators   — RSI, MACD, SMA calculés         │
└──────────────────────▲──────────────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────────────┐
│                PIPELINE (GitHub Actions)                    │
│              brvm-analysis-suite (Python 3.11)              │
│                    Tourne chaque jour                       │
│                                                             │
│  ÉTAPE 0  update_index.py          — indices BRVM           │
│  ÉTAPE 1  data_collector_simple.py — scrape brvm.org (7sec) │
│  ÉTAPE 1b scrape_boc_pdf.py        — BOC PDF PER/div/rdt_net │
│  ÉTAPE 1c scrape_indices.py        — indices BRVMC + BRVM30  │
│  ÉTAPE 1d scrape_commodities.py    — commodités Yahoo Finance │
│  ÉTAPE 1e test_pipeline.py         — 12 tests qualité        │
│  ÉTAPE 2  technical_analyzer_simple.py — RSI, MACD, SMA     │
│  ÉTAPE 3  opportunity_scorer_simple.py — scores 0-100       │
│  ÉTAPE 3b generate_decisions.py    — signaux + régime       │
│  ÉTAPE 3c verify_decisions.py      — vérif. J+20 (dès 07/26)│
│  ÉTAPE 3d test_pipeline.py         — tests post-décisions   │
│  ÉTAPE 4  prediction_analyzer.py   — modèles ML (désactivé) │
│  ÉTAPE 5  fundamental_analyzer.py  — Mistral AI             │
│  ÉTAPE 6  report_generator.py      — rapports multi-AI      │
│  ÉTAPE 7  news_collector.py        — news + scoring IA      │
└─────────────────────────────────────────────────────────────┘
```

---

## Repos

| Repo | Description | URL |
|---|---|---|
| `brvm-analytics` | Frontend React | github.com/clomajo/brvm-analytics |
| `brvm-analysis-suite` | Pipeline Python | github.com/clomajo/brvm-analysis-suite |

---

## Stack technique

| Composant | Technologie | Version |
|---|---|---|
| Frontend | React + Vite | 18 + 3.2.7 |
| Base de données | Supabase (PostgreSQL) | — |
| Pipeline CI/CD | GitHub Actions | Python 3.11 |
| Hébergement frontend | Vercel | — |
| AI Fondamentaux | Mistral AI | mistral-large-latest |
| AI Extraction | Claude API | claude-sonnet-4 |
| Scraping | BeautifulSoup + requests | — |
| Environnement local | macOS Catalina, Node v16.20.2 | Python 3.8/3.14 |

---

## Modèle de scoring

### Facteurs actuels (4 facteurs, gel jusqu'au 01/07/2026)

```
Score composite (0-100) =
  Technique (RSI, MACD, SMA)     ~40%
  Fondamental (narratif Mistral) ~25%
  Liquidité (tier: prestige/liquid/illiquid) ~20%
  Tendance (momentum)            ~15%
```

### Seuils de signal (v1_officielle_20260401)
- **ACHAT** : score >= 65 (en régime BULL uniquement)
- **SURVEILLER** : score 30-64
- **EVITER** : score < 30

### Régimes de marché
- **BULL** : signaux ACHAT activés
- **BEAR** : signaux ACHAT désactivés (alpha négatif documenté: -0.72%)

### Performance documentée (backtest officiel)
- Alpha vs random toutes conditions : **+1.82%**
- Alpha en régime BULL : **+1.02%**
- Alpha en régime BEAR : **-0.72%** (ACHAT désactivé)

---

## Flux de données

```
brvm.org/en/cours-actions/{0-6}
    │ scrape quotidien (BeautifulSoup)
    ▼
historical_data (Supabase)
    │
    ├── technical_analyzer_simple.py
    │       └── RSI(14), MACD(12/26/9), SMA(20/50)
    │               └── technical_indicators (Supabase)
    │
    ├── opportunity_scorer_simple.py
    │       └── score composite 0-100
    │               └── opportunity_scores (Supabase)
    │
    └── generate_decisions.py
            └── ACHAT/SURVEILLER/EVITER + market_regime
                    └── brvm_decisions (Supabase)
                            │
                            └── verify_decisions.py (J+20 — post dégel)
                                    └── brvm_decisions_results
```

---

## Contraintes connues

| Contrainte | Impact | Statut |
|---|---|---|
| Node v16.20.2 (macOS Catalina) | Impossible de upgrader | Contourné |
| Python 3.14 local incompatible TF 2.15 | Entraînement local impossible | Résolu via Google Colab T4 GPU |
| App.jsx monolithique (~3500 lignes) | Maintenance difficile | Dette technique |
| Données historiques pré-split non ajustées | Backtest BOA non fiable | Backlog DATA-05/06 |
| Variation journalière sur données non consécutives | Top Gainers parfois incorrect | Backlog DATA-07 |
| GRU fiable J+1/J+2 uniquement | Horizons J+5-J+10 = indicatifs | ADR-014 — 16/05/2026 |
| Features Mistral statiques incompatibles GRU | Ne pas intégrer dans prédictions prix | ADR-015 — 16/05/2026 |
| Signal technique = bruit (AUC 0.51/10 ans) | Abandonner score composite V1 post-dégel | ADR-016 — 25/05/2026 |
| Signal BOA cours cible = base V2 | cours_cible = dividende / rendement_cible | ADR-017 — 26/05/2026 |
| Liquidité = filtre binaire éliminatoire | +5 à +7% hit rate confirmé | ADR-018 — 25/05/2026 |
| Horizon vérification = J+20 | Remplace 90 jours post-dégel | ADR-019 — 26/05/2026 |

---

## Sécurité

- RLS (Row Level Security) activé sur toutes les tables Supabase
- `brvm_data` : lecture publique
- `brvm_decisions` : lecture publique + écriture service_role
- `user_actions` : lecture/écriture scopée par utilisateur
- Clés API dans GitHub Secrets (jamais dans le code)

## Mise à jour 27/05/2026 — Modèle V2

### Nouveaux scripts opérationnels
| Script | Rôle | Fréquence |
|---|---|---|
| signaux_actifs.py | Watchlist J-10 ex_dividend_date | Lundi (pipeline CI) |
| calculate_target_price.py | Cours cible PER sectoriel + Gordon | Manuel / à intégrer |
| backtest_value.py | Backtest décote vs performance | Analyse ponctuelle |
| backtest_dividend.py | Comportement cours autour ex-date | Analyse ponctuelle |

### Architecture signal V2
### Performance attendue V2 (backtest 2021-2026)
- Médiane J+90 : +15-20%
- Alpha vs BRVMC : +10-13%
- Taux de succès : 65-70%
- Fréquence : 6-8 signaux/an


## Correction splits historiques (29/05/2026)

### fix_splits.py
Script de correction des prix historiques BRVM.
- Localisation : ~/Desktop/brvm-analysis-suite/fix_splits.py
- Usage : python3 fix_splits.py (dry run) | python3 fix_splits.py --apply
- Logique : applique facteurs du plus récent au plus ancien
- Détection splits déjà appliqués : ratio_obs < 1.15 → ignoré
- 50 splits officiels + 15 estimés (marqués ESTIMÉ dans source)

### fix_snts_updates.sql
2,476 UPDATE statements pour corriger historical_data SNTS.
Source : 41_market-data_SONATEL.xlsx (cours réels 2016-2026).
À archiver dans le repo.

### Données historiques post-correction
- historical_data : 110,594 lignes (vs 92,714 avant — nouveaux tickers ajoutés)
- SNTS : série cohérente 2016-2026, prix en FCFA réels
- Tous splits 2017-2018 corrigés sauf 15 estimés

## Backtest V2 — Architecture finale (29/05/2026)

### backtest_value.py
Backtest stratégie value BRVM avec filtre cap+qualité.
- Filtre : cap 150-500B, ROE>15%, P/B<2.5, décote>15%
- Date signal : 30 avril (après publication résultats FY)
- Mesure : J+60 et J+90 depuis date signal
- Benchmark : BRVMC calculé sur mêmes périodes
- FILTRE_CAP_QUALITE = True (mettre False pour voir tous signaux)

### scrape_market_cap.py
Scraper stockanalysis.com pour market_cap et shares_outstanding.
- 45/46 tickers BRVM (ETIT exclu — HTTP 404)
- UPDATE company_fundamentals (toutes années fiscales)
- Délai 1.5s entre requêtes

### SCORECARD_V2.md
Document de référence stratégie V2 — 25 signaux, médiane +7.8%, alpha +2.8%.
