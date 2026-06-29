# Architecture — BRVM Analytics

## Vue d'ensemble

BRVM Analytics est une plateforme B2B SaaS d'analyse quantitative de la BRVM
(Bourse Régionale des Valeurs Mobilières), couvrant 47 tickers sur 8 pays UEMOA.

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Vercel)                       │
│              brvm-analytics.vercel.app                      │
│         React 18 + Vite 3.2.7 — App.jsx (~3500 lignes)     │
│                                                             │
│  src/components/ (découvert 23/06/2026, ADR-017) :          │
│  • BOAComparison.jsx                                        │
│  • Opportunities.jsx                                        │
│  • FinancialAnalysis.jsx — lit target_prices (corrigé      │
│    25/06/2026, ADR-017) — sensible à un eps source faux     │
│    pour certains tickers tant qu'ADR-018 n'est pas résolu   │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API (Supabase)
┌──────────────────────▼──────────────────────────────────────┐
│                   SUPABASE (PostgreSQL)                     │
│              lynevvhmstpcffobwudr.supabase.co               │
│                                                             │
│  Tables principales:                                        │
│  • companies          — 47 tickers BRVM                     │
│  • historical_data    — 92 714+ lignes de prix              │
│  • brvm_decisions     — signaux ACHAT/SURVEILLER/EVITER (V1)│
│  • brvm_decisions_results — vérifications live (dès 07/26)  │
│  • fundamental_analysis   — analyses Mistral (1 ligne par   │
│    rapport, UNIQUE report_url — historisé, ADR-019)         │
│  • technical_indicators   — RSI, MACD, SMA calculés         │
│  • target_prices      — cours cible V2 + decote (calculé)   │
│  • sector_per_history — P/E sectoriel BRVM, saisie mensuelle│
└──────────────────────▲──────────────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────────────┐
│                PIPELINE (GitHub Actions)                    │
│              brvm-analysis-suite (Python 3.11)              │
│                    Tourne chaque jour                       │
│                                                             │
│  ÉTAPE 0  update_index.py          — indices BRVM           │
│  ÉTAPE 1  data_collector_simple.py — scrape brvm.org (7sec) │
│  ÉTAPE 1b test_pipeline.py         — 12 tests qualité       │
│  ÉTAPE 2  technical_analyzer_simple.py — RSI, MACD, SMA     │
│  ÉTAPE 3  opportunity_scorer_simple.py — scores 0-100       │
│  ÉTAPE 3b generate_decisions.py    — signaux V1 + régime    │
│           (GELÉ jusqu'au 01/07/2026 — ADR-001)              │
│  ÉTAPE 3c verify_decisions.py      — vérif. 90j (dès 07/26) │
│  ÉTAPE 3d test_pipeline.py         — tests post-décisions   │
│  ÉTAPE 4  prediction_analyzer.py   — modèles ML (désactivé) │
│  ÉTAPE 5  fundamental_analyzer.py  — Mistral AI (bi-hebdo   │
│           1er et 15 — ADR-021) — analyses historisées       │
│           (1 ligne/rapport, UNIQUE report_url)              │
│  ÉTAPE 6  report_generator.py      — rapports (bi-hebdo,    │
│           1er et 15 — ADR-021)                              │
│  ÉTAPE 7  news_collector.py        — news + scoring IA      │
│                                                             │
│  calculate_target_price.py — cours cible V2 (indépendant   │
│  du gel ADR-001, calibré jusqu'au go-live du 01/07/2026)    │
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

## Modèle de scoring V1

### Facteurs actuels (4 facteurs, gel jusqu'au 01/07/2026 — ADR-001)

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

## Modèle de cours cible V2 (go-live 01/07/2026)

```
Cours cible = EPS moyen (jusqu'à 3 ans, filtre data-quality — ADR-011) × PER sectoriel (70%)
              + dividende / 8% (30%)
```

**PER sectoriel :** lu dynamiquement depuis `sector_per_history` (7 secteurs officiels
BRVM, ADR-010), jamais hardcodé. Alimentation manuelle mensuelle via `update_sector_per.py`.

**Filtre data-quality EPS (ADR-011) :** remplace toute liste d'exclusion statique.
Vérifie la consécutivité des années EPS disponibles (si 2+) et détecte un collapse
EPS >80% YoY. Avec 1 seule année EPS, le ticker est accepté sans contrôle (compromis
assumé pour ne pas exclure des tickers à forte capitalisation par manque d'historique).

**Taux d'actualisation 8% :** maintenu sans modification (ADR-009), origine non
traçable mais pas de méthode de remplacement fiable identifiée.

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
    ├── generate_decisions.py (V1, gelé — ADR-001)
    │       └── ACHAT/SURVEILLER/EVITER + market_regime
    │               └── brvm_decisions (Supabase)
    │                       │
    │                       └── verify_decisions.py (J+90)
    │                               └── brvm_decisions_results
    │
    └── calculate_target_price.py (V2, calibrable jusqu'au 01/07/2026)
            │
            ├── lit sector_per_history (P/E sectoriel, màj mensuelle manuelle)
            ├── applique evaluer_qualite_eps() sur company_fundamentals
            │       (filtre consécutivité + collapse, ADR-011)
            │
            └── ACHAT/NEUTRE/VENTE + decote_pct + per_source (traçabilité)
                    └── target_prices (Supabase)
```

---

## Contraintes connues

| Contrainte | Impact | Statut |
|---|---|---|
| Node v16.20.2 (macOS Catalina) | Impossible de upgrader | Contourné |
| Python 3.14 local incompatible TF 2.15 | Modèles ML non testés | Backlog TECH-02 |
| App.jsx monolithique (~3500 lignes) | Maintenance difficile | Dette technique |
| Données historiques pré-split non ajustées | Backtest BOA non fiable | Backlog DATA-05/06 |
| Variation journalière sur données non consécutives | Top Gainers parfois incorrect | Backlog DATA-07 |
| Parsing automatique du Tableau de Bord BOA non branché | Saisie PER sectoriel manuelle, pas automatique | Backlog (cf. ADR-010) — document source en lien email, pas en pièce jointe |
| Tickers à 1 seule année EPS acceptés sans contrôle qualité | Risque d'EPS atypique non représentatif dans le cours cible V2 | Risque assumé (ADR-011), à surveiller après le 01/07/2026 |
| `shares_outstanding` non fiable depuis stockanalysis.com pour certains tickers | EPS gonflé d'un facteur erroné (cas NTLC : ×20), cours cible V2 aberrant | NTLC : `shares_outstanding` corrigé (ADR-012), mais `eps` lui-même pas recalculé par le scraper — cf. ligne suivante |
| `eps` scrapé sans recalcul depuis `net_income`/`shares_outstanding` (ADR-018) | Toute correction manuelle de `shares_outstanding` seule est écrasée silencieusement par le scraping hebdomadaire suivant si `eps` n'est pas aussi corrigé en base | Détection ajoutée (`check_eps_coherence`, log uniquement) ; NTLC/BICC/SOGC confirmés incohérents au 25/06/2026, correction des données en attente (après run du 29/06/2026) |
| Doublon de calcul Fair Value : `FinancialAnalysis.jsx` recalculait en JS, indépendamment de `target_prices` | Aberrations possibles non filtrées | **Corrigé 25/06/2026 (ADR-017)** — lit désormais `target_prices`, comme `App.jsx` |
| Contrainte SQL parasite `UNIQUE(company_id)` sur `fundamental_analysis` | Analyse Mistral bloquée sur 1 rapport/société ; nouveaux rapports échouaient à la sauvegarde après analyse (travail payant perdu) | **Corrigé 28/06/2026 (ADR-019)** — contrainte supprimée, retour à `UNIQUE(report_url)` |
| Prompts Mistral avec P/E 10x hardcodé (objectif de cours calculé par l'IA) | Valorisation IA divergente du modèle V2 | **Corrigé 28/06/2026 (ADR-020)** — objectif de cours retiré des prompts, source unique = modèle V2 |
| Quota API Mistral (plan Free) épuisé avant fin de mois | Pipeline retombe sur fallback DeepSeek/Gemini, voire fallback_text | **Atténué 28/06/2026 (ADR-021)** — retrait UPSERT + étapes 5/6 bi-hebdo. Reset mensuel le 30 |

---

## Sécurité

- RLS (Row Level Security) activé sur toutes les tables Supabase
- `brvm_data` : lecture publique
- `brvm_decisions` : lecture publique + écriture service_role
- `sector_per_history` : lecture publique, contrainte CHECK sur les 7 secteurs officiels
- `target_prices` : lecture publique, colonne `per_source` avec CHECK (sector_per_history|fallback)
- `user_actions` : lecture/écriture scopée par utilisateur
- Clés API dans GitHub Secrets (jamais dans le code)
