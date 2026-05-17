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
