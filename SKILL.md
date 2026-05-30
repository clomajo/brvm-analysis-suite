---
name: brvm-analytics
description: >
  Contexte de développement de BRVM Analytics — plateforme d'analyse quantitative
  de la BRVM (Bourse Régionale des Valeurs Mobilières). Utiliser ce skill dès qu'une
  tâche concerne le frontend React (App.jsx, composants), le pipeline Python
  (brvm-analysis-suite), Supabase, GitHub Actions, les scripts de scoring/décisions,
  les modèles GRU, les analyses Mistral, ou tout déploiement Vercel lié à ce projet.
  Déclencher aussi pour toute question sur l'architecture, les contraintes techniques,
  les règles métier, ou les procédures opérationnelles de BRVM Analytics.
---

# BRVM Analytics — Skill de développement

## Repos

| Repo | Rôle | URL |
|---|---|---|
| `clomajo/brvm-analytics` | Frontend React → Vercel | github.com/clomajo/brvm-analytics |
| `clomajo/brvm-analysis-suite` | Pipeline Python → GitHub Actions | github.com/clomajo/brvm-analysis-suite |

---

## Stack technique

| Composant | Technologie | Version / détail |
|---|---|---|
| Frontend | React + Vite | 18 + **3.2.7** (ne pas upgrader) |
| Base de données | Supabase PostgreSQL | Project ID: `lynevvhmstpcffobwudr` |
| Pipeline CI/CD | GitHub Actions | Python **3.11** |
| Hébergement | Vercel | Auto-deploy sur push |
| AI Fondamentaux | Mistral AI | `mistral-large-latest` |
| AI Extraction | Claude API | `claude-sonnet-4` |
| Env local | macOS Catalina, Node **v16.20.2** | Python 3.8/3.14 local |
| .env pipeline | `~/Desktop/brvm-analysis-suite/.env` | SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, MISTRAL_API_KEY |

---

## Contraintes critiques — lire avant tout changement

### Frontend (brvm-analytics)
- **Ne jamais télécharger App.jsx directement** — toujours modifier via scripts Python patch en terminal
- **App.jsx est monolithique (~3500 lignes)** — tout le frontend est dans un seul fichier (ADR-002)
- **Ne pas installer react-markdown** — cause des erreurs Vite 3 — FERMÉ définitivement (ADR-031)
- **Node v16.20.2 sur macOS Catalina** — impossible d'upgrader, imports complexes instables
- **Vite 3.2.7** — contraintes esbuild spécifiques, ne pas supposer comportement Vite 4/5
- **Warning chunk >500 KiB** — normal, dû à l'App.jsx monolithique, non bloquant

### Pipeline (brvm-analysis-suite)
- **Toujours utiliser Supabase REST API** — psycopg2 échoue en GitHub Actions (ADR-004)
- **Ne pas modifier `generate_decisions.py`** avant le 01/07/2026 — modèle gelé (ADR-001)
- **Features Mistral statiques** → ne pas intégrer dans les modèles GRU (ADR-015, testé et rejeté)
- **GRU fiable J+1/J+2 uniquement** — afficher J+5+ comme indicatif seulement (ADR-014)
- **load_dotenv() dans heredoc** → utiliser `load_dotenv(find_dotenv(usecwd=True))` sinon AssertionError
- **Corrections de masse** → SQL Editor Supabase uniquement, jamais PATCH REST ligne par ligne (ADR-026)

### Workflow de déploiement frontend
```bash
cd ~/Desktop/brvm-analytics
npm run build
git add src/App.jsx
git commit -m "fix: description"
git push
# Vérifier sur brvm-analytics.vercel.app — hard refresh (Cmd+Shift+R)
```

---

## Thème UI

| Token | Valeur |
|---|---|
| Fond global | `#F8F9FA` |
| Cards | `#FFFFFF` |
| Accent principal | `#2B6CB0` |
| Texte principal | `#1A202C` |
| Texte secondaire | `#1A202C` (contraste corrigé — ne pas utiliser #7d8590) |
| Warning / estimé | `#d2a94d` |
| Fair Value line | `#E07B39` (LightweightCharts, lineStyle=2) |

---

## Architecture UI (état au 30/05/2026 — ADR-013)

**Navbar globale :** `[Recherche ticker]` · Marché · Opportunités · Portefeuille · Obligations
**Page par défaut :** Marché
**Fiche ticker :** Aperçu · Prévisions · Backtest
**Tabs archivés (masqués, code non supprimé) :**
BOA vs BRVM · Risque · Législatif · Direction · Macro · Matières 1ères · Scorecard détaillé

---

## Tables Supabase principales

| Table | Contenu | Accès |
|---|---|---|
| `companies` | 47 tickers — colonne `symbol` (pas `ticker`) | lecture publique |
| `historical_data` | 110,594+ lignes — company_id, trade_date, price, volume | lecture publique |
| `brvm_decisions` | Signaux — colonnes : ticker, date, score, signal, market_regime, liquidity_tier, confidence | lecture publique |
| `target_prices` | Cours cible V2 quotidien — ticker, cours_cible, decote_pct, signal_v2, calcul_date | lecture publique |
| `fundamental_analysis` | Analyses Mistral FY2025 — 45 lignes, UNIQUE company_id | lecture publique |
| `company_fundamentals` | PER, ROE, EPS, market_cap, dividend_yield, shares_outstanding | lecture publique |
| `corporate_events` | Dividendes + AG — ticker, event_type, event_date | lecture publique |
| `commodity_prices` | Cocoa, coton, or, pétrole, USD/XOF (Palm Oil + Rubber retirés) | lecture publique |
| `brvm_decisions_results` | Vérifications J+20 (dès 07/2026) | — |
| `boa_recommendations` | 547 lignes, 17 semaines déc 2025–avr 2026 | — |
| `user_actions` | Moat data | lecture/écriture user + service_role full |

### Colonnes réelles confirmées (pièges courants)
- `brvm_decisions` : signal_date → **`date`** · decision → **`signal`** · regime → **`market_regime`**
- `companies` : **`symbol`** (pas ticker) · `id` pour jointure avec historical_data
- `historical_data` : **`trade_date`** (pas date) · **`price`** (pas close_price) · pas de colonne ticker
- `company_fundamentals` : filtre `roe=not.is.null` pour obtenir FY2025 (FY2026 = vide)
- `fundamental_analysis` : `updated_at` = date réelle analyse · `report_date` = fin exercice fiscal
- `boa_recommendations` : colonnes `action` (BUY/SELL/HOLD/REDUCE) · `cours_act` · `cours_pot` · `rendement` · `potential`
- `brvm_decisions` : score_technique/fondamental/liquidite/tendance → **NULL en V1** (score composite seulement)

### fundamental_analysis — contrainte UNIQUE
- `UNIQUE (company_id)` ajoutée le 30/05/2026
- 45 lignes, 45 company_id distincts (doublons supprimés)
- Requête frontend : `order=updated_at.desc&limit=1` (redondant mais conservé)

**Vues SQL utiles :**
- `v_ytd_performance` — YTD par ticker vs BRVMC
- `v_historical_prices` — historical_data JOIN companies (expose colonne ticker)

---

## Modèle de scoring V1 (gelé jusqu'au 01/07/2026)

```
Score composite (0-100) =
  Technique (RSI, MACD, SMA)     ~40%
  Fondamental (narratif Mistral) ~25%
  Liquidité (tier: prestige/liquid/illiquid) ~20%
  Tendance (momentum)            ~15%
```

**Seuils :** ACHAT >= 65 (BULL uniquement) · SURVEILLER 30-64 · EVITER < 30
**Performance :** Alpha +1.82% global · +1.02% BULL · -0.72% BEAR
**Verdict :** Signal technique = bruit structurel (AUC 0.51, 22 992 signaux) — ADR-016

---

## Modèle V2 (parallèle silencieux — bascule 01/07/2026)

```
Signal V2 = ACHAT si :
  cours_actuel < cours_cible × (1 - seuil)
  ET ROE > 15% ET P/B < 2.5
  ET cap 150-500B FCFA
  ET volume_20j > seuil_liquidite (à calibrer)
  ET J-10 avant ex_dividend_date (signal optimal)
```

**Cours cible :** EPS moyen 3 ans × PER sectoriel (70%) + dividende / 8% (30%)
**Table :** `target_prices` — upsert quotidien via calculate_target_price.py
**Performance backtest :** 25 signaux, médiane J+90 +7.8%, alpha +2.8%, 68% positifs
**Tickers exclus V2 :** NTLC, SNTS, BOAN, BNBC, SICC, UNLC, ETIT, FTSC, CFAC, SIVC (EPS non représentatif)
**Watchlist :** SOGC, SPHC, BOAS, BOABF, ONTBF, TTLC, BOAC

**PER sectoriels :**
- Banque : 12.4x · Agro : 10.2x · Industrie : 13.2x · Telecom : 13.3x · Distribution : 16.1x

---

## Session 30/05/2026 — Résumé des changements

### Pipeline (brvm-analysis-suite)
- V2-06 : Palm Oil + Rubber retirés de scrape_commodities.py (efde604)
- requirements.txt nettoyé — doublons supprimés (9212b00)
- fix_snts_updates.sql archivé dans sql/ (73474e9)
- scrape_market_cap.py automatisé 1er lundi/mois GitHub Actions (7a069ae)
- calculate_target_price.py : EPS moyenne 3 ans + upsert target_prices (b939b53, dc52769)
- verify_decisions.py : VERIFICATION_WINDOW 90 → 20 jours (07f46c6)

### Frontend (brvm-analytics)
- Tab BOA vs BRVM supprimé (25a92a0)
- Fondamentaux clés : FUND_DATA hardcodé → Supabase company_fundamentals (c6a03e8)
- Ligne Fair Value style Morningstar sur graphique (9c65c31)
- Badge Fair Value V2 🎯/📉 sur DecisionCards (965ef99)

### Supabase
- fundamental_analysis : 45 lignes (doublons supprimés) + UNIQUE (company_id)
- target_prices : table créée, RLS activé, lecture publique

---

## Règle opérationnelle — Fin de session

À la fin de chaque session de développement BRVM Analytics, mettre à jour simultanément :
1. SKILL.md — contraintes, ADR, bugs résolus, baselines
2. CHANGELOG.md — entrée datée avec FEAT/INFRA/PERF/FIX
3. BACKLOG.md — nouveaux items identifiés
4. DECISIONS.md — nouveaux ADR
5. ARCHITECTURE.md — changements structurels

Puis commit unique :
```bash
git add SKILL.md CHANGELOG.md BACKLOG.md DECISIONS.md ARCHITECTURE.md
git commit -m "docs: mise à jour documentation session JJ/MM/YYYY"
git push
```
