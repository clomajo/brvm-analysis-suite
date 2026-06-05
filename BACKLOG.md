# Backlog BRVM Analytics

---

## 🟢 COMPLÉTÉS — 2026-06-04

### ✅ DATA-18 — Extraction ROE depuis analyses Mistral
Script `extract_roe_eps.py` — lit `analysis_summary` (pas `analysis_text`).
26/47 tickers avec ROE dans company_fundamentals FY2025.

### ✅ DATA-19 — Calcul EPS depuis net_income/shares_outstanding
`fill_eps_corrected.sql` exécuté. EPS = net_income × 1M / shares_outstanding.
20/47 tickers avec EPS. ROE calculé pour tickers manquants via net_income/total_equity.

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

---

## 🔴 BACKLOG ACTIF — PRIORITÉ HAUTE (post-dégel 01/07/2026)

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

### V2-01 — Cours cible via rendement cible sectoriel
- **Priorité:** Haute — post-dégel
- **Description:** cours_cible = dividend_per_share / rendement_cible_sectoriel
- **Source rendement:** boa_recommendations.rendement (en %, diviser par 100)
- **Note:** rendement BOA confirmé colonne `rendement` dans `boa_recommendations`
- **Dépendance:** ADR-017, ADR-023

### V2-03 — Filtre liquidité binaire dans generate_decisions.py
- **Priorité:** Haute — post-dégel
- **Description:** Bloquer tout signal ACHAT si volume_20j < seuil
- **Calibration:** ratio volume/shares_outstanding · seuils : >0.1%=liquide · 0.01-0.1%=peu liquide · <0.01%=illiquide
- **Note:** Ne pas modifier avant 01/07/2026 (ADR-001)

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
- **Description:** Valider signal SPHC FY2025 + positions BOAB/BOAC/BOABF/SNTS/NTLC
- **Échéance:** Juillet 2026

---

## 🟠 BACKLOG ACTIF — PRIORITÉ MOYENNE

### DATA-20 — Compléter ROE/EPS pour 21 tickers manquants
- **Description:** 21/47 tickers sans ROE · 27/47 sans EPS après session 04/06
- **Sources possibles :** rapports annuels BRVM · BOC PDF archivés · saisie manuelle pour tickers clés
- **Tickers prioritaires :** BOAC, CIEC, SMBC, CFAC, ETIT (ROE extrait mais EPS manquant)

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
