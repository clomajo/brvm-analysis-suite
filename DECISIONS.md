# Décisions Architecturales — BRVM Analytics

Ce document trace les décisions importantes et leur justification.
Format : Contexte → Décision → Raison → Conséquences

---

## ADR-001 — Gel du modèle jusqu'au 01/07/2026
**Date :** 01/04/2026
**Décision :** Aucune modification de `generate_decisions.py` avant le 01/07/2026.
**Raison :** Valider le modèle en conditions réelles sur 90 jours sans changement.
**Conséquences :** Certains bugs et améliorations reportés. Accepté.

---

## ADR-002 — App.jsx monolithique (pas de composants séparés)
**Date :** Mars 2026
**Décision :** Tout le code frontend dans un seul fichier App.jsx.
**Raison :** macOS Catalina + Node v16 rend les imports complexes instables.
**Conséquences :** ~3500 lignes. Dette technique à résorber post juillet 2026.

---

## ADR-003 — ACHAT désactivé en régime BEAR
**Date :** 06/04/2026
**Décision :** Bloquer tous les signaux ACHAT quand market_regime = BEAR.
**Raison :** Alpha de -0.72% en régime BEAR documenté par backtest.

---

## ADR-004 — Supabase REST API plutôt que psycopg2
**Date :** Mars 2026
**Décision :** Utiliser l'API REST Supabase pour toutes les opérations de données.
**Raison :** psycopg2 échoue en GitHub Actions. REST fonctionne partout.

---

## ADR-005 — Scraping brvm.org plutôt qu'API officielle
**Date :** Mars 2026
**Décision :** Scraper les pages HTML de brvm.org avec BeautifulSoup.
**Raison :** La BRVM n'a pas d'API publique documentée.

---

## ADR-006 — Modèle gelé mais données non gelées
**Date :** 13/04/2026
**Décision :** Les corrections qui n'affectent pas `generate_decisions.py` sont autorisées pendant le gel.

---

## ADR-007 — Pricing B2B tiered
**Date :** Mars 2026
**Décision :** 150$/mois (broker), 500$/mois (trading floor), 5 000$/an (asset manager).

---

## ADR-008 — BOA Capital comme premier partenaire cible
**Date :** Avril 2026
**Décision :** Cibler BOA Capital Securities en priorité pour démonstration comparative.

---

## ADR-009 — Score V2 en mode informatif parallèle
**Date :** 18/04/2026
**Décision :** Score V2 calculé quotidiennement affiché comme badge Expérimental sans remplacer V1.

---

## ADR-010 — Pondération dynamique V2 par secteur
**Date :** 18/04/2026
**Décision :** Finance 60/40, Agro 80/20, Autres 70/30, Partielle 80/20, Aucune 100/0.

---

## ADR-011 — Score géopolitique multiplicateur statique mensuel
**Date :** 18/04/2026
**Décision :** CI 1.00, SN/BJ 0.95, TG 0.90, BF 0.75, ML 0.70, NE 0.65.
**Conséquences :** Migration vers table Supabase country_risk prévue (GÉOPOLITIQUE-01).

---

## ADR-012 — stockanalysis.com source données fondamentales
**Date :** 18/04/2026
**Décision :** Scraper stockanalysis.com sur 5 ans. Hebdomadaire GitHub Actions.

---

## ADR-013 — Archivage des tabs décoratifs + nouvelle architecture navbar
**Date :** 11/05/2026
**Décision :** Tabs Risque/Législatif/Direction/Macro/Matières/BOA vs BRVM masqués (code conservé).
**Navbar :** [Recherche] · Marché · Opportunités · Portefeuille · Obligations.

---

## ADR-014 — GRU utile uniquement à J+1/J+2 sur le BRVM
**Date :** 16/05/2026
**Résultats :** Dir.Acc J+2=56.1% · J+5=43.9% · Global=50.1%
**Décision :** Afficher J+1/J+2 comme fiables. J+5+ = indicatifs uniquement.

---

## ADR-015 — Features Mistral incompatibles avec modèles GRU
**Date :** 16/05/2026
**Résultats :** Dir.Acc 35.4% vs baseline 50.1% → -14.7 pts avec features Mistral.
**Décision :** Conserver GRU prix seul. Valeur Mistral = Opportunités uniquement.

---

## ADR-016 — Signal technique = bruit structurel sur le BRVM
**Date :** 25/05/2026
**Résultats :** AUC 0.51 sur 22 992 signaux (2016–2026).
**Décision :** Abandonner le signal technique post-dégel. V2 basé sur valorisation fondamentale.

---

## ADR-017 — Signal BOA cours cible = base du modèle V2
**Date :** 26/05/2026
**Résultats :** BUY hit rate 64.3% à J+20 sur 547 recommandations BOA.
**Décision :** cours_cible = dividende / rendement_cible_sectoriel comme signal principal V2.

---

## ADR-018 — Liquidité = filtre binaire éliminatoire
**Date :** 25/05/2026
**Résultats :** +5 à +7% hit rate en filtrant les illiquides.
**Décision :** Aucun signal ACHAT sur ticker illiquide. Seuil exact à calibrer juillet 2026.

---

## ADR-019 — Horizon de vérification = J+20 (remplace 90 jours)
**Date :** 26/05/2026
**Décision :** verify_decisions.py vérifie à J+20 au lieu de 90 jours.
**Raison :** Signal fondamental BOA peak à J+20. 90j croise trop d'événements exogènes.
**Implémenté :** 30/05/2026 (commit 07f46c6)

---

## ADR-020 — Univers V2 = moyennes caps uniquement (150-500B FCFA)
**Date :** 27/05/2026
**Résultats :** Moyenne cap médiane J+90=+11.0% vs grande cap +0.5% vs petite cap -2.1%.
**Décision :** Restreindre V2 aux caps 150-500B FCFA.
**Watchlist :** SOGC, SPHC, BOAS, BOABF, ONTBF, TTLC, BOAC.

---

## ADR-021 — Signal J-10 avant ex_dividend_date = fenêtre optimale
**Date :** 27/05/2026
**Résultats :** J-10 médiane +3.6%, 86% positifs (50 événements 2023-2026).
**Décision :** Fenêtre d'achat = J-10 avant ex_dividend_date.

---

## ADR-022 — Filtre qualité ROE>15% + P/B<2.5 = filtre éliminatoire V2
**Date :** 27/05/2026
**Résultats :** Filtre combiné : médiane J+90 +9.5% vs -2.0% hors filtre.
**Décision :** ROE>15% ET P/B<2.5 éliminatoire dans V2.

---

## ADR-023 — Modèle V2 en parallèle silencieux jusqu'au 01/07/2026
**Date :** 27/05/2026
**Décision :** V2 tourne dans scripts séparés sans remplacer generate_decisions.py.
**Bascule :** 01/07/2026 après vérification des 3 positions live.

---

## ADR-024 — fix_splits.py = source de vérité splits
**Date :** 29/05/2026
**Décision :** fix_splits.py est la source de vérité. Dry run obligatoire avant --apply.
**Conséquence :** Toute future correction de split passe par ce script.

---

## ADR-025 — Backup avant correction de masse
**Date :** 29/05/2026
**Décision :** Créer backup_historical_data.json avant toute opération de masse.

---

## ADR-026 — SQL Editor pour corrections de masse (pas REST PATCH)
**Date :** 29/05/2026
**Contexte :** fix_splits.py via PATCH REST = 47,000 requêtes ≈ 1h.
**Décision :** Toutes corrections de masse → SQL Editor Supabase (UPDATE direct).

---

## ADR-027 — Date signal V2 = 30 avril (correction look-ahead bias)
**Date :** 29/05/2026
**Contexte :** Utiliser janvier comme date signal = look-ahead bias (résultats FY non publiés).
**Décision :** Date signal = 30 avril de l'année suivante (4 mois après clôture FY).
**Impact :** Médiane J+90 passe de +5.9% à +7.8% — version honnête.

---

## ADR-028 — Pas de filtre décote maximum
**Date :** 29/05/2026
**Contexte :** Décotes >150% performent mieux (médiane +6.3%) que 60-150% (+5.1%).
**Décision :** Aucun plafond sur la décote — les grandes décotes sont le cœur du signal.

---

## ADR-029 — scrape_market_cap.py mensuel automatisé
**Date :** 30/05/2026
**Décision :** scrape_market_cap.py tourne automatiquement le 1er lundi du mois via GitHub Actions.
**Source :** stockanalysis.com/quote/brvm/{ticker}/statistics/
**Implémenté :** commit 7a069ae

---

## ADR-030 — target_prices = table historique quotidienne
**Date :** 30/05/2026
**Contexte :** Choix entre vue SQL, table hebdomadaire ou table quotidienne.
**Décision :** Table quotidienne avec contrainte UNIQUE (ticker, calcul_date).
**Raison :** L'historique des décotes permet de tracker quand un titre franchit le seuil ACHAT — utile pour le forward test juillet 2026. 17K lignes/an = négligeable pour Supabase.
**Conséquences :** calculate_target_price.py upsert quotidiennement dans le pipeline ÉTAPE 1f.

---

## ADR-031 — STYLE-01 fermé — react-markdown incompatible Vite 3
**Date :** 30/05/2026
**Contexte :** react-markdown cause des erreurs esbuild avec Vite 3.2.7.
**Décision :** Item fermé définitivement. Parser inline maison (split \n + détection ##) est le contournement validé.
**Conséquence :** Ne pas revisiter avant migration vers Vite 4+ (post juillet 2026).

---

## ADR-032 — EPS moyenne glissante 3 ans dans calculate_target_price.py
**Date :** 30/05/2026
**Contexte :** EPS ponctuel crée des décotes aberrantes (NTLC +1126%, PALC +127%).
**Décision :** Utiliser moyenne EPS sur 3 dernières années disponibles (filtre abs(eps) < 1e7).
**Raison :** EPS moyen lisse les années exceptionnelles et réduit les faux positifs.
**Conséquences :** Les tickers avec EPS structurellement non représentatif (NTLC, SNTS) restent aberrants — filtrés par critères cap+qualité V2 en aval.
