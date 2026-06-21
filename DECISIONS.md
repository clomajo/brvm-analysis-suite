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

---

## ADR-009 : Taux d'actualisation 8% (composante dividende, cours cible V2) — maintenu sans modification

**Date :** 20/06/2026
**Statut :** Accepté
**Contexte :**

Le calcul du cours cible V2 (`calculate_target_price.py`) utilise un taux d'actualisation de **8%** pour la composante dividende (`dividende / 8%`, pondérée à 30% du cours cible final). L'origine exacte de ce taux n'est pas documentée dans le code — probablement issu d'un document BOA Capital Securities (Strategy ou Stock Guide), mais la méthode de calcul sous-jacente (taux sans risque + prime de risque ? rendement dividende moyen marché ? autre ?) n'a pas pu être retracée.

**Déclencheur de la review :** Baisse du taux directeur BCEAO de -25 bps (3,25% → 3,00%, effective 16/03/2026).

**Analyse :**
- Le taux directeur BCEAO (taux interbancaire, ~3%) n'est pas comparable structurellement à un taux d'actualisation de rendement actions (~8%) — pas de lien mécanique 1:1.
- Le rendement dividende moyen du marché BRVM était estimé à ~9% en 2024 (source : communiqué BOA, résultats 2024), ce qui place le 8% dans une fourchette plausible à l'époque.
- Le rally de marché récent (PER marché ~13,85x T1-2026) suggère mécaniquement une baisse du rendement dividende moyen actuel (cours en hausse à dividende constant = rendement en baisse) — ce qui irait plutôt dans le sens d'un 8% **légèrement surévalué** aujourd'hui, pas sous-évalué.

**Décision :**

Le taux de 8% est **maintenu sans modification** pour le go-live V2 du 01/07/2026. Aucun lien justifiant un ajustement mécanique au taux BCEAO n'a été identifié, et recalibrer sans méthode tracée introduirait plus de risque (chiffre arbitraire) que de garder la valeur actuelle (chiffre déjà en usage, dans une fourchette historiquement plausible).

**Conséquences :**
- Item de dette technique documentée : retracer ou reconstruire la méthodologie du 8% (cible : calcul direct du rendement dividende moyen pondéré du marché BRVM via Supabase, comparable à l'estimation BOA).
- Si le rally se poursuit et que le PER marché continue de monter, réévaluer à la prochaine fenêtre de calibration (post-01/07/2026), pas avant.

**Alternatives rejetées :**
- Ajustement mécanique -25bps (8% → 7,75%) en suivant le taux BCEAO : rejeté, pas de lien méthodologique.
- Recalcul ad hoc à ~7% par analogie de marché : rejeté, pas assez rigoureux sans calcul réel du rendement dividende actuel.

---

## ADR-010 : Migration des PER sectoriels vers la nomenclature officielle BRVM (7 secteurs)

**Date :** 20/06/2026
**Statut :** Accepté

**Contexte :**

`calculate_target_price.py` utilisait 5 PER sectoriels hardcodés (Banque 12.4x, Agro 10.2x,
Industrie 13.2x, Telecom 13.3x, Distribution 16.1x), sans documentation de leur origine ni
de leur date de calibration. Une revue déclenchée par le rally de marché (PER marché
~13,85x T1-2026, en hausse) a révélé un écart important et incohérent en signe avec les
P/E sectoriels actuels publiés par BOA Capital Securities :

| Ancien (5 catégories, code) | Valeur | ≈ Catégorie BOA/BRVM officielle | P/E 2024 BOA |
|---|---|---|---|
| Banque | 12,4x | Services Financiers | 14,7x |
| Telecom | 13,3x | Télécommunications | 14,7x |
| Agro | 10,2x | Consommation de Base | 6,5x |
| Industrie | 13,2x | Industriels | 3,5x |
| Distribution | 16,1x | Consommation Discrétionnaire | 10,0x |

Recherche complémentaire : la BRVM a introduit une nouvelle nomenclature sectorielle
officielle de 7 indices (BRVM-Télécommunications, Services Financiers, Consommation de
Base, Énergie, Consommation Discrétionnaire, Services Publics, Industriels), en vigueur
depuis le 2 janvier 2025, remplaçant l'ancienne classification. Les "secteurs BOA" du
Tableau de Bord quotidien BOA Capital Securities suivent exactement cette nomenclature
officielle — il ne s'agit pas d'une méthode propre à BOA.

**Décision :**

1. Migrer `calculate_target_price.py` des 5 catégories historiques vers les 7 catégories
   officielles BRVM (Télécommunications, Services Financiers, Consommation de Base,
   Énergie, Consommation Discrétionnaire, Services Publics, Industriels).
2. Créer la table Supabase `sector_per_history` (secteur, per_2024, date_releve, source)
   pour stocker le P/E sectoriel courant par secteur, au lieu de valeurs hardcodées.
3. Alimenter cette table par saisie manuelle **mensuelle**, à partir du Tableau de Bord
   quotidien BOA Capital Securities (champ "P/E 2024" par secteur), via le script
   `update_sector_per.py`.
4. `calculate_target_price.py` doit lire la valeur la plus récente par secteur dans
   `sector_per_history` au lieu des constantes hardcodées.

**Raison :**

- Les anciennes valeurs ne correspondent à aucune nomenclature secteur actuellement
  identifiable, et l'écart avec les P/E sectoriels réels actuels est trop important et
  incohérent en signe pour être de la simple obsolescence liée au rally — il s'agit
  probablement d'une calibration ancienne sur une autre base ou méthodologie.
- La nomenclature à 7 secteurs n'est pas un choix arbitraire de méthode : c'est la
  classification **officielle** de la BRVM elle-même depuis janvier 2025. L'adopter
  élimine le besoin d'un mapping approximatif et aligne le projet sur la source de
  vérité du marché.
- Une fréquence de mise à jour mensuelle est jugée suffisante : le P/E sectoriel agrège
  plusieurs sociétés (jusqu'à 15 pour Services Financiers) sur des résultats annuels
  clôturés — il dérive lentement, contrairement aux cours individuels.
- Le parsing PDF automatique du Tableau de Bord a été testé et fonctionne (extraction
  par clustering de coordonnées + validation stricte des 7 secteurs et bornes de
  plausibilité 1x-50x), mais reste non branché en production : le document arrive par
  lien (potentiellement nécessitant authentification), pas par pièce jointe, ce qui
  complique l'automatisation de la récupération du fichier source. La saisie manuelle
  mensuelle est jugée plus fiable et suffisante avant le go-live du 01/07/2026.

**Conséquences :**

- `calculate_target_price.py` doit être modifié pour lire `sector_per_history` (non fait
  à la date de cet ADR — prochaine étape).
- Item de dette technique : si un jour le PDF BOA devient accessible par pièce jointe ou
  par une URL stable sans authentification, le script `parse_boa_dashboard.py` (déjà
  écrit et testé) peut être branché pour automatiser la collecte.
- Aucun impact sur le modèle V1 (`generate_decisions.py`), non concerné par ce changement
  et toujours gelé jusqu'au 01/07/2026 (ADR-001).

**Alternatives rejetées :**
- Mapper les 5 anciennes catégories vers les 7 BRVM officielles : rejeté, introduit une
  couche d'approximation inutile alors que la source officielle est directement
  disponible et déjà recueillie quotidiennement par Jocelyn.
- Reconstruire les PER sectoriels depuis les données Supabase internes (cours × EPS) :
  rejeté, risque de circularité (le cours cible serait calibré sur le cours actuel du
  marché lui-même, réduisant le pouvoir discriminant du signal ACHAT/EVITER).
- Automatisation complète immédiate (email→Drive→GitHub Actions) : reportée après le
  01/07/2026, le document source étant un lien et non une pièce jointe, ce qui ajoute
  une complexité d'authentification non résolue dans le délai disponible.

---

## ADR-011 : Filtre data-quality EPS remplaçant la liste d'exclusion statique

**Date :** 21/06/2026
**Statut :** Accepté

**Contexte :**

Le SKILL.md référençait une liste d'exclusion V2 statique (`NTLC, SNTS, BOAN, BNBC,
SICC, UNLC, ETIT, FTSC, CFAC, SIVC`), présentée comme déjà active dans
`calculate_target_price.py`. Vérification du code réel (session du 13/06/2026) :
cette liste n'a **jamais été implémentée** — `calculate_target_price.py` traitait
tous les tickers sans aucun filtre de qualité EPS. Conséquence directe : des
signaux V2 erronés sur des tickers aux données non représentatives (ex: NTLC
affichant une décote ACHAT de +433% du fait d'années EPS non consécutives mêlant
des montants très différents).

Investigation des cas concrets (13/06/2026, confirmée et affinée le 21/06/2026) :
- **NTLC** : années EPS non consécutives (trou, ex: FY2024/2023/2021).
- **BOAN** : collapse EPS de -92,1% YoY (FY2024 ≈ 250 → FY2025 ≈ 19,66).
- **ETIT** : aucun EPS disponible.
- **SNTS** : données propres et consécutives — ne devait *pas* être exclu, contredisant
  la liste statique du SKILL.md qui l'incluait à tort.

**Décision :**

Remplacer toute liste d'exclusion statique par un filtre dynamique dans
`calculate_target_price.py`, fonction `evaluer_qualite_eps()` :

1. **Minimum 1 année EPS exploitable** pour qu'un ticker soit éligible.
2. **Si 2 années ou plus disponibles** (jusqu'à 3 retenues) : elles doivent être
   les années fiscales les plus récentes, **strictement consécutives** — un trou
   invalide le ticker même s'il a 3+ lignes EPS au total.
3. **Filtre de collapse** : si l'EPS le plus récent chute de plus de 80% par
   rapport à l'année précédente, le ticker est exclu — quel que soit le nombre
   d'années disponibles par ailleurs.
4. **Cas particulier assumé — 1 seule année disponible** : le ticker est accepté
   **sans aucun contrôle de consécutivité ni de collapse** (mathématiquement
   impossible à vérifier avec un seul point de donnée). L'EPS retenu est alors
   cette unique valeur, qui peut être une année atypique non représentative.

Chaque exclusion est loggée avec sa raison précise (`années non consécutives :
[...]`, `collapse EPS X% YoY (A -> B)`, `aucune année EPS exploitable`) — jamais
de silence, conformément au principe de traçabilité déjà appliqué pour le
fallback PER sectoriel (ADR-010).

**Raison :**

- Une liste statique ne capture pas l'évolution des données dans le temps (un
  ticker propre aujourd'hui peut devenir problématique demain, et vice versa) —
  un filtre dynamique sur la qualité réelle des données est plus robuste et ne
  nécessite pas de maintenance manuelle de la liste.
- Le seuil initial de 3 années minimum strictes excluait 6 tickers significatifs
  (dont **ORAC/Orange CI**, une des plus grosses capitalisations du marché
  télécoms) uniquement par manque de profondeur d'historique, sans aucune
  anomalie réelle de données — un coût disproportionné pour le bénéfice de
  robustesse statistique apporté par une 3ᵉ année.
- Le compromis à 1 an minimum a été choisi en connaissance de cause : le risque
  résiduel (accepter une année EPS isolée potentiellement non représentative
  pour les tickers avec un historique très court) est jugé préférable à exclure
  des tickers à forte capitalisation sans justification de qualité de données.

**Conséquences :**

- 7 tickers exclus au run du 21/06/2026 : BICC, BOAN, CFAC, NTLC, ORGT, SAFC, TTLC
  (tous pour années non consécutives, sauf BOAN pour collapse).
- 6 tickers récupérés par rapport à une règle stricte à 3 ans : ORAC, CABC, SAFC*,
  ECOC, SIVC, STBC (*SAFC a finalement été exclu pour années non consécutives,
  pas pour profondeur d'historique — le filtre l'a correctement détecté).
- Risque résiduel à surveiller : un ticker avec 1 seule année EPS atypique
  (résultat exceptionnel, charge non récurrente) sera accepté sans garde-fou.
  Si ce cas se matérialise en signal erroné après le 01/07/2026, réévaluer le
  compromis (ex: capper le poids du signal pour les tickers à 1 an, ou exiger
  une vérification manuelle ponctuelle).
- Le SKILL.md doit être mis à jour : retirer la mention de la liste d'exclusion
  statique, documenter le nouveau filtre dynamique et sa logique.

**Alternatives rejetées :**
- Maintenir le seuil strict à 3 années consécutives : rejeté, exclut des tickers
  significatifs (ORAC notamment) sans justification de qualité de données réelle.
- Seuil intermédiaire à 2 années minimum : envisagé puis abandonné en faveur du
  seuil à 1 an, pour récupérer aussi les tickers à 1 an comme ORAC, ECOC, SIVC,
  STBC — compromis final jugé acceptable malgré l'absence de contrôle possible
  sur ces cas à 1 an.
- Réintroduire une liste statique mise à jour manuellement : rejeté, ne résout
  pas le problème de fond (maintenance manuelle, dérive silencieuse dans le temps,
  comme observé avec le SKILL.md qui listait SNTS à tort).
