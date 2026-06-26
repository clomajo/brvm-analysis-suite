# Backlog BRVM Analytics

> **Note (25/06/2026) :** Ce fichier a été accidentellement écrasé par une
> page d'erreur Cloudflare (commit `78ff24a`, 04/06/2026) et restauré depuis
> l'historique Git (commit `dd25f47`) le 25/06/2026. Les items des sessions
> du 21/06 et du 23/06/2026 — documentés séparément dans
> `BACKLOG_nouveaux_items_21-06-2026.md` et
> `BACKLOG_nouveaux_items_23-06-2026.md` faute de pouvoir lire ce fichier à
> l'époque — sont réintégrés ci-dessous. Si ce fichier est de nouveau
> illisible un jour, vérifier `git log --follow -p -- BACKLOG.md` avant de le
> considérer comme perdu.

---

## 🟢 COMPLÉTÉS — 2026-06-25

### ✅ ADR-017 — Doublon Fair Value FinancialAnalysis.jsx corrigé
`FinancialAnalysis.jsx` lit désormais `target_prices` au lieu de recalculer
en JS (P/E 10x fixe). Courbe historique réelle (forward-fill), texte de
méthode dynamique (`per_ref`/`per_source`). Commit `c7294f6`.

### ✅ ADR-018 (partiel) — Détection eps non recalculé ajoutée
`check_eps_coherence()` dans `scrape_all_v4.py` — log un warning si `eps`
scrapé diverge de `net_income×1M/shares_outstanding` (>10%), sans jamais
corriger automatiquement. Commit `654bfd2`. **Correction des données
elle-même NON faite — voir item actif ci-dessous.**

---

## 🔴 BACKLOG ACTIF — PRIORITÉ HAUTE

### ADR-018 — Corriger eps NTLC/BICC/SOGC en base (après logs du 29/06)
- **Contexte :** `eps` scrapé tel quel depuis stockanalysis.com par
  `scrape_all_v4.py`, jamais recalculé depuis `net_income/shares_outstanding`.
  Confirmés incohérents au 25/06/2026 : NTLC (~20x, 3 années), BICC (~1.5x,
  4 années), SOGC (~0.73x, FY2021-2022 seulement — FY2023+ sains).
  **Lien avec DATA-19 (ci-dessous, déjà complété le 04/06/2026) :** un
  recalcul `eps = net_income×1M/shares_outstanding` avait déjà été fait une
  fois sur 20/47 tickers (`fill_eps_corrected.sql`) — probablement écrasé
  depuis par un run `scrape_all_v4.py --full` (chaque lundi), ce qui
  expliquerait pourquoi le problème est revenu sans qu'aucune session n'ait
  introduit de nouveau bug entre-temps.
- **Action :**
  1. Attendre les logs du run du lundi 29/06/2026 (`check_eps_coherence`,
     commit `654bfd2`) pour avoir la liste complète des tickers incohérents
     sur les 47, pas seulement les 3 déjà confirmés manuellement.
  2. Corriger `eps` en base par requête SQL ciblée pour chaque ticker confirmé
     (cf. ADR-026 — SQL Editor Supabase, jamais PATCH REST ligne par ligne).
  3. **Vérifier après coup que la correction persiste après le run suivant**
     du lundi d'après (06/07/2026) — c'est l'étape qui avait été oubliée pour
     ADR-012, et qui a permis au bug de revenir silencieusement pendant
     3 semaines sans être détecté.
  4. Si le problème touche un grand nombre de tickers (pas seulement 3),
     reconsidérer l'option rejetée en ADR-018 : recalcul automatique
     systématique de `eps` dans `scrape_all_v4.py` plutôt qu'un simple log.
- **Source :** Conversation du 25/06/2026, ADR-017/ADR-018.

### MODEL-01 — Modèle pragmatique BRVM (prochaine session)
- **Priorité:** Haute — à construire avant bascule 01/07/2026
- **Description:** Signal combiné : BOA_action + BOA_potential + ROE_relatif + momentum_MA20
- **Logique:**
  ```python
  signal_achat = (
      boa_action in ["BUY", "HOLD"]     # BOA pas négatif
      AND boa_potential > 5              # upside BOA > 5%
      AND roe > roe_median_secteur       # qualité relative
      AND prix > ma20                    # momentum positif
  )
  ```
- **Avantage vs V3 :** Utilise ce qu'on a réellement · backtestable · transparent · indépendant de BOA
- **Dépendance :** ROE sectoriel médian (calculable depuis company_fundamentals)
- **⚠️ À recroiser avec le modèle V2 (cours cible PER+Gordon, ADR-009/010/011)
  qui a depuis été construit et calibré entre le 20 et le 23/06/2026 — vérifier
  si ce MODEL-01 est encore pertinent en parallèle du V2 ou s'il est superseded.**

### V2-01 — Cours cible via rendement cible sectoriel
- **Priorité:** Haute — post-dégel
- **Description:** cours_cible = dividend_per_share / rendement_cible_sectoriel
- **Source rendement:** boa_recommendations.rendement (en %, diviser par 100)
- **Note:** rendement BOA confirmé colonne `rendement` dans `boa_recommendations`
- **⚠️ Possiblement déjà couvert par le modèle V2 actuel (composante Gordon
  30%, `calculate_target_price.py`, ADR-009) — à vérifier si distinct ou
  redondant avant de retravailler.**

### V2-03 — Filtre liquidité binaire dans generate_decisions.py
- **Priorité:** Haute — post-dégel
- **Description:** Bloquer tout signal ACHAT si volume_20j < seuil
- **Calibration:** ratio volume/shares_outstanding · seuils : >0.1%=liquide · 0.01-0.1%=peu liquide · <0.01%=illiquide
- **Note:** Ne pas modifier avant 01/07/2026 (ADR-001)

### V2-04 — Intégrer signaux V2 complets dans l'interface
- **Priorité:** Haute — post-dégel
- **Description:** Afficher signal J-10, cours_cible, décote dans Opportunités et fiche ticker
- **Note:** badge Fair Value V2 sur DecisionCards ✅, page "AI Fundamental
  Analysis" (`FinancialAnalysis.jsx`) ✅ corrigée le 25/06 (ADR-017)
- **Reste:** onglet Opportunités à vérifier/compléter avec les colonnes V2

### DATA-17 — Calibrer seuil volume_20j pour filtre liquidité V2
- **Priorité:** Haute — juillet 2026
- **Action:** Analyser distribution volume_20j par liquidity_tier après dégel

### Forward test V2 — Checkpoint juillet 2026
- **Priorité:** Haute
- **Description:** Valider signal SPHC FY2025 + positions BOAB/BOAC/BOABF/SNTS/NTLC
- **Échéance:** Juillet 2026
- **⚠️ NTLC est exclu du calcul V2 depuis ADR-011 — vérifier que ce checkpoint
  est toujours pertinent tel que formulé, ou l'ajuster en conséquence.**

### Mise à jour mensuelle des PER sectoriels (rituel — déjà en cours)
- **Contexte :** `sector_per_history` alimentée manuellement chaque mois via
  `update_sector_per.py`, depuis le P/E 2024 du Tableau de Bord BOA Capital
  Securities (Lettre quotidienne, page 2).
- **Action :** Rituel mensuel à tenir — sans mise à jour, fallback sur valeurs
  figées (datées du 18/06/2026), avec warning visible mais sans blocage.
- **Source :** ADR-010, conversation du 20-21/06/2026.

---

## 🟠 BACKLOG ACTIF — PRIORITÉ MOYENNE

### Intégration du pattern pré/post ex-dividende dans le signal V2
- **Contexte :** Intuition de Jocelyn (20/06/2026) — distincte de la stratégie
  de capture de dividende déjà validée (achat J-19, fill rate ≥75%).
  Intégrer la hausse anticipative pré-ex-div et la baisse mécanique post-ex-div
  directement comme composante du signal V2, plutôt que comme stratégie de
  timing séparée.
- **Action :**
  - Attendre les résultats de la régression 10 ans (weekend du 20-21/06) sur
    le point d'achat optimal post-ex-div.
  - Quantifier le pattern avant intégration — actuellement une intuition.
  - Ne pas traiter avant le 01/07/2026.
- **Source :** Conversation du 20-21/06/2026.

### Tickers à 1 seule année EPS — risque de représentativité
- **Contexte :** Le filtre ADR-011 accepte sans contrôle les tickers à 1 seule
  année EPS (ORAC, ECOC, SIVC, STBC au 21/06/2026) — risque résiduel assumé
  d'EPS atypique non représentatif.
- **Action (si matérialisé après le 01/07/2026) :** Surveiller les signaux V2
  sur ces tickers lors de la vérification live (dès 07/2026). Si signal
  erroné détecté : capper le poids du signal pour les tickers à 1 an, ou
  vérification manuelle ponctuelle.
- **Source :** Conversation du 21/06/2026 (ADR-011).

### DATA-20 — Compléter ROE/EPS pour 21 tickers manquants
- **Description:** 21/47 tickers sans ROE · 27/47 sans EPS après session 04/06
- **Sources possibles :** rapports annuels BRVM · BOC PDF archivés · saisie manuelle pour tickers clés
- **Tickers prioritaires :** BOAC, CIEC, SMBC, CFAC, ETIT (ROE extrait mais EPS manquant)
- **⚠️ À recouper avec ADR-018 avant de relancer un script de remplissage EPS
  — s'assurer que le nouveau remplissage ne sera pas écrasé par
  `scrape_all_v4.py` comme cela semble être arrivé pour DATA-19.**

### DATA-10 — Corriger prix corrompus SICC et ONTBF
- **SICC:** Prix ~10x trop élevés — source Sikafinance à corriger
- **ONTBF:** Négociation suspendue — données à vérifier
- **Impact:** Fausse le hit rate ACHAT

### PRED-03 — Scorecard GRU auditable dans l'app
- Afficher taux direction correcte par ticker · MAPE réel vs théorique
- Alimenté par predictions_results
- **Note (25/06/2026) :** Un Scorecard GRU live existe déjà dans le dashboard
  (47% direction correcte global, détail par ticker visible) — vérifier si
  cet item est déjà couvert ou s'il reste un écart fonctionnel.

### FUND-08 — Gouvernance/Risk tab — données réelles
- extract_governance.py — re-parser 158 analyses Mistral → company_governance
- Priorité basse jusqu'à réactivation des tabs archivés

### GRU — Réentraînement sur données corrigées
- Relancer sur historical_data post-splits + SNTS corrigé
- Prérequis : vérifier MAPE réel vs théorique post juillet 2026

### PRED-04 — GRU multi-features (prix + RSI + volume)
- Features dynamiques (RSI, volume) à tester post juillet 2026
- Features statiques (Mistral) prouvées nuisibles (ADR-015)

### Automatisation complète du parsing du Tableau de Bord BOA
- **Contexte :** `parse_boa_dashboard.py` écrit et testé (clustering de
  coordonnées, validation stricte 7 secteurs + bornes 1x-50x). Fonctionne sur
  le PDF du 18/06/2026. Non branché — document source arrive par lien email,
  pas par pièce jointe, complexité d'authentification non résolue avant 01/07.
- **Action :**
  - Vérifier si le lien pointe vers un PDF direct ou une visionneuse web.
  - Vérifier si une connexion à un portail BOA Capital est requise.
  - Si résolu : email (Gmail + Apps Script) → Drive → GitHub Actions →
    `parse_boa_dashboard.py --write`, alerte si échec validation.
- **Données source :** `sql_create_sector_per.sql`, `parse_boa_dashboard.py`
  déjà prêts. Saisie manuelle mensuelle via `update_sector_per.py` en attendant.
- **Source :** Conversation du 21/06/2026.

---

## 🟡 BACKLOG ACTIF — PRIORITÉ BASSE

### SCORE-05 — Bonus dividende imminent dans score V2
### SCORE-06 — Bonus AG dans score V2
### FUND-06 — Notations BloomField Investment
### DATA-08 — Calendrier AG depuis brvm.org
### DATA-09 — Commodités tab — données réelles
### DATA-15 — FTSC dividende aberrant (75.73% rdt_net)
### DATA-16 — Enrichir EPS historique FY2019-FY2020
### SIGNAL-02 — Déduplication sectorielle BOA
### GÉOPOLITIQUE-01 — Migrer GEO_MULTIPLIER vers table Supabase
### Ajouter RPC Supabase apply_split
### Documents BRVM manquants (CABC 2017, CIEC 2018, SIVC 2017)

---

## 🟢 COMPLÉTÉS — 2026-06-23

### ✅ ADR-012 — shares_outstanding NTLC corrigé (partiellement)
`shares_outstanding` corrigé en base (1 100 000 → 22 070 400), confirmé
persistant. **⚠️ Correction du 25/06/2026 : `eps` lui-même n'avait PAS été
recalculé/persisté malgré l'affirmation initiale — cf. ADR-018, item actif
ci-dessus.**

### ✅ Mettre à jour ARCHITECTURE.md/SKILL.md — composants frontend réels
Documenté `BOAComparison.jsx`, `Opportunities.jsx`, `FinancialAnalysis.jsx`
comme composants distincts. Complété définitivement le 25/06/2026 avec le
statut à jour d'ADR-017 (corrigé) et ADR-018.

---

## 🟢 COMPLÉTÉS — 2026-06-21

### ✅ ADR-009 — Taux d'actualisation 8% maintenu (documenté, pas modifié)
### ✅ ADR-010 — PER sectoriels migrés vers 7 secteurs officiels BRVM
### ✅ ADR-011 — Filtre data-quality EPS remplace liste d'exclusion statique
### ✅ update_sector_per.py — script de saisie mensuelle créé

---

## 🟢 COMPLÉTÉS — 2026-06-04

### ✅ DATA-18 — Extraction ROE depuis analyses Mistral
Script `extract_roe_eps.py` — lit `analysis_summary` (pas `analysis_text`).
26/47 tickers avec ROE dans company_fundamentals FY2025.

### ✅ DATA-19 — Calcul EPS depuis net_income/shares_outstanding
`fill_eps_corrected.sql` exécuté. EPS = net_income × 1M / shares_outstanding.
20/47 tickers avec EPS. ROE calculé pour tickers manquants via net_income/total_equity.
**⚠️ Voir ADR-018 (25/06/2026) : ce recalcul semble avoir été écrasé depuis
par un run `scrape_all_v4.py --full` — le même type de correction est
nécessaire à nouveau pour NTLC/BICC/SOGC à ce jour.**

### ✅ RESEARCH-01 — Exploration modèle Fair Value V3
Prototype DDM/PE hybride testé. Rejeté (ADR-033). Modèle pragmatique identifié.

---

## 🟢 COMPLÉTÉS — 2026-05-30

### ✅ V2-06 — Retirer Palm Oil et Rubber de scrape_commodities.py
### ✅ DATA-14 — pymupdf dans requirements.txt
### ✅ fix_snts_updates.sql archivé
### ✅ ADR-029 — scrape_market_cap.py mensuel automatisé
### ✅ UI-02 — Supprimer tab BOA vs BRVM
### ✅ DATA-11 — Nettoyer doublons fundamental_analysis
### ✅ DATA-12 — Fondamentaux clés connectés à Supabase
### ✅ V2-07 — EPS moyenne glissante 3 ans
### ✅ V2-05 — Table target_prices + upsert quotidien
### ✅ V2-02 — verify_decisions.py horizon J+20
### ✅ CHART-01 — Ligne Fair Value style Morningstar
### ✅ UI-03 — Badge Fair Value V2 sur DecisionCards
### ✅ STYLE-01 — FERMÉ (react-markdown incompatible)

---

## 🟢 COMPLÉTÉS — sessions précédentes

### ✅ DATA-05/06 — Correction splits historiques (29/05/2026)
### ✅ SNTS historique corrigé (29/05/2026)
### ✅ scrape_market_cap.py (29/05/2026)
### ✅ DATA-10 — SICC/ONTBF données corrompues (05/05/2026)
### ✅ PRED-01 — GRU via Supabase REST (03/05/2026)
### ✅ PRED-02 — Tracking record prédictions (03/05/2026)
### ✅ SCORE-07 — verify_decisions.py Scorecard live (05/05/2026)
### ✅ FUND-07 — Signal fondamental dans brvm_decisions (03/05/2026)
### ✅ UI-01 — Badge signal_combine + data_completeness (03/05/2026)
### ✅ UI-04 — Badge "vs clôture J-1" (16/05/2026)
### ✅ DATA-13 — scrape_boc_pdf.py (26/05/2026)
