# Backlog BRVM Analytics

---

## 🟢 COMPLÉTÉS — 2026-05-30

### ✅ V2-06 — Retirer Palm Oil et Rubber de scrape_commodities.py
FUTR.KL et TOCOM-RUBBER.T retirés — HTTP 404 permanent. Commit efde604.

### ✅ DATA-14 — pymupdf dans requirements.txt
Déjà présent. Doublons (joblib, pypdf, feedparser) nettoyés. Commit 9212b00.

### ✅ fix_snts_updates.sql archivé
Déplacé Downloads → sql/ du repo. Commit 73474e9.

### ✅ ADR-029 — scrape_market_cap.py mensuel automatisé
Ajouté au workflow GitHub Actions (1er lundi du mois). Commit 7a069ae.

### ✅ UI-02 — Supprimer tab BOA vs BRVM
Tab et composant BOAComparison retirés. Commit 25a92a0.

### ✅ DATA-11 — Nettoyer doublons fundamental_analysis
45 lignes, 45 company_id distincts. Contrainte UNIQUE ajoutée.

### ✅ DATA-12 — Fondamentaux clés connectés à Supabase
FUND_DATA hardcodé remplacé par fetch company_fundamentals. ROE ajouté. Commit c6a03e8.

### ✅ V2-07 — EPS moyenne glissante 3 ans
fetch_fundamentals() retourne EPS moyen 3 ans. Commit dc52769.

### ✅ V2-05 — Table target_prices + upsert quotidien
Table créée (Supabase), upsert dans calculate_target_price.py, pipeline ÉTAPE 1f. Commit b939b53.

### ✅ V2-02 — verify_decisions.py horizon J+20
VERIFICATION_WINDOW 90 → 20 jours. Commit 07f46c6.

### ✅ CHART-01 — Ligne Fair Value style Morningstar
Ligne pointillée orange sur graphique historique depuis target_prices. Commit 9c65c31.

### ✅ UI-03 — Badge Fair Value V2 sur DecisionCards
Badge 🎯/📉 décote % + cours_cible sur chaque card. Fetch optimisé. Commit 965ef99.

### ✅ STYLE-01 — FERMÉ
react-markdown incompatible Vite 3.2.7 (ADR-031). Parser inline maison = solution définitive.

### ✅ scrape_eps_fy2025.py — INUTILE
FY2025 non encore publié pour BOAB/BOAC/BOAS/SOGC. scrape_all_v4.py capturera automatiquement dès publication. Pas de script nécessaire.

---

## 🟢 COMPLÉTÉS — sessions précédentes

### ✅ DATA-05/06 — Correction splits historiques (29/05/2026)
50 splits appliqués, 47,606 lignes corrigées. fix_splits.py = source de vérité.

### ✅ SNTS historique corrigé (29/05/2026)
2,476 updates. Données réelles 2016-2026 depuis SONATEL.xlsx.

### ✅ scrape_market_cap.py (29/05/2026)
45/46 tickers. market_cap + shares_outstanding dans company_fundamentals.

### ✅ DATA-10 — SICC/ONTBF données corrompues (05/05/2026)
Identifié et exclu du hit rate. historical_data corrigé.

### ✅ PRED-01 — GRU via Supabase REST (03/05/2026)
### ✅ PRED-02 — Tracking record prédictions (03/05/2026)
### ✅ SCORE-07 — verify_decisions.py Scorecard live (05/05/2026)
### ✅ FUND-07 — Signal fondamental dans brvm_decisions (03/05/2026)
### ✅ UI-01 — Badge signal_combine + data_completeness (03/05/2026)
### ✅ UI-04 — Badge "vs clôture J-1" (16/05/2026)
### ✅ DATA-13 — scrape_boc_pdf.py (26/05/2026)

---

## 🔴 BACKLOG ACTIF — POST-DÉGEL 01/07/2026

### V2-01 — Cours cible via rendement cible sectoriel
- **Priorité:** Haute — post-dégel
- **Description:** cours_cible = dividend_per_share / rendement_cible_sectoriel
- **Source rendement:** boa_recommendations.rendement historique moyen par ticker
- **Dépendance:** ADR-017, ADR-023

### V2-03 — Filtre liquidité binaire dans generate_decisions.py
- **Priorité:** Haute — post-dégel
- **Description:** Bloquer tout signal ACHAT si volume_20j < seuil
- **Note:** Ne pas modifier avant 01/07/2026 (ADR-001)
- **Dépendance:** DATA-17 (calibration seuil)

### V2-04 — Intégrer signaux V2 complets dans l'interface
- **Priorité:** Haute — post-dégel
- **Description:** Afficher signal J-10, cours_cible, décote dans Opportunités et fiche ticker
- **Note:** badge Fair Value V2 déjà déployé sur DecisionCards (UI-03 ✅)
- **Reste:** onglet dédié V2 dans fiche ticker

### DATA-17 — Calibrer seuil volume_20j pour filtre liquidité V2
- **Priorité:** Haute — juillet 2026
- **Action:** Analyser distribution volume_20j par liquidity_tier après dégel

### Forward test V2 — Checkpoint juillet 2026
- **Priorité:** Haute
- **Description:** Valider signal SPHC FY2025 + positions BOAB/BOAS/SOGC quand EPS FY2025 publiés
- **Échéance:** Juillet 2026 (90 jours après avril 2026)

---

## 🟠 BACKLOG ACTIF — PRIORITÉ MOYENNE

### DATA-10 — Corriger prix corrompus SICC et ONTBF
- **SICC:** Prix ~10x trop élevés — source Sikafinance à corriger
- **ONTBF:** Négociation suspendue — données à vérifier
- **Impact:** Fausse le hit rate ACHAT

### PRED-03 — Scorecard GRU auditable dans l'app
- Afficher taux direction correcte par ticker · MAPE réel vs théorique
- Alimenté par predictions_results

### FUND-08 — Gouvernance/Risk tab — données réelles
- extract_governance.py — re-parser 158 analyses Mistral → company_governance
- Priorité basse jusqu'à réactivation des tabs archivés

### GRU — Réentraînement sur données corrigées
- Relancer sur historical_data post-splits + SNTS corrigé
- Prérequis : vérifier MAPE réel vs théorique post juillet 2026

### PRED-04 — GRU multi-features (prix + RSI + volume)
- Features dynamiques (RSI, volume) à tester post juillet 2026
- Features statiques (Mistral) prouvées nuisibles (ADR-015)

---

## 🟡 BACKLOG ACTIF — PRIORITÉ BASSE

### SCORE-05 — Bonus dividende imminent dans score V2
- 0-30 jours → +8 points · 31-60 jours → +4 points — activer après juillet 2026

### SCORE-06 — Bonus AG dans score V2
- AG prévues dans 30 jours → +5 points

### FUND-06 — Notations BloomField Investment
- Notes crédit BOA group (BOAC, BOABF, BOAM) — 3-4 tickers seulement

### DATA-08 — Calendrier AG depuis brvm.org
- Compléter corporate_events avec type AG

### DATA-09 — Commodités tab — données réelles
- Pipeline Yahoo Finance quotidien déjà en place — connecter au frontend

### DATA-11 — Doublons fundamental_analysis — ✅ RÉSOLU
- Contrainte UNIQUE ajoutée. Clos.

### DATA-15 — FTSC dividende aberrant (75.73% rdt_net)
- Filtré par scrape_boc_pdf.py. Vérifier source réelle (coupon obligataire ?)

### DATA-16 — Enrichir EPS historique FY2019-FY2020
- stockanalysis.com ne remonte pas avant FY2021
- Alternative : BOC PDF archivés brvm.org depuis 2015

### SIGNAL-01 — Filtre détresse relative ⚠️ — ✅ DÉPLOYÉ
- Badge déjà en production (seuil -25pts vs BRVMC)

### SIGNAL-02 — Déduplication sectorielle BOA
- Alerte si 3+ titres même groupe en BUY simultané

### GÉOPOLITIQUE-01 — Migrer GEO_MULTIPLIER vers table Supabase
- country_risk table — remplace valeurs hardcodées dans generate_decisions.py

### Ajouter RPC Supabase apply_split
- Pour corrections futures de splits depuis Python sans SQL Editor

### Documents BRVM manquants
- CABC 2017, CIEC 2018, SIVC 2017 — confirmer facteurs estimés vs officiels
