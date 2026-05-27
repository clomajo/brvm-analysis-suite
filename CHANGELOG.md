# Changelog — BRVM Analytics

Tous les changements notables sont documentés ici.
Format : `[DATE] TYPE: Description (commit)`

Types : `BUG` `FEAT` `FIX` `PERF` `DATA` `TEST` `INFRA`

---

## 2026-04-26

### FEAT — Composant FinancialAnalysis.jsx — 8 onglets complets
- **Commits:** multiples — FinancialAnalysis.jsx
- **Onglets:** Vue d'ensemble · P&L · Cash Flow · Valorisation · Dividende · Peers · Fair Value · Prévisions
- **Fair Value:** EPS moyen 3 ans × P/E 10x — cours historique 3 ans vs Fair Value (graphique)
- **Prévisions:** CAGR historique 5 ans → projection 3 ans CA/RN/EPS/DPA avec graphique
- **Peers:** comparaison sectorielle automatique depuis company_management.industry
- **Note Morningstar:** divergence technique vs fondamental expliquée

### FEAT — Prompt NYSE-style dans fundamental_analyzer.py (bon fichier)
- **Commit:** d5285fe + patches — fundamental_analyzer.py
- **Sections:** Investment Thesis · Recommandation + price target · CA&Croissance · Rentabilité · Dividende&FCF · Moat Rating · Contexte sectoriel BRVM
- **Peer comparison:** tableau sectoriel FY2025 injecté automatiquement dans le prompt
- **Moat Rating:** WIDE/NARROW/NONE dans les 3 modèles (DeepSeek, Gemini, Mistral)
- **Données:** company_fundamentals 5 ans injectées dans le prompt

### FEAT — scrape_indices.py — BRVMC + BRVM30 quotidiens
- **Commit:** c4c6fda — scrape_indices.py + workflow
- **Source:** brvm.org/en/marche/bulletin-officiel-de-la-cote
- **Fix:** indices bloqués au 18 avril → mis à jour quotidiennement dès demain 6h UTC

### FEAT — scrape_commodities.py — Prix réels Yahoo Finance
- **Commit:** dec2aa8 — scrape_commodities.py + workflow
- **Commodités:** cocoa (CC=F), cotton (CT=F), gold (GC=F), crude (CL=F), USD/XOF (EUR/USD × 655.957)
- **Table:** commodity_prices — 1263 prix insérés
- **Frontend:** CommoditiesView lit depuis Supabase avec fallback PRNG

### FEAT — Badge détresse relative dans DecisionCards
- **Commit:** c931d23 — App.jsx
- **Seuil:** YTD ticker < YTD BRVMC - 25pts
- **Vue SQL:** v_ytd_performance (avec filtre aberrations > ±50%)
- **Affichage:** ⚠️ Relative Distress · YTD X% · -Xpts vs BRVMC

### FIX — Portfolio — vrais prix depuis fetchLiveData
- **Commit:** 04a73eb — App.jsx
- **Avant:** generateDemoData (PRNG) pour tous les tickers portfolio
- **Après:** fetchLiveData depuis Supabase avec fallback demo

### FIX — Contraste texte — #7d8590 → #1A202C
- **Commit:** e87f2c1 — App.jsx
- **Description:** 216 remplacements + 29 textes secondaires pour meilleur contraste

### DATA — Vue v_ytd_performance créée
- **Source:** historical_data JOIN companies — prix début 2026 vs prix actuel
- **Filtre:** exclut variations > ±50% (aberrations ONTBF, SICC)

### DATA — Vue v_historical_prices créée
- **Source:** historical_data JOIN companies — expose colonne ticker
- **Usage:** FinancialAnalysis Fair Value chart

---

## 2026-04-25 / 2026-04-26

### FEAT — Composant FinancialAnalysis.jsx — graphiques et tableaux depuis Supabase
- **Commits:** 5988e3e, 1cb3cf1, 4747996, aaed5ae, e44a6c4 — FinancialAnalysis.jsx
- **Données:** company_fundamentals — 43 tickers, 5 ans (FY2021–FY2025), 52 colonnes
- **Onglets:** Vue d'ensemble · P&L · Cash Flow · Valorisation · Dividende · Peers
- **Graphiques:** Chart.js — CA/RN, marges, FCF, P/E historique/forward, dividende+rendement
- **Source:** stockanalysis.com via scraper existant

### FEAT — Onglet Peers — comparaison sectorielle automatique
- **Commit:** 9ca09e1 — FinancialAnalysis.jsx
- **Source:** company_management.industry + company_fundamentals FY2025
- **Couverture:** 43 tickers, 14 secteurs
- **Affichage:** Tableau comparatif CA, RN, marge, ROE, P/E, P/B, dividende

### FEAT — Thème corporatif gris clair + bleu finance
- **Commit:** bc52c42 — App.jsx
- **Description:** Remplacement de 500+ couleurs inline (fonds sombres → gris clair, textes blancs → sombres)
- **Palette:** Fond #F8F9FA, cards #FFFFFF, accent #2B6CB0, texte #1A202C

### FEAT — Prompt Mistral NYSE-style 6 sections
- **Commit:** f83a893 — report_generator.py
- **Sections:** Investment Thesis · Recommandation + price target · CA&Croissance · Rentabilité · Dividende&FCF · Risques&Opportunités · Contexte sectoriel
- **Nouveau:** Objectif de cours (EPS × P/E ~10x), trigger de révision, scénarios

### FEAT — Données company_fundamentals injectées dans prompt Mistral
- **Commit:** f83a893 — report_generator.py
- **Description:** Tableau 5 ans (CA, RN, EBITDA, marges, ROE, EPS, DPA, P/E, FCF) injecté dans le prompt avant génération
- **Impact:** Mistral interprète maintenant les vraies données financières structurées

### FIX — Texte brut Mistral masqué + rapport unique (le plus récent)
- **Commits:** 4747996, eb488b8 — App.jsx
- **Avant:** Markdown brut illisible, plusieurs rapports affichés
- **Après:** Une ligne sobre + composant FinancialAnalysis unique (rapport le plus récent)

### FIX — Industry mappée pour ETIT, SICC, STBC
- **Source:** Supabase SQL UPDATE company_management
- **ETIT:** Commercial Banks · **SICC:** Agriculture · **STBC:** Food and Kindred Products

### INFRA — chart.js ajouté comme dépendance npm
- **Commit:** 1cb3cf1 — package.json

### BACKLOG — Nouveaux items identifiés
- react-markdown pour rendre le texte Mistral structuré
- Price vs Fair Value chart (Fair Value = EPS moyen 3 ans × P/E ~10x)
- Filtre détresse relative vs BRVM Composite (badge ⚠️)
- Déduplication sectorielle BOA (alerte si 3+ titres même groupe en BUY)

---

## 2026-04-21

### FEAT — Table corporate_events + scraper dividendes Sikafinance
- **Commit:** 455bc33 — scrape_corporate_events.py
- **Données:** 6 dividendes 2026 + 119 historiques 2022-2025
- **Table:** corporate_events (ticker, event_type, event_date, amount, yield_pct)

### FEAT — Scraper calendrier RichBourse API JSON
- **Commit:** 61f709a — scrape_corporate_events.py v2
- **URL:** richbourse.com/outils/calendrier/events (API JSON FullCalendar)
- **Données:** 226 AG + 142 EX_DIVIDEND + 142 DIVIDEND_PAYMENT = 674 events total
- **Mise à jour:** Automatique chaque lundi (ETAPE 1c GitHub Actions)
- **Impact:** Calendrier corporate events complet et auto-actualisé chaque année

### FEAT — Badge dividende imminent dans DecisionCard
- **Commits:** 70b98ed, eda5a42, 4410c4b — App.jsx
- **Description:** Badge 💰 sur chaque carte avec ex-dividend dans 60 jours
- **Affichage:** Aujourd'hui / Demain / Dans Xj + date exacte
- **Fix:** Calcul timezone UTC corrigé, offset -1 jour pour éviter exclusion

### FIX — Doublons SDCC/SDSC dans TICKER_TO_SYMBOL
- **Commits:** 8b78590, 10bcc71 — App.jsx
- **Description:** Clé SDCC dupliquée remplacée par SDSC (Bolloré),
  puis doublon SDSC supprimé. Build propre sans warnings.

### DATA — AG avril-juin 2026 insérées
- **Source:** RichBourse calendrier + stockanalysis.com earnings dates
- **Total:** 22 AG pour avril-juin 2026 dans corporate_events

---

## 2026-04-18

### FEAT — Scraper fondamentaux 5 ans depuis stockanalysis.com
- **Commit:** 60568df — scrape_all_v4.py
- **Tables:** company_fundamentals (178 lignes), company_management (46 lignes)
- **Couverture:** 43/47 tickers financiers, 46/46 management
- **Données:** Revenue/NI/EPS/Marges 5 ans + CEO/CFO/Employés + EarningsDate + ExDivDate

### FEAT — Score V2 fondamentaux + géopolitique
- **Commit:** c21ab75 — generate_decisions.py
- **Formule:** (Tech x ratio_tech + Fund x ratio_fund) x geo_multiplier
- **Géopolitique:** CI 1.00, SN/BJ 0.95, TG 0.90, BF 0.75, ML 0.70, NE 0.65
- **Mode:** Informatif uniquement — score V1 intact jusqu au 01/07/2026

### FEAT — Badge Score V2 dans DecisionCard
- **Commit:** bf23251 — App.jsx
- **Affichage:** Score V2 + delta + badge Geo x0.XX pour pays AES

### FEAT — Management tab vraies données Supabase
- **Commit:** c724287 — App.jsx
- **Impact:** CEO/CFO réels pour 46 tickers (ex: SNTS → Brelotte Ba)

### FIX — IndexPanel valeur réelle BRVMC/BRVM30
- **Commit:** a2b68ca — App.jsx

### INFRA — Pipeline hebdomadaire scraper fondamentaux
- **Commit:** 60568df — brvm-analysis.yml ETAPE 1b chaque lundi

### ADR — ADR-009 à ADR-012 ajoutés dans DECISIONS.md

---

## 2026-04-13

### FEAT — Tests qualité pipeline automatiques (12 tests)
- **Repo:** brvm-analysis-suite
- **Commit:** 0d5dea4
- **Description:** Ajout de `test_pipeline.py` avec 12 tests automatiques couvrant :
  T1 tickers uniques, T2 prix nuls, T3 doublons, T4 anomalies >40%,
  T5 décisions générées, T6 ACHAT en BEAR, T7 scores hors limites,
  T8 fraîcheur données, T9 données non consécutives, T10 signaux sans prix,
  T11 distribution scores, T11b dérive modèle
- **Impact:** Détection automatique des problèmes de données avant génération des décisions

### INFRA — Suppression || true silencieux (étapes 4/6/7)
- **Repo:** brvm-analysis-suite
- **Commit:** 0d5dea4
- **Description:** Remplacement de `python script.py || true` par blocs if/else
  dans les étapes GitHub Actions 4 (Prédictions), 6 (Rapports), 7 (News)
- **Impact:** Les échecs sont maintenant visibles dans les logs au lieu d'être masqués

### FIX — Fetcher couvrait 1 secteur sur 7
- **Repo:** brvm-analysis-suite
- **Commit:** b6f0b55
- **Description:** `data_collector_simple.py` ne fetchait que `/en/cours-actions/0`
  (Consommation de Base). Boucle ajoutée sur les 7 secteurs BRVM (indices 0-6).
  Correction également : table cible = plus grande table par nombre de rows,
  `session_date` initialisé dès le début, `Content-Type` ajouté aux headers.
- **Impact:** SIVC, SNTS, ONTBF et tous les titres Télécoms/Énergie/Services
  jamais mis à jour depuis le début. Fix livré le 13/04/2026.
- **Tickers affectés:** SNTS, SIVC, ONTBF, ORAC et tous titres hors secteur CB

### FIX — 52-week high/low basé sur 10 ans de données brutes
- **Repo:** brvm-analytics (frontend)
- **Commits:** 6fbf620, fc9e0bc
- **Description:** `Math.max(...allCloses)` calculait le plus haut sur toutes les
  données historiques sans filtre. Double correction :
  (1) Limiter à 1 an glissant (`oneYearAgo`)
  (2) Exclure variations journalières >40% (splits non ajustés)
- **Exemple:** BOAN affichait 116 938 FCFA (pic 2016 pré-split) au lieu de ~2 825 FCFA
- **Impact:** Affichage 52-week corrigé sur tous les tickers

### DATA — Splits historiques groupe BOA identifiés
- **Source:** Scan SQL + Investing.com + rapport BRVM
- **Description:** Splits confirmés :
  - BOAN : 10:1 le 27/10/2017 + 1.6:1 le 03/09/2024
  - BOAB : ~10:1 le 31/10/2017 + 1.6:1 le 03/09/2024
  - BOAC : ~10:1 le 26/10/2017 + 1.6:1 le 25/10/2024
  - BOABF : ~10:1 le 24/10/2017 + 1.6:1 le 28/08/2024
  - BOAS : ~10:1 le 30/10/2017 + 1.5:1 le 28/08/2024
  - BOAM : ~10:1 le 22/12/2017 + 1.5:1 le 27/08/2024
  - ONTBF : 2:1 le 29/08/2018
  - SITAB : 20:1 le 27/07/2018
  - CFAC : split le 21/12/2017
  - SAFC : 5:1 le 24/12/2018
- **Statut:** Non corrigé dans historical_data — backlog DATA-05/06 après juillet 2026
- **Impact:** Backtest non fiable sur données pré-split pour ces tickers

### DATA — Variation journalière sur données non consécutives
- **Ticker affecté:** ETIT (et potentiellement autres)
- **Description:** App calcule `(prix_N - prix_N-1) / prix_N-1` sans vérifier
  que N et N-1 sont des jours de bourse consécutifs. ETIT avait un gap du
  20/03 au 07/04 (fetcher ne couvrait qu'un secteur) → variation affichée
  +6.25% au lieu de 0.00%
- **Statut:** Détecté, couvert par T9, non corrigé — backlog DATA-07 après juillet 2026
- **Impact:** Top Gainers potentiellement incorrect pour tickers avec données manquantes

---

## 2026-04-12

### FIX — Modèle composite score — seuil abaissé 55→30 rows
- **Repo:** brvm-analytics
- **Commit:** dd29674
- **Description:** Seuil minimum de données abaissé pour permettre les décisions
  sur tickers moins liquides. Champ `data_completeness` (High/Medium/Low) ajouté.

---

## 2026-04-06

### FEAT — Régime de marché BULL/BEAR
- **Description:** Signaux ACHAT désactivés en régime BEAR.
  Alpha documenté : +1.82% vs random toutes conditions,
  +1.02% BULL, -0.72% BEAR.

### FEAT — Composition BRVM 30 avril 2026 intégrée

### FEAT — Scorecard EOP (End of Period) — chiffres honnêtes

---

## 2026-04-01

### FEAT — Lancement pipeline v1 officielle
- **Classification:** v1_officielle_20260401
- **Description:** Première version officielle du modèle. Gel jusqu'au 01/07/2026.
  Première vérification live : 01/07/2026.

---

## 2026-03-26 (sprint fondateur)

### FEAT — Plateforme BRVM Analytics — version initiale
- React 18 + Vite, Supabase, GitHub Actions, Mistral AI
- 92 714 lignes historiques importées (10 ans)
- TradingView Lightweight Charts
- Onglets : Aperçu, Marché, Opportunités, Scorecard, Risque,
  Législatif, Direction, Prévisions, Backtest, Portefeuille, Obligations, Macro
- Pricing B2B : 150$/mois broker, 500$/mois trading floor, 5 000$/an asset manager

---

## 2026-05-03

### FEAT — Signal fondamental Mistral intégré dans brvm_decisions
- **Script:** extract_fundamental_signals.py
- **Description:** Analyse les 158 résumés Mistral via API — extrait signal_fondamental (positif/neutre/négatif), croissance_ca_pct, resume_fondamental
- **Colonne:** signal_combine = combinaison signal technique + fondamental
- **Règles:** ACHAT + positif = CONVICTION FORTE · ACHAT + neutre = ACHAT MODÉRÉ · ACHAT + négatif = PRUDENCE · SURVEILLER + positif = À SURVEILLER +
- **Coverage:** 41/47 tickers analysés (BOAC, BOAS, CBIBF sans analyse au départ)

### DATA — Analyses fondamentales BOAB, BOABF, BOAC insérées manuellement
- **Source:** États financiers certifiés + rapports d'activité officiels BRVM
- **BOAB:** Série 2021-2025 — PNB +10,2% en 2025, ROE 17,1%, dividende 585 FCFA mai 2026 → signal positif
- **BOABF:** Série 2022-Q1 2026 — PNB -10,75% au Q1 2026, coût du risque x25 vs 2023 → signal négatif
- **BOAC:** Série 2021-Q3 2025 — PNB +19,6% en 2024, ROE ~28,5%, ralentissement 2025 → signal neutre
- **Impact:** BOAC passe de null à ACHAT MODÉRÉ (technique ACHAT + fondamental neutre)

### FEAT — Badge signal_combine + data_completeness dans DecisionCard
- **Commit:** 0564e52 — App.jsx
- **Description:** Badge bleu signal_combine affiché quand différent du signal technique · Badge orange/gris data_completeness pour Medium/Low uniquement
- **Script:** patch_decision_badge.py

### FEAT — prediction_analyzer_v2.py — GRU via Supabase REST
- **Commit:** 30602ad — prediction_analyzer_v2.py
- **Description:** Migration complète de psycopg2 vers requests REST · Charge modèles .keras depuis /modeles/ · Insère 10 prédictions/ticker dans table predictions
- **Fix:** brvm_data → historical_data · close_price → price
- **Résultat:** 410 prédictions insérées (41/49 tickers) · run_date 2026-05-04
- **Workflow:** ÉTAPE 4 mise à jour — utilise v2 avec SUPABASE_URL/KEY au lieu de DB_*

### FEAT — Tab Forecast — GRU (IA) réel depuis Supabase
- **Commit:** 58ff732 — App.jsx
- **Description:** useEffect fetch prédictions GRU depuis Supabase pour ticker actif · Fallback vers lstmForecast si pas de données · Renommage LSTM-like → GRU (IA) partout
- **Ensemble:** recalculé avec gruVals au lieu de lstmVals

### FEAT — verify_predictions.py — tracking record GRU
- **Commit:** e4c502e — verify_predictions.py
- **Description:** Compare predicted_price vs prix réel pour prediction_date = today · Calcule error_pct, direction_correct, MAPE moyen · Upsert dans predictions_results
- **Table:** predictions_results créée (company_id, run_date, prediction_date, predicted_price, actual_price, error_pct, direction_correct)
- **Workflow:** ÉTAPE 3e ajoutée · Premier tracking record disponible : 14 mai 2026
- **Objectif:** Comparer taux de réussite GRU vs MAPE théorique des modèles entraînés

### INFRA — Repo nettoyé + .gitignore
- **Commit:** 00000a8
- **Description:** 38 fichiers temporaires supprimés (backups, scripts de test, patches) · .gitignore ajouté pour éviter récurrence

---

## 2026-05-11

### ARCH — Réorganisation complète de l'architecture UI
- **Navbar globale:** [Recherche ticker] · Marché · Opportunités · Portefeuille · Obligations
- **Page par défaut:** Marché
- **Fiche ticker:** Aperçu · Prévisions · Backtest
- **Dans Marché:** Breadth · Heatmap · Top Gainers/Losers · Scorecard résumé 3 KPIs (expandable)
- **Tabs archivés (masqués, non supprimés):** BOA vs BRVM · Risque · Législatif · Direction · Macro · Matières 1ères · Scorecard détaillé
- **Raison:** Tabs sans données réelles = décoration. Corrélation macro/matières/gouvernance/législatif avec cours = chantier futur dédié.
- **Référence:** ADR-013

---

## 2026-05-16

### FEAT — verify_decisions.py — vérification automatique signaux J-90
- **Commit:** 7dfd294 — verify_decisions.py
- **Description:** Vérifie les signaux brvm_decisions à J-90, compare prix signal vs prix réel, upsert dans brvm_decisions_results. Fallback automatique ±5 jours (weekends/fériés). Cache company_id pour optimisation.
- **Résultats:** Hit rate 52.2% sur 550 signaux cumulés · 50.0% sur J-43 (36 signaux)
- **Workflow:** ÉTAPE 3c — tourne après generate_decisions.py

### FEAT — verify_predictions.py — vérification prévisions GRU vs réel
- **Commit:** a8145ec — verify_predictions.py
- **Description:** Compare predicted_price vs prix réel pour toutes les prévisions dont prediction_date ≤ today. Calcule error_pct, direction_correct, MAE% par horizon.
- **Résultats:** 1845 prévisions vérifiées · Dir.Acc J+2=56.1% · J+5+=43.9% · Global=50.1%
- **Conclusion:** GRU utile uniquement à J+1/J+2. Afficher uniquement ces horizons dans l'app.
- **Table:** predictions_results — colonne prediction_id ajoutée + contrainte UNIQUE
- **Workflow:** ÉTAPE 3e

### FIX — Badge "vs clôture J-1" sous les variations de prix
- **Commit:** 3326f4c — App.jsx (brvm-analytics)
- **Description:** Note discrète grise sous chaque variation de prix pour clarifier qu'il s'agit de la variation vs la clôture précédente (et non intraday comme brvm.org)

### DATA — 47/47 tickers avec signal Mistral FY2025
- **Commits:** bf0d97b, b8e5770 — fundamental_analyzer.py, extract_fundamental_signals.py
- **CBIBF:** slug coris-bank-international ajouté · signal positif (PNB +9.7%)
- **FTSC:** slug filtisac-ci ajouté · signal négatif (CA -19.7%)
- **BOAS:** inséré manuellement depuis PDFs 2021-2026 · signal positif (PNB +4.5% FY2025)
- **SIVC:** rebrandée Erium CI · inséré manuellement · signal positif (CA +13% T3 2025)
- **PRSC:** inséré manuellement depuis états financiers 2018-2025 · signal positif (CA +9% FY2025)
- **Fix:** fiscal_year corrigé de "2025" → "FY2025" dans extract_fundamental_signals.py
- **Coverage:** 47/47 tickers — couverture complète pour la première fois

### TEST — Réentraînement GRU avec features Mistral (Colab)
- **Résultat:** Dir.Acc 35.4% vs baseline 50.1% → -14.7 pts
- **Conclusion:** Features statiques Mistral (signal + CA%) nuisent aux modèles de séries temporelles — même conclusion que Pilla & Mekonen (S&P 500, 2025). GRU actuels conservés.
- **Valeur Mistral:** Tab Opportunités uniquement (generate_decisions.py), pas prédictions de prix.

### INFRA — venv311/ et .env_temp retirés du repo
- **Commit:** b8e5770
- **Description:** .gitignore mis à jour pour exclure l'environnement virtuel et les fichiers temporaires de credentials

---

## 2026-05-17

### FIX — Labels et dates section Analyse Mistral
- **Commits:** ad72d1b, 7cae8d0, 74757ff, 65294a0, 05b03ae — App.jsx
- **Badge heatmap:** supprimé (était permanent sans condition réelle)
- **Section fondamentaux:** renommée "Fondamentaux clés" · badge ⚠️ Données estimées en orange
- **Titre Mistral:** doublon "Données FY2025" retiré du titre → gardé uniquement dans le sous-titre
- **Date analyse:** corrigée — affiche maintenant updated_at (date réelle de la dernière analyse Mistral quotidienne) au lieu de report_date (fin d'exercice fiscal FY2025)
- **limit=1 + order=updated_at.desc:** toujours la dernière analyse, bug de duplication neutralisé

### DATA — fundamental_analysis : comportement clarifié
- **Mise à jour:** quotidienne via UPDATE (pas INSERT) — updated_at reflète la dernière analyse
- **Doublons détectés:** company_id=42 a 3 entrées — neutralisé par limit=1
- **report_date:** = fin d'exercice fiscal (2025-12-31) — ne pas confondre avec date de génération

---

## 2026-05-25

### PERF — Régression logistique live (751 signaux, avril–mai 2026)
- Hit rate J+5=39% J+10=36% J+20=33% J+30=26% — signal inversé sur cette période
- AUC J+20=0.691 — bon modèle mais à l'envers (score élevé = baisse prédite)
- Liquidité filtre : +5 à +7% de hit rate → filtre binaire confirmé
- Coefficient regime_bull fort à J+20/J+30, non significatif à court terme
- Seuil optimal ROC = 95 sur 14 signaux (artefact période baissière)

### PERF — Backtest 10 ans (22 992 signaux, 2016–2026)
- AUC 0.51 tous scores confondus — signal technique structurellement nul
- Aucune formule de score ne performe mieux qu'une autre (V1, RSI seul, trend seul = identiques)
- Régime BULL/BEAR inversé : BEAR 55% > BULL 49.6% à J+10
- Signal s'améliore avec le temps : J+5=47.9% → J+30=56.7% (signal fondamental lent)
- Conclusion : signal technique = bruit sur BRVM (ADR-016)

### FEAT — Identification signal BOA cours cible
- Méthode BOA = DCF/multiples → cours_cible stable = valeur intrinsèque annuelle
- Hit rate BOA BUY 64.3% J+20 / SELL 24.5% J+20 (inversé — correction lente marché illiquide)
- Formule reverse-engineered : cours_cible = dividende / rendement_cible_sectoriel
- Base V2 : décote vs valeur intrinsèque (pas score technique)

### INFRA — Débogage colonnes Supabase
- brvm_decisions : signal_date→date, decision→signal, regime→market_regime
- companies : ticker→symbol
- historical_data : date→trade_date, close_price→price (pas de colonne ticker)
- Score composite seulement en V1 (composantes détaillées NULL)
