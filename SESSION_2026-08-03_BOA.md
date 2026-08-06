# SESSION 03/08/2026 — Source BOA & diagnostic du modèle de valorisation V2

**Branche :** `remediation-2026-07`
**Statut :** hors plan de remédiation formel (T0–T17 clos) — backlog général
**Documents source :** bulletin hebdo « Recommandations 03–06/08/2026 » + « Lettre quotidienne 03-08-2026 » (Tableau de Bord)

---

## Résumé

Point de départ : Jocelyn a été ajouté à la liste de diffusion BOA Capital Securities et
souhaitait comparer les prévisions BOA aux cours cibles du pipeline.

Résultat : la comparaison a fonctionné, et elle a mis au jour un **défaut structurel de
`calculate_target_price.py`** — les PER sectoriels utilisés sont des multiples historiques
2024 agrégés, incohérents avec leurs propres constituants, produisant une sous-évaluation
systématique de l'ensemble du marché hors télécoms et financières.

Ce résultat converge avec T9 (V2 ne bat pas la stratégie naïve) et T14 (V2 structurellement
concentrée sur les banques) et en fournit **l'explication mécanique** : V2 ne peut voir
d'opportunité que là où son multiple de référence est élevé, c'est-à-dire chez les banques.

---

## 1. Travaux réalisés

### Lot B0 — diagnostic de la table `boa_recommendations` (clos)

| Question | Réponse |
|---|---|
| Contenu | 547 lignes, 2025-12-01 → 2026-04-30, 39 tickers, 17 semaines. Actions : SELL 348 (64%), REDUCE 91, BUY 57, HOLD 51 |
| Script d'ingestion | `parse_boa_letter.py` + `.github/workflows/parse_boa_letter.yml`, cron `0 14 * * 1-5` — **toujours actif, aucune donnée depuis le 30/04** (échec silencieux ~3 mois) |
| Cause de l'arrêt | Documents BOA plus disponibles ; commit `bc353bb` (20/05) « lien CDN expire ». Non confirmé par les logs Actions (`gh` CLI non installé) |
| Consommateurs | `calculate_target_price_v3.py`, `tools/falsification_v2.py`, `boa_simple.py`, `check_boa_rendements.py` |
| Frontend | `src/components/BOAComparison.jsx` toujours présent (repo `brvm-analytics`), seul l'appel retiré (`25a92a0`). **Import mort dans `App.jsx` ligne 3** → dette technique |
| Benchmark `alpha` | **`benchmark_return` n'est PAS le BRVMC** — c'est la moyenne simple des `variation_pct` des tickers du même run (`verify_decisions.py:159-171`, `DECISIONS.md:943,955`). Le vrai indice existe : `historical_data`, `company_id=48` |
| Tickers non appariés | BOAMA, BOAML, BOANG, SAPH. SAPH → SPHC probable ; BOAMA/BOAML possiblement deux codes pour un même titre |

### Lot B2.1 — chargement semaine `2026-W32` (clos, partiel)

27 lignes insérées sur 30. **CBIBF, PRSC, SDSC non chargés** — absents du commentaire
narratif du bulletin, action non déterminée. Valeurs conservées dans `boa_2026-08-03.csv`.

Tableau groupe BOA (BOAS/BOAML/BOAC/BOAB/BOABF/BOANG) non chargé : publié sans `action`
ni `cours_pot`, or `action` est `NOT NULL`.

### Lot B3 — comparaison `cours_pot` (BOA) vs `cours_cible` (V2) (clos)

16 tickers appariés au 03/08/2026. Écart médian global : **−24,3%**.

| Secteur | n | Écart médian V2 vs BOA | PER en base |
|---|---|---|---|
| Télécommunications | 3 | **+28,5%** | 14,70 |
| Services financiers | 4 | **+16,5%** | 14,70 |
| Consommation de base | 4 | −38,1% | 6,50 |
| Consommation discrétionnaire | 1 | −60,5% | 10,00 |
| Énergie | 1 | −48,0% | 5,10 |
| Industriels | 1 | −33,5% | 3,50 |
| Services publics | 2 | −65,6% | 6,00 |

**Séparation parfaite** : les 7 titres à PER 14,70 sont tous positifs, les 9 autres tous
négatifs. Aucun chevauchement. La corrélation avec le PER sectoriel est monotone.

Hypothèses testées et **réfutées** en cours de route :
- Le mode de calcul (`Gordon100`) expliquerait le biais → **non**, `Gordon100` n'apparaît
  nulle part (14 en `PER70+Gordon30`, 2 en `PER100`, écarts comparables)
- L'écart serait plus large sur les financières (hypothèse T14) → **inverse** : les
  financières sont le secteur le PLUS cohérent avec BOA

**Désaccord directionnel total** : 3 signaux d'achat dans le croisement, 3 désaccords.
- STBC : BOA ACHAT (+18,8%) / V2 VENTE (−22,1%) — cibles 27 555 vs 18 067
- ONTBF : BOA SELL (−28,9%) / V2 ACHAT (+25,6%) — cibles 2 130 vs 3 762
- SNTS : BOA REDUCE (0%) / V2 ACHAT (+28,5%)

---

## 2. Découverte principale — les PER sectoriels sont inutilisables

### Vérification contre le Tableau de Bord du 03/08

Les 7 valeurs de `sector_per_history` correspondent **exactement** à la colonne P/E 2024
du bulletin. **Aucune erreur de transcription.** Le problème est en amont.

### Défaut 1 — multiples historiques appliqués à des prix actuels

Le bulletin précise : « Le calcul des ratios des années passées s'opère sur la base du
cours de clôture de l'exercice fiscal. » Ce sont donc des P/E arrêtés fin 2024.

Or la BRVM affiche **+40,40% en y-t-d 2026**. Et BOA publie elle-même en première page :

| Indicateur (03/08/2026) | Valeur |
|---|---|
| PER 2025 estimé, total marché | **14,59x** |
| P/E 2024, total marché | 7,2x |
| P/E 2023, total marché | 6,2x |
| DY 2025 estimé | 6,21% |
| BRVM C | 485,43 pts (+40,40% ytd) |

Le pipeline valorise donc le marché à environ **la moitié** du multiple que BOA retient
elle-même pour l'exercice courant.

### Défaut 2 — les lignes sectorielles ne sont pas des agrégats de leurs constituants

Plus grave, car ce défaut ne se corrige pas par une simple mise à jour.

**SERVICES PUBLICS** — ligne sectorielle 2024 : **6,0x**. Constituants :

| Société | P/E 2024 |
|---|---|
| CIE CI | 12,2x |
| SODE CI | 14,4x |

Deux sociétés, toutes deux au-dessus de 12, moyenne affichée à 6,0. Mathématiquement
impossible pour une moyenne des constituants.

**TELECOMMUNICATIONS** — ligne sectorielle 2023 : **38,7x**. Aucun constituant ne dépasse
13,7x (ORANGE CI 13,7x, ONATEL BF 7,3x, SONATEL SN 5,4x).

Ces lignes sont vraisemblablement pondérées par capitalisation sur une base différente,
ou calculées sur un agrégat bénéfice/capitalisation. **Elles ne sont pas applicables à
l'EPS d'une société individuelle**, ce que fait pourtant `calculer_cours_cible`.

### Illustration — SODECI (SDCC)

| Méthode | Cible |
|---|---|
| Pipeline actuel (EPS 595,18 × 6,0) | 3 999,76 |
| Avec le P/E propre de SODE CI (× 14,4) | ~8 570 |
| Cible BOA | 13 040 |
| Cours actuel | 11 900 |

L'écart de −69,3% mesuré en B3 vient intégralement du multiple.

---

## 3. Autres constats sur `calculate_target_price.py`

### La liste d'exclusion V2 documentée n'existe pas dans le code

`grep -n "SNTS\|EXCLU\|exclude\|TICKERS_EXCLUS"` ne retourne qu'une ligne : le mapping
sectoriel (`"SNTS": "TELECOMMUNICATIONS"`).

La liste documentée dans `SKILL.md` (NTLC, SNTS, BOAN, BNBC, SICC, UNLC, ETIT, FTSC, CFAC,
SIVC — « EPS non représentatif ») **n'est pas implémentée**. Elle décrit une intention.

Conséquence observée : **SNTS produit un signal ACHAT** (cible 39 841,82) et SIVC un signal
VENTE, alors que tous deux sont censés être exclus. **Écart documentation/code sur un
script de production alimentant des signaux d'achat.**

### Couverture 22/45

22 tickers ont un cours cible au 03/08/2026 (`companies` contient 47 lignes dont BRVM30 et
BRVMC, donc 45 sociétés réelles).

Les absents ne sont **pas exclus** — ils sont rejetés par le filtre data-quality
`evaluer_qualite_eps` (ADR-011), avec une raison explicite. **Cette raison est déjà
imprimée** par le script (lignes 250-253) : `🚫 N ticker(s) exclu(s) par le filtre
data-quality` suivi du motif par ticker.

→ **La cause des 23 rejets est disponible dans les logs GitHub Actions du dernier run.**
Aucun diagnostic à construire, juste à consulter. `gh` CLI n'est pas installé localement.

### Point de vigilance — fragmentation de `company_fundamentals`

Aucune ligne ne porte simultanément `eps`, `roe` et `dividend_yield`. Chez BICC : 4 lignes
avec EPS/ROE, 2 autres lignes distinctes avec le `dividend_yield`. Même motif chez BOAN,
CFAC, NTLC, ORGT.

Même famille de piège que `corporate_events` (`EX_DIVIDEND` vs `DIVIDEND_HISTORY`).
Le script agrège correctement par ticker, mais toute requête ad hoc doit en tenir compte.

### Aucun défaut confirmé dans la logique du script

Deux alertes que j'avais levées et qui se sont révélées **fausses** après lecture du code
complet (artefact d'un `sed` sur fenêtres non contiguës) :
- Bug de variable échappée sur `fiscal_year` → **n'existe pas**, le code est correct
- `eps_avg` non utilisé → **faux**, il est stocké sous la clé `"eps"` et relu correctement

Le script rejette proprement et loggue ses exclusions. Le problème est dans **la donnée
d'entrée** (`sector_per_history`), pas dans la logique.

---

## 4. Ce que le Tableau de Bord apporte comme source de données

Le bulletin quotidien contient, **par société** :
- BPA 2023 et 2024 → comblerait une partie des trous de `company_fundamentals`
- **P/E individuel** 2023 et 2024 → alternative directe au multiple sectoriel
- **P/B individuel** 2023 et 2024 → exactement ce que réclame l'item T14 (modèle P/E+P/B
  pour SERVICES_FINANCIERS)
- D/Y individuel, nombre de titres, capitalisation, perf 2026

C'est une source nettement plus riche que ce qui est actuellement exploité.

---

## 5. Prochaines sessions — propositions

**Aucune modification de production n'a été faite.** Tout ce qui suit est à cadrer et à
valider avant écriture de code (classe B, gate humain).

### P1 — ADR de constat (rédaction seule, ~30 min)
Consigner le défaut des PER sectoriels, l'écart documentation/code sur les exclusions, et
le fait que `benchmark_return` n'est pas un indice. Prochain numéro disponible : **ADR-039**
(ADR-038 pris le 30/07, commit `c41e507`).

### P2 — Consulter les logs Actions du dernier run `calculate_target_price`
Récupérer la liste des 23 tickers rejetés et leur motif. Installer `gh` ou consulter
l'interface web. Lecture seule, ~15 min. **Préalable à toute décision sur la couverture.**

### P3 — Refonte du multiple de valorisation (chantier principal)
Trois pistes, par ordre de simplicité croissante :
1. **P/E individuel par société** issu du Tableau de Bord, au lieu du multiple sectoriel
2. **Multiple prospectif** cohérent avec le PER 2025E publié par BOA (14,59x marché)
3. **Recalcul des moyennes sectorielles** à partir des constituants du Tableau de Bord

Réserve : la piste 1 pose une question circulaire — utiliser le P/E d'une société pour
calculer sa propre cible revient à valider son cours actuel. À arbitrer méthodologiquement
avant de coder.

### P4 — Item T14 revisité
L'hypothèse initiale (modèle P/E+P/B dédié aux financières) est **affaiblie** par B3 : les
financières sont le secteur le plus cohérent avec BOA. Le problème prioritaire est le
multiple, pas le secteur bancaire. L'item reste valable mais descend en priorité.

### P5 — Résidus de la source BOA
- Charger CBIBF, PRSC, SDSC (lire la couleur de ligne dans le PDF hebdo)
- Contrainte `UNIQUE (week_label, ticker)` à envisager — **réserve** : le cron
  `parse_boa_letter.yml` tourne toujours ; vérifier que le script fait un UPSERT et non
  un INSERT simple avant d'ajouter la contrainte
- Nettoyer l'import mort `BOAComparison` dans `App.jsx` ligne 3
- Décider du mode d'alimentation durable (source email désormais, plus lien CDN)

### P6 — Défaut du kill-switch (indépendant, T10-B)
`benchmark_return` étant une moyenne de cohorte, il est très sensible aux valeurs
extrêmes. Cela **explique mécaniquement** le faux déclenchement du 28/07 : ETIT +39,6% et
UNXC +42,2% ont porté le « benchmark » à +2,79%. Le critère alpha mesure donc « ce ticker
bat-il ses pairs du jour », pas « bat-il le marché ». Le vrai indice existe
(`historical_data`, `company_id=48`). À traiter séparément.

---

## 6. Lots BOA restants du PLAN_BOA_2026-08.md

- **B1** (backtest historique des recos BOA, gate décisionnel) — **non exécuté.** Note :
  T9/Phase 11 contient déjà un « Volet B — recos BOA » (action=BUY, n=57, médiane J+90
  brute 11,34%, 80,7% positifs) qui mesure le rendement brut mais pas l'alpha.
  Critère d'acceptation à corriger : les fenêtres J+90 sur publication hebdomadaire se
  chevauchent à ~92%, donc les 547 lignes ne sont pas 547 observations indépendantes.
  Définir des **épisodes** (suite de semaines à même `action` = 1 observation).
  Attention : la publication n'est pas strictement hebdomadaire (7 semaines manquantes,
  et un `2026-W12b`) — ne pas calculer la consécutivité sur l'incrément de `week_label`.
- **B4** (matrice BOA × V1/V2) — non exécuté
- **B5** (documentation) — partiellement couvert par le présent document

Note sur `week_label` : format ISO. `2025-W53` est invalide en ISO strict (2025 compte 52
semaines) — la numérotation 2025 du parser est approximative. Utiliser `date_start`/
`date_end` pour tout appariement de dates sur la période décembre 2025.

---

## 7. Réserve transversale

`sector_per_history.source = 'boa_tableau_de_bord'`. Le pipeline est donc **alimenté par
BOA** puis comparé **aux cibles de BOA**. Ce n'est pas une validation croisée indépendante.

Cela renforce plutôt qu'affaiblit le constat : les deux partent des mêmes multiples publiés
et divergent d'un facteur ~3 sur SODECI, ce qui localise l'erreur dans l'usage qu'en fait
le pipeline — application d'un agrégat sectoriel à un EPS individuel.

Mais si une source indépendante est souhaitée à terme pour valider le modèle, BOA ne peut
pas jouer ce rôle.

---

**Mise à jour du 06/08/2026** — l'hypothèse « lien CDN expiré » (ligne 33) est **réfutée**. Cause réelle : le cron `parse_boa_letter.yml` se déclenchait à 14h00 UTC alors que le bulletin est publié entre 15h57 et 16h57 UTC. Le jeton CDN `zexxawdwssuc` n'a jamais expiré. Détail complet dans `REMEDIATION_LOG.md`, section « Incident production — workflows planifiés en échec (06/08/2026) ».
