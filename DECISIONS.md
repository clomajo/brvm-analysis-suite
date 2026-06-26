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

**Mise à jour (23/06/2026) :** Cette description est partiellement obsolète.
Le repo contient en réalité plusieurs composants séparés dans `src/components/`
(`BOAComparison.jsx`, `Opportunities.jsx`, `FinancialAnalysis.jsx`), découverts
lors de l'investigation ADR-017. `App.jsx` reste le composant principal et le
plus volumineux, mais "pas de composants séparés" n'est plus exact. Ce
décalage doc/code a directement contribué à une investigation plus longue que
nécessaire (recherche infructueuse dans `App.jsx` du calcul Fair Value
réellement situé dans `FinancialAnalysis.jsx`). À garder en tête : vérifier
`src/components/` en plus de `App.jsx` pour toute recherche future de code
frontend.

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

---

## ADR-012 : Correction shares_outstanding NTLC — source stockanalysis.com erronée

**Date :** 23/06/2026
**Statut :** Accepté

**Contexte :**

Un signalement direct sur l'app en production a révélé un Fair Value V2 absurde
pour NTLC (Nestlé CI) : cours cible 80 006,67 FCFA contre un cours réel de
15 005 FCFA, soit une décote affichée de +433%. Investigation menée jusqu'à la
cause racine :

1. Le calcul reconstitué manuellement a confirmé que le script
   `calculate_target_price.py` (version antérieure au filtre ADR-011) avait
   utilisé un EPS moyen de 16 908,06 FCFA/action pour NTLC — cohérent avec les
   valeurs stockées dans `company_fundamentals` (EPS FY2024=16447,64,
   FY2023=15003,53, FY2021=19273,0).
2. Recalcul indépendant de l'EPS à partir de `net_income / shares_outstanding`
   a confirmé que la valeur stockée était **interne cohérente** avec
   `shares_outstanding = 1 100 000` — donc pas une erreur de calcul du
   pipeline, mais une donnée de base déjà fausse à la source.
3. Confirmation par recherche externe et capture d'écran utilisateur : **3
   sources indépendantes** (richbourse.com, BOA Capital — Tableau de Bord
   18/06/2026, Sikafinance) convergent sur **22 070 400 actions** pour NTLC —
   soit un facteur d'erreur de **~20x** par rapport à la valeur stockée.
4. Le scraping de `company_fundamentals` est confirmé comme provenant de
   **stockanalysis.com**, qui affiche lui-même `Shares Out: 1.10M` pour NTLC —
   donc le pipeline de scraping fonctionne correctement, c'est la source
   externe qui porte une donnée erronée (cause probable : split d'actions
   Nestlé CI jamais répercuté côté stockanalysis.com, cohérent avec d'autres
   cas de splits BRVM non ajustés déjà documentés au 13/04/2026 pour le
   groupe BOA).
5. Vérification systématique sur les 45 autres tickers ayant `shares_outstanding`
   et `market_cap` renseignés (`market_cap / shares_outstanding` comparé au
   cours réel) : **aucun autre ticker** ne présente d'écart anormal — le
   problème est confirmé isolé à NTLC, pas un problème systémique de la source.

**Décision :**

1. Corriger `shares_outstanding` pour NTLC dans `company_fundamentals` :
   1 100 000 → **22 070 400**.
2. Recalculer et corriger la colonne `eps` pour NTLC à partir de
   `net_income × 1 000 000 / 22 070 400`, sur toutes les lignes avec
   `net_income` connu. Validation croisée : les valeurs recalculées
   (822,37 / 750,19 / 753,36 / 963,64 pour FY2024/2023/2022/2021)
   correspondent quasi exactement aux BNPA publiés par Sikafinance
   (822,00 / 750,00 / 753,36 / 963,65) — écart résiduel négligeable,
   probablement lié à un arrondi du nombre d'actions utilisé en interne
   par Sikafinance.
3. Ne PAS modifier le filtre `evaluer_qualite_eps()` (ADR-011) en réaction à
   ce bug : NTLC reste exclu du calcul V2 pour une raison distincte et
   toujours valide (années EPS non consécutives — FY2025 et FY2022 manquants
   dans le flux normal du pipeline), indépendamment de la correction de
   `shares_outstanding`.

**Raison :**

- Le filtre ADR-011 vérifie la consécutivité et le collapse EPS, mais n'a
  structurellement aucun moyen de détecter une erreur de `shares_outstanding`
  qui produit un EPS interne cohérent (calculé correctement à partir d'une
  donnée de base fausse) — ce n'est pas un trou dans le filtre, c'est un
  problème de donnée source que seule une vérification croisée à des
  références externes peut révéler.
- Une correction manuelle ciblée est jugée suffisante et proportionnée : le
  problème est confirmé isolé à un seul ticker sur 46, pas un défaut
  systémique de stockanalysis.com nécessitant un changement de source globale.

**Conséquences :**

- Aucun changement de signal V2 pour NTLC à court terme : il reste exclu par
  ADR-011, peu importe la correction de `shares_outstanding`/`eps`. La
  correction assainit néanmoins la donnée de base pour tout usage futur
  (affichage de fiche société, comparatifs PER/PB, et un éventuel retour de
  NTLC dans le calcul V2 si FY2025/FY2022 sont un jour complétés).
- Item de vigilance ajouté : si une future donnée `shares_outstanding`
  scrapée depuis stockanalysis.com produit un EPS ou un PER implicite hors
  de toute fourchette plausible (ex: PER < 1x ou > 100x), envisager une
  vérification croisée systématique avant intégration, plutôt que d'attendre
  un signalement utilisateur sur l'app en production.
- Aucune ligne `target_prices` à corriger pour NTLC : la ligne aberrante du
  21/06/2026 (cours cible 80 006,67 FCFA) a déjà été supprimée séparément
  (cf. nettoyage manuel du 23/06/2026, requête `DELETE` ciblée sur
  `ticker='NTLC' AND calcul_date='2026-06-21'`).

**Correction (25/06/2026) — l'affirmation ci-dessus était fausse :**

La section "Décision" point 2 affirmait que la colonne `eps` avait été
recalculée et corrigée pour NTLC, avec validation décimale contre Sikafinance.
Vérification directe de `company_fundamentals` le 25/06/2026 (suite à un
nouveau signalement Fair Value aberrant sur NTLC, cf. ADR-018) a montré que
`eps` contient toujours les valeurs fausses d'avant correction (FY2024 =
16 447,64 au lieu de 822,37, etc.) — seul `shares_outstanding` a réellement
persisté en base à 22 070 400. La correction `eps` a probablement été
calculée et validée en session (les chiffres cités ci-dessus sont corrects
arithmétiquement) mais jamais écrite dans Supabase, ou écrasée par le
scraping hebdomadaire suivant (`scrape_all_v4.py`, qui réécrit `eps` sans
jamais le recalculer depuis `net_income/shares_outstanding` — cf. ADR-018
pour la cause racine complète). Lecture à tirer : une correction validée en
session n'est pas une correction persistée — vérifier après coup que
l'écriture en base a bien eu lieu, surtout si un script automatique tourne
sur la même table par la suite.

**Alternatives rejetées :**
- Changer la source de scraping de `company_fundamentals` vers Sikafinance ou
  richbourse pour tous les tickers : rejeté pour l'instant, le problème étant
  confirmé isolé — un changement de source globale serait disproportionné et
  introduirait un nouveau risque de migration sans bénéfice démontré au-delà
  de ce cas unique.
- Modifier le filtre data-quality pour détecter les PER/EPS implausibles en
  plus de la consécutivité : envisagé mais non retenu dans l'immédiat — un
  seul cas confirmé sur 46 tickers ne justifie pas une nouvelle règle
  générale tout de suite. À reconsidérer si d'autres cas similaires
  apparaissent lors de futurs scrapings.

---

## ADR-017 : Doublon de calcul Fair Value identifié — FinancialAnalysis.jsx (non corrigé)

**Date :** 23/06/2026
**Statut :** Accepté (constat) — correction reportée à une session ultérieure

**Contexte :**

Suite à la correction du bug `shares_outstanding` NTLC (ADR-012), un signalement
direct sur l'app en production a montré que l'aberration Fair Value (164 476
FCFA pour NTLC, "EPS moyen × P/E sectoriel 10x") persistait malgré la
correction des données en base. Investigation du frontend a révélé l'existence
d'un **composant séparé et jusque-là non documenté** : `src/components/
FinancialAnalysis.jsx` (page "AI Fundamental Analysis"), distinct du composant
principal `App.jsx` qui lit déjà correctement `target_prices`.

`FinancialAnalysis.jsx` recalcule sa propre Fair Value **directement en
JavaScript côté navigateur**, à partir d'une requête `company_fundamentals`
filtrée sur `fiscal_year=eq.FY2025` :

```js
const avgEPS = last3.reduce((sum, d) => sum + (d.eps || 0), 0)
               / last3.filter(d => d.eps).length;
```

combiné à un **P/E sectoriel codé en dur à 10x**, affiché littéralement dans le
texte : `"Méthode: EPS moyen X ans × P/E sectoriel 10x"`.

Ce calcul ne bénéficie d'aucune des protections construites le 20-23/06/2026 :
- Pas de lecture de `sector_per_history` (ADR-010) — PER toujours fixé à 10x,
  indépendamment du secteur réel du ticker.
- Pas de filtre `evaluer_qualite_eps()` (ADR-011) — `last3` prend les 3
  dernières lignes disponibles sans vérifier consécutivité ni collapse.
- Pas de garde-fou `decote_pct < 200` (présent dans `App.jsx` au moment de la
  lecture de `target_prices`, ligne ~3576) — aucune borne de plausibilité.

L'architecture documentée dans `ARCHITECTURE.md` ne mentionnait que `App.jsx`
("tout le frontend est dans un seul fichier (ADR-002)") — la découverte de
`src/components/BOAComparison.jsx`, `Opportunities.jsx`, et
`FinancialAnalysis.jsx` comme fichiers séparés constitue une mise à jour
nécessaire de cette description architecturale, indépendamment du bug lui-même.

**Décision :**

1. Constater et documenter ce doublon de calcul comme item de dette technique
   prioritaire — non corrigé à la date de cet ADR, reporté à une session
   ultérieure par manque de temps.
2. Approche de correction retenue pour la prochaine session : **Option B**
   — faire lire à `FinancialAnalysis.jsx` l'historique déjà présent dans
   `target_prices` (plusieurs lignes par ticker, une par `calcul_date`),
   plutôt que de recalculer en JavaScript. Permet d'afficher une vraie courbe
   Fair Value dans le temps (pas une ligne plate), sans dupliquer la logique
   Python de `calculate_target_price.py` en JavaScript.
3. Options explicitement écartées pour cette correction :
   - Réécrire la même logique de calcul en JavaScript dans le composant
     (dupliquerait le problème structurel qui a permis cette divergence).
   - Construire une fonction de calcul partagée (Supabase Edge Function en
     Deno/TypeScript) appelée par les deux frontends : jugée disproportionnée
     pour ce besoin (nouvelle surface de code et de maintenance, nouveau
     langage, sans bénéfice clair au-delà de cette page de détail). Écartée
     aussi car indépendante des caractéristiques de la machine locale —
     l'exécution se fait côté cloud (Supabase/Vercel), pas sur le Mac mini.
4. Correction de la documentation architecturale : `ARCHITECTURE.md` doit
   lister les composants séparés du frontend (`BOAComparison.jsx`,
   `Opportunities.jsx`, `FinancialAnalysis.jsx`), pas seulement `App.jsx`.

**Raison :**

- Le vrai risque structurel n'est pas seulement le P/E à 10x ou l'absence de
  filtre — c'est l'existence même d'un calcul métier dupliqué dans deux
  langages (Python et JavaScript). Toute future correction du modèle V2
  (nouveau secteur, ajustement du taux d'actualisation, nouvelle règle
  data-quality) devra être répétée dans les deux endroits si la duplication
  persiste, avec le risque réel d'oubli déjà démontré aujourd'hui par ce cas.
- Le composant principal (`App.jsx`) a déjà la bonne architecture (lecture de
  `target_prices`, garde-fou de plausibilité) — il n'y a pas besoin
  d'inventer une nouvelle solution, seulement d'aligner `FinancialAnalysis.jsx`
  sur ce pattern déjà éprouvé.

**Conséquences :**

- **L'aberration Fair Value reste visible sur la page "AI Fundamental
  Analysis" pour NTLC et potentiellement d'autres tickers** jusqu'à la
  correction de ce composant. Le composant principal (DecisionCard, `App.jsx`)
  n'est pas affecté — il affiche déjà la bonne donnée (ou `null` si filtrée).
- Risque pour tout ticker dont l'EPS source serait localement faux (comme
  NTLC l'était avant ADR-012) : `FinancialAnalysis.jsx` afficherait la même
  classe d'aberration, sans aucun garde-fou actuel pour l'intercepter.
- Item de backlog créé : patch de `FinancialAnalysis.jsx` selon l'option B,
  à traiter lors d'une prochaine session (code du composant non examiné en
  détail à la date de cet ADR — seules les lignes de calcul et d'affichage
  ont été identifiées par recherche ciblée `grep`).

**Alternatives rejetées :**
- Corriger immédiatement avec un patch minimal (garde-fou de plausibilité
  uniquement, sans toucher au calcul lui-même) : rejeté car ça masquerait le
  symptôme sans résoudre la duplication — le composant afficherait "N/D" au
  lieu d'un chiffre faux, mais ne donnerait jamais le bon chiffre.
- Supprimer purement le composant et rediriger vers l'affichage simple de
  `App.jsx` : rejeté à la demande explicite de Jocelyn, qui souhaite
  conserver le niveau de détail actuel de cette page (P&L, Cash Flow,
  Valorisation, Dividende, Peers, Prévisions).

---

## ADR-018 : Correction ADR-017 + cause racine eps non recalculé (scrape_all_v4.py)

**Date :** 25/06/2026
**Statut :** Accepté — partiellement implémenté (détection en place, correction des données reportée)

**Contexte :**

ADR-017 a été corrigé : `FinancialAnalysis.jsx` lit désormais `target_prices`
au lieu de recalculer en JS (patch appliqué via `patch_adr017_fairvalue.py`,
commit `c7294f6` sur `brvm-analytics`). En vérifiant le résultat sur NTLC,
le composant affichait toujours une Fair Value aberrante : 80 007 FCFA contre
un cours réel de 15 000 FCFA (+433% upside), avec la mention "PER sectoriel
6,5x (sector_per_history)" — donc le patch fonctionnait correctement, mais
lisait une ligne `target_prices` elle-même fausse, datée du 30/05/2026.

Investigation jusqu'à la cause racine :

1. La ligne `target_prices` du 30/05/2026 utilisait un EPS de 16 908,06 FCFA
   pour NTLC — cohérent avec l'ancien bug `shares_outstanding` (×20), pas
   avec la correction ADR-012.
2. Vérification directe de `company_fundamentals` : `shares_outstanding` =
   22 070 400 (correct, ADR-012 bien persisté) mais `eps` = 16 447,64 pour
   FY2024 (faux — devrait être 822,37, cf. correction apportée à ADR-012
   ci-dessus). Confirmé sur 3 années (FY2024, FY2023, FY2021), ratio ~20,0x
   exact dans chaque cas.
3. Lecture du workflow GitHub Actions (`brvm-analysis.yml`) : `scrape_all_v4.py
   --full` tourne chaque lundi (ÉTAPE 1b), immédiatement suivi de
   `calculate_target_price.py` (ÉTAPE 1f) dans le même run. Donc toute
   correction manuelle de `eps` en base est écrasée au scraping suivant si
   elle n'est pas reproductible par le scraper lui-même.
4. Lecture de `scrape_all_v4.py` : `eps` est scrapé **tel quel** depuis le
   champ "EPS (Basic)" de stockanalysis.com (`elif 'eps (basic)' in metric:
   r['eps'] = v`), sans aucun recalcul à partir de `net_income`/
   `shares_outstanding`. `shares_outstanding` lui-même n'est récupéré que
   pour l'année courante (`scrape_overview()`, page "overview"), jamais par
   année historique — donc même un recalcul correct de `eps` ne peut
   s'appuyer sur un `shares_outstanding` propre à chaque année passée.
5. Vérification élargie (requête SQL comparant `eps` stocké vs
   `net_income×1M/shares_outstanding` sur tout `company_fundamentals`) :
   confirmé sur 2 autres tickers en plus de NTLC —
   **BICC** (ratio ~1,5x, 4 années touchées : FY2021, FY2022, FY2023, FY2025)
   et **SOGC** (ratio ~0,73x, mais seulement FY2021-FY2022 — FY2023/2024/2025
   sont sains, ratio 1.00). ORGT et BOAN montrent des écarts faibles
   (1,04-1,09x), probablement de l'arrondi plutôt qu'un vrai bug — non
   traités comme prioritaires.

**Décision :**

1. **Ne pas corriger les données immédiatement.** Choix explicite de
   comprendre la cause racine avant toute correction, pour éviter de
   reproduire l'erreur d'ADR-012 (correction validée mais non persistée /
   silencieusement écrasée).
2. **Ajouter une détection de cohérence, sans correction automatique** :
   nouvelle fonction `check_eps_coherence()` dans `scrape_all_v4.py` (commit
   `654bfd2` sur `brvm-analysis-suite`). Recalcule `eps` théorique depuis
   `net_income×1M/shares_outstanding` et compare au `eps` scrapé ; log un
   warning explicite si l'écart dépasse 10%. **Ne modifie jamais `row['eps']`**
   — le risque qu'une erreur de `net_income` ou `shares_outstanding` scrapé
   se propage silencieusement dans un `eps` recalculé automatiquement est
   jugé supérieur au bénéfice d'une correction immédiate.
3. **Approximation assumée et documentée** : `shares_outstanding` de FY2025
   (overview courant) est réutilisé pour vérifier aussi les années
   historiques (FY2021-2024), sous l'hypothèse que le nombre d'actions n'a
   pas changé sur la période. Risque de faux-positif en cas de split ou
   d'augmentation de capital non documenté — signalé explicitement dans le
   message de warning généré.
4. Tests unitaires effectués sur les 3 cas confirmés (NTLC, BICC, SOGC) +
   4 cas sains (SPHC, SGBC, NSBC, ORGT) + cas limites (None, zéro) avant
   déploiement — voir détail des résultats dans la conversation du
   25/06/2026. Détection précise sur SOGC : warning généré seulement pour
   FY2021/2022 (les années réellement décalées), silence correct sur
   FY2023+ (saines) — pas de blanket warning sur tout le ticker.
5. Correction réelle des données (NTLC/BICC/SOGC) reportée à après le
   run automatique du lundi suivant (29/06/2026), pour disposer de la liste
   complète des incohérences sur les 47 tickers avant de corriger — plutôt
   que de corriger au coup par coup à chaque découverte manuelle.

**Raison :**

- Le pattern découvert ("correction persistée sur une colonne, pas sur une
  autre colonne dérivée, écrasée par un script automatique non synchronisé")
  est un risque structurel qui peut toucher d'autres champs dérivés du
  pipeline, pas seulement `eps`. Documenter la détection avant la correction
  permet de vérifier l'ampleur réelle du problème plutôt que de le traiter
  comme un cas isolé comme cela avait été fait (à tort) pour ADR-012.
- Une correction automatique de `eps` à chaque run, sans visibilité, aurait
  le même défaut structurel que le bug actuel : un changement de donnée
  invisible et non audité. Le log explicite permet une décision humaine
  informée à chaque cas, conformément au principe de traçabilité déjà
  appliqué pour `per_source` (ADR-010) et les raisons d'exclusion EPS
  (ADR-011).

**Conséquences :**

- NTLC, BICC, SOGC ont toujours un `eps` faux dans `company_fundamentals`
  à la date de cet ADR — non corrigé. NTLC reste sans impact sur les
  signaux V2 (exclu par ADR-011, raison distincte). SOGC est en watchlist
  V2 active — vigilance requise, mais ses données les plus récentes
  (FY2023+, qui pèsent dans le calcul EPS moyen 3 ans) sont saines.
- Le composant `FinancialAnalysis.jsx` (ADR-017, désormais corrigé pour la
  duplication de calcul) continuera d'afficher fidèlement la Fair Value
  fausse pour NTLC tant que `target_prices` n'est pas recalculé avec un
  `eps` correct — ce n'est plus un bug d'affichage, c'est un problème de
  donnée source en amont.
- Item de backlog créé : attendre les logs du run du 29/06/2026, lister
  l'ensemble des tickers incohérents détectés, puis appliquer une correction
  SQL persistante (pas une correction "en session" comme ADR-012) sur les
  cas confirmés.

**Alternatives rejetées :**

- Recalculer `eps` automatiquement et systématiquement dans
  `scrape_all_v4.py` (écraser la valeur scrapée par le calcul) : rejeté pour
  l'instant — risque de masquer une éventuelle erreur amont sur `net_income`
  sans aucune visibilité, contrairement à un warning explicite qui force une
  vérification.
- Corriger uniquement NTLC/BICC/SOGC sans changement structurel du script :
  rejeté, ne traiterait que les symptômes déjà connus et laisserait
  réapparaître le même problème sur un futur ticker sans aucun signal
  d'alerte, comme cela s'est produit silencieusement depuis le 30/05/2026
  jusqu'à la découverte du 25/06/2026.
