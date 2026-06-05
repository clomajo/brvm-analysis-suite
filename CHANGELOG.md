# Changelog — BRVM Analytics

Tous les changements notables sont documentés ici.
Format : `[DATE] TYPE: Description (commit)`

Types : `BUG` `FEAT` `FIX` `PERF` `DATA` `TEST` `INFRA`

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
