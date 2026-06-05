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

---

## Contraintes critiques — lire avant tout changement

### Frontend (brvm-analytics)
- **Ne jamais télécharger App.jsx directement** — toujours modifier via scripts Python patch en terminal
- **App.jsx est monolithique (~3500 lignes)** — tout le frontend est dans un seul fichier (ADR-002)
- **Ne pas installer react-markdown** — cause des erreurs Vite 3 (incompatibilité esbuild)
- **Node v16.20.2 sur macOS Catalina** — impossible d'upgrader, imports complexes instables
- **Vite 3.2.7** — contraintes esbuild spécifiques, ne pas supposer comportement Vite 4/5

### Pipeline (brvm-analysis-suite)
- **Toujours utiliser Supabase REST API** — psycopg2 échoue en GitHub Actions (ADR-004)
- **Ne pas modifier `generate_decisions.py`** avant le 01/07/2026 — modèle gelé (ADR-001)
- **Features Mistral statiques** → ne pas intégrer dans les modèles GRU (ADR-015, testé et rejeté)
- **GRU fiable J+1/J+2 uniquement** — afficher J+5+ comme indicatif seulement (ADR-014)

### Workflow de déploiement frontend
```bash
cd ~/Desktop/brvm-analytics
# 1. Modifier via script Python patch (jamais éditer App.jsx directement)
npm run build          # Vérifier que le build passe — obligatoire
git add src/App.jsx
git commit -m "fix: description"
git push               # Vercel déploie en ~60 secondes
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
| Texte secondaire | `#7d8590` → utiliser `#1A202C` (contraste corrigé) |

---

## Architecture UI (état au 11/05/2026 — ADR-013)

**Navbar globale :** `[Recherche ticker]` · Marché · Opportunités · Portefeuille · Obligations

**Page par défaut :** Marché

**Fiche ticker :** Aperçu · Prévisions · Backtest

**Tabs archivés (masqués, code non supprimé) :**
BOA vs BRVM · Risque · Législatif · Direction · Macro · Matières 1ères · Scorecard détaillé

---

## Tables Supabase principales

| Table | Contenu | Accès |
|---|---|---|
| `companies` | 47 tickers BRVM | lecture publique |
| `historical_data` | 92 714+ lignes de prix | lecture publique |
| `brvm_decisions` | Signaux ACHAT/SURVEILLER/EVITER | lecture publique + écriture service_role |
| `brvm_decisions_results` | Vérifications live (dès 07/2026) | — |
| `fundamental_analysis` | Analyses Mistral par ticker | — |
| `technical_indicators` | RSI, MACD, SMA calculés | — |
| `predictions` | Prévisions GRU (410 rows/run) | — |
| `predictions_results` | Tracking record GRU | — |
| `corporate_events` | AG, ex-dividendes, paiements | — |
| `commodity_prices` | Cocoa, coton, or, pétrole, USD/XOF | — |
| `company_fundamentals` | 5 ans FY2021–FY2025, 43 tickers | — |
| `user_actions` | Moat data — scopé par utilisateur | lecture/écriture user + service_role full |

**Vues SQL utiles :**
- `v_ytd_performance` — YTD par ticker vs BRVMC (filtre aberrations >±50%)
- `v_historical_prices` — historical_data JOIN companies (expose colonne ticker)

---

## Modèle de scoring (gelé jusqu'au 01/07/2026)

```
Score composite (0–100) :
  Technique (RSI, MACD, SMA)        ~40%
  Fondamental (narratif Mistral)    ~25%
  Liquidité (prestige/liquid/illiquid) ~20%
  Tendance (momentum)               ~15%
```

**Seuils :**
- ACHAT : score ≥ 65 (régime BULL uniquement)
- SURVEILLER : score 30–64
- EVITER : score < 30

**Régimes :** BULL = SMA50 > SMA200 sur BRVMC · BEAR = ACHAT désactivé (alpha -0.72%)

**Performance documentée :** Alpha +1.82% toutes conditions · +1.02% BULL · -0.72% BEAR

---

## Pipeline GitHub Actions (brvm-analysis-suite)

| Étape | Script | Rôle |
|---|---|---|
| ÉTAPE 0 | `update_index.py` | Indices BRVM |
| ÉTAPE 1 | `data_collector_simple.py` | Scrape brvm.org (7 sec) |
| ÉTAPE 1b | `test_pipeline.py` | 12 tests qualité |
| ÉTAPE 2 | `technical_analyzer_simple.py` | RSI, MACD, SMA |
| ÉTAPE 3 | `opportunity_scorer_simple.py` | Scores 0–100 |
| ÉTAPE 3b | `generate_decisions.py` | Signaux + régime (**GELÉ**) |
| ÉTAPE 3c | `verify_decisions.py` | Vérif. 90j → `brvm_decisions_results` |
| ÉTAPE 3d | `test_pipeline.py` | Tests post-décisions |
| ÉTAPE 4 | `prediction_analyzer_v2.py` | GRU via Supabase REST |
| ÉTAPE 5 | `fundamental_analyzer.py` | Mistral AI |
| ÉTAPE 6 | `report_generator.py` | Rapports multi-AI |
| ÉTAPE 7 | `news_collector.py` | News + scoring IA |

---

## État du modèle (baseline établie au 16/05/2026)

| Métrique | Valeur | Source |
|---|---|---|
| Hit rate signaux | 52.2% / 550 signaux | `verify_decisions.py` |
| Dir.Acc GRU J+2 | 56.1% | `verify_predictions.py` |
| Dir.Acc GRU J+5+ | 43.9% | → indicatif uniquement |
| Couverture Mistral | 47/47 tickers FY2025 | `extract_fundamental_signals.py` |
| Vérification live | 01/07/2026 | `brvm_decisions_results` |

---

## Problèmes connus (ne pas tenter de corriger avant dégel)

| Problème | Impact | Statut |
|---|---|---|
| ONTBF / SICC prix ~10x inflés en 2026 | Fausse le hit rate | Exclu manuellement |
| `report_generator.py` → `relation "report_summary" does not exist` | Non bloquant | Ignoré |
| Données pré-split non ajustées (CFAC, SAFC) | Backtest non fiable | Backlog DATA-05/06 |
| Variation journalière sur jours non consécutifs | Top Gainers parfois incorrect | Backlog DATA-07 |
| Tab Commodités — fallback PRNG encore actif | Données pas réelles | Backlog DATA-09 |

---

## Sécurité

- RLS activé sur toutes les tables Supabase
- Clés API dans GitHub Secrets — **jamais dans le code**
- `brvm_data` : lecture publique · `brvm_decisions` : lecture publique + écriture service_role

---

## Portefeuille réel (référence)

| Ticker | Quantité | Prix d'achat (approx.) |
|---|---|---|
| BOAB | 5 | — |
| BOAC | 10 | — |
| NTLC | 5 | — |
| SNTS | 10 | 28 500 FCFA |

Broker : BOA Capital Direct (SGI). Total ~506 922 FCFA au 30/04/2026.

---

## ADR clés à retenir

| ADR | Décision |
|---|---|
| ADR-001 | Modèle gelé jusqu'au 01/07/2026 |
| ADR-002 | App.jsx monolithique — contrainte macOS Catalina |
| ADR-003 | ACHAT désactivé en régime BEAR |
| ADR-004 | Supabase REST API uniquement (pas psycopg2) |
| ADR-013 | Tabs décoratifs archivés — nouvelle navbar |
| ADR-014 | GRU fiable J+1/J+2 uniquement |
| ADR-015 | Features Mistral statiques → nuisent au GRU, rejetées |
