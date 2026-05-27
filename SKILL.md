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
- **Ne pas installer react-markdown** — cause des erreurs Vite 3 (incompatibilité esbuild)
- **Node v16.20.2 sur macOS Catalina** — impossible d'upgrader, imports complexes instables
- **Vite 3.2.7** — contraintes esbuild spécifiques, ne pas supposer comportement Vite 4/5
- **Warning chunk >500 KiB** — normal, dû à l'App.jsx monolithique, non bloquant

### Pipeline (brvm-analysis-suite)
- **Toujours utiliser Supabase REST API** — psycopg2 échoue en GitHub Actions (ADR-004)
- **Ne pas modifier `generate_decisions.py`** avant le 01/07/2026 — modèle gelé (ADR-001)
- **Features Mistral statiques** → ne pas intégrer dans les modèles GRU (ADR-015, testé et rejeté)
- **GRU fiable J+1/J+2 uniquement** — afficher J+5+ comme indicatif seulement (ADR-014)
- **load_dotenv() dans heredoc** → utiliser `load_dotenv(find_dotenv(usecwd=True))` sinon AssertionError

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
| Texte secondaire | `#7d8590` → utiliser `#1A202C` (contraste corrigé) |
| Warning / estimé | `#d2a94d` |

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
| `companies` | 47 tickers — colonne `symbol` (pas `ticker`) | lecture publique |
| `historical_data` | 110 449+ lignes — company_id, trade_date, price, volume | lecture publique |
| `brvm_decisions` | Signaux — colonnes : ticker, date, score, signal, market_regime, liquidity_tier, confidence | lecture publique |
| `brvm_decisions_results` | Vérifications live (dès 07/2026) | — |
| `boa_recommendations` | 547 lignes, 17 semaines déc 2025–avr 2026 | — |
| `fundamental_analysis` | Analyses Mistral FY2025 | — |
| `company_fundamentals` | PER, dividende, rdt_net depuis BOC PDF (colonnes financières sinon null) | — |
| `commodity_prices` | Cocoa, coton, or, pétrole, USD/XOF | — |
| `user_actions` | Moat data | lecture/écriture user + service_role full |

### Colonnes réelles confirmées (pièges courants)
- `brvm_decisions` : signal_date → **`date`** · decision → **`signal`** · regime → **`market_regime`**
- `companies` : **`symbol`** (pas ticker) · `id` pour jointure avec historical_data
- `historical_data` : **`trade_date`** (pas date) · **`price`** (pas close_price) · pas de colonne ticker
- `boa_recommendations` : colonnes `action` (BUY/SELL/HOLD/REDUCE) · `cours_act` · `cours_pot` · `rendement` · `potential`
- `brvm_decisions` : score_technique/fondamental/liquidite/tendance → **NULL en V1** (score composite seulement)

### fundamental_analysis — détails importants
- `report_date` = fin exercice fiscal · `updated_at` = date réelle analyse Mistral
- Requête frontend : `order=updated_at.desc&limit=1`
- Doublons company_id=42 — neutralisé par limit=1, à corriger post-dégel

**Vues SQL utiles :**
- `v_ytd_performance` — YTD par ticker vs BRVMC
- `v_historical_prices` — historical_data JOIN companies (expose colonne ticker)

---

## Modèle de scoring V1 (gelé jusqu'au 01/07/2026)
endskill

---

## Session 25/05/2026 — Analyse régression live (52 jours)

### Résultats régression logistique (751 signaux, avril–mai 2026)

| Horizon | Hit rate | AUC | Interprétation |
|---|---|---|---|
| J+5 | 39.0% | 0.626 | Signal inversé |
| J+10 | 36.2% | 0.637 | Signal inversé |
| J+20 | 32.9% | 0.691 | Signal inversé fort |
| J+30 | 25.9% | 0.672 | Signal inversé fort |

**Conclusion : modèle inversé sur cette période** — score élevé = baisse prédite
- Coefficient `score` : -0.31 à J+5, -0.28 à J+10 (p<0.05)
- Coefficient `confidence` : +0.42 à J+5 (utile), -0.56 à J+30 (nocif)
- Coefficient `regime_bull` : non significatif J+5/J+10, fort à J+20/J+30
- Liquidité filtre : +5.1% J+5, +5.2% J+10, +7.0% J+20 → **filtre confirmé**
- Seuil optimal ROC : 95 (sur 14 signaux seulement — artefact période baissière)

**Nuance importante :** 52 jours de données sur une seule fenêtre de marché — inversion possiblement conjoncturelle, pas structurelle. À valider avec backtest 10 ans.

### Scripts produits (session 25/05)
- `regression_brvm_horizons.py` — régression logistique multi-horizons (live)
- Colonnes réelles confirmées lors du débogage :
  - `brvm_decisions.date` (pas signal_date)
  - `brvm_decisions.signal` (pas decision)
  - `companies.symbol` (pas ticker)
  - `historical_data.trade_date` + `price` (pas close_price)
  - Score composite seulement en V1 (composantes détaillées = NULL)

### Conclusions session 25/05
- Signal technique = bruit sur 52 jours → confirmé structurellement par backtest 10 ans (session suivante)
- Liquidité = filtre utile → confirmé
- Horizon J+20 optimal pour signal fondamental
- BOA Capital utilise méthode cours cible (DCF/multiples) → signal fondamental, pas technique
- Modèle V2 = décote vs valeur intrinsèque (cours_cible BOA) plutôt que score technique
