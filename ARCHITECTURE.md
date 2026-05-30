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
│  • companies              — 47 tickers BRVM                 │
│  • historical_data        — 110,594+ lignes de prix         │
│  • brvm_decisions         — signaux ACHAT/SURVEILLER/EVITER │
│  • brvm_decisions_results — vérifications J+20 (dès 07/26) │
│  • fundamental_analysis   — analyses Mistral (45 lignes,    │
│                             UNIQUE company_id)              │
│  • company_fundamentals   — PER/ROE/EPS/market_cap 5 ans   │
│  • target_prices          — cours cible V2 quotidien        │
│  • corporate_events       — dividendes + AG                 │
│  • commodity_prices       — cocoa/cotton/gold/crude/USDXOF  │
│  • technical_indicators   — RSI, MACD, SMA calculés         │
└──────────────────────▲──────────────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────────────┐
│                PIPELINE (GitHub Actions)                    │
│              brvm-analysis-suite (Python 3.11)              │
│                    Tourne chaque jour à 6h UTC              │
│                                                             │
│  ÉTAPE 0  update_index.py           — indices BRVM          │
│  ÉTAPE 1  data_collector_simple.py  — scrape brvm.org       │
│           scrape_boc_pdf.py         — BOC PDF PER/div       │
│           scrape_indices.py         — BRVMC + BRVM30        │
│           scrape_commodities.py     — Yahoo Finance (5 cmd) │
│  ÉTAPE 1b scrape_all_v4.py         — fondamentaux (lundi)  │
│  ÉTAPE 1c scrape_corporate_events.py— dividendes (lundi)   │
│  ÉTAPE 1f calculate_target_price.py — cours cible V2       │
│  ÉTAPE 2  technical_analyzer_simple.py — RSI, MACD, SMA    │
│  ÉTAPE 3  opportunity_scorer_simple.py — scores 0-100      │
│  ÉTAPE 3b generate_decisions.py    — signaux + régime      │
│  ÉTAPE 3c verify_decisions.py      — vérif. J+20           │
│  ÉTAPE 3d test_pipeline.py         — tests qualité         │
│  ÉTAPE 3e verify_predictions.py    — vérif. GRU vs réel    │
│  ÉTAPE 4  prediction_analyzer_v2.py— GRU 10 jours          │
│  ÉTAPE 5  fundamental_analyzer.py  — Mistral AI            │
│  ÉTAPE 6  report_generator.py      — rapports              │
│  ÉTAPE 7  news_collector.py        — news + scoring IA     │
│  ÉTAPE V2 signaux_actifs.py        — watchlist J-10 (lundi)│
│  ÉTAPE V2b scrape_market_cap.py    — market cap (1er lundi)│
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

### V1 — Facteurs actuels (gel jusqu'au 01/07/2026)

```
Score composite (0-100) =
  Technique (RSI, MACD, SMA)     ~40%
  Fondamental (narratif Mistral) ~25%
  Liquidité (tier: prestige/liquid/illiquid) ~20%
  Tendance (momentum)            ~15%
```

**Seuils signal (v1_officielle_20260401) :**
- ACHAT : score >= 65 (régime BULL uniquement)
- SURVEILLER : score 30-64
- EVITER : score < 30

**Performance documentée :**
- Alpha vs random toutes conditions : +1.82%
- Alpha en régime BULL : +1.02%
- Alpha en régime BEAR : -0.72% (ACHAT désactivé)
- Signal technique = bruit structurel (AUC 0.51 sur 10 ans) — ADR-016

### V2 — Modèle value + dividende + qualité (post-dégel 01/07/2026)

```
Signal V2 = ACHAT si :
  cours_actuel < cours_cible × (1 - seuil_decote)
  ET ROE > 15%
  ET P/B < 2.5
  ET cap 150-500B FCFA
  ET volume_20j > seuil_liquidite (à calibrer)
  ET J-10 avant ex_dividend_date (signal optimal)
```

**Cours cible :** EPS moyen 3 ans × PER sectoriel (70%) + dividende / 8% (30%)
**Performance backtest (FY2021-FY2024, 25 signaux) :**
- Médiane J+90 : +7.8%
- Alpha vs BRVMC : +2.8%
- Taux de succès : 68%
- Win/Loss ratio : 3.5x

**PER sectoriels empiriques :** Banque 12.4x · Agro 10.2x · Industrie 13.2x · Telecom 13.3x · Distribution 16.1x

---

## Table target_prices (créée 30/05/2026)

```sql
CREATE TABLE target_prices (
  id SERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  fiscal_year TEXT,
  secteur TEXT,
  eps NUMERIC,           -- moyenne 3 ans
  dividende NUMERIC,
  per_ref NUMERIC,
  cours_cible NUMERIC,
  prix_actuel NUMERIC,
  decote_pct NUMERIC,
  signal_v2 TEXT,        -- ACHAT / NEUTRE / VENTE
  methode TEXT,          -- PER70+Gordon30 / PER100 / Gordon100
  calcul_date DATE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT unique_ticker_date UNIQUE (ticker, calcul_date)
);
```

Alimentée quotidiennement par `calculate_target_price.py` (ÉTAPE 1f).
Lue par le frontend pour : ligne Fair Value sur graphique + badge décote sur DecisionCards.

---

## Frontend — Architecture UI (état au 30/05/2026)

**Navbar globale :** `[Recherche ticker]` · Marché · Opportunités · Portefeuille · Obligations
**Page par défaut :** Marché
**Fiche ticker :** Aperçu · Prévisions · Backtest

**Fonctionnalités actives :**
- Ligne Fair Value pointillée (#E07B39) sur graphique LightweightCharts (CHART-01)
- Badge décote V2 🎯/📉 sur chaque DecisionCard (UI-03)
- Fondamentaux clés depuis Supabase : pe_ratio, pb_ratio, market_cap, dividend_yield, shares_outstanding, roe (DATA-12)
- Badge détresse relative ⚠️ (YTD < BRVMC - 25pts)
- Badge dividende imminent 💰 (ex-date dans 60 jours)

**Tabs archivés (masqués, code conservé) :**
BOA vs BRVM · Risque · Législatif · Direction · Macro · Matières 1ères · Scorecard détaillé

---

## Tables Supabase — Colonnes réelles (pièges courants)

| Table | Colonne | Note |
|---|---|---|
| `brvm_decisions` | `date` | (pas signal_date) |
| `brvm_decisions` | `signal` | (pas decision) |
| `brvm_decisions` | `market_regime` | (pas regime) |
| `companies` | `symbol` | (pas ticker) |
| `historical_data` | `trade_date` | (pas date) |
| `historical_data` | `price` | (pas close_price) |
| `company_fundamentals` | `fiscal_year` | filtre roe=not.is.null pour FY2025 |
| `fundamental_analysis` | `updated_at` | date réelle analyse (pas report_date) |

**Vues SQL utiles :**
- `v_ytd_performance` — YTD par ticker vs BRVMC
- `v_historical_prices` — historical_data JOIN companies (expose ticker)

---

## Contraintes connues

| Contrainte | Impact | Statut |
|---|---|---|
| Node v16.20.2 (macOS Catalina) | Impossible d'upgrader | Contourné |
| App.jsx monolithique (~3500 lignes) | Maintenance difficile | Dette technique (ADR-002) |
| Vite 3.2.7 + esbuild | react-markdown incompatible | ADR-031 — parser inline maison |
| GRU fiable J+1/J+2 uniquement | J+5+ = indicatifs | ADR-014 |
| Features Mistral incompatibles GRU | Ne pas intégrer dans prédictions | ADR-015 |
| Signal technique = bruit (AUC 0.51) | Abandonner post-dégel | ADR-016 |
| EPS NTLC/SNTS non représentatif | Décotes aberrantes >200% | Filtrés par abs(decote_pct)<200 |
| 15 splits estimés (non confirmés BRVM) | Facteurs arrondis | Marqués ESTIMÉ dans fix_splits.py |
| ETIT HTTP 404 stockanalysis.com | Pas de market_cap | Exclu scrape_market_cap.py |

---

## Sécurité

- RLS activé sur toutes les tables Supabase
- `brvm_decisions` : lecture publique + écriture service_role
- `target_prices` : lecture publique + écriture service_role
- `fundamental_analysis` : lecture publique (UNIQUE company_id depuis 30/05)
- `user_actions` : lecture/écriture scopée par utilisateur
- Clés API dans GitHub Secrets (jamais dans le code)

---

## Scripts V2 opérationnels

| Script | Rôle | Fréquence |
|---|---|---|
| calculate_target_price.py | Cours cible PER+Gordon → target_prices | Quotidien (ÉTAPE 1f) |
| signaux_actifs.py | Watchlist J-10 ex_dividend_date | Lundi |
| scrape_market_cap.py | market_cap + shares_outstanding | 1er lundi du mois |
| backtest_value.py | Backtest décote vs performance | Analyse ponctuelle |
| backtest_dividend.py | Comportement cours autour ex-date | Analyse ponctuelle |
| fix_splits.py | Correction splits historiques | Manuel (dry run obligatoire) |

---

## Données historiques — État au 30/05/2026

- `historical_data` : 110,594 lignes
- Splits corrigés : 50 officiels + 15 estimés (fix_splits.py)
- SNTS : série cohérente 2016-2026 (fix_snts_updates.sql — archivé dans sql/)
- Backup : backup_historical_data.json (local, ne pas commiter)
- Commodités actives : cocoa, cotton, gold, crude, USD/XOF (Palm Oil + Rubber retirés)
