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

