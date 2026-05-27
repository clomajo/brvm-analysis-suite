# Backlog BRVM Analytics — Avril 2026
Voir fichier téléchargé pour version complète.

## 🟡 AJOUTS POST-21 AVRIL 2026

### SCORE-05 — Bonus dividende imminent dans score V2
Lire `corporate_events` pour calculer jours avant détachement.
- 0-30 jours → +8 points score V2
- 31-60 jours → +4 points score V2
Activer après juillet 2026.

### SCORE-06 — Bonus AG dans score V2
Lire `corporate_events` pour AG prévues dans 30 jours → +5 points.

### FUND-06 — Notations BloomField Investment
Scraper bloomfield-investment.com pour notes crédit BOA group (BOAC, BOABF, BOAM).
Intégrer dans score fondamental V2.
Priorité basse — couvre seulement 3-4 tickers.

### DATA-08 — Calendrier AG depuis brvm.org
Ajouter scraping des convocations AG depuis publications officielles BRVM.
Compléter `corporate_events` avec type AG en plus des dividendes.

### STYLE-01 — react-markdown pour rendre le texte Mistral
- **Priorité:** Haute
- **Description:** npm install react-markdown — rendre les 6 sections NYSE-style au lieu de les masquer
- **Impact:** Analyse Mistral lisible et structurée dans le tab Fondamentaux

### CHART-01 — Price vs Fair Value chart
- **Priorité:** Haute  
- **Description:** Calculer Fair Value = EPS moyen 3 ans × P/E ~10x — afficher sur graphique cours historique
- **Style:** Morningstar Equity Research

### SIGNAL-01 — Filtre détresse relative vs BRVM Composite
- **Priorité:** Moyenne
- **Description:** Badge ⚠️ sur titres sous-performant BRVM Composite de plus de X pts
- **Trigger:** YTD ticker < YTD BRVMC - 20pts

### SIGNAL-02 — Déduplication sectorielle BOA
- **Priorité:** Moyenne
- **Description:** Alerte si 3+ titres du même groupe (BOA, etc.) sortent BUY le même jour
- **Cas d'usage:** BOAB + BOABF + BOAS en BUY simultané = signal sectoriel, pas 3 opportunités indépendantes


---

## 🟢 COMPLÉTÉS — 2026-05-05

### ✅ DATA-10 — SICC/ONTBF données corrompues (identifié 05/05)
Prix SICC = 25 555 FCFA le 03/04 (réel ~4 290) → exclure du hit rate · Corriger historical_data

### ✅ PRED-01 — GRU via Supabase REST — COMPLÉTÉ 03/05
### ✅ PRED-02 — Tracking record prédictions — COMPLÉTÉ 03/05
### ✅ SCORE-07 — verify_decisions.py Scorecard live — COMPLÉTÉ 05/05
35 signaux vérifiés · 62.9% hit rate · ÉTAPE 3c pipeline active


## 🟢 COMPLÉTÉS — 2026-05-03

### ✅ FUND-07 — Signal fondamental dans brvm_decisions
extract_fundamental_signals.py opérationnel · signal_combine calculé · 41/47 tickers couverts

### ✅ PRED-01 — GRU via Supabase REST
prediction_analyzer_v2.py · 410 prédictions insérées · Tab Forecast GRU (IA) live

### ✅ PRED-02 — Tracking record prédictions
verify_predictions.py · Table predictions_results · Premier résultat : 14 mai 2026

### ✅ UI-01 — Badge signal_combine + data_completeness
DecisionCard enrichie · Badge bleu signal_combine · Badge données partielles/limitées

---

## 🔴 BACKLOG ACTIF — À FAIRE


### DATA-10 — Corriger prix corrompus SICC et ONTBF
- **Priorité:** Haute
- **SICC:** Prix 25 555 FCFA le 03/04 (réel ~4 290) — inflation ~10x détectée précédemment
- **ONTBF:** Négociation suspendue — données à vérifier
- **Impact:** Fausse le hit rate ACHAT (SICC exclu manuellement du calcul actuel)
- **Source:** Sikafinance fichiers historiques

### UI-02 — Supprimer tab "BOA vs BRVM"
Trop peu d'utilité · Réduire le nombre de tabs

### UI-03 — Ligne résumé multi-indicateurs dans DecisionCard
Format : 📊 Score 76 · GRU +2.2% · 💰 Dividende 10j · Fondamental positif
Lire depuis brvm_decisions + predictions + corporate_events

### PRED-03 — Scorecard GRU auditable dans l'app
Afficher taux direction correcte par ticker · MAPE réel vs MAPE théorique · Évolution dans le temps
Alimenté par predictions_results

### STYLE-01 — react-markdown pour texte Mistral
npm install react-markdown · Rendre les 6 sections NYSE-style

### DATA-09 — Commodités tab — données réelles
Remplacer PRNG restant · Pipeline Yahoo Finance quotidien déjà en place

### FUND-08 — Gouvernance/Risk tab — données réelles
extract_governance.py · Re-parser 158 analyses Mistral → company_governance

### FUND-09 — Fundamentals comme 5e facteur de scoring
extract_fundamentals.py · Intégrer P/E, dividende, croissance dans generate_decisions.py

### PRED-04 — GRU multi-features (prix + RSI + volume)
- **Priorité:** Basse — post juillet 2026
- **Référence:** arxiv.org/html/2501.17366v1 — "GRU/LSTM for Financial Time Series Prediction"
- **Description:** Le papier démontre que les modèles GRU hybrides avec features supplémentaires surpassent GRU prix seul. Actuellement prediction_analyzer_v2.py utilise uniquement close_price comme feature d'entrée.
- **Améliorations proposées:**
  - Ajouter RSI(14) comme feature d'entrée
  - Ajouter volume normalisé
  - Considérer mécanisme d'attention (GRU + Attention layer)
  - Gérer les gaps de liquidité BRVM (jours sans transaction)
- **Prérequis:** Tracking record 14 mai 2026 — vérifier MAPE réel vs théorique avant de modifier les modèles
- **Impact attendu:** Réduction MAPE sur tickers liquides (SGBC, SNTS, ECOC) · Moins d'impact sur tickers illiquides
- **Note:** Marché frontier BRVM = moins efficient → patterns GRU persistent plus longtemps qu'en marché développé. Avantage structurel à exploiter.

---

## 2026-05-16 — Mises à jour

### ✅ PRED-02 — verify_predictions.py opérationnel
Dir.Acc J+2=56.1%, J+5+=43.9%. GRU utile J+1/J+2 uniquement.

### ✅ SCORE-03 — verify_decisions.py opérationnel
Hit rate 52.2% sur 550 signaux. Tourne quotidiennement ÉTAPE 3c.

### ✅ DATA-11 — 47/47 tickers signal Mistral FY2025
Couverture complète. CBIBF/FTSC/BOAS/SIVC/PRSC complétés.

### ✅ UI-04 — Badge "vs clôture J-1" déployé
Note discrète sous les variations de prix. Commit 3326f4c.

### ❌ PRED-05 — GRU + features Mistral (signal + CA%)
Testé sur Colab — Dir.Acc 35.4% vs baseline 50.1%. Rejeté.
Features statiques Mistral nuisent aux séries temporelles.
Valeur Mistral = Opportunités uniquement.

### PRED-04 — GRU multi-features (prix + RSI + volume)
Mise à jour priorité : tester RSI/volume avant features fondamentales.
Features statiques (signal Mistral) prouvées nuisibles. Features
dynamiques (RSI, volume) à tester en priorité post juillet 2026.

---

## 2026-05-17 — Nouveaux items

### DATA-11 — Nettoyer doublons fundamental_analysis
- **Priorité:** Basse — post dégel 01/07/2026
- **Description:** company_id=42 a 3 entrées en double dans fundamental_analysis
- **Fix:** DELETE doublons, garder updated_at le plus récent par company_id
- **Puis:** ALTER TABLE fundamental_analysis ADD CONSTRAINT unique_company UNIQUE(company_id)
- **Impact actuel:** Neutralisé par order=updated_at.desc&limit=1 dans le frontend

### DATA-12 — Fondamentaux clés — connecter à Supabase
- **Priorité:** Basse — post dégel 01/07/2026
- **Description:** Section "Fondamentaux clés" utilise un objet JS hardcodé (~lignes 3493-3504) pour ~15 tickers seulement
- **Fix:** Lire depuis company_fundamentals (Supabase) — colonnes pe_ratio, pb_ratio, div_yield, shares_outstanding
- **Impact:** Badge ⚠️ Données estimées disparaît · couverture 43/47 tickers

---

## 2026-05-25/26 — Nouveaux items

### ✅ PERF-01 — Régression logistique live (25/05/2026)
Hit rate J+5=39% J+10=36% — signal inversé sur période baissière.
Liquidité filtre confirmé +5 à +7%. Backtest 10 ans lancé.

### ✅ PERF-02 — Backtest 10 ans signal V1 (25/05/2026)
22 992 signaux — AUC 0.51 structurel. Signal technique = bruit confirmé.
Scripts : regression_brvm_horizons.py + backtest_regression.py

### ✅ DATA-13 — scrape_boc_pdf.py — Bulletin Officiel de la Cote (26/05/2026)
PER, dividende, rdt_net, date_dividende pour 47 tickers/jour.
Intégré pipeline ÉTAPE 1b. Filtre rdt_net > 20%. Commit b8fc9f6.

### V2-01 — Cours cible par ticker (post-dégel 01/07/2026)
- **Priorité:** Haute — base modèle V2
- **Description:** Calculer `cours_cible = dividend_per_share / rendement_cible_sectoriel` pour chaque ticker
- **Source dividende:** company_fundamentals (scrape_boc_pdf.py quotidien)
- **Source rendement cible:** boa_recommendations.rendement historique moyen par ticker
- **Signal:** ACHAT si potentiel > +10% + liquide + dividende disponible
- **Dépendance:** ADR-017

### V2-02 — Modifier verify_decisions.py horizon J+20 (post-dégel 01/07/2026)
- **Priorité:** Haute
- **Description:** Remplacer vérification 90 jours par J+20
- **Raison:** ADR-019 — signal BOA peak à J+20, 90j = trop d'événements exogènes
- **Impact:** Résultats de vérification plus rapides et plus propres

### V2-03 — Filtre liquidité binaire dans generate_decisions.py (post-dégel)
- **Priorité:** Haute
- **Description:** Bloquer tout signal ACHAT si volume_20j < seuil (à calibrer juillet)
- **Raison:** ADR-018 — liquidité filtre +5 à +7% hit rate confirmé
- **Note:** Ne pas modifier avant 01/07/2026 (ADR-001)

### DATA-14 — pymupdf dans requirements.txt CI GitHub Actions
- **Priorité:** Haute — bloquant pour pipeline CI
- **Description:** scrape_boc_pdf.py utilise pymupdf mais non déclaré dans requirements.txt
- **Fix:** Ajouter `pymupdf` dans requirements.txt
- **Impact:** GitHub Actions échoue silencieusement sans cette dépendance

### DATA-15 — FTSC dividende aberrant dans bulletin BRVM
- **Priorité:** Basse — informatif
- **Description:** FTSC affiche dividende 1726 FCFA / rdt_net 75.73% dans le bulletin officiel
- **Statut:** Filtré par rdt_net > 20% dans scrape_boc_pdf.py
- **À vérifier:** Source réelle dividende FTSC (confusion avec coupon obligataire ?)
