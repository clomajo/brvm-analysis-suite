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

## ADR-013 — Archivage des tabs décoratifs + nouvelle architecture navbar
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 11/05/2026
**Décision :** Tabs Risque/Législatif/Direction/Macro/Matières/BOA vs BRVM masqués (code conservé).
**Navbar :** [Recherche] · Marché · Opportunités · Portefeuille · Obligations.

---

## ADR-014 — GRU utile uniquement à J+1/J+2 sur le BRVM
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

> **Supersédé par ADR-044** (10/08/2026) — le GRU est fermé définitivement
> (MASE 1.888, direction 47.9 %, sous la persistance naïve). Conservé pour la
> traçabilité de la décision d'origine.

**Date :** 16/05/2026
**Résultats :** Dir.Acc J+2=56.1% · J+5=43.9% · Global=50.1%
**Décision :** Afficher J+1/J+2 comme fiables. J+5+ = indicatifs uniquement.

---

## ADR-015 — Features Mistral incompatibles avec modèles GRU
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 16/05/2026
**Résultats :** Dir.Acc 35.4% vs baseline 50.1% → -14.7 pts avec features Mistral.
**Décision :** Conserver GRU prix seul. Valeur Mistral = Opportunités uniquement.

---

## ADR-016 — Signal technique = bruit structurel sur le BRVM
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 25/05/2026
**Résultats :** AUC 0.51 sur 22 992 signaux (2016–2026).
**Décision :** Abandonner le signal technique post-dégel. V2 basé sur valorisation fondamentale.

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

---

## ADR-019 : Analyse fondamentale bloquée — contrainte SQL parasite + extraction titre

> **Note (T17, 30/07/2026) :** ce numéro ADR-019 a écrasé, par collision de numérotation le 28/06/2026, un ADR antérieur du 26/05/2026 sur l'horizon de vérification (J+20 vs 90 jours). Ce texte original a été restauré sous **ADR-038** — voir cette entrée pour la décision sur `verify_decisions.py` et `VERIFICATION_WINDOW`.

**Date :** 28/06/2026
**Statut :** Accepté — implémenté

**Contexte :**

L'analyse Mistral de SONATEL affichée dans l'app datait de "Q3 2025" alors que
l'exercice 2025 est clos (dividendes payés en mai 2026) et que le rapport
T1 2026 est publié sur brvm.org depuis le 17/04/2026. Investigation :

1. `company_fundamentals` contient bien FY2025 complet (eps=3420, net_income=
   341963) — donc la donnée annuelle existe, le problème n'est pas le scraping
   des chiffres.
2. La table `fundamental_analysis` n'a qu'UNE ligne pour SONATEL, datée du
   rapport T3 2025 (PDF `20251031`). Aucune trace de T1 2026.
3. Les logs GitHub Actions (run du 26/06) montrent que le rapport T1 2026 a été
   correctement téléchargé, son texte extrait, et analysé par Mistral AVEC
   SUCCÈS — mais la sauvegarde a échoué : `duplicate key value violates unique
   constraint "unique_company_fundamental"` `DETAIL: Key (company_id)=(18)
   already exists`. Même erreur observée pour company_id=17.
4. La table avait DEUX contraintes : `fundamental_analysis_report_url_key`
   (`UNIQUE(report_url)`, l'originale, cohérente avec le code) ET
   `unique_company_fundamental` (`UNIQUE(company_id)`, parasite). Cette
   dernière n'est référencée NULLE PART (ni Git, ni ADR, ni code) — probablement
   ajoutée tôt via l'éditeur graphique Supabase, en contradiction avec le code
   Python qui gère pourtant `ON CONFLICT (report_url) DO UPDATE` (preuve que
   l'intention était d'historiser plusieurs rapports par société).
5. Bug secondaire découvert dans `_find_all_reports()` : le titre du rapport
   était lu depuis le texte du lien `<a>` (toujours "Télécharger", générique),
   pas depuis le vrai titre qui est dans un `<strong>` de la cellule précédente
   du même `<tr>`. Conséquence : impossible de distinguer un T1 d'un T3, et la
   date retombait systématiquement sur le 31/12 de l'année (fallback).

**Décision :**

1. Supprimer la contrainte parasite `unique_company_fundamental` (`UNIQUE
   (company_id)`). La table revient à sa contrainte d'origine saine
   `fundamental_analysis_report_url_key` (`UNIQUE(report_url)`), permettant
   l'historisation de plusieurs rapports par société comme le code l'attend.
   Script SQL `fix_unique_company_fundamental.sql` (vérifs préalables incluses).
2. Corriger `_find_all_reports()` : nouvelle fonction `_parse_date_from_titre()`
   qui lit le vrai titre depuis le `<strong>` du `<tr>` parent et en extrait une
   date précise selon le type de rapport (1er/2e/3e/4e trimestre → fin du
   trimestre correspondant ; semestre ; annuel/exercice → 31/12). Le tri par
   date devient enfin fiable. Commit `d2c0a13`.
3. Retrait du mode UPSERT dans `_load_analysis_memory_from_db()` (cf. ADR-020,
   décision liée prise dans la même session pour le quota).

**Raison :**

- Le symptôme ("Q3 2025" figé) était la conséquence visible d'un échec SQL
  silencieux : chaque run refaisait tout le travail coûteux (téléchargement,
  extraction, appel Mistral payant) puis échouait à la dernière étape sans que
  rien ne remonte dans l'interface. Le coût a été payé pendant ~3 semaines sans
  aucun résultat persisté.
- Assouplir une contrainte trop stricte (revenir à l'unicité par report_url,
  déjà existante) est sûr et réversible ; supprimer des lignes pour forcer
  l'unicité par société aurait été destructeur.

**Conséquences :**

- Dès le prochain run, le rapport T1 2026 (et tous les rapports manquants pour
  les sociétés ayant déjà une ligne) pourront s'enregistrer.
- Leçon transversale : un échec de sauvegarde APRÈS un appel API réussi (donc
  facturé) doit être un signal d'alarme visible, pas une ligne ERROR noyée.
  Item backlog créé pour renforcer ce logging.

---

## ADR-020 : Analyse Mistral sans valorisation chiffrée (source unique = modèle V2)

**Date :** 28/06/2026
**Statut :** Accepté — implémenté

**Contexte :**

Les 3 prompts de `fundamental_analyzer.py` (DeepSeek, Gemini, Mistral)
demandaient à l'IA de calculer elle-même un "Objectif de cours" via "EPS moyen
3 ans x P/E sectoriel ~10x" — exactement le P/E 10x hardcodé et obsolète qu'on
avait éliminé du frontend en ADR-017, mais réintroduit ici dans le texte du
prompt. L'IA produisait donc une valorisation chiffrée selon une méthode
périmée, qui pouvait diverger du cours cible réel du modèle V2 (`target_prices`,
PER sectoriel dynamique + Gordon).

**Décision (option C retenue) :**

Retirer complètement la ligne "Objectif de cours" et "Upside/Downside" des 3
prompts. L'analyse IA se concentre désormais exclusivement sur le qualitatif
(thèse, rentabilité, dividende, risques, moat, contexte sectoriel) — ce que les
LLM font de façon fiable. Une instruction explicite est ajoutée : "NE PAS
calculer ni proposer d'objectif de cours chiffré". Le cours cible chiffré vient
exclusivement du modèle V2 affiché séparément. Commit `0a8deab`.

**Alternatives rejetées :**

- Option A (pointer le prompt vers la vraie valeur `target_prices`) : nécessitait
  d'injecter cette donnée dans le prompt, plus de code, et laissait l'IA
  manipuler un chiffre de valorisation.
- Option B (corriger la formule dans le prompt vers la vraie méthode V2) :
  l'IA aurait continué à recalculer de son côté, recréant le risque de
  divergence — exactement le problème qu'ADR-017 a éliminé.

**Raison :**

- Même principe que ADR-017 : une seule source de vérité pour la valorisation.
  Un LLM est doué pour le narratif, pas pour produire un chiffre de valorisation
  reproductible. Faire calculer un prix par l'IA recrée le problème de double
  source qu'on venait d'éliminer côté frontend.

**Conséquences :**

- Les analyses régénérées après cette date n'afficheront plus d'objectif de
  cours chiffré dans la section RECOMMANDATION — uniquement un signal qualitatif
  (ACHAT/CONSERVER/VENTE) et le cours actuel. Le chiffre cible reste disponible
  via le badge V2 / la page Fair Value (ADR-017).
- Les anciennes analyses en base gardent leur ancien format jusqu'à
  régénération (qui n'arrivera qu'au prochain nouveau rapport, mode UPSERT
  retiré — cf. ADR-021).

---

## ADR-021 : Sobriété quota Mistral — retrait UPSERT + cadence bi-hebdomadaire

**Date :** 28/06/2026
**Statut :** Accepté — implémenté

**Contexte :**

Le quota API Mistral (plan Free, `chat.mistral.ai` / "Vibe") a été épuisé à 100%
avant la fin du mois, suspendant l'accès jusqu'au reset du 30/06/2026. Deux
causes structurelles identifiées :

1. **Mode UPSERT** : `_load_analysis_memory_from_db()` vidait la mémoire des
   analyses déjà faites à chaque run (`self.analysis_memory = set()`), forçant
   la régénération de TOUT l'historique à chaque exécution quotidienne — alors
   que les fondamentaux ne changent qu'au rythme des publications (trimestriel).
   Le docstring de la fonction promettait pourtant un "skip définitif" que le
   code ne faisait pas.
2. **Cadence quotidienne** des étapes 5 (analyse fondamentale) et 6 (génération
   rapports), toutes deux dépendantes de Mistral, alors que leur source ne
   change pas tous les jours.

**Décision :**

1. Retirer le mode UPSERT : `analysis_memory` charge réellement les URLs déjà
   en base et les skip définitivement. Régénération forcée = manuelle si besoin
   (vider la table ou flag CLI dédié), jamais par défaut. Commit `0a8deab`.
2. Passer les étapes 5 et 6 du workflow en bi-hebdomadaire (1er et 15 du mois)
   via une garde `DOM=$(date +%d)`, sur le modèle des autres étapes
   conditionnelles existantes (1b, 1c, V2b). Commit `29dfde2`.

**Raison :**

- Les fondamentaux d'une société changent 4 fois par an au plus. Une analyse
  quotidienne (et pire, une régénération quotidienne de tout l'historique)
  était du gaspillage pur de quota, sans aucune nouvelle information produite
  la plupart des jours.
- Question soulevée pendant la session ("et si un rapport est mis à jour sur le
  site ?") : écartée volontairement comme trop complexe à détecter de façon
  fiable. Un rapport officiel corrigé sort en général sous une nouvelle URL
  (donc traité comme nouveau) ; le cas d'un même fichier silencieusement
  remplacé est rare et accepté comme angle mort assumé.

**Conséquences :**

- Consommation Mistral drastiquement réduite : plus de régénération inutile, et
  appels concentrés sur 2 jours/mois.
- Un nouveau rapport publié entre deux dates (ex. le 5 du mois) ne sera analysé
  qu'au 15 — délai acceptable pour des fondamentaux trimestriels.
- Reste quotidienne : ÉTAPE 3c (`verify_decisions.py`, utilise Mistral mais
  vérifie des signaux J+20 datés, vraie raison de tourner chaque jour) — à
  surveiller si elle pèse sur le quota.

## ADR-022 — Filtre qualité ROE>15% + P/B<2.5 = filtre éliminatoire V2
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 27/05/2026
**Résultats :** Filtre combiné : médiane J+90 +9.5% vs -2.0% hors filtre.
**Décision :** ROE>15% ET P/B<2.5 éliminatoire dans V2.

---

## ADR-023 — Modèle V2 en parallèle silencieux jusqu'au 01/07/2026
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 27/05/2026
**Décision :** V2 tourne dans scripts séparés sans remplacer generate_decisions.py.
**Bascule :** 01/07/2026 après vérification des 3 positions live.

---

## ADR-024 — fix_splits.py = source de vérité splits
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 29/05/2026
**Décision :** fix_splits.py est la source de vérité. Dry run obligatoire avant --apply.
**Conséquence :** Toute future correction de split passe par ce script.

---

## ADR-025 — Backup avant correction de masse
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 29/05/2026
**Décision :** Créer backup_historical_data.json avant toute opération de masse.

---

## ADR-026 — SQL Editor pour corrections de masse (pas REST PATCH)
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 29/05/2026
**Contexte :** fix_splits.py via PATCH REST = 47,000 requêtes ≈ 1h.
**Décision :** Toutes corrections de masse → SQL Editor Supabase (UPDATE direct).

---

## ADR-027 — Date signal V2 = 30 avril (correction look-ahead bias)
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 29/05/2026
**Contexte :** Utiliser janvier comme date signal = look-ahead bias (résultats FY non publiés).
**Décision :** Date signal = 30 avril de l'année suivante (4 mois après clôture FY).
**Impact :** Médiane J+90 passe de +5.9% à +7.8% — version honnête.

---

## ADR-028 — Pas de filtre décote maximum
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 29/05/2026
**Contexte :** Décotes >150% performent mieux (médiane +6.3%) que 60-150% (+5.1%).
**Décision :** Aucun plafond sur la décote — les grandes décotes sont le cœur du signal.

---

## ADR-029 — scrape_market_cap.py mensuel automatisé
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

> **Décision toujours en vigueur, exécution en panne.** Le 12/08/2026, il a été
> constaté que `company_fundamentals.scraped_at` est figé au 27/05/2026 pour
> `market_cap` : l'automatisation décidée ici ne produit plus d'écriture.
> Cause distincte de celle d'ADR-049 (PATCH ciblé, pas un upsert) — à diagnostiquer.

**Date :** 30/05/2026
**Décision :** scrape_market_cap.py tourne automatiquement le 1er lundi du mois via GitHub Actions.
**Source :** stockanalysis.com/quote/brvm/{ticker}/statistics/
**Implémenté :** commit 7a069ae

---

## ADR-030 — target_prices = table historique quotidienne
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 30/05/2026
**Contexte :** Choix entre vue SQL, table hebdomadaire ou table quotidienne.
**Décision :** Table quotidienne avec contrainte UNIQUE (ticker, calcul_date).
**Raison :** L'historique des décotes permet de tracker quand un titre franchit le seuil ACHAT — utile pour le forward test juillet 2026. 17K lignes/an = négligeable pour Supabase.
**Conséquences :** calculate_target_price.py upsert quotidiennement dans le pipeline ÉTAPE 1f.

---

## ADR-031 — STYLE-01 fermé — react-markdown incompatible Vite 3
> **Restauré le 12/08/2026.** Perdu lors du commit `0412529` (04/06/2026), qui a
> réécrit `DECISIONS.md` au lieu de l'enrichir (27 insertions, 183 suppressions,
> 32 ADR ramenés à 8). Texte restitué depuis `d59214f` (30/05/2026) sans modification.

**Date :** 30/05/2026
**Contexte :** react-markdown cause des erreurs esbuild avec Vite 3.2.7.
**Décision :** Item fermé définitivement. Parser inline maison (split \n + détection ##) est le contournement validé.
**Conséquence :** Ne pas revisiter avant migration vers Vite 4+ (post juillet 2026).

---

## ADR-032 : NTLC — Split réel confirmé, prix pré-2017-09-11 corrigés

**Date :** 09/07/2026
**Statut :** Adopté

**Contexte**

La correction de `company_fundamentals.shares_outstanding` pour NTLC
(1 100 000 → 22 070 400, ~×20.064) a soulevé la question de savoir si
un split réel de l'action avait eu lieu, auquel cas les prix historiques
pré-split dans `historical_data` seraient faussés (non ajustés).

**Investigation (T3, script jetable `tools/investigate_ntlc.py`)**

- Une seule discontinuité de prix > 40% détectée sur tout l'historique
  NTLC : 2017-09-11, -94.62% (49450 → 2660 FCFA).
- Confirmation source officielle : **BRVM Avis N°164-2017/BRVM/DG**
  (07/09/2017), fractionnement NESTLE CI à raison de **20 actions
  nouvelles pour 1 action ancienne**. Valeur théorique post-split
  annoncée : 2 475 FCFA (cohérent avec 49450/20 = 2472.5).
- Le ratio shares_outstanding (20.064) diffère légèrement du ratio de
  split officiel (20 exact) — écart de 70 400 actions (~0.32%), source
  non identifiée. Sans impact sur la correction des prix, qui doit
  suivre le ratio de split officiel, pas le ratio shares_outstanding.

**Décision**

Prix pré-2017-09-11 corrigés via SQL Editor (ADR-026) :

```sql
UPDATE historical_data
SET price = price / 20
WHERE company_id = 22 AND trade_date < '2017-09-11';
```

361 lignes affectées (2016-03-22 → 2017-09-08). Vérification post-
correction : continuité de prix confirmée (2016 : 2355–3911 FCFA,
2017 : 1900–3100 FCFA), plus de discontinuité ×20 dans l'historique.

**Conséquences**

- Backtests et graphiques NTLC désormais fiables sur toute la période
  2016+.
- Le léger écart entre ratio de split (20) et ratio shares_outstanding
  (20.064) reste à investiguer séparément si `shares_outstanding` est
  revérifié — ne pas réutiliser 20.064 pour d'autres corrections liées
  au split.
- Backup pré-correction disponible dans
  `~/Desktop/brvm-backups/2026-07-08/` (T0) en cas de rollback.

**Source**
BRVM Avis N°164-2017/BRVM/DG — https://www.richbourse.com/common/actualite/afficher-fichier/07-09-2017-nestle-ci-fractionnement-dactions-valeur-theorique

## ADR-033 : EPS recalculé (net_income/shares_outstanding) comme valeur primaire, avec garde-fou de sanité — 11/07/2026

**Contexte (T4) :** `scrape_all_v4.py` scrapait l'EPS directement depuis stockanalysis.com
("EPS (Basic)"), avec un simple calcul de cross-check (`check_eps_coherence`) qui
loggait les divergences sans jamais corriger `row['eps']`.

**Décision :** `eps_recalcule = net_income × 1 000 000 / shares_outstanding` devient
la valeur primaire écrite dans `company_fundamentals.eps`. L'eps scrapé devient le
signal de cross-check (fallback si recalcul impossible, log si divergence).

**Garde-fou ajouté :** si le ratio eps_scrapé/eps_recalcule est hors [0.2, 5] ou de
signe incohérent, le remplacement est bloqué et l'eps scrapé est conservé — pour
éviter d'insérer des valeurs aberrantes en base (cf. limite connue ci-dessous).

**Limite connue — NON résolue par cet ADR :** `shares_outstanding` scrapé en direct
depuis stockanalysis.com souffre de deux problèmes cumulés, hors périmètre T4 :
1. `parse_val()` n'applique pas le multiplicateur du suffixe `'M'` (ex. "1.10M" → `1.1`
   au lieu de `1 100 000`) — bug de parsing générique, potentiellement présent sur
   d'autres champs de la page overview.
2. Pour NTLC (et probablement BICC, SOGC — cf. docstring `check_eps_coherence`),
   stockanalysis.com n'a jamais répercuté le split 20:1 de 2017 (ADR-032) sur
   `shares_outstanding` — la vraie valeur (22 070 400, confirmée par calcul manuel :
   822.37 FCFA d'EPS FY2024 exact) n'existe qu'en base Supabase (correction
   manuelle antérieure, ADR-012), pas côté source.

**Conséquence :** pour NTLC, le garde-fou bloque le remplacement (ratio ~1e-6, hors
bornes) → `eps_scraped` (16447.64, lui-même faux) reste en base. Le critère
d'acceptation initial de T4 (NTLC FY2024 = 822.37 FCFA) n'est **pas** atteint.
Traitement reporté — cf. BACKLOG.md.

**Validation :** 24/24 tests pytest passent (non-régression). Validation manuelle
NTLC FY2024 : eps_recalcule=16 500 000 000 (aberrant), garde-fou déclenché, eps
scrapé conservé — comportement attendu et volontaire.

## ADR-034 : Frais de transaction et traitement IRVM — T5a

**Contexte** : Collecte des frais de courtage réels et taux IRVM pour l'intégration T5b dans le pipeline de backtest dividend capture.

**Décisions** :
1. Structure de frais de transaction retenue :
   - Commission BRVM : 0,2% du montant (acheteur + vendeur), source officielle brvm.org
   - Commission DC/BR : 0,1% du montant (acheteur + vendeur), source officielle brvm.org
   - Courtage SGI BOA Capital Securities : 1% du montant, maximum homologué 1% — **source Scribd non-primaire, non re-confirmée via CREPMF ou avis d'opéré réel**
2. IRVM : Jocelyn confirmé personne physique (formulaire consentement BOA Capital, 27/12/2025). Taux applicable dépend du statut brut/net par titre, indiqué par avis officiel BRVM (astérisque = brut, IRVM à appliquer ; sans astérisque = net, IRVM déjà déduit).
3. Méthode de calcul confirmée sur cas réel (NTLC exercice 2024) : dividende net = dividende brut × (1 − taux IRVM). Ex. 820 FCFA brut × (1 − 0,12) = 721,6 FCFA net pour personne physique.
4. Statuts confirmés par ticker (dernière donnée disponible) :
   - BOAC : net (exercice 2025, 594,528 FCFA)
   - BOAB : net (exercice 2025, 585 FCFA)
   - ECOC : brut, IRVM 12% (exercice 2025, 888 FCFA)
   - NTLC : brut, IRVM 12% (exercice 2024, 820 FCFA — exercice 2025 non encore publié à cette date)
   - NSBC : net (exercice 2024, 759,2612 FCFA — exercice 2025 non encore publié à cette date)
   - SMBC : **aucun avis identifié, statut brut/net et taux inconnus**

**Limitations connues (voir BACKLOG.md)** : taux courtage SGI non confirmé par source primaire ; SMBC sans donnée ; NTLC/NSBC exercice 2025 non publiés ; possible désynchronisation brut/net dans `corporate_events` déjà stocké.

**Statut** : T5a clôturée avec limitations documentées. T5b peut démarrer avec ces valeurs, sous réserve de correction ultérieure si les gaps se résolvent.
## ADR-035 — Colonne alpha dans la vérification quotidienne (T16)

**Date :** 28/07/2026

**Statut :** Accepté, en production (commit `4368e2e`, branche `remediation-2026-07`)

### Contexte

`verify_decisions.py` mesurait uniquement le rendement brut de chaque signal à J+20 (`variation_pct`). "Battre le marché" n'était mesuré nulle part — un signal ACHAT à +3% était compté comme un succès même si l'ensemble du marché BRVM avait fait +8% ce jour-là. Cette absence rendait toute comparaison honnête entre V1 et V2, ou entre stratégies, structurellement incomplète : un hit rate élevé peut refléter un marché haussier général plutôt que la qualité du signal (biais déjà identifié dans l'entrée du 18/07/2026 sur le J+90, groupe BOA/SNTS).

T16 était identifiée comme prérequis de toutes les expérimentations (E1.*, E2.*) et de toute comparaison V1/V2 rigoureuse, avant même T5c dans l'ordre de priorité recommandé initialement — réalisée après T5c dans les faits, sans que cela pose de problème pratique (les expériences `tools/experiments/` calculent leur propre alpha en interne, indépendamment de cette colonne).

### Décision

1. **Schéma** — deux colonnes ajoutées à `brvm_decisions_results` via SQL Editor (conforme ADR-026, mass DB corrections via SQL Editor uniquement) :
   ```sql
   ALTER TABLE brvm_decisions_results
      ADD COLUMN benchmark_return numeric,
      ADD COLUMN alpha numeric;
   ```

2. **Définition du benchmark** — `benchmark_return` = moyenne simple (non pondérée) des `variation_pct` de **tous les tickers vérifiés le même jour**, dans le même run de `verify_decisions.py`. Pas un indice BRVM officiel, pas de pondération par capitalisation — un proxy de marché local à l'échantillon quotidien de signaux vérifiés.

3. **Alpha** — `alpha = variation_pct − benchmark_return`, calculé et injecté par ligne après la boucle de vérification, avant l'upsert.

4. **Tolérance de prix** — aucune nouvelle logique introduite. Le calcul réutilise directement `variation_pct`, déjà calculé par `get_price_at_date()` avec sa tolérance existante de ±5 jours calendaires. La spec initiale envisageait une tolérance dédiée de ±3 jours ouvrés pour le benchmark spécifiquement ; décision prise de ne pas la complexifier — simplicité et cohérence avec le code existant priorisées sur une conformité littérale à la spec écrite initiale (décision de session, 28/07/2026).

5. **Portée** — patch strictement additif à `verify_decisions.py` (aucune signature de fonction modifiée, aucun paramètre ajouté). Aucun script consommateur externe cassé (seul appelant en prod = GitHub Actions, workflow quotidien après `generate_decisions.py`).

### Conséquences

- **Pas de backfill sur l'historique.** Les lignes de `brvm_decisions_results` antérieures au 28/07/2026 ont `benchmark_return`/`alpha` = `NULL`. Un backfill rétroactif serait une tâche séparée (calcul day-by-day sur l'historique complet), non traitée ici.
- **Limite connue** : si un seul ticker est vérifié un jour donné, `benchmark_return` = son propre `variation_pct` et `alpha` = 0 pour ce ticker — mathématiquement correct mais non informatif ce jour-là. Cas marginal, pas bloquant.
- **`benchmark_return` n'est pas un indice de référence externe** (pas le BRVM Composite officiel) — c'est la moyenne des signaux vérifiés ce jour-là, qui peut différer du marché global si l'échantillon de signaux du jour est biaisé sectoriellement. À garder en tête pour toute lecture future de la colonne `alpha`.
- **Débloque** : badge proof-level frontend (T16 était listé comme prérequis), toute future comparaison V1/V2 alpha-ajustée, et la règle de cadence "une promotion de modèle en prod toutes les 4 semaines, mesurée par la colonne alpha" mentionnée dans les principes du projet.

### Validation

Testé en conditions réelles le 28/07/2026 : 47 tickers vérifiés, `benchmark_return` = +2.79%, upsert confirmé en base (vérifié par requête directe post-exécution). Aucune régression sur le hit rate global cumulé (54.3%, cohérent avec l'historique).
## ADR-036 — Règle de sortie V2 (T10, Volet A)

**Date :** 28/07/2026

**Statut :** Accepté — figé avant toute position réelle sur signaux V2

### Contexte

V2 (cours cible) sait générer des signaux ACHAT, mais aucune règle de sortie ni aucun seuil de suspension (kill-switch) n'existait avant cette décision. Le plan de remédiation (Phase 12, T10) impose que ces deux volets soient figés **avant** l'accumulation de positions réelles sur signaux V2 — pas après les premières pertes. C'est la seule tâche du plan dont l'échéance est dictée par le portefeuille personnel de Jocelyn, pas par l'ordre du plan.

### Décision

Trois règles de sortie, appliquées dans cet ordre de priorité (la première condition atteinte déclenche la sortie) :

1. **Sortie cible** — le cours atteint ≥ 95% du `cours_cible` du jour (recalculé au refresh courant, pas figé à la date d'achat).
2. **Sortie temps** — J+90 depuis la date d'achat, si aucune des autres conditions n'a déclenché avant. Horizon aligné sur celui du backtest V2 (T5b, T6, E2.*).
3. **Sortie fondamentale** — le ticker sort des critères de sélection V2 (ROE, collapse EPS) au refresh suivant → sortie au prochain point de liquidité disponible (pas de vente forcée immédiate, la BRVM étant peu liquide).

**Pas de stop-loss prix serré.** Décision explicite de ne pas utiliser de stop-loss classique. Rationale : sur la BRVM, l'exécution d'un stop est illusoire du fait de l'illiquidité structurelle de la majorité des tickers — un ordre stop peut ne trouver aucune contrepartie au moment voulu, ou s'exécuter à un prix très dégradé par rapport au seuil visé. La protection contre les pertes extrêmes vient plutôt de deux mécanismes complémentaires :
- Le **sizing** (T11, sous gate Phase 13 — pas encore actif) : limiter la mise par signal selon la qualité du signal et la liquidité du titre.
- Le **kill-switch** (T10, Volet B) : suspension des nouveaux achats V2 si la performance récente des signaux se dégrade, indépendamment des positions déjà ouvertes.

### Conséquences

- Ces règles de sortie sont **manuelles à ce stade** — aucune automatisation d'ordres n'existe ni n'est prévue dans le périmètre actuel du projet. Elles servent de référence de décision pour Jocelyn, pas de déclencheur automatique.
- La sortie fondamentale dépend de la fraîcheur du refresh V2 — si le pipeline de scoring a un délai ou une panne silencieuse (cf. T1/`health_check.py`), la détection de sortie fondamentale peut être retardée. Aucune action corrective spécifique prise ici ; couvert indirectement par T1.
- L'absence de stop-loss signifie que le risque de perte maximale par position n'est plafonné que par la sortie temps (J+90) et la surveillance manuelle — pas par un mécanisme automatique de coupure de perte. Ce choix est assumé au vu de l'illiquidité BRVM, mais reste un risque à garder en tête tant que le sizing (T11) n'est pas actif.
- Débloque la suite du Volet B (script `killswitch_check.py`) et, à terme, T11 (sizing continu) une fois la Phase 13 gate levée (T6 + T9 favorables).

### Prochaine étape

Volet B — script `tools/killswitch_check.py` (délégable, Classe A ou B selon le protocole du plan), constantes par défaut à confirmer : `N_MIN=15`, `SEUIL_POSITIFS=0.50`, `SEUIL_MEDIANE=0.0`.
## ADR-037 — Concentration sectorielle de V2 (T14)

**Date :** 30/07/2026

**Statut :** Constat documenté — aucun changement de pipeline dans cette tâche (lecture seule, conforme à la spec T14)

### Contexte

Hypothèse à vérifier (Phase 11 du plan de remédiation) : V2 (cours cible) serait en réalité un "long banques UEMOA avec timing dividende" plutôt qu'une sélection de valeur diversifiée. Script `tools/diagnostic_concentration_sectorielle.py`, mapping sectoriel repris de `calculate_target_price.py` (`SECTEUR_OFFICIEL`, 7 catégories officielles BRVM — distinct du mapping simplifié de `backtest_value.py` et du mapping `companies.sector`, qui coexistent tous deux dans le repo sans être synchronisés entre eux).

### Résultats

| Volet | n | Secteur dominant | % | Seuil 60% |
|---|---|---|---|---|
| (a) 25 signaux ACHAT du backtest V2 (FY2021-FY2024) | 25 | SERVICES_FINANCIERS | 68.0% | Dépassé |
| (b) Signaux ACHAT actuels de `target_prices` (30/07/2026) | 3 | TELECOMMUNICATIONS | 66.7% | Dépassé (non interprétable, voir réserve) |

**Réserve sur le Volet (b) :** n=3 seulement. Avec un échantillon aussi restreint, tout secteur ayant 2 signaux sur 3 dépasse mécaniquement le seuil de 60%, indépendamment de toute concentration structurelle réelle du modèle. Ce chiffre reflète l'état instantané de `target_prices` au 30/07/2026, pas une mesure fiable de biais sectoriel — à ne pas comparer au même niveau de confiance que le Volet (a).

**Le Volet (a) est le résultat robuste** : sur l'échantillon complet et stable des 25 signaux historiques du backtest, 17 proviennent du secteur Services Financiers (banques), soit 68% — nettement au-dessus des 60% du seuil défini par le plan, et aussi au-dessus des ~34% que représente ce secteur dans l'univers total de tickers mappés (16/47), ce qui exclut un simple effet de composition du marché.

### Décision (règle appliquée textuellement, plan de remédiation T14)

**"V2 = exposition sectorielle concentrée ; plafond d'exposition par secteur à fixer par Jocelyn (proposition de départ : 50% du capital alloué à V2)."**

Aucune valeur de plafond tranchée dans cette tâche — décision Jocelyn à prendre séparément, hors périmètre de ce diagnostic (lecture seule).

### Conséquences

- Confirme et précise l'hypothèse de départ : V2 n'est pas un modèle diversifié, il surpondère structurellement les Services Financiers.
- Cohérent avec T9 (V2 ne bat pas la stratégie dividende naïve, elle-même concentrée sur 6 tickers dont une majorité de banques) — deux résultats indépendants pointant vers la même réalité : la performance apparente de V2 pourrait être en grande partie un effet sectoriel bancaire plutôt qu'un edge de sélection général.
- Un plafond d'exposition par secteur (T14) devient d'autant plus pertinent si une décision de production sur V2 est prise à l'avenir, malgré le gel actuel de la Phase 13 (cf. T9).

### Item BACKLOG ajouté (priorité haute)

**Modèles de valorisation différenciés par secteur.** V2 utilise un modèle unique (PER sectoriel × EPS + composante dividende) pour tous les secteurs, ne faisant varier que la valeur du PER de référence. La littérature financière établit que les praticiens utilisent des modèles structurellement différents par secteur — pour les banques spécifiquement, une combinaison P/E + P/B ou un modèle d'actualisation des dividendes est standard, le DCF classique étant jugé inadapté pour les institutions financières (bilan et régulation spécifiques). Ceci pourrait expliquer une partie de la sur-représentation des banques dans les signaux ACHAT de V2 : non pas une vraie sous-évaluation, mais un modèle structurellement plus favorable à ce secteur qu'aux autres. Piste à explorer : modèle P/E+P/B dédié pour SERVICES_FINANCIERS, cohérent avec la pratique observée sur le dividend capture (déjà concentré sur des banques et validé empiriquement par T5c-A/T5c-B/E2.6/E2.7-A). Non traité dans cette session — item de recherche, pas une correction immédiate.
## ADR-038 — Horizon de vérification = J+20 (remplace 90 jours) [restauré — ex-ADR-019, écrasé par collision de numérotation le 28/06/2026]

**Date :** 26/05/2026 (date de la décision originale)

**Note de restauration (30/07/2026, T17) :** ce texte est la restauration intégrale de l'ADR-019 original, écrasé le 28/06/2026 lorsqu'un autre sujet ("Analyse fondamentale bloquée — contrainte SQL parasite + extraction titre") a réutilisé le même numéro. Contenu retrouvé via `git log -p -- DECISIONS.md`, commit `13a041c` (26/05/2026, "ADR-016 à ADR-019 — signal technique bruit, BOA V2, liquidité filtre, horizon J+20"). Texte reproduit sans modification depuis l'original. Voir l'ADR-019 actuel pour le renvoi croisé.

**Contexte :** Backtest 10 ans montre signal s'améliorant de J+5=47.9% à J+30=56.7%. Régression live montre pic BOA à J+20.

**Décision :** Modifier `verify_decisions.py` pour vérifier à J+20 au lieu de 90 jours post-dégel.

**Raison :** 90 jours croise trop d'événements exogènes (AG, ex-dividendes, chocs macro) qui masquent le signal initial. Le signal fondamental BOA peak à J+20 — c'est l'horizon de convergence naturel sur le BRVM.

**Conséquences :** Résultats de vérification plus rapides et plus propres. Modifier aussi l'affichage "Valide jusqu'au" sur les DecisionCards post-dégel.

**Note complémentaire (30/07/2026) :** cette décision reste la justification en vigueur du comportement actuel de `verify_decisions.py` (`VERIFICATION_WINDOW = 20`, cf. commentaire dans le code source). L'entrée du 18/07/2026 dans `REMEDIATION_LOG.md` (calcul ad hoc multi-horizons J+20 à J+90) a depuis nuancé ce choix — le hit rate continue de croître au-delà de J+20 (81.8% à J+90 sur un échantillon plus restreint, n=132), mais cette découverte n'a pas encore donné lieu à une révision formelle de cet ADR ; elle reste documentée comme observation ad hoc distincte, avec ses propres réserves méthodologiques (biais de tendance de marché non contrôlé).

---

## ADR-039 — Backfill historique de la colonne alpha (T16-backfill)

**Date :** 30/07/2026

**Statut :** Accepté, exécuté en base (`backfill_alpha.sql` + `tools/backfill_alpha.py`, branche `remediation-2026-07`)

### Contexte

ADR-035 laissait explicitement ouvert le backfill historique : les 3088 lignes de `brvm_decisions_results` antérieures au 28/07/2026 avaient `alpha`/`benchmark_return` = `NULL`, contre une couverture ≥95% exigée par la spec v1.4. Conséquence pratique immédiate : le kill-switch T10-B, dont le critère repose sur l'alpha, ne disposait que d'une seule journée de données (n=47 au 28/07) et s'est déclenché sur ce qui a été documenté comme un probable artefact de faible n. Sans backfill, T10-B ne pouvait pas être considéré comme opérationnel.

### Décision

1. **Clé de cohorte — divergence assumée avec la production.** Le backfill groupe par `(signal_date, verification_date)`, alors que `verify_decisions.py` groupe par jour de vérification seul. Justification : le 16/05/2026 est un jour de rattrapage où deux cohortes de signaux distinctes ont été vérifiées ensemble (36 lignes du 03/04, 47 lignes du 16/04), soit deux fenêtres de détention différentes. Grouper par jour seul aurait produit un benchmark unique ne correspondant à aucune des deux cohortes ; les benchmarks séparés valent respectivement 3.64 et 1.41 — l'écart n'est pas négligeable. Les 65 autres jours n'ont qu'une seule `signal_date` : sur eux, les deux clés donnent un résultat rigoureusement identique.

2. **Définition inchangée** — `benchmark_return` = moyenne simple des `variation_pct` de la cohorte, tous signaux confondus (ACHAT/SURVEILLER/VENDRE) ; `alpha = variation_pct − benchmark_return`. Arrondi à 2 décimales sur les deux colonnes, aligné sur la précision de `variation_pct`.

3. **Périmètre** — filtre `alpha IS NULL` : les 47 lignes du 28/07 écrites par `verify_decisions.py` ne sont pas retouchées et servent de **témoin de conformité** (voir Validation).

4. **Exécution** — une unique requête `UPDATE ... FROM` transactionnelle via SQL Editor (conforme ADR-026), pas de génération de 3088 `UPDATE` unitaires : atomicité, aucun état partiel possible. `tools/backfill_alpha.py` est un harnais de **vérification en lecture seule**, rejouable, n'écrivant rien.

5. **Sauvegarde préalable** — snapshot JSON complet de la table (3135 lignes) pris avant écriture, hors repo. Supabase Free n'offre aucune sauvegarde automatique : un UPDATE de masse sans snapshot serait irrécupérable.

### Conséquences

- **Couverture 100%** (3135/3135), au-delà des 95% exigés. L'écart de conformité stricte à la spec v1.4 documenté dans ADR-035 est levé.
- **Débloque T10-B** : le kill-switch dispose désormais de 67 cohortes d'historique au lieu d'un jour unique. Le déclenchement du 28/07 doit être réévalué sur cette base avant toute conclusion sur V1.
- **Débloque la relecture de T9 en alpha** : les trois volets de la falsification comparaient des médianes de rendement brut sur des fenêtres temporelles non appariées (réserve méthodologique explicitement notée dans `REMEDIATION_LOG.md`). L'alpha neutralise en partie ce biais.
- **Débloque le badge proof-level frontend**, déjà listé comme dépendant de T16.
- **Nouvel item backlog — désalignement production/historique.** `verify_decisions.py` groupe toujours par `verification_date` seul. Sans effet aujourd'hui, mais au prochain jour de rattrapage la production écrira un benchmark mélangé, incohérent avec l'historique backfillé. Correctif d'une ligne, mais modification de production : traité séparément, pas dans cette tâche.
- **Limite héritée d'ADR-035, inchangée** : `benchmark_return` reste la moyenne des signaux vérifiés, pas un indice BRVM officiel. L'alpha mesure donc "battre l'échantillon vérifié du jour", pas "battre le BRVM Composite". Les chiffres ne sont pas comparables à une performance publiée contre indice.
- **Auto-inclusion assumée** : chaque ligne fait partie de son propre benchmark, ce qui contracte l'alpha d'un facteur ~46/47 (≈2%). Un leave-one-out serait plus pur mais divergerait des lignes de production ; l'uniformité a été priorisée sur la pureté.
- **Cohorte du 03/04 asymétrique** : 36 tickers au lieu de 47, son benchmark porte donc sur un sous-ensemble de l'univers. Reconstruire les 11 manquants depuis `historical_data` aurait ouvert un chemin de données neuf pour une seule cohorte sur 67 — écarté.

### Validation

Trois contrôles, exécutés en SQL puis revalidés indépendamment via REST par `tools/backfill_alpha.py` :

1. **Couverture** — 3135/3135 = 100.00%, 0 NULL restant.
2. **Invariant mathématique** — la moyenne des `alpha` d'une cohorte doit valoir exactement 0 par construction. Vérifié sur les 67 cohortes : écart maximal à zéro = 0.004894, soit le résidu d'arrondi attendu (2 décimales réparties sur ~47 lignes). Un écart supérieur aurait signalé une erreur de regroupement.
3. **Témoin de production** — confrontation de la formule aux 47 lignes du 28/07 écrites par `verify_decisions.py`, non retouchées par le backfill : benchmark recalculé = +2.79% (identique), **0 divergence** sur les 47 lignes, `benchmark_return` et `alpha` compris. C'est le contrôle décisif : il établit que les valeurs historiques rétro-calculées sont homogènes à celles produites en production, donc comparables entre elles.

---

## ADR-040 — Décalage d'un an de `DIVIDEND_HISTORY.fiscal_year` (constat de bug)

**Date :** 31/07/2026

**Statut :** Constat accepté, corrections non faites (tâches séparées, cf. BACKLOG)

### Contexte

Découvert le 31/07/2026 à l'occasion d'une analyse de sensibilité frais/IRVM, à partir de pièces justificatives fournies par Jocelyn : avis officiels BRVM de paiement de dividendes (N°111 SONATEL, N°121 BOA BÉNIN, N°137 ONATEL, N°228 NESTLÉ CI, exercice 2025) et avis de crédit du courtier BOA Capital Securities.

### Constat

`corporate_events.DIVIDEND_HISTORY` (source `sikafinance_history`, 936 lignes) étiquette `fiscal_year` avec **un an de retard**. `EX_DIVIDEND` (source `richbourse_calendar`) et `DIVIDEND` (source `sikafinance`, 46 lignes) suivent la convention BRVM correcte.

Preuve : le même montant apparaît deux fois dans `dividend_cycle_exploration.csv`, à deux ex-dates distantes d'un an.

| ticker | ligne DIVIDEND_HISTORY | ligne DIVIDEND | vérité terrain (avis de crédit) |
|---|---|---|---|
| SNTS | 1740.0 — ex 2025-05-20 | 1740.0 — ex 2026-05-22 | 17 400 pour 10 titres, reçu 29/05/2026 |
| BOAB | 585.0 — ex 2025-05-30 | 585.0 — ex 2026-05-14 | 2 925 pour 5 titres, reçu 29/05/2026 |
| ONTBF | 145.0 — ex 2025-07-17 | 145.32 — ex 2026-06-12 | 2 325 pour 16 titres, reçu 17/06/2026 |
| BOAC | 595.0 — ex 2025-05-16 | 594.53 — ex 2026-05-05 | 5 945 pour 10 titres, reçu 11/05/2026 |

Le dividende réellement détaché en mai 2025 par SONATEL était 1655, pas 1740.

### Conséquences

1. **Look-ahead d'un an.** `tools/falsification_v2.py` (T9 volet A, lignes 133-145) joint `EX_DIVIDEND × DIVIDEND_HISTORY` sur `fiscal_year` strictement égal — jointure documentée comme « obligatoire » dans le code, mais fausse. Chaque ex-date reçoit le montant de l'année suivante.

2. **Propagation à toute la chaîne dividende.** `dividend_cycle_exploration.csv` (produit par `tools/explore_dividend_cycle.py`) porte le même défaut : **77 des 89 cycles exploitables** utilisent un montant décalé (12 seulement viennent de la source saine `DIVIDEND`). Ce CSV alimente E2.6, E2.7-A, E2.7-B et T5c-A (`E2_8_rotation`).

3. **Ampleur — erreur de mesure modérée** : médiane +8.2%, moyenne +20.8%, 63% des cycles surestimés, étendue −77.9% à +398.5%. Le dividende pesant ~8-15% du prix, une erreur médiane de +8% vaut ~+0.8 pt de rendement par cycle, contre un alpha médian T5c-A de +7.39 pts. La conclusion qualitative de T5c-A/E2.7 tient donc probablement ; les chiffres publiés sont faux.

4. **Ampleur — erreur de sélection, problème principal.** `yield_pct` est décalé comme le montant. Le filtre `yield_pct >= 8%` de T9 volet A a donc **sélectionné les trades sur le rendement de l'année suivante**. Ce n'est plus de l'imprécision de mesure mais du look-ahead sur le choix des positions, avec un biais orienté (63% de surestimation). Le volet A à 100% de trades positifs devient suspect.

5. **Le verdict T9 est fragilisé.** *« V2 non différencié de la stratégie naïve — GELER la Phase 13 »* reposait sur la comparaison d'un bras naïf contaminé (médiane 13.14%, 100% positifs) contre V2 (7.81%, 68%). La comparaison est à refaire. **Ceci ne réhabilite pas V2** : T6 (IC95% borne basse négative) et T14 (concentration sectorielle 68% SERVICES_FINANCIERS) restent des résultats indépendants et inchangés.

6. **12 cas graves** (|erreur| ≥ 50%), dont SPHC FY2023 (+398.5%), STBC FY2023 (+209.6%), SOGC FY2023 (+155.1%). SOGC, STBC et CBIBF figurent parmi les tickers « robustes » de T5c-A.

7. **Correction possible mais coûteuse** : pour toute ligne `DIVIDEND_HISTORY` d'exercice FY, le montant correct est celui de FY−1. **26 cycles deviennent non corrigeables** (le plus ancien de chaque ticker n'a pas de FY−1) — soit ~29% de l'échantillon perdu.

### Résultat négatif à conserver

Une première tentative de preuve par les prix (`tools/diag_decalage_fiscal_year.py`) a été **invalidée** : elle supposait que le cours chute du montant du dividende à l'ex-date. Les données montrent que ce n'est pas le cas sur la BRVM (ONTBF : chutes de +5, −8.5, −20, +30 pour des dividendes de 145 à 288 ; ECOC 2026 et ORAC 2026 : chute exactement nulle pour 781 et 704 FCFA). Le score 60/40 obtenu ne mesure rien et ne doit pas être cité.

**Piste ouverte par cet échec** : si le cours ne s'ajuste pas à l'ex-date, le dividende est encaissé sans la perte en capital qui le compenserait sur un marché efficient — ce serait un mécanisme candidat pour expliquer le succès du dividend capture, indépendant du bug de jointure. À vérifier en contrôlant les volumes (plusieurs chutes à exactement 0.0 suggèrent des cours figés faute de transaction).

### Preuve retenue

Documentaire, pas statistique : concordance des avis officiels BRVM, des avis de crédit du courtier et des lignes `DIVIDEND` de la base, sur quatre tickers indépendants.

---

## ADR-041 — `company_fundamentals.dividend_per_share` mélange brut et net (constat de bug)

**Date :** 31/07/2026

**Statut :** Constat accepté, correction non faite (décision de convention en attente de Jocelyn)

### Contexte

Découvert le 31/07/2026 en vérifiant si le décalage d'ADR-040 touchait la production. Il ne la touche pas — `calculate_target_price.py` lit `company_fundamentals`, pas `corporate_events`. Mais l'examen a révélé un défaut distinct, lui en production.

### Constat

**Deux scripts écrivent la même colonne avec des conventions incompatibles :**

| script | source | `fiscal_year` écrit | convention montant | dans le workflow |
|---|---|---|---|---|
| `scrape_all_v4.py` | stockanalysis.com | FY2021→FY2025 (exercice comptable) | **brut** | oui |
| `scrape_boc_pdf.py` | Bulletin Officiel de la Cote (BRVM) | `FY{année_civile}` = FY2026 | **net** (champ `rdt_net`, ligne 122) | oui |

Le rapport entre les deux vaut exactement le taux d'IRVM du pays de l'émetteur. Sur 24 tickers comparables, **17 ont un résidu nul (±0.0%)** après division par le facteur `1/(1−taux)`, sur cinq taux distincts :

| taux IRVM | pays | facteur | tickers à résidu nul |
|---|---|---|---|
| 12% | Côte d'Ivoire | +13.6% | BICC, CABC, CFAC, NTLC, SDCC, SIBC, SOGC, SPHC, TTLC, SGBC, STBC |
| 10% | Sénégal | +11.1% | SNTS, BOAS, TTLS |
| 12,5% | Burkina Faso | +14.3% | ONTBF |
| 7% | Mali / Niger | +7.5% | BOAM, BOAN |

Concordance sur cinq taux différents : l'explication n'est pas fortuite.

**Sept exceptions**, toutes attribuables à un second effet superposé — un décalage d'exercice (le dividende a changé d'une année sur l'autre) :
- résidus négatifs : BOAB −20.0%, BOAC −23.3%, ECOC −9.5%, PALC −2.1% (hausses réelles du dividende, confirmées pour BOAB 468→585 et BOAC 459→594.53 par les avis de crédit)
- résidus positifs : BOABF +8.0%, ORAC +6.7%, CIEC +5.6% (variation dans le même sens que l'effet IRVM)

### Ce qui n'est PAS un bug

La formule du cours cible V2 applique Gordon au dividende (`dividende / TAUX_ACTUALISATION`, poids 30%). Utiliser le **brut** est la convention standard. La valeur actuellement retenue en production est donc du brut, ce qui est cohérent avec la formule.

Mécanisme de sélection : `fetch_fundamentals()` (ligne 217) filtre sur `eps=not.is.null`. Les lignes FY2026 du BOC n'ont pas d'EPS, donc elles sont écartées et `latest` tombe sur la ligne FY2025 de stockanalysis. C'est un filtrage **accidentel** — il produit aujourd'hui le bon résultat sans que rien ne le garantisse.

### Le vrai défaut

Une même colonne porte deux conventions selon le dernier script ayant écrit, et aucun consommateur ne sait laquelle il lit. Les consommateurs identifiés sont `calculate_target_price.py`, `signaux_actifs.py` et `report_generator.py`.

Le jour où le BOC renseigne un EPS, où l'ordre d'exécution du workflow change, ou où un upsert écrase l'autre, les cours cibles se déplacent d'environ 12% sans qu'aucune ligne de code n'ait été modifiée. **Risque latent, pas incident en cours.**

Impact chiffré si la bascule survenait : la composante Gordon pèse 30% du cours cible, donc un passage brut→net déplacerait le cours cible d'environ −3,5%, dans le sens qui réduit la décote et donc le nombre de signaux ACHAT.

### Options de correction (décision Jocelyn requise)

Le choix porte sur la convention que la colonne doit porter. Aucune n'est appliquée à ce stade.

1. **Colonne = brut, source unique stockanalysis.** `scrape_boc_pdf.py` cesse d'écrire `dividend_per_share` (il continue d'écrire `pe_ratio`, `dividend_yield`, `ex_dividend_date`). Le plus simple ; perd la donnée BOC, qui est pourtant la source primaire.
2. **Deux colonnes distinctes** — `dividend_per_share_brut` et `dividend_per_share_net`, chaque script écrivant la sienne. Le plus propre ; nécessite un `ALTER TABLE`, une migration des données existantes et la mise à jour des trois consommateurs.
3. **Colonne = net, conversion à la lecture.** Cohérent avec le rendement réellement encaissé, mais impose de connaître le taux d'IRVM par pays à chaque lecture et change la formule de Gordon.

L'option 2 est la seule qui préserve les deux informations. Elle est aussi la plus coûteuse.

Point connexe, indépendant de ce choix : `scrape_boc_pdf.py` ligne 111 (`fy = f"FY{trade_date.year}"`) étiquette le dividende par son **année de versement**, pas par l'exercice. Le dividende de l'exercice 2025, versé en mai 2026, est écrit en FY2026. À corriger quelle que soit l'option retenue.

### Validation

Analyse en lecture seule, aucune écriture en base ni en production. Test : pour chaque ticker, comparaison de la ligne effectivement retenue par `fetch_fundamentals()` (la plus récente avec EPS non-null) à la ligne FY2026 du BOC, résidu calculé après division par `1/(1−taux_IRVM_pays)`. Taux issus des sources publiques recoupées le 31/07/2026 et de l'avis BRVM N°228 (NESTLE CI, exercice 2025), qui mentionne explicitement 12% personnes physiques / 10% personnes morales.

**Réserve** : la table de correspondance ticker→pays a été établie manuellement pour ce diagnostic et n'existe pas dans le repo. Elle mériterait d'être versionnée si l'option 3 est retenue.

---

## ADR-042 — Migration des clés Supabase legacy vers le format `sb_secret_` / `sb_publishable_`

**Date** : 06/08/2026
**Statut** : appliqué côté pipeline, en attente côté frontend

**Contexte.** Supabase a désactivé les clés API legacy (`anon`, `service_role`, format JWT) le **2026-07-27T21:46:45+00:00**. Le remplacement est un couple `sb_publishable_...` (navigateur, équivalent `anon`) / `sb_secret_...` (serveur, équivalent `service_role`). La désactivation est intervenue côté Supabase indépendamment de toute action locale : une rotation de clé *dans* le système legacy (effectuée la semaine du 27/07) ne suffit pas, c'est le format lui-même qui n'est plus honoré.

**Symptôme.** Les deux workflows planifiés ont échoué en boucle. Deux signatures distinctes selon le mode d'accès :
- appels REST directs (`requests`) → HTTP 401, corps `{"message":"Legacy API keys are disabled","hint":"..."}` ;
- client `supabase-py` → `SupabaseException: Invalid API key`, levée dans `create_client()` avant tout appel réseau.

**Décision.**
1. Le secret GitHub `SUPABASE_SERVICE_ROLE_KEY` contient désormais une clé `sb_secret_...`. **Le nom du secret est conservé** malgré l'imprécision (ce n'est plus une clé `service_role`) : le renommer imposerait de modifier tous les workflows et tous les scripts en une fois. Dette assumée et tracée.
2. `supabase-py` doit être ≥ 2.30.0 : les versions antérieures (2.6.0 en production) rejettent le nouveau format. Le bump entraîne `realtime` et `storage3` en 2.30.0 (voir REMEDIATION_LOG 06/08).
3. Les appels REST directs (`apikey` + `Authorization: Bearer`) fonctionnent sans modification de code avec le nouveau format — ADR-004 (REST-only) reste valide et n'est pas remis en cause.

**Reste à faire.** `VITE_SUPABASE_ANON_KEY` (Vercel, projet `brvm-analytics`, non modifiée depuis le 02/04/2026) est toujours une clé legacy `anon`. Le frontend fonctionne encore, donc la désactivation ne semble pas appliquée au rôle `anon` avec la même rigueur — mais la même panne silencieuse est possible à tout moment. Migration vers `sb_publishable_...` à planifier.

**Leçon opérationnelle.** Une clé désactivée côté fournisseur ne produit aucune alerte : seuls les workflows planifiés échouent, et personne ne lit les échecs planifiés. `health_check.py` ne couvre pas ce cas.

---

## ADR-043 — Clôture de la chaîne « dividend capture »

**Date** : 08/08/2026
**Statut** : décidé — piste abandonnée

**Décision.** La chaîne d'expérimentations « dividend capture » (E2.6, E2.7-A, E2.7-B, E2.8, T5c-A, T5c-B) est close. Aucune stratégie de capture de dividende n'est retenue en production. Cette décision est définitive en l'état des données ; elle ne pourra être rouverte que par une hypothèse *nouvelle*, pas par un ré-examen des résultats existants.

**Motif 1 — cause racine des résultats publiés : asymétrie de benchmark.** Toute expérience calculant le rendement du sujet dividende inclus tout en comparant à un benchmark prix pur produit un alpha fictif exactement égal au rendement du dividende. L'audit du 07/08 (commit `741fcfd`) mesure une contribution mécanique de +8,561 pts sur E2.6 et une contribution identique à trois décimales sur E2.8/T5c-A : ces deux « résultats » ne sont pas deux découvertes indépendantes, c'est le même artefact compté deux fois. E2.7-A et E2.7-B reposent sur la même mécanique (12/12 combinaisons positives dans chaque grille = profil d'un terme additif quasi constant) ; ils ne sont pas audités et ne le seront pas, l'audit ne changeant aucune décision.

**Motif 2 — test indépendant, négatif.** E3.0 (08/08/2026) mesure la trajectoire du prix autour de l'ex-date **sans faire intervenir aucun montant de dividende**, donc sans jointure sur `fiscal_year` : la mesure est immunisée contre l'asymétrie de benchmark *et* contre ADR-040 par construction. Seuils fixés par écrit avant lecture des données, sur la médiane de `recup_45_vs_pre` : ≥ −0,5% → mécanisme vivant ; entre −0,5% et −2,6% (frais aller-retour) → ne couvre pas ses frais ; < −2,6% → mécanisme mort.

Résultat sur SNTS/BOAC/BOAB, 16 cycles dont 14 exploitables (2016–2026) : **médiane −3,03%**, 4/14 cycles positifs (28,6%), dispersion −11,34% à +3,26%. **Seuil « mécanisme mort » franchi.**

**Motif 3 — convergence de deux méthodes indépendantes.** L'arithmétique a priori (0,88 × D encaissé − 0,37 × D de décrochage − 2,6% de frais ≈ +1% net sur un rendement de 7%) et la mesure empirique (−3,03% de prix + ~6,2% de dividende net d'IRVM − 2,6% de frais ≈ +0,5%) donnent la même réponse. Un gain d'environ 1% pour une dispersion de 15 points n'est pas une stratégie exploitable. La sensibilité au taux de courtage SGI (1%, non confirmé par source primaire — ADR-034) suffit à le rendre négatif.

**Correction factuelle documentée — l'ajustement du prix est différé, pas partiel.** L'hypothèse en vigueur était : « la BRVM n'ajuste pas le prix à l'ex-date, le décrochage observé est partiel (~37% du dividende), d'où une opportunité de capture. » E3.0 montre que le décrochage à J0 est effectivement quasi nul (médiane **−1,79%**) mais que la baisse **se poursuit ensuite** : médiane `ex_to_30` = **−2,38%**, `ex_to_45` = −1,06%. Le marché ajuste lentement, sur 30 à 45 jours, au lieu d'ajuster d'un coup. La prémisse « décrochage partiel = gisement » est donc fausse : il n'y a pas de partie non ajustée à capturer, seulement un ajustement étalé. Cette correction vaut indépendamment de la stratégie abandonnée et s'applique à toute analyse future de fenêtres post-ex-date.

**Périmètre fermé par cette décision.** Audit E2.7-A/B ; production T5c-A (déjà suspendue) et T5c-B ; analyse de sensibilité frais/IRVM sur T5c ; remédiation du bug ADR-040 (`fiscal_year` off-by-one) — plus aucun travail actif ne dépend de cette jointure. ADR-040 reste un constat de bug valide et non corrigé, à traiter si un futur besoin réactive `DIVIDEND_HISTORY`.

**Non affectés.** Validation multi-horizon V1 (commit `8ef56ad`, n=843), T9, T14, positions réelles du portefeuille : méthodologies distinctes, ne passent pas par `compute_benchmark` et n'intègrent pas de dividende dans le calcul de rendement.

**Réserve de portée.** E3.0 porte sur 3 tickers et 14 cycles exploitables. C'est exploratoire, pas concluant en soi — mais il ne s'agissait pas de prouver l'absence d'effet : il s'agissait de vérifier si la piste méritait d'être poursuivie après l'effondrement de ses résultats publiés. Le signe est défavorable et converge avec l'arithmétique. Cela suffit à arrêter.

**Leçon méthodologique.** Vérifier la symétrie du calcul de rendement entre sujet et benchmark **avant** d'interpréter tout alpha, pour chaque expérience de la chaîne. Un seuil pré-enregistré n'a de valeur que s'il est respecté quand il tombe du mauvais côté.

## ADR-044 — Fermeture de l'onglet Prévisions (modèle GRU non exploitable)

**Date** : 2026-08-10
**Statut** : Accepté
**Commit audit** : `95290c1` (branche `remediation-2026-07`)

### Contexte

Le modèle GRU alimente l'onglet Prévisions du frontend et tourne en production
via `brvm-analysis.yml` (`prediction_analyzer_v2.py` L195, `verify_predictions.py` L174)
depuis le commit `2d025d4` du 16/05/2026. Aucune vérification de ses sorties n'avait
jamais été lue — troisième occurrence du schéma « modèle en production sans validation »
après V2 et V3.

### Méthode

Seuils **pré-enregistrés avant lecture des résultats**, conformément au protocole E3.0 :

| Critère | Seuil |
|---|---|
| MASE = MAE_gru / MAE_naïve | < 0.85 : valeur ajoutée — 0.85–1.0 : marginal — ≥ 1.0 : fermeture |
| Taux de direction correcte | ≥ 55 % |

Comparateur : persistance naïve (prévision = dernier prix connu à `run_date`),
benchmark standard de la littérature de prévision (Hyndman & Athanasopoulos ;
M-competitions ; Meese & Rogoff 1983 pour le cas financier).

Appariement strict : aucune ligne n'entre dans une jambe sans sa contrepartie.
5 800 paires, **0 rejet faute de baseline**. Immunisé contre le défaut d'asymétrie
de benchmark qui a invalidé E2.6 et T5c-A (ADR-043).

Script : `tools/experiments/GRU_VERIF/audit_gru_vs_naive.py` (Classe A, lecture seule).

### Résultats

| Horizon | n | MAE GRU | MAE naïve | MASE | Direction |
|---|---|---|---|---|---|
| GLOBAL | 5800 | 641.30 | 339.74 | **1.888** | **47.9 %** |
| J+1–3 | 1476 | 296.55 | 150.96 | 1.964 | 56.4 % |
| J+4–7 | 1517 | 522.73 | 277.61 | 1.883 | 47.4 % |
| J+8–14 | 2266 | 841.01 | 449.11 | 1.873 | 43.7 % |
| J+15–30 | 541 | 1077.91 | 570.90 | 1.888 | 44.0 % |

### Décision

**L'onglet Prévisions ferme.** Le GRU produit une erreur ~1.9× supérieure à la
persistance naïve et une direction sous le hasard. Le seuil de fermeture (MASE ≥ 1.0)
est franchi de très loin.

Robustesse du verdict :
- MASE stable 1.87–1.96 sur **tous** les horizons — aucune poche d'exploitabilité
- Direction se **dégrade** avec l'horizon (56.4 % → 43.7 %), inverse du comportement
  attendu d'un modèle captant une tendance réelle
- Médianes cohérentes avec les moyennes — pas d'effet outlier
- Le seul point au-dessus du seuil de direction (J+1–3, 56.4 %) s'accompagne du pire
  MASE du tableau (1.964) : sens deviné, amplitude inexploitable pour un cours cible

### Séquence d'exécution

1. ADR-044 (présent commit)
2. Retrait de l'onglet du frontend — repo `brvm-analytics`, `App.jsx` via script de
   patch Python (ADR-002). **Session distincte.**
3. Débranchement de `verify_predictions.py` et `prediction_analyzer_v2.py` de
   `brvm-analysis.yml` — **après** le retrait frontend uniquement.

Ordre non négociable : couper le pipeline avant le retrait frontend laisserait un
onglet affiché alimenté par des données gelées, pire que la situation actuelle.
Les scripts et les tables `predictions` / `predictions_results` ne sont pas supprimés.

### Anomalie relevée (backlog, sans effet sur le verdict)

27 533 prévisions échues sur 33 333 ne sont jamais entrées dans `predictions_results`
(couverture 17 %). Règle de sélection inconnue. Ne réhabilite pas le modèle :
il faudrait que les 83 % manquants soient massivement meilleurs, incohérent avec
l'uniformité observée sur 5 800 points et sur cinq tranches d'horizon.

### Dette technique associée

- `prediction_analyzer.py` (`229f512`, 14/03/2026) — mort, référencé uniquement dans
  `.github/workflows/brvm-analysis.yml.backup`
- `patch_gru_forecast.py` — non tracké, script de patch ponctuel, rejoint la liste
  des fichiers non trackés à la racine

### Conséquence sur la refonte frontend

Le bloquant « recherche doc GRU/Prévisions » de la session du 27/07/2026 est **levé** :
la vérification existait et tournait, le verdict est négatif. L'onglet Prévisions sort
de la nav cible. La home reste sur V1 seul — seul modèle du projet disposant d'une
validation empirique (n=843, 65.6 % à J+20 → 81.8 % à J+90, commit `8ef56ad`).


## ADR-045 — Refonte home : fusion Aperçu + Marché (spec figée, implémentation conditionnée)

**Date :** 10/08/2026
**Statut :** ACCEPTÉ — implémentation bloquée par ADR-046
**Remplace :** notes de session 27/07/2026 (spec non formalisée)
**Lié à :** ADR-044 (retrait Prévisions de la nav cible)

### Contexte
La home actuelle (Aperçu) duplique une partie de l'onglet Marché. Session 27/07 :
décision de fusion, l'Aperçu absorbe Marché, qui disparaît de la nav.
Deux prérequis étaient en suspens : l'origine réelle de « Volume vs moy. 0.4x »
(levé ci-dessous) et la doc GRU/Prévisions (levé par ADR-044).

### Décision
Structure retenue :
1. Bandeau marché global, horodatage unique « Données au [date] » (J-1, non répété par bloc)
2. Trois blocs : Top 5 hausses / Top 5 baisses / bloc 3 (cf. ADR-046)
3. « Opportunités du jour » — liste unique de signaux ACHAT, non séparés structurellement,
   chaque carte taguée par origine + badge proof-level
   ATTENTION ARBITRAGE OUVERT : ADR-044 conclut « la home reste sur V1 seul ». La présente
   spec, antérieure, prévoit V1+V2 badgés. Contradiction non tranchée — à arbitrer avant
   codage de cette section.
4. Tableau complet 47 tickers

Règle transversale : tout ticker cliquable réutilise le point d'entrée existant chargeant
l'analyse fondamentale IA. Ne pas dupliquer la logique.

### Vérifications ayant levé le blocage volume
- `historical_data.volume` : 114 122 / 114 122 lignes non-null, alimenté jusqu'au 10/08
- `App.jsx:3539-3545` : `volRatio = lastVolume / avgVolume20` sur données réelles (fetch L156)
- `App.jsx:1472` : le snapshot marché fetche déjà `company_id, price, volume` — le bloc
  « plus négociés » ne nécessitait aucun ajout au scraping
- Conclusion : « Volume vs moy. » est une donnée réelle, pas un placeholder

### Conséquences
- Le classement par montant échangé se calcule frontend (`price × volume`) : `value` inutilisable
- Market Breadth / Sector Performance / Heatmap ne sont plus bloqués techniquement ;
  leur inclusion devient un arbitrage éditorial de densité, non tranché
- Décision bloc 3 : option C (bloc « Activités du marché » complet), donc home reportée
  derrière la construction d'un ingesteur d'indices — cf. ADR-046
- Nav cible : 12 → 10 onglets (fusion Marché + retrait Prévisions par ADR-044)

---

## ADR-046 — Le Bulletin Officiel de la Cote comme source de référence marché

**Date :** 10/08/2026
**Statut :** ACCEPTÉ
**Lié à :** ADR-045 (bloc 3), ADR-040, ADR-041

### Contexte
Le bloc « Activités du marché » (modèle brvm.org) exige 6 valeurs. Inventaire Supabase :
- `new_market_indicators` : vide
- `new_market_events` : vide
- `v_latest_market_data` : nom trompeur, contient `predicted_price` (vue de prédictions)
- Aucune donnée d'indice BRVM-C / BRVM-30 / BRVM-PRESTIGE en base
- Capitalisation obligataire : absente

Seules 2 lignes sur 6 étaient calculables. Option C retenue : construire l'ingesteur d'abord.

### Décision
Le Bulletin Officiel de la Cote (BOC), PDF quotidien publié par la BRVM, devient la source
de référence pour les données marché agrégées, en remplacement d'un scraping de la page
d'accueil brvm.org.

Justification — un seul document couvre :

| Donnée | Page BOC | État antérieur |
|---|---|---|
| BRVM-C / 30 / PRESTIGE + var. jour & annuelle | 1 | absent |
| Capitalisation actions & obligations | 1 | absent |
| Volume / valeur transigés marché | 1 | absent |
| Market Breadth (hausse/baisse/inchangé) | 1 | calculé frontend |
| 7 indices sectoriels + PER moyen par secteur | 1 | `sector_per_history` manuel |
| Par ticker : ouv/clôt/volume/valeur | 3-4 | `value` morte |
| Dernier dividende net + date de paiement | 3-4 | ADR-040 / ADR-041 |
| Opérations en cours (dividendes à venir, IRVM) | 10 | partiel |
| Quantités résiduelles achat/vente | 11 | absent |
| Calendrier AG | 17-18 | `corporate_events` |
| Marché obligataire complet | 5-9 | absent |

### Stabilité de la source — vérifiée
Pattern : `https://www.brvm.org/sites/default/files/boc_AAAAMMJJ_2.pdf`

- Suffixe `_2` invariant sur 13 dates testées, 2023 → 2026
- Aucun token, aucun paramètre d'expiration — stockage Drupal statique
- Bulletin du 30/12/2022 toujours servi intégralement en 08/2026 (3 ans 8 mois)
- Risque CDN écarté : profil opposé à celui qui a tué `parse_boa_letter` le 30/04/2026
- Backfill pluriannuel viable ; le scraper n'a besoin que de la date

### Règle opérationnelle — traitement des 404
Un 404 signifie « jour non ouvré », pas « ingestion cassée » (vérifié : 07/08/2026,
fête nationale ivoirienne, absent du listing officiel).

Le scraper traite le 404 comme skip normal et n'alerte qu'après N jours ouvrés consécutifs
sans bulletin. Sans cette règle, l'hétérogénéité des jours fériés des 8 pays UEMOA
génère des fausses alertes permanentes — et une alerte permanente est une alerte ignorée,
mécanisme exact de la mort silencieuse de l'ingestion BOA.

### Rupture de schéma — contrainte de conception du parser
Les séries ne sont pas continues :

| | BOC 2022 | BOC 2026 |
|---|---|---|
| Indices phares | BRVM 10, BRVM Composite | Composite, BRVM 30, BRVM Prestige |
| Indices sectoriels | 8 (Industrie, Transport, Agriculture, Distribution, Autres, Petites capi) | 7 (Télécoms, Conso discrétionnaire, Services financiers, Conso de base, Industriels, Énergie, Services publics) |
| Base sectorielle | 100 au 14/06/1999 | 100 au 02/01/2025 |
| Structure marché actions | par secteur | par compartiment (Prestige / Principal) |

Ruptures identifiées : avis BRVM 259-2022 « Nouveaux indices », refonte du 02/01/2026.
Un backfill naïf produirait une série avec sauts de base et changement de nomenclature.
Le parser doit être versionné par période.

### Renommages d'émetteurs — jointure
SIVC (Air Liquide → Erium), SDSC (Bolloré → Africa Global Logistics),
SEMC (Crown SIEM → Eviosys Packaging), TTLC (Total → TotalEnergies Marketing).
SVOC (Movis) présent en 2022, absent en 2026.

Joindre exclusivement par `symbole`, jamais par libellé.

---

## ADR-047 — PER sectoriels BOC : non-injection dans V2

**Date :** 10/08/2026
**Statut :** REPORTÉ (décision explicite, non oubli)

### Contexte
Le BOC publie quotidiennement le PER moyen des 7 secteurs officiels, dans la nomenclature
exacte de `SECTEUR_OFFICIEL` (`calculate_target_price.py`). Cela permettrait d'automatiser
`update_sector_per.py`, actuellement manuel/interactif. Le BOC donne aussi un taux de
rendement moyen du marché empirique (6,01 % au 10/08/2026), qui rendrait caduc
le 8 % arbitraire du terme `3,75 × DPS` de V2.

### Décision
Le gain d'automatisation sur `sector_per_history` est acquis et sera exploité.
L'injection dans le calcul V2 est reportée, pour trois raisons :

1. Distorsion par outliers. PER sectoriel INDUSTRIELS = 109,25 (tiré par SDSC 179,26,
   FTSC 64,62), CONSO DISCRÉTIONNAIRE = 39,86 (tiré par BNBC 565,40). Un
   `0,70 × per_ref × EPS` produirait des cours cibles absurdes.
2. Méthodologie non neutre. La BRVM calcule ses PER moyens en excluant UNILEVER CI
   (782,98) — traitement d'outlier ad hoc, signalé par simple astérisque, non documenté.
3. V2 reste gelé. T9 (pas de différenciation vs stratégie dividende naïve) et T14
   (68 % du signal concentré sur SERVICES_FINANCIERS = effet sectoriel) ne sont pas levés.
   Améliorer un intrant d'un modèle dont l'edge n'est pas démontré n'apporte rien.

Substituer un paramètre de modèle en cours de route sans test pré-enregistré est le motif
d'erreur déjà consigné au projet. Toute reprise passera par un test pré-enregistré séparé,
hors production.


## ADR-048 — Ingesteur BOC existant débranché, et schéma cible retenu

**Date :** 11/08/2026
**Statut :** ACCEPTÉ
**Lié à :** ADR-046 (source BOC), ADR-004 (psycopg2), ADR-026 (SQL Editor)

### Contexte
En cherchant la cible d'écriture du nouveau parser BOC (`tools/parse_boc.py`,
commit `ebdb580`), un inventaire des références à `new_market_indicators` a révélé
qu'un ingesteur BOC complet existe déjà dans le repo — `data_collector.py` — et
qu'il n'est pas branché.

Constats :
- `data_collector.py` L59-79 : récupère la liste des BOC depuis
  `https://www.brvm.org/fr/bulletins-officiels-de-la-cote`
- L151 `extract_market_indicators()` : extrait Composite / 30 / Prestige /
  capitalisation / volume moyen / valeur moyenne par regex sur le texte du PDF
- L289 : `INSERT INTO new_market_indicators ... ON CONFLICT (extraction_date) DO UPDATE`
- L384-385 : les deux fonctions sont bien appelées dans le flux principal
- **Mais** `brvm-analysis.yml` L72 appelle `data_collector_simple.py`, qui ne
  touche ni au BOC ni aux indicateurs (grep vide)

Conséquence : `new_market_indicators` est vide, et `report_generator.py` la lit
dans 3 requêtes (L96, L119, L143) — les sections correspondantes du rapport sont
donc dégradées ou vides depuis l'origine, sans que rien ne l'ait signalé.
Même motif que `scrape_market_cap.py` : panne silencieuse, non couverte par
`health_check.py`.

### Pourquoi ne pas simplement rebrancher `data_collector.py`

1. **Extraction par regex sur texte linéaire.** Le flux texte du BOC entrelace les
   colonnes Actions et Obligations : les libellés d'un bloc sortent après les
   valeurs de l'autre. Une regex `LIBELLE\s+([\d\s,\.]+)` apparie donc des
   valeurs arbitraires. Le motif `BRVM\s+30\s+([\d\s,\.]+)` est particulièrement
   exposé — c'est la version regex d'un bug rencontré et corrigé dans
   `parse_boc.py` (le « 30 » du libellé capté comme fragment numérique,
   produisant 30233.99 au lieu de 233.99).
2. **Aucun contrôle de cohérence.** Le script peut écrire des valeurs fausses
   sans qu'aucune vérification ne le détecte.
3. **psycopg2 direct** — violation ADR-004, décision toujours pendante.

`tools/parse_boc.py` (extraction positionnelle + 8 invariants arithmétiques)
remplace `extract_market_indicators()` comme moteur d'extraction.

### Défaut structurel de `report_generator.py`

Ses trois requêtes ordonnent par `id DESC`, jamais par date. La variation
journalière compare `id` et `id - 1` (L119-135). Tant que l'insertion est
strictement chronologique, `id` et date coïncident. **Dès qu'un backfill insère
de l'historique après coup, la correspondance est rompue** : l'`id` le plus élevé
ne sera plus la date la plus récente, et les variations deviendront silencieusement
fausses.

C'est structurellement incompatible avec le backfill BOC prévu. Correction
nécessaire avant tout backfill : ordonner par `extraction_date`.

### Décision — schéma cible

Trois tables nouvelles portent la donnée riche du BOC (~50 champs page 1) :
- `boc_indices` — tous types d'indices (PHARE / COMPARTIMENT / TOTAL_RETURN /
  SECTORIEL), une ligne par (date_seance, indice)
- `boc_market_stats` — agrégats par (date_seance, marché ∈ ACTIONS/OBLIGATIONS)
- `boc_market_indicators` — les 14 indicateurs, une ligne par date_seance

`new_market_indicators` est **conservée et alimentée en parallèle** (ses 6 colonnes),
afin de ne pas casser `report_generator.py`. Sa migration vers les tables `boc_*`
est hors périmètre et reste à planifier.

Chaque table porte une contrainte unique sur sa clé métier, pour permettre
l'upsert idempotent : rejouer une date déjà ingérée met à jour au lieu de dupliquer.

Une contrainte unique est ajoutée sur `new_market_indicators.extraction_date` :
le `ON CONFLICT (extraction_date)` de `data_collector.py` l'exige et elle est
absente du schéma actuel — tout upsert lèverait une erreur 42P10.

`base_reference` étiquette le régime de base de chaque indice dès l'ingestion.
Principe retenu, conforme à la pratique des fournisseurs de données : stocker le
niveau publié tel quel, ne jamais retraiter l'historique, décrire les régimes à
part. Le chaînage entre régimes, s'il devient nécessaire, sera un calcul à la
lecture. Un référentiel de correspondance sectorielle 8→7 sera ajouté le jour où
un parser v2022 existera — étiqueter dès l'origine coûte zéro, ré-étiqueter après
coup coûte cher.

Aucun `DROP` : `new_market_indicators` et `new_market_events` ne sont pas
supprimées, contrairement à ce que laissait entendre l'entrée backlog du 10/08
(rédigée sur l'hypothèse erronée qu'elles étaient orphelines).


## ADR-049 — `scrape_boc_pdf.py` : second écrivain de `dividend_per_share`, et trois défauts associés

**Date :** 12/08/2026
**Statut :** CONSTAT — corrections à planifier
**Résout :** ADR-041 (convention brut/net indéterminée)
**Complète :** ADR-040 (off-by-one `fiscal_year`)

### Contexte
En cherchant où brancher l'ingestion BOC page 1 (`tools/ingest_boc.py`), l'inventaire
des scripts appelés par `brvm-analysis.yml` a révélé que `scrape_boc_pdf.py` tourne
quotidiennement en ÉTAPE 1 et parse déjà le BOC — pages 3-4, tableau par ticker.

**Il n'y a pas de doublon avec `tools/ingest_boc.py`** : périmètres disjoints
(page 1 vs pages 3-4), tables disjointes (`boc_*` vs `company_fundamentals`).
Les deux scripts utilisent le même pattern d'URL et la même bibliothèque (pymupdf).

Trois scripts BOC coexistent donc désormais dans le repo :

| Script | Périmètre | Écrit dans | Statut |
|---|---|---|---|
| `data_collector.py` | page 1 (6 indicateurs) | `new_market_indicators` | débranché (ADR-048) |
| `scrape_boc_pdf.py` | pages 3-4 (par ticker) | `company_fundamentals` | **production quotidienne** |
| `tools/ingest_boc.py` | page 1 (~50 champs) | `boc_*` + `new_market_indicators` | nouveau |

### Résolution d'ADR-041 — convention brut/net

`scrape_boc_pdf.py` L124 : `"dividend_per_share": rec["dividende"]`, extrait de la
colonne « Dernier dividende payé — **Montant net** » du BOC.

ADR-041 notait deux scripts concurrents sans convention établie, et supposait que
la colonne contenait du brut « par accident, comportement correct mais non
intentionnel ». **Le constat réel est plus grave** : selon lequel des deux scripts
a écrit en dernier pour un ticker donné, la valeur est brute ou nette. La colonne
ne mélange pas seulement deux conventions au niveau du schéma — elle les mélange
**ligne à ligne**, selon l'ordre d'exécution.

Portée : toute expérience lisant `company_fundamentals.dividend_per_share`
(E2.6, E2.7-A, E2.7-B, T5c-A, T9 volet A) s'appuie sur une colonne
potentiellement hétérogène. À évaluer avant toute reprise de ces travaux.

### Trois défauts supplémentaires dans `scrape_boc_pdf.py`

**1. `ex_dividend_date` reçoit une date de paiement.**
L125 : `"ex_dividend_date": rec["date_div"]`, alimenté par la colonne « Dernier
dividende payé — Date » du BOC, qui est la date de **paiement**, pas la date de
**détachement**. Ce sont deux dates distinctes, séparées de plusieurs jours.
`ex_dividend_date` est le pivot de la stratégie de capture de dividende et du
travail de recherche sur le timing d'achat post-ex-dividende.

**2. `fiscal_year` reproduit l'off-by-one d'ADR-040.**
L114 : `fy = f"FY{trade_date.year}"` — l'année de la date du **bulletin**, pas
celle de l'exercice. Un dividende de l'exercice 2025 payé en août 2026 est
étiqueté FY2026. ADR-040 attribuait ce décalage au seul `scrape_corporate_events.py` ;
un second script produit le même effet, sur une table différente.

**3. Vérification TLS désactivée.**
L14-15 : `ctx.check_hostname = False` et `ctx.verify_mode = ssl.CERT_NONE`.
Le contournement n'est pas nécessaire : `tools/parse_boc.py` télécharge les mêmes
PDF via `requests` avec vérification normale, sans incident sur 142 séances.

**4. `except:` nu dans la boucle de recherche du bulletin.**
L26 : `except: d -= timedelta(days=1)` avale toute exception — y compris une clé
Supabase invalide ou une erreur de parsing — et remonte jusqu'à 10 jours en
arrière. Un échec structurel se présente donc comme « bulletin non trouvé ».
Contraire à la règle projet (pas d'`except` silencieux).

**5. Upsert sans `on_conflict`.**
L130-134 : `Prefer: resolution=merge-duplicates` sans paramètre `on_conflict`,
contrairement aux autres scripts du projet.

### Décision
Constats consignés, corrections **non appliquées dans cette session** : elles
touchent un script de production quotidienne et une décision ouverte (ADR-041),
et méritent chacune leur propre validation. Portées au backlog.

Aucune correction ne doit être faite sans décider au préalable **quelle
convention** (brut ou net) fait autorité pour `dividend_per_share` — corriger un
seul des deux écrivains figerait l'incohérence au lieu de la résoudre.

### Note de méthode
`tools/ingest_boc.py` a été écrit sans que l'existence de `scrape_boc_pdf.py` et
`data_collector.py` ait été vérifiée au préalable. Le périmètre s'est révélé
disjoint, donc sans conséquence — mais la vérification aurait dû précéder
l'écriture. `ARCHITECTURE.md` ne mentionnait aucun des deux (cf. sa refonte,
même session) : c'est précisément le mécanisme qui produit les écrivains
concurrents constatés dans ce projet (ADR-041, trois mappings sectoriels).


## ADR-050 — ADR-022 (filtre qualité ROE/P-B) n'a jamais été implémenté

**Date :** 12/08/2026
**Statut :** CONSTAT — aucune action sur le code
**Concerne :** ADR-022, T9, T14
**Découvert à l'occasion de :** la restauration des 14 ADR perdus (commit `a005dd9`)

### Constat

ADR-022 (27/05/2026) décide : « ROE>15% ET P/B<2.5 éliminatoire dans V2 », sur la
base d'un écart mesuré de 11,5 points — médiane J+90 de +9,5 % avec filtre contre
−2,0 % sans.

Vérification du code de production :

- `calculate_target_price.py` (script V2) ne contient **ni `roe`, ni `pb_ratio`** —
  aucune occurrence
- `git log -S "roe" -- calculate_target_price.py` : **aucun commit**. Le mot n'a
  jamais figuré dans ce fichier.

Le seuil de 15 % existe ailleurs dans le projet, mais jamais comme filtre
éliminatoire V2 :

| Emplacement | Usage | Modèle |
|---|---|---|
| `generate_decisions.py:171` | `roe > 15 → roe_s = 80` | V1, score gradué |
| `calculate_target_price_v3.py:259` | `roe >= 15` | V3 |
| `signaux_actifs.py:119` | `ok_roe = roe > 15` | script de signalement |
| `FinancialAnalysis.jsx:714` | coloration conditionnelle | affichage |

Aucune trace d'un seuil P/B < 2.5 utilisé comme filtre, où que ce soit.

### ADR-011 ne supersède pas ADR-022

Hypothèse examinée puis écartée : `evaluer_qualite_eps()` (ADR-011, 21/06/2026)
aurait pu remplacer le filtre. Lecture faite, ADR-011 ne mentionne ni ADR-022, ni
le ROE, ni le P/B. Les deux traitent de problèmes distincts :

- **ADR-011** — qualité de la *série EPS* : consécutivité des exercices, collapse
  supérieur à 80 % YoY, disponibilité
- **ADR-022** — qualité de l'*émetteur* : rentabilité des capitaux propres,
  valorisation relative aux fonds propres

Un ticker peut avoir une série EPS impeccable et un ROE de 3 %. ADR-011 le laisse
passer ; ADR-022 l'aurait éliminé.

### Question ouverte — portée sur T9 et T14

T9 conclut que V2 ne se différencie pas d'une stratégie dividende naïve. T14
établit que 68 % des signaux V2 se concentrent sur SERVICES_FINANCIERS.

Ces deux résultats portent sur le V2 **tel qu'implémenté**, c'est-à-dire sans le
filtre qualité décidé par ADR-022. Ce qui a été falsifié n'est donc pas exactement
le modèle qui avait été décidé.

**Ce constat ne réhabilite pas V2.** Il pose une question à laquelle rien ne permet
de répondre aujourd'hui : un V2 filtré par ROE/P-B aurait-il passé T9 ? Y répondre
supposerait de rejouer T9 sur un V2 filtré, avec des seuils pré-enregistrés avant
lecture des résultats.

Il est également possible que le filtre ait été écarté délibérément après ADR-022,
sans que la décision soit consignée — la période concernée (27/05 → 04/06) est
précisément celle dont les ADR ont été perdus.

### Décision

**Aucune action sur le code.** V2 est gelé (phase 13, T9). Implémenter un filtre
dans un modèle gelé, ou rejouer un test de falsification sur un modèle modifié en
cours de route, sont deux choses que le projet s'interdit — c'est le motif d'erreur
déjà consigné à propos des substitutions de paramètres.

Le constat est enregistré. La reprise éventuelle de V2 devra trancher : appliquer
ADR-022, l'abandonner formellement, ou rejouer T9 avec le filtre.

### Motif récurrent — deuxième occurrence sur le même script

ADR-011 rapporte exactement le même incident, six semaines plus tôt :

> « Le SKILL.md référençait une liste d'exclusion V2 statique, présentée comme déjà
> active dans `calculate_target_price.py`. Vérification du code réel : cette liste
> n'a **jamais été implémentée**. »

Deux écarts décision/implémentation sur le même fichier, découverts tous deux par
hasard — le premier en juin lors d'une investigation sur NTLC, le second en
restaurant un ADR effacé. Dans les deux cas, la documentation affirmait qu'un
filtre tournait alors qu'il n'existait pas.

Le problème de fond n'est pas ADR-022 : c'est qu'aucun mécanisme ne vérifie qu'une
décision atteint le code. Un ADR peut être adopté, documenté, cité comme faisant
autorité, et rester lettre morte sans que rien ne le signale.
