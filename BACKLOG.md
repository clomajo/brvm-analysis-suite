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
