# Changelog — BRVM Analytics

Tous les changements notables sont documentés ici.
Format : `[DATE] TYPE: Description (commit)`

Types : `BUG` `FEAT` `FIX` `PERF` `DATA` `TEST` `INFRA`

---

## 2026-06-21

### FIX — PER sectoriels hardcodés remplacés par lecture dynamique (ADR-010)
- **Repo:** brvm-analysis-suite
- **Description:** `calculate_target_price.py` utilisait 5 PER sectoriels hardcodés
  (Banque 12.4x, Agro 10.2x, Industrie 13.2x, Telecom 13.3x, Distribution 16.1x dans
  une version du SKILL.md ; Banque 10.0x, Agro 14.0x, Industrie 12.0x, Telecom 12.0x,
  Distribution 13.0x dans le code réel — incohérence documentation/code constatée).
  Les deux séries de valeurs étaient incohérentes avec les P/E sectoriels actuels
  publiés par BOA Capital Securities (écarts de -36% à +18% selon le secteur).
- **Cause racine:** Nomenclature à 5 catégories (Banque/Agro/Industrie/Telecom/
  Distribution) jamais alignée sur aucune classification officielle. La BRVM a
  introduit une nomenclature officielle à 7 secteurs depuis le 02/01/2025
  (Consommation de Base, Consommation Discrétionnaire, Énergie, Industriels,
  Services Financiers, Services Publics, Télécommunications), jamais adoptée ici.
- **Fix:** Migration complète vers les 7 secteurs officiels BRVM, mapping des 47
  tickers reconstruit depuis richbourse.com (source exhaustive). Nouvelle table
  `sector_per_history` alimentée manuellement chaque mois depuis le P/E 2024 du
  Tableau de Bord BOA Capital Securities (`update_sector_per.py`). Fallback
  documenté et tracé (`per_source` dans `target_prices`) si une valeur manque.
- **Bonus:** Corrige un bug préexistant — CFAC (CFAO Motors) apparaissait dans
  2 secteurs à la fois (agro ET distribution) dans l'ancien dict `SECTEURS`.
- **Impact:** Cours cible V2 recalculé pour tous les tickers avec une base
  sectorielle cohérente et actualisable, plutôt qu'une valeur figée et incertaine.

### FIX — Liste d'exclusion V2 statique remplacée par filtre data-quality (ADR-011)
- **Repo:** brvm-analysis-suite
- **Description:** Le SKILL.md référençait une liste d'exclusion V2
  (NTLC, SNTS, BOAN, BNBC, SICC, UNLC, ETIT, FTSC, CFAC, SIVC) présentée comme
  active. Vérification du code réel : cette liste n'avait **jamais été
  implémentée** — `calculate_target_price.py` traitait tous les tickers sans
  filtre, produisant des signaux erronés (ex: NTLC affichait une décote ACHAT
  de +433% du fait d'années EPS non consécutives mêlant des montants disparates).
  La liste documentée était aussi partiellement fausse : SNTS y figurait alors
  que ses données sont propres et consécutives.
- **Fix:** Nouveau filtre dynamique `evaluer_qualite_eps()` :
  1. Minimum 1 année EPS exploitable pour être éligible.
  2. Si 2+ années disponibles (jusqu'à 3) : doivent être consécutives.
  3. Exclusion si collapse EPS >80% YoY, quel que soit le nombre d'années.
  4. Cas à 1 seule année : accepté sans contrôle (impossible à vérifier avec
     un seul point) — compromis assumé pour ne pas exclure des tickers à forte
     capitalisation (ex: ORAC/Orange CI) uniquement par manque d'historique.
  Chaque exclusion est loggée avec sa raison précise à chaque run.
- **Tickers exclus au run du 21/06/2026:** BICC, BOAN, CFAC, NTLC, ORGT, SAFC,
  TTLC (années non consécutives, sauf BOAN pour collapse -92.1% YoY).
- **Tickers récupérés vs un seuil strict à 3 ans:** ORAC, ECOC, SIVC, STBC
  (1 an, acceptés sans contrôle) ; CABC (2 ans, propre).
- **Impact:** Décisions V2 plus fiables, basées sur un filtre vérifiable et
  documenté plutôt qu'une liste statique inexistante en pratique.

### INFRA — Taux d'actualisation 8% maintenu, origine documentée comme non traçable (ADR-009)
- **Repo:** brvm-analysis-suite
- **Description:** Revue déclenchée par la baisse du taux directeur BCEAO
  (-25 pdb, 3,25%→3,00%, mars 2026). Origine du 8% non retrouvée (probablement
  un document BOA Capital ancien, méthodologie non documentée). Le taux BCEAO
  (taux interbancaire, ~3%) n'est pas comparable structurellement à un taux
  d'actualisation de rendement actions (~8%) — pas de lien mécanique 1:1.
- **Décision:** Maintenu sans modification, faute de méthode de recalibration
  fiable. Documenté en ADR plutôt que recalibré à l'aveugle.

### FEAT — Script `update_sector_per.py` (saisie mensuelle des PER sectoriels)
- **Repo:** brvm-analysis-suite
- **Description:** CLI interactif demandant le P/E 2024 par secteur (7 valeurs),
  upsert dans `sector_per_history`. Source manuelle : Tableau de Bord BOA
  Capital Securities (Lettre quotidienne, page 2).

### FEAT — Script `parse_boa_dashboard.py` (non branché en production)
- **Repo:** brvm-analysis-suite
- **Description:** Parsing automatique du Tableau de Bord BOA par clustering de
  coordonnées de mots (le PDF n'a pas de grille de table détectable par
  `pdfplumber.extract_tables()`). Validation stricte avant écriture : échoue
  bruyamment si les 7 secteurs attendus ne sont pas tous trouvés avec des
  valeurs plausibles (1x–50x). Testé et fonctionnel sur le PDF du 18/06/2026.
- **Statut:** Non branché en production — le document source arrive par lien
  dans l'email (pas par pièce jointe), ce qui ajoute une complexité
  d'authentification non résolue dans le délai disponible avant le 01/07/2026.

### DATA — Table `sector_per_history` créée
- **Description:** secteur (CHECK sur les 7 valeurs officielles), per_2024,
  date_releve, source. RLS activé, lecture publique.

### DATA — Colonne `per_source` ajoutée à `target_prices`
- **Description:** Traçabilité de l'origine du PER utilisé par ligne
  (`sector_per_history` ou `fallback`) — CHECK constraint sur ces 2 valeurs.

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
