# Changelog — BRVM Analytics

Tous les changements notables sont documentés ici.
Format : `[DATE] TYPE: Description (commit)`

Types : `BUG` `FEAT` `FIX` `PERF` `DATA` `TEST` `INFRA`

---

## 2026-06-28

### FIX — Analyse fondamentale bloquée sur Q3 2025 : contrainte SQL parasite (ADR-019)
- **Repo:** brvm-analysis-suite / Supabase
- **Commit:** `d2c0a13` (Python) + correction SQL en base
- **Description:** L'analyse Mistral de SONATEL restait figée sur le rapport
  T3 2025 malgré la publication du T1 2026 (17/04/2026). Cause racine : la
  table `fundamental_analysis` avait une contrainte parasite
  `unique_company_fundamental` (`UNIQUE(company_id)`) — non documentée nulle
  part — qui n'autorisait qu'UN rapport par société. Chaque tentative de
  sauvegarde d'un nouveau rapport échouait avec `duplicate key`, APRÈS que le
  PDF ait été téléchargé, extrait et analysé par Mistral (travail payant perdu).
- **Fix SQL:** suppression de `unique_company_fundamental` ; la table revient à
  sa contrainte d'origine `fundamental_analysis_report_url_key`
  (`UNIQUE(report_url)`), cohérente avec le `ON CONFLICT (report_url)` du code.
  Doublon de contrainte créé pendant l'opération nettoyé ensuite.
- **Fix Python:** `_find_all_reports()` lisait le titre depuis le texte du lien
  (`"Télécharger"`, générique) au lieu du vrai titre dans le `<strong>` du
  `<tr>`. Nouvelle fonction `_parse_date_from_titre()` extrait une date précise
  par type de rapport (trimestre/semestre/annuel). Tri par date enfin fiable.
- **Impact:** dès le prochain run, T1 2026 et les rapports manquants pour les
  sociétés déjà en base pourront s'enregistrer.

### FIX — Prompts Mistral sans valorisation chiffrée (ADR-020)
- **Repo:** brvm-analysis-suite
- **Commit:** `0a8deab`
- **Description:** Les 3 prompts (DeepSeek/Gemini/Mistral) demandaient à l'IA
  de calculer un objectif de cours via "P/E sectoriel ~10x" — le même P/E 10x
  obsolète éliminé du frontend en ADR-017, réintroduit ici dans le prompt.
  Retiré : l'analyse IA se concentre sur le qualitatif, le cours cible vient
  exclusivement du modèle V2 (`target_prices`). Instruction explicite ajoutée
  pour empêcher l'IA de réintroduire un prix.

### PERF — Sobriété quota Mistral : retrait UPSERT + cadence bi-hebdomadaire (ADR-021)
- **Repo:** brvm-analysis-suite
- **Commits:** `0a8deab` (UPSERT) + `29dfde2` (workflow)
- **Description:** Quota API Mistral (plan Free) épuisé à 100% avant fin de mois.
  Deux causes : (1) le mode UPSERT régénérait TOUT l'historique d'analyses à
  chaque run quotidien (`_load_analysis_memory_from_db` vidait la mémoire de
  skip) ; (2) les étapes 5 et 6 (toutes deux Mistral) tournaient quotidiennement.
- **Fix:** UPSERT retiré — un rapport déjà analysé est skippé définitivement.
  Étapes 5 et 6 passées en bi-hebdomadaire (1er et 15 du mois) via garde
  `DOM=$(date +%d)`.
- **Impact:** consommation Mistral fortement réduite. Délai max d'analyse d'un
  nouveau rapport : jusqu'au prochain 1er ou 15 (acceptable pour des
  fondamentaux trimestriels).

---

## 2026-06-25

### FIX — Doublon de calcul Fair Value corrigé (ADR-017)
- **Repo:** brvm-analytics (frontend)
- **Commit:** `c7294f6`
- **Description:** `FinancialAnalysis.jsx` recalculait sa propre Fair Value
  en JavaScript (P/E sectoriel 10x fixe, aucun filtre data-quality),
  indépendamment de `target_prices`. Remplacé par une lecture directe de
  `target_prices` (dernières 180 lignes par ticker), identique à la logique
  déjà utilisée par `App.jsx`.
- **Détail :**
  - Graphique "Cours vs Fair Value — 3 ans" : ligne plate remplacée par une
    vraie courbe historique (forward-fill depuis `target_prices`).
  - Texte de méthode : `per_ref`/`per_source` affichés dynamiquement au lieu
    du "P/E sectoriel 10x" fixe.
  - Tickers exclus ADR-011 : affichage "N/D" (comportement déjà géré par le
    JSX existant).
- **Outil :** script de patch `patch_adr017_fairvalue.py`, testé par
  validation croisée (patch manuel vs script) avant déploiement.
- **Impact :** Dashboard et page "AI Fundamental Analysis" affichent
  désormais la même Fair Value pour un ticker donné — fin de la divergence
  documentée en ADR-017.

### BUG — eps non recalculé depuis stockanalysis.com, cause racine identifiée (ADR-018)
- **Repo:** brvm-analysis-suite
- **Commit:** `654bfd2`
- **Description:** Suite à la correction ADR-017, NTLC affichait toujours
  une Fair Value aberrante (80 007 FCFA, +433%) — pas un bug d'affichage
  cette fois, mais une donnée `target_prices` fausse à la source (ligne du
  30/05/2026, calculée avec un `eps` jamais corrigé).
- **Cause racine :** `scrape_all_v4.py` récupère `eps` tel quel depuis le
  champ "EPS (Basic)" de stockanalysis.com, sans jamais le recalculer depuis
  `net_income/shares_outstanding`. La correction `shares_outstanding`
  d'ADR-012 n'a donc jamais corrigé `eps` en base — soit la correction n'a
  jamais été persistée, soit elle a été écrasée par le scraping hebdomadaire
  suivant (`scrape_all_v4.py --full`, tous les lundis, immédiatement suivi de
  `calculate_target_price.py` dans le même run GitHub Actions).
- **Correction d'ADR-012 :** l'affirmation "eps recalculé et corrigé pour
  NTLC" dans ADR-012 était fausse — vérification directe du 25/06/2026 montre
  que `company_fundamentals.eps` contient toujours les valeurs d'avant
  correction.
- **Ampleur élargie :** vérification systématique (`eps` stocké vs
  `net_income×1M/shares_outstanding`) sur tout `company_fundamentals` a
  confirmé 2 tickers de plus : **BICC** (ratio ~1,5x, 4 années touchées) et
  **SOGC** (ratio ~0,73x, mais seulement FY2021-2022 — FY2023+ sains).
- **Fix (partiel) :** nouvelle fonction `check_eps_coherence()` dans
  `scrape_all_v4.py` — recalcule l'`eps` théorique et log un warning explicite
  si l'écart dépasse 10%. **Ne corrige jamais `eps` automatiquement** — choix
  délibéré pour éviter de propager silencieusement une erreur amont sur
  `net_income`/`shares_outstanding`, et pour ne pas répéter l'erreur ADR-012
  (correction non vérifiée après coup).
- **Limite documentée :** `shares_outstanding` n'est scrapé que pour l'année
  courante (FY2025) ; la vérification sur FY2021-2024 réutilise cette valeur
  par approximation (hypothèse "nombre d'actions constant" — risque de
  faux-positif en cas de split/augmentation de capital non documenté).
- **Tests :** validé sur NTLC/BICC/SOGC (3/3, 2/2, et précisément FY2021-2022
  seulement pour SOGC) + 4 cas sains sans faux positif (SPHC, SGBC, NSBC,
  ORGT) + cas limites (None, zéro).
- **Statut :** Correction des données (NTLC/BICC/SOGC) reportée à après le
  run du lundi 29/06/2026, pour disposer de la liste complète des tickers
  touchés avant correction SQL persistante.

---

## 2026-06-23

### FIX — Correction shares_outstanding NTLC (ADR-012)
- **Repo:** brvm-analysis-suite / Supabase
- **Description:** Signalement utilisateur direct sur l'app : Fair Value
  NTLC affichait une décote de +433% (cours cible 80 006,67 FCFA vs cours
  réel 15 005 FCFA). Cause racine : `shares_outstanding` dans
  `company_fundamentals` stocké à 1 100 000 au lieu de 22 070 400 (facteur
  d'erreur ×20), provenant de la source stockanalysis.com elle-même
  (probable split d'actions non répercuté côté agrégateur), pas d'un bug du
  pipeline de scraping.
- **Validation:** 3 sources indépendantes convergentes (richbourse.com, BOA
  Capital — Tableau de Bord 18/06/2026, Sikafinance) confirment 22 070 400
  actions. EPS recalculé après correction validé à la décimale contre les
  BNPA Sikafinance (822,37 vs 822,00 pour FY2024, etc.).
- **Vérification systémique:** les 45 autres tickers avec `shares_outstanding`
  renseigné ont été contrôlés (`market_cap / shares_outstanding` vs cours
  réel) — aucun autre cas similaire détecté, problème confirmé isolé à NTLC.
- **Fix:** `shares_outstanding` et `eps` corrigés dans `company_fundamentals`
  pour NTLC. Ligne `target_prices` aberrante (calcul_date 2026-06-21)
  supprimée manuellement par requête SQL ciblée.
  **⚠️ Correction du 25/06/2026 :** seul `shares_outstanding` a réellement
  persisté en base. `eps` contient toujours les valeurs fausses d'avant
  correction (cf. entrée du 25/06/2026, ADR-018, qui identifie la cause
  racine — `eps` n'est jamais recalculé par le pipeline de scraping).
- **Non-impact:** NTLC reste exclu du calcul V2 par le filtre data-quality
  (ADR-011, années EPS non consécutives) — cette correction n'affecte pas
  les signaux V2 actuels, elle assainit uniquement la donnée de base.

### BUG — Doublon de calcul Fair Value identifié, NON corrigé (ADR-017)
- **Repo:** brvm-analytics (frontend)
- **Description:** Investigation du signalement NTLC a révélé l'existence
  d'un composant frontend séparé et jusque-là non documenté,
  `src/components/FinancialAnalysis.jsx` (page "AI Fundamental Analysis"),
  qui recalcule sa propre Fair Value **directement en JavaScript**,
  indépendamment de `target_prices` :
  - P/E sectoriel codé en dur à 10x (aucun lien avec `sector_per_history`,
    ADR-010)
  - Pas de filtre data-quality équivalent à `evaluer_qualite_eps()` (ADR-011)
  - Pas de garde-fou de plausibilité (le composant principal `App.jsx` a un
    filtre `decote_pct < 200` que celui-ci n'a pas)
  - EPS lu depuis `company_fundamentals` filtré sur `fiscal_year=eq.FY2025`
    uniquement (logique de fallback non encore investiguée en détail)
- **Impact:** la page "AI Fundamental Analysis" continue d'afficher des
  Fair Value potentiellement aberrantes pour NTLC et tout autre ticker à
  donnée source défaillante, même après la correction ADR-012. Le composant
  principal (DecisionCard, `App.jsx`) n'est pas affecté.
- **Statut:** NON corrigé à ce jour — reporté à une session ultérieure.
  Approche retenue : faire lire à `FinancialAnalysis.jsx` l'historique déjà
  présent dans `target_prices` (plusieurs lignes par `calcul_date`) plutôt
  que de dupliquer la logique Python en JavaScript — permettrait aussi
  d'afficher une vraie courbe Fair Value dans le temps plutôt qu'une ligne
  plate. Alternative (Edge Function de calcul partagé) jugée disproportionnée.

### DOC — Correction architecture frontend (ADR-002 mis à jour)
- **Description:** `ARCHITECTURE.md`/`SKILL.md` décrivaient le frontend
  comme "App.jsx monolithique, pas de composants séparés" (ADR-002, mars
  2026). Découverte de 3 fichiers composants distincts dans
  `src/components/` (`BOAComparison.jsx`, `Opportunities.jsx`,
  `FinancialAnalysis.jsx`) lors de l'investigation du bug Fair Value
  ci-dessus. Documentation corrigée pour refléter l'architecture réelle.

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

## 09/07/2026

### FIX
- NTLC : correction prix historiques pré-2017-09-11 (÷20, split réel
  confirmé BRVM Avis N°164-2017/BRVM/DG). 361 lignes corrigées dans
  historical_data. Voir ADR-032.

## 30-31/07/2026

### FIX
- **T16-backfill** : rétro-remplissage `alpha`/`benchmark_return` sur
  `brvm_decisions_results`. Couverture 100% (3135/3135), 3088 lignes mises
  à jour. Clé de cohorte `(signal_date, verification_date)` — le 16/05
  mêlait deux cohortes aux fenêtres de détention différentes. Voir ADR-039.
  Le plan de remédiation formel (T0→T17) est désormais intégralement clos.

### CONSTAT — deux bugs documentés, non corrigés
- **ADR-040** : `corporate_events.DIVIDEND_HISTORY.fiscal_year` retarde d'un
  an (`scrape_corporate_events.py:161`, `str(int(year)-1)` erroné). La
  jointure sur `fiscal_year` attribue à chaque ex-date le montant de l'année
  suivante — look-ahead. **77 des 89 cycles** de
  `dividend_cycle_exploration.csv` sont touchés, donc E2.6, E2.7-A, E2.7-B,
  T5c-A et T9 volet A. Le filtre `yield >= 8%` de T9 ayant sélectionné les
  trades sur le rendement de l'année suivante, le verdict de gel de la
  Phase 13 est fragilisé (ne réhabilite pas V2 : T6 et T14 sont
  indépendants). Preuve documentaire : avis BRVM exercice 2025 + avis de
  crédit du courtier.
- **ADR-041** : `company_fundamentals.dividend_per_share` mélange brut et
  net selon le script qui écrit en dernier — `scrape_all_v4.py`
  (stockanalysis) écrit du brut, `scrape_boc_pdf.py` (BOC BRVM) du net.
  17 tickers sur 24 à résidu nul après division par le facteur IRVM du pays.
  Pas d'erreur de calcul actuelle (Gordon s'applique au brut), mais risque
  latent : le filtre `eps=not.is.null` écarte les lignes BOC par accident.
  Décision de convention en attente.

### DOCS
- ADR-039, ADR-040, ADR-041 ajoutés à `DECISIONS.md`
- `tools/backfill_alpha.py`, `tools/diag_decalage_montants.py`,
  `tools/diag_decalage_fiscal_year.py` (ce dernier **invalidé** : le cours
  BRVM ne s'ajuste pas du montant du dividende à l'ex-date — résultat
  négatif conservé pour ne pas refaire l'erreur)

### KNOWN ISSUE
- `tools/killswitch_check.py` : aucun filtre sur `signal` (ligne 82) et
  seuils fixés à 0 alors que la médiane structurelle de l'alpha d'univers
  vaut -1.84. Se déclenche en permanence, ne mesure rien.


## 10/08/2026

Aucun code produit — session d'investigation et de décision.

- DOC : ADR-044 — fermeture onglet Prévisions (GRU MASE 1.888, direction 47.9 %) ;
  lève le bloquant « doc GRU » de la session 27/07 ; nav cible 12 → 10 onglets
- DOC : ADR-045 — spec home (fusion Aperçu + Marché) formalisée ; blocage « Volume vs moy. »
  levé, donnée confirmée réelle (`volume` 100 % de couverture, `volRatio` calculé sur fetch réel)
- DOC : ADR-046 — Bulletin Officiel de la Cote retenu comme source de référence marché.
  Pattern d'URL déterministe `boc_AAAAMMJJ_2.pdf` vérifié sur 13 dates (2023→2026),
  sans expiration ; règle 404 = jour non ouvré ; rupture de taxonomie sectorielle documentée
- DOC : ADR-047 — PER sectoriels BOC : injection dans V2 explicitement reportée, V2 reste gelé
- INFRA : inventaire Supabase — `new_market_indicators` et `new_market_events` vides,
  `v_latest_market_data` mal nommée, `historical_data.value` morte (14,9 %)
- FIX (à traiter) : `market_cap.scraped_at` figé au 27/05/2026 → `scrape_market_cap.py`
  possiblement en panne depuis 2,5 mois — porté au backlog en priorité haute
