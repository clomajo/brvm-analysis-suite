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


---

## Session 27/05/2026 — Modèle V2 : Value + Dividende + Qualité

### Contexte
- Fix pymupdf ajouté à requirements.txt — scrape_boc_pdf.py opérationnel
- Palm Oil (FUTR.KL) et Rubber (TOCOM-RUBBER.T) — HTTP 404 permanent — à retirer de scrape_commodities.py
- Pipeline complet vert : 47 records, 1272 prix commodités, 48 tickers BOC parsés

### Modèle V2 — Signal primaire validé par backtest

Acheter J-10 avant ex_dividend_date sur moyennes caps (150-300 Mds FCFA) avec ROE>15% et P/B<2.5x.
Performance attendue : mediane +15-20% a J+90, alpha +10-13% vs BRVMC, taux de succes 65-70%, frequence 6-8 signaux/an.

Regles de gestion :
- Max 4 positions simultanees, max 25% portefeuille par position
- Stop relatif : sortir si J+30 < BRVMC - 5%
- Horizon cible : J+60 (alpha maximal) ou J+90 si fondamentaux solides

### PER sectoriels empiriques (calcules sur donnees reelles, filtre 2-50x)
- Banque : 12.4x (n=11)
- Agro : 10.2x (n=4)
- Industrie : 13.2x (n=12)
- Telecom : 13.3x (n=3)
- Distribution : 16.1x (n=8)

### Tickers exclus modele V2 (EPS non representatif)
NTLC, SNTS, BOAN, BNBC, SICC, UNLC, ETIT, FTSC, CFAC, SIVC

### Watchlist moyennes caps confirmees
- SOGC, SPHC, BOAS, BOABF — Cap+Qualite confirmes (mediane J+90 = +18.2%)
- ONTBF, TTLC — Cap seule (P/B hors filtre)

### Resultats backtest

Backtest value (FY2021-FY2024, 65 signaux) :
- Decote >15% : med J+60 = +6.7%, alpha +2.9%, 72% positifs
- Decote >80% : med J+60 = +11.3%, alpha +7.5%, 83% positifs
- BRVMC benchmark : +3.8% J+60, +5.2% J+90

Backtest dividende (2023-2026, 50 evenements) :
- J-10 : mediane +3.6%, 86% positifs — signal le plus propre
- J+10 : mediane 0.0%, 44% positifs — correction immediate
- J+90 : mediane +0.5%, 51% positifs — signal bruite sans filtre

Backtest par taille de cap (J+90) :
- Grande (>300 Mds) : mediane +0.5%, 60% positifs
- Moyenne (150-300 Mds) : mediane +11.0%, 67% positifs
- Petite (<130 Mds) : mediane -2.1%, 40% positifs

Filtre combine ROE>15% + P/B<2.5 (n=11) : mediane J+90 = +9.5%, alpha +4.3%
Hors filtre (n=13) : mediane J+90 = -2.0%

### Scripts produits (session 27/05)
- calculate_target_price.py — cours cible PER sectoriel + Gordon
- backtest_value.py — backtest decote vs performance FY2021-FY2024
- backtest_dividend.py — comportement cours autour ex_dividend_date
- signaux_actifs.py — watchlist J-10 hebdomadaire (pipeline lundi)
- backtest_regression.py, boa_simple.py — scripts complementaires

### Colonnes confirmees (session 27/05)
- company_fundamentals : ticker, fiscal_year, eps, pb_ratio, roe, pe_ratio, market_cap, ex_dividend_date, dividend_per_share
- FY2026 = donnees vides pour la plupart — toujours filtrer roe=not.is.null pour obtenir FY2025

### ADR session 27/05
- ADR-016 : Modele V2 parallele silencieux jusqu'au 01/07/2026 — pas de remplacement V1 avant verification live
- ADR-017 : Univers V2 = moyennes caps uniquement (150-300 Mds FCFA)
- ADR-018 : Fenetres J-10 = signal d'achat optimal avant ex_dividend_date
- ADR-019 : Palm Oil et Rubber retires de scrape_commodities.py (HTTP 404 permanent)

## Règle opérationnelle — Fin de session

À la fin de chaque session de développement BRVM Analytics, mettre à jour simultanément :
1. SKILL.md — contraintes, ADR, bugs résolus, baselines
2. CHANGELOG.md — entrée datée avec FEAT/INFRA/PERF/FIX
3. BACKLOG.md — nouveaux items identifiés
4. DECISIONS.md — nouveaux ADR
5. ARCHITECTURE.md — changements structurels

Puis commit unique :
git add SKILL.md CHANGELOG.md BACKLOG.md DECISIONS.md ARCHITECTURE.md
git commit -m "docs: mise à jour documentation session JJ/MM/YYYY"
git push
