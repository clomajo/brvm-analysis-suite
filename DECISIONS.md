# Décisions Architecturales — BRVM Analytics

Ce document trace les décisions importantes et leur justification.
Format : Contexte → Décision → Raison → Conséquences

---

## ADR-001 — Gel du modèle jusqu'au 01/07/2026
**Date :** 01/04/2026
**Contexte :** Le modèle v1 vient d'être déployé. Des améliorations sont possibles.
**Décision :** Aucune modification de `generate_decisions.py` avant le 01/07/2026.
**Raison :** Pour valider le modèle en conditions réelles, il faut une période de 90 jours sans changement. Modifier les règles en cours de test invaliderait la vérification.
**Conséquences :** Certains bugs d'affichage et améliorations fondamentales sont reportés. Accepté.

---

## ADR-002 — App.jsx monolithique (pas de composants séparés)
**Date :** Mars 2026
**Contexte :** Architecture React standard suggère de séparer les composants.
**Décision :** Tout le code frontend dans un seul fichier App.jsx.
**Raison :** Contrainte technique — macOS Catalina + Node v16 rend les imports complexes instables. Patch via terminal Python plus fiable qu'une architecture multi-fichiers dans cet environnement.
**Conséquences :** Fichier de ~3500 lignes difficile à maintenir. Dette technique à résorber après juillet 2026 si migration vers machine plus récente.

---

## ADR-003 — ACHAT désactivé en régime BEAR
**Date :** 06/04/2026
**Contexte :** Le backtest montre alpha de -0.72% en régime BEAR.
**Décision :** Bloquer tous les signaux ACHAT quand market_regime = BEAR.
**Raison :** Un signal ACHAT avec alpha négatif nuit aux clients et à la crédibilité de la plateforme. Mieux vaut ne pas signaler que mal signaler.
**Conséquences :** En période BEAR, seuls SURVEILLER et EVITER sont émis. Testé par T6 automatiquement.

---

## ADR-004 — Supabase REST API plutôt que psycopg2
**Date :** Mars 2026
**Contexte :** Connexion directe PostgreSQL via psycopg2 échoue en GitHub Actions.
**Décision :** Utiliser l'API REST Supabase pour toutes les opérations de données.
**Raison :** psycopg2 nécessite des credentials DB directs qui posent des problèmes de réseau en CI. L'API REST fonctionne partout avec la clé service_role.
**Conséquences :** Requêtes légèrement plus lentes. Certaines opérations complexes (GROUP BY, LATERAL) nécessitent des workarounds en Python.

---

## ADR-005 — Scraping brvm.org plutôt qu'API officielle
**Date :** Mars 2026
**Contexte :** La BRVM n'a pas d'API publique documentée.
**Décision :** Scraper les pages HTML de brvm.org avec BeautifulSoup.
**Raison :** Seule option disponible. La structure HTML est stable depuis plusieurs années.
**Conséquences :** Fragile si la BRVM change la structure de ses pages. Risque à monitorer via T1 (moins de 47 tickers détectés).

---

## ADR-006 — Modèle gelé mais données non gelées
**Date :** 13/04/2026
**Contexte :** Le gel du modèle (ADR-001) ne doit pas empêcher les corrections de bugs de données.
**Décision :** Les corrections qui n'affectent pas `generate_decisions.py` sont autorisées pendant la période de gel.
**Raison :** Un bug de fetcher (1 secteur sur 7) ou d'affichage (52-week high/low) n'impacte pas la logique de scoring. Le corriger améliore la qualité sans biaiser le test.
**Conséquences :** Distinction claire entre "modèle" (gelé) et "données/affichage" (corrigeable).

---

## ADR-007 — Pricing B2B tiered
**Date :** Mars 2026
**Contexte :** Positionnement institutionnel vs retail.
**Décision :** 3 tiers — 150$/mois (broker individuel), 500$/mois (trading floor), 5 000$/an (asset manager).
**Raison :** La valeur créée est proportionnelle au volume d'actifs gérés. Un asset manager gérant 100M$ paie proportionnellement moins qu'un broker individuel.
**Conséquences :** Nécessite une infrastructure d'authentification et de gestion des accès (Phase 5 du roadmap).

---

## ADR-008 — BOA Capital comme premier partenaire cible
**Date :** Avril 2026
**Contexte :** Identification du premier client commercial.
**Décision :** Cibler BOA Capital Securities en priorité.
**Raison :** Double rôle — SGI (broker) et émetteur d'analyses hebdomadaires. Permet de mesurer la performance de BRVM Analytics vs BOA Capital sur les mêmes titres. Argument commercial fort.
**Conséquences :** Construire la base de données des recommandations BOA Capital (backlog P6-01) pour préparer la démonstration comparative.

## ADR-009 — Score V2 en mode informatif parallèle
**Date:** 18/04/2026
**Décision:** Score V2 calculé quotidiennement et affiché comme badge Expérimental sans remplacer V1.
**Raison:** Respecte le gel ADR-001 tout en mesurant l impact des fondamentaux en temps réel.
**Conséquences:** Basculement officiel vers V2 le 01/07/2026 après analyse des performances.

## ADR-010 — Pondération dynamique V2 par secteur
**Date:** 18/04/2026
**Décision:** Finance 60/40, Agro 80/20, Autres 70/30, Partielle 80/20, Aucune 100/0.
**Raison:** Les banques ont des fondamentaux riches. Les agro sont pilotées par les matières premières.

## ADR-011 — Score géopolitique multiplicateur statique mensuel
**Date:** 18/04/2026
**Décision:** CI 1.00, SN/BJ 0.95, TG 0.90, BF 0.75, ML 0.70, NE 0.65.
**Raison:** Régimes militaires BF/ML/NE = risque systémique non capturé par technique.
**Conséquences:** CBIBF 77→55.9, BOAN 96→46.3. Migration vers table Supabase country_risk prévue.

## ADR-012 — stockanalysis.com source données fondamentales
**Date:** 18/04/2026
**Décision:** Scraper stockanalysis.com — Income Statement, Balance Sheet, Ratios, Management sur 5 ans.
**Raison:** Seule source gratuite couvrant la BRVM. GuruFocus 200$/mois. API BRVM inexistante.
**Conséquences:** Scraper hebdomadaire GitHub Actions. 3 tickers non couverts (ETIT, SEMC, SICC).

## ADR-013 — Archivage des tabs décoratifs + nouvelle architecture navbar
**Date:** 11/05/2026
**Contexte:** Tabs Risque, Législatif, Direction, Macro, Matières 1ères et BOA vs BRVM présents dans l'UI sans données réelles structurées derrière. Navigation ticker par boutons individuels peu scalable.
**Décision:** (1) Archiver ces tabs — code masqué mais non supprimé. (2) Nouvelle navbar: [Recherche] + Marché · Opportunités · Portefeuille · Obligations. (3) Fiche ticker: Aperçu · Prévisions · Backtest. (4) Scorecard intégré dans Marché comme section résumé expandable.
**Raison:** L'idée de corrélation entre ces facteurs et le cours est valide mais nécessite des données historiques structurées (BCEAO, matières premières, gouvernance) avant de pouvoir être utile. En l'état c'est de la décoration qui nuit à la clarté de l'interface.
**Conséquences:** UI plus claire. Chantier data dédié à planifier pour réintégration future. Aucun code supprimé — réversible.

## ADR-014 — GRU utile uniquement à J+1/J+2 sur le BRVM
**Date:** 16/05/2026
**Contexte:** verify_predictions.py a vérifié 1845 prévisions GRU sur les horizons J+2 à J+10.
**Résultats:** Dir.Acc J+2=56.1% · J+5=43.9% · J+7=43.9% · J+10=43.9% · Global=50.1%
**Décision:** Afficher uniquement les prévisions J+1 et J+2 dans l'app comme prévisions fiables. Les horizons J+5 à J+10 sont affichés à titre indicatif uniquement avec mention explicite de faible fiabilité.
**Raison:** À partir de J+5, le GRU performe moins bien qu'un tirage au sort. Sur un marché peu liquide comme le BRVM, les chocs de liquidité dominent le signal technique au-delà de 2 jours.
**Conséquences:** Tab Prévisions à revoir pour mettre J+1/J+2 en avant. Horizons longs = informatifs uniquement.

## ADR-015 — Features Mistral incompatibles avec modèles GRU de séries temporelles
**Date:** 16/05/2026
**Contexte:** Test réentraînement GRU avec 3 features (prix + signal_fondamental + croissance_ca_pct) sur 47 tickers via Google Colab T4 GPU.
**Résultats:** Dir.Acc moyenne 35.4% vs baseline GRU prix seul 50.1% → -14.7 pts.
**Décision:** Conserver les modèles GRU actuels (prix seul). Ne pas intégrer les features Mistral dans les modèles de prévision de prix.
**Raison:** Les features Mistral sont statiques (même valeur sur toute la séquence de 20 jours). Le GRU interprète cette constante comme du bruit qui perturbe l'apprentissage des patterns de prix. Conclusion identique à Pilla & Mekonen (S&P 500, 2025) : features additionnelles nuisent au LSTM/GRU sur données financières.
**Conséquences:** Valeur des signaux Mistral = tab Opportunités (generate_decisions.py) uniquement. Pour améliorer les prédictions : tester features dynamiques (RSI, volume) post juillet 2026.

## ADR-016 — Signal technique = bruit structurel sur le BRVM
**Date :** 25/05/2026
**Contexte :** Backtest 10 ans (22 992 signaux, 2016–2026) sur RSI/MACD/SMA/trend/vol_regime.
**Résultats :** AUC 0.51 tous scores confondus. Aucune formule de pondération ne performe mieux qu'une autre. Régime BULL/BEAR inversé : BEAR 55% > BULL 49.6% à J+10.
**Décision :** Abandonner le signal technique comme prédicteur directionnel post-dégel. Ne pas reconstruire de score composite technique pour V2.
**Raison :** Le BRVM (fixing quotidien, faibles volumes, corrections lentes) rend les indicateurs de momentum classiques structurellement inutiles. RSI/MACD/SMA mesurent du bruit sur ce marché.
**Conséquences :** Modèle V2 basé sur valorisation fondamentale (cours cible BOA). Score V1 conservé jusqu'au 01/07/2026 uniquement pour compléter la période de validation.

## ADR-017 — Signal BOA cours cible = base du modèle V2
**Date :** 26/05/2026
**Contexte :** Analyse hit rate BOA Capital sur 547 lignes, 17 semaines (déc 2025–avr 2026).
**Résultats :** BUY hit rate 60.7% J+10 / 64.3% J+20 / 56.6% J+30. SELL hit rate 24.5% J+20 (inversé — correction lente sur marché illiquide). Potentiel BOA >10% → hausse réelle 64-70% à J+20.
**Décision :** Utiliser `cours_cible = dividende / rendement_cible_sectoriel` comme signal principal V2. Rendements cibles par ticker déduits de l'historique BOA 17 semaines.
**Raison :** Signal fondamental de valorisation (décote vs valeur intrinsèque) performant sur horizons J+20 — cohérent avec la microstructure BRVM (convergence lente vers valeur fondamentale).
**Conséquences :** `company_fundamentals` alimenté quotidiennement via `scrape_boc_pdf.py`. Signal ACHAT si potentiel >10% + liquide + dividende disponible.

## ADR-018 — Liquidité = filtre binaire éliminatoire (pas composante additive)
**Date :** 25/05/2026
**Contexte :** Régression logistique live (751 signaux) et backtest 10 ans.
**Résultats :** Filtrer les tickers illiquides améliore le hit rate de +5 à +7 points systématiquement. liq_score en composante additive = coefficient négatif en régression (contre-intuitif).
**Décision :** La liquidité est un filtre binaire éliminatoire dans V2. Aucun signal ACHAT sur ticker illiquide, quelle que soit la valorisation.
**Raison :** Un titre illiquide avec potentiel +30% ne peut pas être exploité — spread, impossibilité d'exécution, risque de blocage. La liquidité ne doit pas "compenser" une mauvaise décote — elle doit bloquer le signal.
**Conséquences :** Périmètre V2 réduit aux tickers avec volume_20j suffisant. Critère exact à calibrer en juillet.

## ADR-019 — Horizon de vérification = J+20 (remplace 90 jours)
**Date :** 26/05/2026
**Contexte :** Backtest 10 ans montre signal s'améliorant de J+5=47.9% à J+30=56.7%. Régression live montre pic BOA à J+20.
**Décision :** Modifier `verify_decisions.py` pour vérifier à J+20 au lieu de 90 jours post-dégel.
**Raison :** 90 jours croise trop d'événements exogènes (AG, ex-dividendes, chocs macro) qui masquent le signal initial. Le signal fondamental BOA peak à J+20 — c'est l'horizon de convergence naturel sur le BRVM.
**Conséquences :** Résultats de vérification plus rapides et plus propres. Modifier aussi l'affichage "Valide jusqu'au" sur les DecisionCards post-dégel.

## ADR-020 — Univers V2 = moyennes caps uniquement
**Date:** 27/05/2026
**Contexte:** Backtest dividende (50 événements 2023-2026) par taille de capitalisation.
**Résultats:** Grande cap médiane J+90=+0.5%, Moyenne cap=+11.0%, Petite cap=-2.1%.
**Décision:** Restreindre l'univers V2 aux capitalisations 150-300 Mds FCFA.
**Raison:** Grandes caps trop suivies (signal déjà intégré), petites caps trop erratiques (liquidité, exécution). Zone d'inefficience exploitable = moyennes caps.
**Watchlist actuelle:** SOGC, SPHC, BOAS, BOABF, ONTBF, TTLC.
**Conséquences:** Environ 6-8 signaux par an. Max 4 positions simultanées.

## ADR-021 — Signal J-10 avant ex_dividend_date = fenêtre d'achat optimale
**Date:** 27/05/2026
**Contexte:** Backtest 50 événements de détachement dividende 2023-2026.
**Résultats:** J-10 médiane +3.6%, 86% positifs. J-30 médiane 0.0%, 46% positifs.
**Décision:** Fenêtre d'achat = J-10 avant ex_dividend_date. Ni J-30 (trop tôt, pas de signal) ni J-5 (trop peu de marge d'exécution sur la BRVM).
**Raison:** Le marché BRVM anticipe le dividende dans les 10 jours précédant le détachement — comportement comportemental clair et reproductible.
**Conséquences:** signaux_actifs.py tourne chaque lundi et alerte quand J-10 approche.

## ADR-022 — Filtre qualité ROE>15% + P/B<2.5 = filtre éliminatoire V2
**Date:** 27/05/2026
**Contexte:** Analyse ROE et P/B sur groupe hausse vs baisse J+90 (backtest dividende).
**Résultats:** ROE seul non discriminant (23.4% vs 23.6%). P/B+ROE combinés : médiane +9.5% vs -2.0%.
**Décision:** Filtre combiné ROE>15% ET P/B<2.5 est éliminatoire dans V2.
**Raison:** P/B capte la surévaluation relative que le ROE ne voit pas. Un titre peut être rentable (ROE élevé) mais surévalué (P/B>3) — dans ce cas le dividende ne suffit pas à soutenir le cours.
**Conséquences:** Environ 4-6 tickers passent le filtre simultanément sur la BRVM.

## ADR-023 — Modèle V2 en parallèle silencieux jusqu'au 01/07/2026
**Date:** 27/05/2026
**Contexte:** Modèle V1 gelé (ADR-001). V2 validé par backtest mais pas encore en conditions réelles.
**Décision:** V2 tourne en scripts séparés (signaux_actifs.py, calculate_target_price.py) sans remplacer generate_decisions.py.
**Raison:** Respecter la période de validation live V1 (avril-juillet 2026). Comparer V1 vs V2 en silencieux. Décision de bascule au 01/07/2026 après vérification des 3 positions live.
**Conséquences:** Aucun changement frontend avant juillet. V2 loggé dans GitHub Actions chaque lundi.


## ADR-020 — fix_splits.py source de vérité (29/05/2026)
Statut : ACCEPTÉ
Contexte : 61 splits détectés, 50 confirmés par avis officiels BRVM.
Décision : fix_splits.py est la source de vérité. Dry run obligatoire avant --apply.
Conséquence : toute future correction de split passe par ce script.

## ADR-021 — Backup avant correction de masse (29/05/2026)
Statut : ACCEPTÉ
Décision : créer backup_historical_data.json avant toute opération de masse.
Format : JSON complet via pagination REST (batch 1000 lignes).

## ADR-022 — SQL Editor pour corrections de masse (29/05/2026)
Statut : ACCEPTÉ
Contexte : fix_splits.py via PATCH REST = 47,000 requêtes ≈ 1h.
Décision : toutes corrections de masse → SQL Editor Supabase (UPDATE direct).
Conséquence : créer RPC apply_split() pour usage futur depuis Python.
