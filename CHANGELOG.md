# Changelog — BRVM Analytics

Tous les changements notables sont documentés ici.
Format : `[DATE] TYPE: Description (commit)`

Types : `BUG` `FEAT` `FIX` `PERF` `DATA` `TEST` `INFRA`

---

## [2026-05-30]

### FIX — Pipeline : nettoyage et corrections mineures
- V2-06 : retrait Palm Oil (FUTR.KL) et Rubber (TOCOM-RUBBER.T) de scrape_commodities.py — HTTP 404 permanent (commit efde604)
- requirements.txt : suppression doublons joblib, pypdf, feedparser (commit 9212b00)
- fix_snts_updates.sql archivé dans sql/ du repo (commit 73474e9)

### INFRA — Pipeline : automatisation mensuelle market_cap
- scrape_market_cap.py ajouté au workflow GitHub Actions — 1er lundi du mois (ADR-025) (commit 7a069ae)

### INFRA — Pipeline : calculate_target_price.py → Supabase
- Table target_prices créée : ticker, cours_cible, decote_pct, signal_v2, methode, calcul_date
- Upsert quotidien ajouté dans calculate_target_price.py (commit b939b53)
- Intégré pipeline ÉTAPE 1f (après collecte prix, avant analyse technique)
- 25 lignes insérées au premier run (28 tickers avec fondamentaux disponibles)
- Contrainte UNIQUE (ticker, calcul_date) — pas de doublons

### FEAT — EPS moyenne glissante 3 ans dans calculate_target_price.py
- V2-07 : fetch_fundamentals() retourne EPS moyen sur 3 ans max au lieu de l'année la plus récente
- Filtre abs(eps) < 1e7 conservé pour exclure aberrations extrêmes
- Tickers exclus par nature (NTLC EPS non représentatif) filtrés en aval par critères cap+qualité V2
- Log affiche "(moy Xans)" pour traçabilité (commit dc52769)

### FIX — verify_decisions.py horizon J+20 (ADR-019)
- VERIFICATION_WINDOW : 90 → 20 jours
- Label GitHub Actions mis à jour : "90-day lookback" → "J+20 — ADR-019" (commit 07f46c6)

### FIX — Frontend : suppression tab BOA vs BRVM
- UI-02 : tab et composant BOAComparison retirés de la navbar et du rendu (commit 25a92a0)

### FEAT — Frontend : Fondamentaux clés connectés à Supabase
- DATA-12 : FUND_DATA hardcodé (~15 tickers) remplacé par fetch Supabase company_fundamentals
- Colonnes : pe_ratio, pb_ratio, market_cap, dividend_yield, shares_outstanding, roe, fiscal_year
- Filtre roe=not.is.null pour pointer sur FY2025 (dernière année avec données réelles)
- Badge "SOURCE: Supabase · FY2025" remplace "⚠️ Données estimées"
- Ajout ROE comme 6e métrique (commit c6a03e8)

### DATA — Supabase : nettoyage doublons fundamental_analysis
- DATA-11 : DELETE doublons — 45 lignes, 45 company_id distincts (était ~200+ lignes)
- Contrainte UNIQUE (company_id) ajoutée sur fundamental_analysis

### FEAT — Frontend : ligne Fair Value style Morningstar sur graphique
- CHART-01 : ligne pointillée orange (#E07B39, lineStyle=2) sur toute la période affichée
- Fetch depuis target_prices (dernier calcul_date par ticker)
- Filtre décote aberrante abs(decote_pct) < 200 (exclut NTLC)
- Prop fairValue passée à InteractiveChart, ajoutée aux deps useEffect (commit 9c65c31)

### FEAT — Frontend : badge Fair Value V2 sur DecisionCards
- UI-03 : badge 🎯/📉 avec décote % et cours_cible FCFA sur chaque card
- Fetch target_prices optimisé — uniquement les tickers du jour (pas 200 lignes)
- Vert si décote > 0 (sous-évalué), rouge si décote < 0 (surévalué)
- Intégré dans DecisionCardView après badge détresse relative (commit 965ef99)

---

## [2026-05-29 — soir]

### FEAT — Backtest V2 finalisé
- filtre cap+qualite : 150-500B FCFA, ROE>15%, P/B<2.5
- correction look-ahead bias : date signal = 30 avril (après publication résultats)
- résultats honnêtes : 25 signaux, médiane J+90 +7.8%, alpha +2.8%, 68% positifs
- SCORECARD_V2.md créé

### FEAT — scrape_market_cap.py
- 45/46 tickers scraped depuis stockanalysis.com/quote/brvm/{ticker}/statistics/
- market_cap et shares_outstanding mis à jour dans company_fundamentals
- ETIT : HTTP 404 permanent (exclu)

### INFRA — backtest_value.py mis à jour
- filtre cap+qualite intégré (FILTRE_CAP_QUALITE = True)
- dates signal corrigées (fy_dates → avril)
- CAP_MAX élargi 300B → 500B (inclut BOAC)

---

## [2026-05-29]

### INFRA — DATA-05/06 : Correction splits historiques
- fix_splits.py : 50 splits appliqués, 47,606 lignes corrigées
- 11 splits ignorés (déjà dans données source)
- 15 facteurs estimés (non documentés officiellement)
- Backup historical_data.json créé (110,594 lignes)

### INFRA — SNTS historique corrigé
- fix_snts_updates.sql : 2,476 prix remplacés par données réelles (2016-2026)
- Données source : 41_market-data_SONATEL.xlsx
- company_fundamentals SNTS : shares_outstanding et market_cap corrigés

### FIX — Frontend vue d'ensemble
- FinancialAnalysis.jsx : latest pointe sur dernier FY avec données réelles
- Correction : FY2026 NULL n'est plus affiché par défaut

### FIX — Pipeline InvalidJSONError
- technical_analyzer_simple.py : sanitize NaN/Inf avant envoi Supabase
- import math ajouté

---

## 2026-05-27

### INFRA — Fix pipeline
- pymupdf ajouté à requirements.txt — scrape_boc_pdf.py opérationnel en CI
- Palm Oil (FUTR.KL) et Rubber (TOCOM-RUBBER.T) — HTTP 404 permanent Yahoo Finance
- Pipeline complet vert : 47 records prix, 1272 prix commodités, 48 tickers BOC parsés
- BRVMC=420.33, BRVM30=197.33 au 27/05/2026

### FEAT — Modèle V2 : signal value + dividende + qualité
- Signal primaire validé : acheter J-10 avant ex_dividend_date sur moyennes caps
- Filtre qualité : ROE>15% + P/B<2.5 → médiane J+90 = +9.5%, alpha +4.3% vs BRVMC
- Filtre taille : moyennes caps (150-300 Mds FCFA) → médiane J+90 = +11.0%
- Combinaison Cap+Qualité : médiane J+90 = +18.2%, alpha +13% vs BRVMC
- Signal dividende J-10 : 86% réussite sur 10 jours (50 événements 2023-2026)

### PERF — Backtest value (FY2021-FY2024, 65 signaux)
- Décote >15% : médiane J+60 = +6.7%, alpha +2.9%, 72% positifs
- Décote >80% : médiane J+60 = +11.3%, alpha +7.5%, 83% positifs
- BRVMC benchmark : +3.8% J+60, +5.2% J+90

### PERF — PER sectoriels empiriques calculés
- Banque 12.4x, Agro 10.2x, Industrie 13.2x, Telecom 13.3x, Distribution 16.1x
- Filtre 2-50x appliqué — tickers exclus : BNBC(445), BOAN(190), SICC(137), UNLC(846)

### INFRA — Scripts V2 ajoutés au pipeline
- calculate_target_price.py — cours cible PER sectoriel + Gordon
- backtest_value.py — backtest décote vs performance FY2021-FY2024
- backtest_dividend.py — comportement cours autour ex_dividend_date
- signaux_actifs.py — watchlist J-10 hebdomadaire (pipeline lundi)
- ADR-020 à ADR-023 ajoutés (voir DECISIONS.md)

---

## 2026-05-25

### PERF — Régression logistique live (751 signaux, avril–mai 2026)
- Hit rate J+5=39% J+10=36% J+20=33% J+30=26% — signal inversé sur cette période
- AUC J+20=0.691 — bon modèle mais à l'envers (score élevé = baisse prédite)
- Liquidité filtre : +5 à +7% de hit rate → filtre binaire confirmé
- Coefficient regime_bull fort à J+20/J+30, non significatif à court terme

### PERF — Backtest 10 ans (22 992 signaux, 2016–2026)
- AUC 0.51 tous scores confondus — signal technique structurellement nul
- Aucune formule de score ne performe mieux qu'une autre
- Conclusion : signal technique = bruit sur BRVM (ADR-016)

---

## 2026-05-17

### FIX — Labels et dates section Analyse Mistral
- Badge heatmap supprimé · Section fondamentaux renommée "Fondamentaux clés"
- Date analyse corrigée — updated_at (date réelle) au lieu de report_date (fin exercice)

---

## 2026-05-16

### FEAT — verify_decisions.py — vérification automatique signaux J-90
- Commit 7dfd294 — Hit rate 52.2% sur 550 signaux · ÉTAPE 3c pipeline active

### FEAT — verify_predictions.py — vérification prévisions GRU vs réel
- Commit a8145ec — Dir.Acc J+2=56.1% · J+5+=43.9% · GRU utile J+1/J+2 uniquement

### FIX — Badge "vs clôture J-1" sous les variations de prix
- Commit 3326f4c

### DATA — 47/47 tickers avec signal Mistral FY2025
- Couverture complète pour la première fois

---

## 2026-04-26

### FEAT — Composant FinancialAnalysis.jsx — 8 onglets complets
### FEAT — Prompt NYSE-style dans fundamental_analyzer.py
### FEAT — scrape_indices.py — BRVMC + BRVM30 quotidiens
### FEAT — scrape_commodities.py — Prix réels Yahoo Finance
### FEAT — Badge détresse relative dans DecisionCards
### FIX — Portfolio — vrais prix depuis fetchLiveData
### FIX — Contraste texte — #7d8590 → #1A202C

---

## 2026-04-21

### FEAT — Table corporate_events + scraper dividendes Sikafinance
### FEAT — Scraper calendrier RichBourse API JSON (674 events)
### FEAT — Badge dividende imminent dans DecisionCard

---

## 2026-04-18

### FEAT — Scraper fondamentaux 5 ans depuis stockanalysis.com
### FEAT — Score V2 fondamentaux + géopolitique
### FEAT — Badge Score V2 dans DecisionCard
