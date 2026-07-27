# PLAN D'EXPÉRIMENTATION — Modèles V1 & V2
**Version 1.0 — 18/07/2026**
**Complément du PLAN_REMEDIATION (≥ v1.4). Exécution par modèle Claude
léger en autonomie Classe A.**

---

## Objet et principes

Objectif : identifier les modifications de V1 et V2 qui augmentent
l'**alpha net** (rendement − benchmark − frais), avec preuve avant
promotion. Ce plan ne modifie JAMAIS la production : toute expérience
est offline, en lecture seule. Une promotion en prod est toujours une
tâche séparée Classe B dans le flux habituel (diff revu + ADR + Jocelyn).

- Statuts des expériences → **EXPERIMENTS_LOG.md** (nouveau document,
  racine du repo, versionné). REMEDIATION_LOG.md reste réservé aux
  tâches T*.
- Une expérience = une session. Pas de chaînage entre expériences.
- Cadence prod : **maximum 1 promotion de modèle toutes les 4 semaines**,
  pour que l'alpha vérifié (T16) reste attribuable.

---

## AUTONOMIE — Classe A (à coller en début de chaque session)

```
CLASSE A — EXPÉRIENCE OFFLINE. Autonomie élargie :
- Enchaîne TOUTES les étapes internes de l'expérience sans demander de
  validation intermédiaire. Seuls comptent : la sortie finale, les
  critères, la règle d'interprétation appliquée textuellement.
- Jusqu'à 5 tentatives d'auto-correction sur TES propres scripts
  (triage infra inchangé : erreur réseau/clé → 1 retry puis STOP).
- Organisation interne du code libre, scripts jetables autorisés dans
  le dossier de l'expérience.

INTERDIT MÊME EN CLASSE A :
- Écrire ailleurs que dans tools/experiments/<id>/ (+ EXPERIMENTS_LOG.md).
- Modifier un script existant du repo, écrire en base (REST GET
  uniquement, pagination Range), toucher aux workflows.
- Conclure au-delà des règles d'interprétation écrites. Cas ambigu →
  escalade, aucune conclusion.
- Ajuster paramètres, filtres ou données pour retrouver un chiffre
  attendu — si le résultat surprend, il est rapporté tel quel.
- Tester des variantes non listées dans la spec (anti-overfitting) :
  toute variante supplémentaire = nouvelle expérience validée par
  Jocelyn d'abord.

CONTRAINTES TECHNIQUES (rappel) : python3 explicite ·
load_dotenv(find_dotenv(usecwd=True)) · module logging obligatoire,
pas de print pour les erreurs, pas d'except silencieux ·
REST https://lynevvhmstpcffobwudr.supabase.co/rest/v1/ ·
companies.symbol · historical_data.trade_date/.price ·
brvm_decisions.date/.signal/.market_regime.
```

**Prompt template session Classe A :**
```
Expérience Classe A du PLAN_EXPERIMENTATION_MODELES. Exécute-la de bout
en bout en autonomie, applique la règle d'interprétation textuellement,
consigne le résultat dans EXPERIMENTS_LOG.md. Aucune modification hors
tools/experiments/<id>/.
[COLLER LE BLOC AUTONOMIE CLASSE A]
[COLLER L'EXPÉRIENCE]
```

---

## Conventions communes (référencées par toutes les expériences)

- **Benchmark équipondéré** : sur une fenêtre [d1, d2], moyenne simple
  des rendements de tous les tickers ayant un prix valide aux deux
  bornes (prix valide = dernier cours à ≤ 3 jours ouvrés de la borne).
- **Épisode** : signaux consécutifs du même ticker espacés de ≤ 5 jours
  ouvrés = 1 épisode (date d'entrée = premier signal).
- **Alpha** : rendement du titre − benchmark équipondéré, même fenêtre.
- **Bootstrap** : 10 000 tirages, rééchantillonnage par épisode ou par
  cohorte (jamais par signal-jour), IC95 percentile.
- Chaque expérience vit dans `tools/experiments/<id>/` avec un script
  principal `<id>.py`, sortie = tableau + verdict → EXPERIMENTS_LOG.md.

---

## GATES (dépendances dures)

| Expérience | Prérequis |
|---|---|
| Toutes (E1.*, E2.*) | **T16** (colonne alpha) exécutée |
| E1.5 | E1.1 à E1.4 tranchées + T15 exécutée |
| E2.1, E2.2, E2.3 | **T9** rendue (donc **T5c** close) |
| E2.4, E2.5 | **T5c** close (script committé) + seuil liquidité T5b validé par Jocelyn |

**Chemin critique : T5c étape 0 (règles écrites par Jocelyn).**

---

# VOLET E1 — Modèle V1 (signal composite)

## E1.1 — Momentum cross-sectionnel 12-1 (remplaçant candidat de la technique)

**Contexte :** la composante technique (40% du score) fait AUC 0.51 sur
22 992 signaux. Le momentum relatif 12-1 est le seul "technique"
documenté robuste sur marchés frontières — à tester sur la BRVM.

**Spécification :**
1. Dates de rebalancement : 1er jour ouvré de chaque mois, de janv 2022
   au dernier mois complet.
2. À chaque date, pour chaque ticker avec ≥ 13 mois d'historique :
   `mom = P(t−21 j ouvrés) / P(t−252 j ouvrés) − 1`. Ticker exclu du
   mois si dernier cours > 10 j ouvrés avant la date.
3. Portefeuille long = tercile supérieur (skip du mois si < 5 titres
   classables).
4. Alpha J+20 et J+60 de chaque titre du tercile vs benchmark
   équipondéré ; agrégation PAR COHORTE MENSUELLE.
5. Sortie : n cohortes, alpha médian de cohorte (J+20, J+60), % de
   cohortes positives, split par `market_regime` à la date si disponible.

**Règles d'interprétation :**
- n ≥ 8 cohortes ET alpha médian J+60 ≥ +2 pts ET ≥ 60% de cohortes
  positives → "Momentum 12-1 : remplaçant candidat de la composante
  technique — promotion = tâche Classe B + ADR."
- Alpha médian J+60 ≤ 0 → "Momentum 12-1 inopérant sur BRVM — ne pas
  tester de variantes proches."
- Sinon → escalade, aucune conclusion.

## E1.2 — Fondamental mécanique vs narratif IA

**Contexte :** 25% du score V1 = `signal_fondamental`, peuplé par
`extract_fundamental_signals.py` — script orphelin (T8), signal
potentiellement figé. Tester un remplaçant mécanique reproductible.

**Spécification :**
1. Diagnostic fraîcheur : par ticker, date de dernière mise à jour de
   `signal_fondamental` → tableau de staleness (rattaché au finding T8).
2. Score mécanique par ticker : +1 si EPS YoY dernier exercice > 0 ;
   +1 si ROE dernier exercice > ROE précédent. Mapping : 2 → HAUSSIER,
   1 → NEUTRE, 0 → BAISSIER. (Marge en 3e composante seulement si
   disponible pour ≥ 80% des tickers.)
3. Sur l'historique `brvm_decisions` × résultats J+20 : alpha médian
   des signaux ACHAT émis quand narratif = positif vs quand
   mécanique = HAUSSIER (mêmes fenêtres) ; taux d'accord des deux
   signaux ; n de chaque branche.

**Règles d'interprétation :**
- Mécanique ≥ narratif en alpha médian ET n ≥ 30 par branche →
  "Remplaçant candidat — supprime la dépendance au script orphelin."
- Narratif > mécanique de ≥ 1.5 pt → "Conserver le narratif MAIS
  réparer son automatisation (renvoi item T8/BACKLOG)."
- Sinon → escalade.

## E1.3 — PEAD (dérive post-publication)

**Contexte :** sur un marché lent, la dérive après publication de
résultats est l'anomalie la plus probable non exploitée par V1.

**Spécification :**
1. ÉTAPE BLOQUANTE — disponibilité des dates d'événement : inventorier
   les candidates (`corporate_events` type AG ; `fundamental_analysis.
   report_date` ; date de première apparition d'un exercice dans
   `company_fundamentals`). Si < 30 événements datés fiables →
   verdict : "PEAD non testable avec les données actuelles — item
   BACKLOG : collecter les dates de publication." STOP.
2. Sinon : surprise proxy = ΔEPS YoY de l'exercice publié (pas de
   consensus sur la BRVM). Terciles de surprise.
3. Alpha J+30 et J+60 post-événement par tercile.

**Règle :** tercile sup − tercile inf ≥ +3 pts d'alpha J+60 avec
n ≥ 30 → "Signal événementiel candidat (nouvelle composante V1)."
Sinon documenter, sans conclusion négative définitive (données minces).

## E1.4 — Le régime BULL/BEAR a-t-il du skill ?

**Spécification :**
1. Historique `market_regime` : pour chaque jour, rendement du
   benchmark équipondéré sur les 20 j ouvrés SUIVANTS.
2. Comparer distribution BULL vs BEAR ; bootstrap par blocs (épisodes
   de régime contigus) → IC95 de la différence de médianes.

**Règles :**
- Différence > 0 avec IC95 excluant 0 → "Le régime a du skill —
  BEAR peut devenir un signal ALLEGER (décision Jocelyn, tâche
  séparée). L'alpha de V1 inclut légitimement l'évitement du BEAR."
- Sinon → "Régime = filtre d'activité sans valeur prédictive — toute
  évaluation de V1 doit se faire en alpha intra-BULL uniquement
  (entrée pour T15/E1.5)."

## E1.5 — Réoptimisation des pondérations (GATE : après E1.1–E1.4 + T15)

**Spécification :**
1. Unité = épisode. Cible = alpha J+20 > 0. Features = uniquement les
   composantes retenues par E1.1–E1.4 (MAXIMUM 3).
2. Régression logistique, walk-forward 3 plis chronologiques (fit sur
   pli k, éval sur pli k+1).
3. Comparer hit rate et alpha médian vs pondération actuelle
   40/25/20/15 sur les plis d'évaluation uniquement.

**Règle de promotion standard :** amélioration simultanée du hit rate
ET de l'alpha médian sur les plis out-of-sample → candidat (Classe B +
ADR). INTERDIT : > 3 features, itérations de réglage hors spec.

---

# VOLET E2 — Modèle V2 (cours cible / valorisation)

## E2.1 — Plafond de capitalisation (GATE : T9)

**Contexte :** le filtre 150-500 Mds exclut SONATEL, le titre le plus
liquide de la cote. "Les grosses caps sont efficientes" est douteux
sur la BRVM.

**Spécification :**
1. ÉTAPE INTÉGRITÉ : les capitalisations à la DATE des signaux
   historiques sont-elles disponibles (source `scrape_market_cap.py` /
   table associée) ? Si seules les caps actuelles existent → bandeau
   obligatoire en tête de sortie : "BIAIS LOOK-AHEAD — résultat
   indicatif uniquement."
2. Variantes de sélection (logique de `backtest_value.py` répliquée,
   fichier source NON modifié, commit 49a64b6 cité) :
   (a) baseline 150-500 Mds · (b) plancher seul ≥ 50 Mds ·
   (c) sans contrainte de cap.
3. Par variante : n signaux, médiane J+90, % positifs, IC95 bootstrap
   de la médiane si n ≥ 20.

**Règle :** une variante avec n > baseline ET médiane ≥ baseline
− 0.5 pt → "Élargissement candidat : plus de puissance statistique
sans perte de qualité." Sinon conserver baseline.

## E2.2 — Double métrique : P/B justifié par le ROE (GATE : T9)

**Spécification :**
1. Condition additionnelle par ticker :
   `PB_ticker < PB_secteur_médian × (ROE_ticker / ROE_secteur_médian)`.
2. Rejouer les signaux du backtest V2 avec cette condition EN PLUS de
   la décote EPS×PER → sous-ensemble.
3. Sortie : n, médiane J+90, % positifs, avant/après.

**Règles :**
- Médiane ET % positifs en hausse avec n ≥ 12 → "Double métrique
  candidate — la précision monte, ce qui manque à l'IC95 de T6."
- n < 12 → "Filtre trop strict pour l'univers BRVM — documenter,
  ne pas promouvoir."

## E2.3 — Taux d'actualisation : grille et paliers (GATE : T9)

**Spécification :**
1. Grille uniforme r ∈ {0.07, 0.08, 0.09, 0.10} sur la composante
   dividende de la cible (TAUX_ACTUALISATION de config/params.py,
   répliqué offline — fichier prod non touché).
2. Variante 2 paliers (financières / non-financières) : valeurs
   fournies par Jocelyn AVANT la session — jamais choisies par le
   modèle. Si non fournies → variante sautée, noté.
3. Sortie : impact sur cibles, décotes, composition de la sélection,
   perf des signaux rejoués.

**Règle :** si le CLASSEMENT des signaux change fortement avec r
(> 30% de rotation de la sélection entre r=0.07 et r=0.10) → "Cible
fragile au taux — toute valeur unique est arbitraire ; privilégier
les paliers (décision Jocelyn)." Sinon → "Cible robuste au taux."

## E2.4 — Extension d'univers dividend capture (GATE : T5c + seuil T5b validé)

**Contexte :** l'edge le plus documenté du projet est le dividend
capture sur 6 tickers. Un univers plus large = plus de trades/an =
plus d'alpha total, si la qualité tient.

**Spécification :**
1. Screening FY2023-FY2025, tous tickers : yield au point d'achat
   théorique ≥ 8% (paramètre) · volume_20j ≥ seuil validé T5b ·
   statut brut/net CONNU (ADR-034 ; inconnu → exclu, listé à part).
2. Backtester l'univers étendu avec `backtest_dividend_capture.py`
   (la source T5c, règles STRICTEMENT identiques).
3. Sortie : core 6 vs étendu — n trades, WR, médiane nette, durée.

**Règle :** l'étendu conserve WR ≥ 80% ET médiane nette ≥ +5% →
"Extension candidate — liste des tickers ajoutés soumise à Jocelyn."
Dégradation → "Conserver le core 6 ; l'edge ne s'étend pas."

## E2.5 — Optimisation de l'entrée post-ex-div (GATE : T5c)
*(formalise l'exploration régression prévue)*

**Spécification :**
1. Données : `regression_dataset.csv` (présent à la racine) +
   `v_historical_prices` (10 ans). Par événement : trajectoire
   J0 → J+30 normalisée par le prix théorique ex-div (P_cum − D).
2. Distribution du creux : jour du minimum, profondeur vs prix
   théorique.
3. Tester EXACTEMENT 3 règles d'entrée : (a) J+1 fixe ·
   (b) premier jour où cours < prix théorique ·
   (c) seuil cours < prix théorique − 2%.
   Rendement mesuré à J+32 (durée médiane de la stratégie), net selon
   conventions ADR-034.
4. Split stabilité : résultats sur 1re et 2e moitié temporelle
   séparément.

**Règle :** une règle bat l'entrée actuelle (médiane +1 pt ET WR non
dégradé) SUR LES DEUX MOITIÉS → "Règle d'entrée candidate —
intégration dans backtest_dividend_capture.py = tâche Classe B + ADR."
Sinon conserver l'entrée actuelle. INTERDIT d'inventer une 4e règle.

---

## Ordre d'exécution recommandé

| Priorité | Item | Note |
|---|---|---|
| 0 (toi) | T5c étape 0 — règles écrites | Chemin critique, débloque T9 + E2.4/E2.5 |
| 1 | T16 (Classe B, plan remédiation) | Prérequis de tout |
| 2 | T15 puis E1.4 | Contrôles V1 — légers, ce weekend |
| 3 | E1.1, E1.2 | 2 sessions Classe A |
| 4 | T5c → T9 → E2.1, E2.2, E2.3 | Branche V2 |
| 5 | E2.4, E2.5 | Le gisement principal |
| 6 | E1.3 (selon données), E1.5 (dernier) | |

**Rappel final :** une expérience ne modifie jamais la prod. Une
promotion = une tâche Classe B + ADR + validation écrite, maximum une
toutes les 4 semaines, mesurée ensuite par la colonne alpha (T16).

---

# E2.6 — Identification du mécanisme dividende (H1 / H2 / H3)

**Classe A — expérience offline, lecture seule.**

**Gate : E2.6 précède désormais E2.4 et E2.5.** Ces deux expériences
supposent un mécanisme identifié ; elles restent gelées tant que E2.6
n'a pas rendu son verdict.

## Contexte

T5c étape 0 (commit `d771ece`) a produit 89 cycles annonce → ex-date →
paiement sur 49 tickers. Chute médiane à l'ex-date : 13,9% du dividende
(jamais 48% sur aucune découpe testée), erratique (0% dans un cas sur
trois, >100% ailleurs). Cycle non homogène : délai AG→ex de 30-40 j
pour les BOA, 62-104 j pour NTLC/SMBC.

Le chiffre de juin (93% WR, +8,3% net médian) n'est reproductible depuis
aucun artefact du repo. Cette expérience ne cherche PAS à le retrouver.
Elle détermine s'il existe un mécanisme stable et attribuable.

## Trois hypothèses concurrentes

- **H1 — Dérive post-annonce.** Le cours dérive à la hausse entre l'AG
  et le paiement, indépendamment du détachement. Motif NSBC (+7,5% /
  +6,0% / +12,4% en var_totale, chute_ex 2,2% / 2,2% / 0,0%). L'edge
  serait un hold sur la fenêtre.
- **H2 — Sous-réaction à l'ex-date.** Hypothèse d'origine. Déjà
  affaiblie (médiane 13,9%) ; à vérifier sur sous-groupe ex ante.
- **H3 — Pas de mécanisme (hypothèse nulle).** Le rendement de juin
  venait du marché haussier (+18%). H3 doit être battue explicitement.

## Données

- `dividend_cycle_exploration.csv` (commit `d771ece`) — 89 cycles
- `v_historical_prices` via REST GET (pagination Range par 1000)
- Répertoire de travail : `tools/experiments/E2_6/`
- Aucune écriture en base, aucune modification de script existant

## Spécification

### Étape 1 — Alpha par cycle (test principal)

Pour chaque cycle, fenêtre [date_annonce, date_paiement] :
1. `rendement_cycle` = variation du titre, dividende inclus s'il est
   encaissé dans la fenêtre (brut : ni frais ni IRVM ici).
2. `benchmark_cycle` = moyenne simple des rendements de tous les
   tickers ayant un prix valide aux deux bornes, **ticker analysé
   exclu**. Prix valide = dernier cours ≤ 3 jours ouvrés de la borne.
3. `alpha_cycle = rendement_cycle − benchmark_cycle`.
4. Sortie `E2_6_alpha_par_cycle.csv` : ticker, fiscal_year,
   date_annonce, date_ex, date_paiement, duree_jours, dividende,
   yield_pct, rendement_cycle, benchmark_cycle, alpha_cycle,
   chute_ex_pct, statut_cotation_ex.

### Étape 2 — Désambiguïsation des chute_ex = 0.0%

Classer `statut_cotation_ex` :
- `COTE_SANS_VARIATION` : cours présent à la date ex ET au dernier jour
  coté avant, les deux égaux.
- `NON_COTE` : aucun cours à la date ex, ou dernier cours antérieur de
  plus de 3 jours ouvrés.
- `COTE_AVEC_VARIATION` : tous les autres cas.

Les `NON_COTE` sont **exclus des statistiques H2** (chute non mesurable)
et **conservés pour H1** (rendement de détention valide). Reporter les
effectifs des trois catégories.

### Étape 3 — Trois découpes autorisées, aucune autre

Pour chacune : n, alpha médian, % d'alpha positifs.
1. **Par ticker** (≥ 3 cycles ; les autres agrégés en « n<3 », non
   interprétés).
2. **Par année civile de l'ex-date.**
3. **Par tercile de yield** (cycles avec yield disponible).

Toute découpe supplémentaire = nouvelle expérience validée par Jocelyn.

### Étape 4 — Test H2 sur sous-groupe ex ante

Critère d'appartenance connu AVANT l'ex-date. Trois candidats, et
uniquement ceux-là :
- (a) délai AG→ex ≤ 45 jours (profil BOA)
- (b) yield dans le tercile supérieur
- (c) volume_20j avant l'annonce ≥ médiane de l'échantillon

Pour chacun : chute_ex médiane, n, % de cycles à chute < 30%.
**INTERDIT** de construire un sous-groupe à partir du résultat.

## Règles d'interprétation (textuelles)

Appliquer dans l'ordre, s'arrêter à la première qui déclenche :

- **H1 retenue** si alpha médian global ≥ +2 pts ET ≥ 60% des tickers
  à n≥3 ont un alpha médian positif ET alpha médian positif sur chacune
  des 4 années.
  → « H1 confirmée — dérive post-annonce. Mécanisme candidat pour T5c :
  hold annonce→paiement. Règle d'entrée à cadrer avec Jocelyn. »

- **H2 retenue** si H1 non retenue ET un sous-groupe ex ante présente
  une chute_ex médiane < 30% avec n ≥ 12 (NON_COTE exclus).
  → « H2 confirmée sur sous-groupe [critère] — sous-réaction
  exploitable. Critère d'éligibilité à figer en ADR avant backtest. »

- **H3 retenue** sinon.
  → « H3 retenue — aucun mécanisme dividende identifiable. Le chiffre
  de juin (93% WR) est réputé non reproduit. T5c se conclut sans
  backtest ; E2.4 et E2.5 restent gelées. Décision : Jocelyn. »

- **Cas limite** — H1 échoue sur un seul de ses trois critères, OU un
  sous-groupe H2 atteint n ≥ 12 avec chute médiane entre 30 et 35% :
  **escalade au modèle avancé, aucune conclusion écrite.**

## Interdits spécifiques

- Ne pas modifier `tools/explore_dividend_cycle.py` ni ses sorties.
- Ne pas élargir la fenêtre AG, ne pas ajouter de cycles.
- Ne pas calculer frais, IRVM, fill rate — hors périmètre.
- Ne pas proposer de règle d'entrée ou de sortie.
- Ne pas tester d'hypothèse H4 improvisée.
- Si un résultat surprend, il est rapporté tel quel. **Aucun paramètre
  ajusté pour rapprocher un chiffre d'une valeur attendue.**

## Critères d'acceptation

1. `E2_6_alpha_par_cycle.csv` produit, 89 lignes (ou écart justifié).
2. Effectifs des trois `statut_cotation_ex` reportés.
3. Les trois découpes produites, aucune autre.
4. Les trois sous-groupes ex ante testés.
5. Une règle d'interprétation appliquée textuellement, ou escalade.
6. Résultat consigné dans `EXPERIMENTS_LOG.md`.
7. Aucune écriture hors `tools/experiments/E2_6/` et `EXPERIMENTS_LOG.md`.

# E2.7-A — Grille entree/sortie, rotation dediee

**Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).**

## Contexte

E2.6 a confirme H1 (derive post-annonce) sur la fenetre [date_annonce,
date_paiement], alpha median +7.33 pts, 89 cycles, 4 annees (2022-2025).
E2.7-A teste si un point d'entree/sortie different de la fenetre brute
ameliore ou degrade cet alpha, pour une strategie de ROTATION DEDIEE
(achat specifique pour le cycle dividende, revente ensuite — pas un
hold long terme).

## Grilles (fixees, aucune autre combinaison testee)

- **Entree** (relatif a date_annonce) : J-5, J0 (=date_annonce, reference
  E2.6), J+5, J+10
- **Sortie** (relatif a date_paiement) : paiement-5j, paiement (reference
  E2.6), paiement+5j

12 combinaisons au total. Toute combinaison hors de cette grille = nouvelle
experience validee par Jocelyn d'abord.

## Donnees

- `dividend_cycle_exploration.csv` (commit d771ece), cycles exploitables=True
- `v_historical_prices` via REST GET (pagination Range par 1000)
- Univers : **tous les 49 tickers**, aucun filtre prealable
- Repertoire de travail : `tools/experiments/E2_7A/`
- Aucune ecriture en base, aucune modification de script existant

## Specification

### Etape 1 — Alpha par cycle x combinaison

Pour chacune des 12 combinaisons (entree_offset, sortie_offset) :
1. `date_entree` = date_annonce + entree_offset (jours calendaires)
2. `date_sortie` = date_paiement + sortie_offset
3. Si date_sortie <= date_entree pour un cycle donne : cycle exclu de
   CETTE combinaison uniquement, comptabilise et reporte (n exclus).
4. `rendement_cycle` = variation du titre entre dernier cours <= 5j avant
   date_entree et dernier cours <= 5j avant date_sortie, dividende inclus
   s'il est encaisse dans la fenetre [date_entree, date_sortie]. Brut :
   ni frais ni IRVM.
5. `benchmark_cycle` = moyenne simple des rendements de tous les tickers
   (hors ticker analyse) ayant un prix valide aux deux bornes (meme
   regle de tolerance qu'E2.6 : <=3 jours ouvres).
6. `alpha_cycle = rendement_cycle - benchmark_cycle`

Sortie `E2_7A_alpha_par_combinaison.csv` : ticker, fiscal_year,
entree_offset, sortie_offset, date_entree, date_sortie, rendement_cycle,
benchmark_cycle, alpha_cycle.

### Etape 2 — Robustesse par combinaison (PAS de selection du max)

Pour chacune des 12 combinaisons, sur l'ensemble des cycles valides :
n, alpha median, % de cycles positifs.

Produire un tableau recapitulatif 4x3 (entree x sortie) avec ces trois
chiffres par case.

### Etape 3 — Comparaison a la reference E2.6

Reference = combinaison (J0, paiement), c'est-a-dire exactement la
fenetre testee dans E2.6. Pour les 11 autres combinaisons, calculer
l'ecart d'alpha median par rapport a cette reference.

## Regles d'interpretation (textuelles)

Appliquer dans l'ordre, s'arreter a la premiere qui declenche :

- **Grille robuste, reference validee** si au moins 9 des 12
  combinaisons ont un alpha median positif ET la combinaison de
  reference (J0, paiement) reste dans le tercile superieur des 12
  combinaisons (classees par alpha median).
  -> « Grille robuste. La fenetre E2.6 (annonce->paiement) est un choix
  raisonnable, pas une coincidence. Ecart-type inter-combinaisons a
  rapporter mais pas de changement de regle recommande. »

- **Amelioration localisee** si la reference n'est PAS dans le tercile
  superieur, mais qu'une combinaison specifique domine avec un alpha
  median superieur d'au moins 3 points a la reference ET n >= 15 pour
  cette combinaison ET c'est la seule dans ce cas (pas de quasi-egalite
  avec 2+ combinaisons).
  -> « Combinaison [X] preferable a la reference E2.6 de [ecart] points
  (n=[n]). A considerer pour la regle d'entree/sortie, decision Jocelyn.
  Prudence : une seule experience, pas de validation croisee out-of-
  sample a ce stade. »

- **Grille instable (cas limite)** sinon — y compris si plusieurs
  combinaisons sont proches du maximum sans dominance claire.
  -> « Grille instable — aucune combinaison ne domine clairement.
  Signal probablement bruite sur n=89 cycles bruts repartis en 12 cases.
  Escalade au modele avance, aucune conclusion ecrite sur le choix
  entree/sortie. »

## Interdits specifiques

- Ne pas choisir "la meilleure case" sans passer par la regle
  d'interpretation ci-dessus.
- Ne pas tester de combinaison hors grille.
- Ne pas calculer frais, IRVM — hors perimetre (E2.7-A mesure le
  mecanisme brut, pas la rentabilite nette).
- Si un resultat surprend, il est rapporte tel quel.

## Criteres d'acceptation

1. `E2_7A_alpha_par_combinaison.csv` produit, 12 combinaisons x jusqu'a
   89 cycles chacune (avec exclusions reportees par combinaison).
2. Tableau recapitulatif 4x3 produit et affiche.
3. Comparaison a la reference E2.6 produite pour les 11 autres cases.
4. Une regle d'interpretation appliquee textuellement, ou escalade.
5. Resultat consigne dans `EXPERIMENTS_LOG.md`.
6. Aucune ecriture hors `tools/experiments/E2_7A/` et `EXPERIMENTS_LOG.md`.

---

# E2.7-B — Timing d'entree, detention longue

**Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).**

## Contexte

Meme mecanisme (H1, derive post-annonce) mais objectif different de
E2.7-A : ici, on suppose que le titre est/sera detenu LONG TERME de
toute facon (pas de sortie liee au cycle dividende). La question est
uniquement : entrer pres d'une date d'annonce de dividende bat-il un
point d'entree choisi au hasard dans l'annee, sur la meme duree de
detention ?

## Grilles (fixees, aucune autre combinaison testee)

- **Entree** (relatif a date_annonce) : J-5, J0 (=date_annonce), J+5, J+10
- **Duree de detention** : 35j, 47j, 70j (Q1 / mediane / Q3 de
  `duree_jours` mesures sur les 89 cycles d'E2.6 — pas de valeur
  importee d'ailleurs). Le max observe (424j) est ecarte comme outlier,
  non retenu dans la grille.

12 combinaisons (4 offsets x 3 durees) au total. Toute combinaison hors
de cette grille = nouvelle experience validee par Jocelyn d'abord.

## Reference aleatoire

Pour chaque ticker et chaque duree de la grille (35j, 47j, 70j) :
moyenne des rendements sur TOUTES les fenetres glissantes de cette duree
disponibles dans l'historique du ticker (pas uniquement autour des dates
de dividende), echantillonnees tous les 10 jours calendaires pour
limiter le volume de calcul. Trois references par ticker, une par duree.

## Donnees

- Memes sources qu'E2.7-A (CSV dividendes + REST v_historical_prices)
- Univers : tous les 49 tickers
- Repertoire de travail : `tools/experiments/E2_7B/`
- Aucune ecriture en base, aucune modification de script existant

## Specification

### Etape 1 — Rendement par cycle x offset x duree

Pour chacune des 12 combinaisons (offset, duree), pour chaque cycle
dividende exploitable :
1. `date_entree` = date_annonce + offset
2. `date_sortie_calc` = date_entree + duree (jours calendaires)
3. `rendement_cycle` = variation du titre entre dernier cours <=5j avant
   date_entree et dernier cours <=5j avant date_sortie_calc, dividende(s)
   inclus s'il y en a dans la fenetre (peut inclure le dividende source
   ET un dividende suivant si la fenetre le capture — a signaler si ca
   arrive, ne pas exclure).

Sortie `E2_7B_rendement_par_combinaison.csv` : ticker, fiscal_year,
offset, duree, date_entree, date_sortie_calc, rendement_cycle.

### Etape 2 — Reference aleatoire par ticker x duree

Pour chaque ticker ayant au moins un cycle dividende exploitable, pour
chacune des 3 durees (35j, 47j, 70j) : rendement moyen sur toutes les
fenetres glissantes de cette duree, echantillonnees tous les 10 jours
calendaires sur toute la periode ou le ticker a des prix disponibles.

Sortie `E2_7B_reference_aleatoire.csv` : ticker, duree, n_fenetres,
rendement_moyen.

### Etape 3 — Ecart par combinaison (offset x duree)

Pour chacune des 12 combinaisons : ecart moyen = moyenne, sur tous les
cycles de cette combinaison, de (rendement_cycle - reference_aleatoire
du ticker/duree correspondant). Reporter n, ecart moyen, ecart median,
% de cycles ou l'entree-dividende bat la reference aleatoire.

Produire un tableau recapitulatif 4x3 (offset x duree), meme format que
le tableau d'E2.7-A.

## Regles d'interpretation (textuelles)

Appliquer dans l'ordre, s'arreter a la premiere qui declenche :

- **Timing dividende confirme** si au moins 9 des 12 combinaisons ont un
  ecart median positif ET, parmi les 4 offsets, au moins 2 des 3 durees
  associees a l'offset le plus proche de l'annonce (J0 ou J-5) ont un %
  de cycles battant la reference >=55%.
  -> « Timing d'entree autour de l'annonce de dividende ameliore le
  rendement vs entree aleatoire, de facon robuste a travers les durees
  testees. Combinaison(s) a discuter avec Jocelyn : [lister les
  meilleures]. »

- **Pas d'effet timing detectable** si moins de 6 des 12 combinaisons
  ont un ecart median positif, ou si l'ecart existe mais le % de cycles
  gagnants est <55% pour la quasi-totalite des combinaisons (effet
  moyen tire par quelques gros cycles, pas un edge fiable).
  -> « Aucun effet de timing fiable detecte au-dela du mecanisme deja
  documente par E2.6. Pour une strategie de detention longue, le moment
  d'entree autour d'une annonce de dividende n'apporte pas d'avantage
  mesurable et robuste a travers les durees testees. »

- **Cas limite** — entre 6 et 8 combinaisons positives, ou resultats
  contradictoires entre offsets/durees (ex: J0/35j positif et fiable,
  J+10/70j negatif et fiable, pas de tendance coherente).
  -> « Resultats incoherents entre combinaisons — escalade au modele
  avance, aucune conclusion ecrite. »

## Interdits specifiques

- Ne pas choisir "la meilleure case" de la grille 4x3 sans passer par
  la regle d'interpretation ci-dessus.
- Ne pas tester de combinaison hors grille (offsets et durees fixes).
- Ne pas calculer frais, IRVM — hors perimetre.
- Ne pas exclure de cycles pour "nettoyer" un resultat qui deçoit.

## Criteres d'acceptation

1. `E2_7B_rendement_par_combinaison.csv` et
   `E2_7B_reference_aleatoire.csv` produits.
2. Tableau recapitulatif 4x3 (offset x duree) produit et affiche.
3. Une regle d'interpretation appliquee textuellement, ou escalade.
4. Resultat consigne dans `EXPERIMENTS_LOG.md`.
5. Aucune ecriture hors `tools/experiments/E2_7B/` et `EXPERIMENTS_LOG.md`.

# E2.7-A — Grille entree/sortie, rotation dediee

**Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).**

## Contexte

E2.6 a confirme H1 (derive post-annonce) sur la fenetre [date_annonce,
date_paiement], alpha median +7.33 pts, 89 cycles, 4 annees (2022-2025).
E2.7-A teste si un point d'entree/sortie different de la fenetre brute
ameliore ou degrade cet alpha, pour une strategie de ROTATION DEDIEE
(achat specifique pour le cycle dividende, revente ensuite — pas un
hold long terme).

## Grilles (fixees, aucune autre combinaison testee)

- **Entree** (relatif a date_annonce) : J-5, J0 (=date_annonce, reference
  E2.6), J+5, J+10
- **Sortie** (relatif a date_paiement) : paiement-5j, paiement (reference
  E2.6), paiement+5j

12 combinaisons au total. Toute combinaison hors de cette grille = nouvelle
experience validee par Jocelyn d'abord.

## Donnees

- `dividend_cycle_exploration.csv` (commit d771ece), cycles exploitables=True
- `v_historical_prices` via REST GET (pagination Range par 1000)
- Univers : **tous les 49 tickers**, aucun filtre prealable
- Repertoire de travail : `tools/experiments/E2_7A/`
- Aucune ecriture en base, aucune modification de script existant

## Specification

### Etape 1 — Alpha par cycle x combinaison

Pour chacune des 12 combinaisons (entree_offset, sortie_offset) :
1. `date_entree` = date_annonce + entree_offset (jours calendaires)
2. `date_sortie` = date_paiement + sortie_offset
3. Si date_sortie <= date_entree pour un cycle donne : cycle exclu de
   CETTE combinaison uniquement, comptabilise et reporte (n exclus).
4. `rendement_cycle` = variation du titre entre dernier cours <= 5j avant
   date_entree et dernier cours <= 5j avant date_sortie, dividende inclus
   s'il est encaisse dans la fenetre [date_entree, date_sortie]. Brut :
   ni frais ni IRVM.
5. `benchmark_cycle` = moyenne simple des rendements de tous les tickers
   (hors ticker analyse) ayant un prix valide aux deux bornes (meme
   regle de tolerance qu'E2.6 : <=3 jours ouvres).
6. `alpha_cycle = rendement_cycle - benchmark_cycle`

Sortie `E2_7A_alpha_par_combinaison.csv` : ticker, fiscal_year,
entree_offset, sortie_offset, date_entree, date_sortie, rendement_cycle,
benchmark_cycle, alpha_cycle.

### Etape 2 — Robustesse par combinaison (PAS de selection du max)

Pour chacune des 12 combinaisons, sur l'ensemble des cycles valides :
n, alpha median, % de cycles positifs.

Produire un tableau recapitulatif 4x3 (entree x sortie) avec ces trois
chiffres par case.

### Etape 3 — Comparaison a la reference E2.6

Reference = combinaison (J0, paiement), c'est-a-dire exactement la
fenetre testee dans E2.6. Pour les 11 autres combinaisons, calculer
l'ecart d'alpha median par rapport a cette reference.

## Regles d'interpretation (textuelles)

Appliquer dans l'ordre, s'arreter a la premiere qui declenche :

- **Grille robuste, reference validee** si au moins 9 des 12
  combinaisons ont un alpha median positif ET la combinaison de
  reference (J0, paiement) reste dans le tercile superieur des 12
  combinaisons (classees par alpha median).
  -> « Grille robuste. La fenetre E2.6 (annonce->paiement) est un choix
  raisonnable, pas une coincidence. Ecart-type inter-combinaisons a
  rapporter mais pas de changement de regle recommande. »

- **Amelioration localisee** si la reference n'est PAS dans le tercile
  superieur, mais qu'une combinaison specifique domine avec un alpha
  median superieur d'au moins 3 points a la reference ET n >= 15 pour
  cette combinaison ET c'est la seule dans ce cas (pas de quasi-egalite
  avec 2+ combinaisons).
  -> « Combinaison [X] preferable a la reference E2.6 de [ecart] points
  (n=[n]). A considerer pour la regle d'entree/sortie, decision Jocelyn.
  Prudence : une seule experience, pas de validation croisee out-of-
  sample a ce stade. »

- **Grille instable (cas limite)** sinon — y compris si plusieurs
  combinaisons sont proches du maximum sans dominance claire.
  -> « Grille instable — aucune combinaison ne domine clairement.
  Signal probablement bruite sur n=89 cycles bruts repartis en 12 cases.
  Escalade au modele avance, aucune conclusion ecrite sur le choix
  entree/sortie. »

## Interdits specifiques

- Ne pas choisir "la meilleure case" sans passer par la regle
  d'interpretation ci-dessus.
- Ne pas tester de combinaison hors grille.
- Ne pas calculer frais, IRVM — hors perimetre (E2.7-A mesure le
  mecanisme brut, pas la rentabilite nette).
- Si un resultat surprend, il est rapporte tel quel.

## Criteres d'acceptation

1. `E2_7A_alpha_par_combinaison.csv` produit, 12 combinaisons x jusqu'a
   89 cycles chacune (avec exclusions reportees par combinaison).
2. Tableau recapitulatif 4x3 produit et affiche.
3. Comparaison a la reference E2.6 produite pour les 11 autres cases.
4. Une regle d'interpretation appliquee textuellement, ou escalade.
5. Resultat consigne dans `EXPERIMENTS_LOG.md`.
6. Aucune ecriture hors `tools/experiments/E2_7A/` et `EXPERIMENTS_LOG.md`.

---

# E2.7-B — Timing d'entree, detention longue

**Classe A — experience offline, lecture seule. Gate : depend d'E2.6 (H1 confirmee, commit 67a39b6).**

## Contexte

Meme mecanisme (H1, derive post-annonce) mais objectif different de
E2.7-A : ici, on suppose que le titre est/sera detenu LONG TERME de
toute facon (pas de sortie liee au cycle dividende). La question est
uniquement : entrer pres d'une date d'annonce de dividende bat-il un
point d'entree choisi au hasard dans l'annee, sur la meme duree de
detention ?

## Grilles (fixees, aucune autre combinaison testee)

- **Entree** (relatif a date_annonce) : J-5, J0 (=date_annonce), J+5, J+10
- **Duree de detention** : 35j, 47j, 70j (Q1 / mediane / Q3 de
  `duree_jours` mesures sur les 89 cycles d'E2.6 — pas de valeur
  importee d'ailleurs). Le max observe (424j) est ecarte comme outlier,
  non retenu dans la grille.

12 combinaisons (4 offsets x 3 durees) au total. Toute combinaison hors
de cette grille = nouvelle experience validee par Jocelyn d'abord.

## Reference aleatoire

Pour chaque ticker et chaque duree de la grille (35j, 47j, 70j) :
moyenne des rendements sur TOUTES les fenetres glissantes de cette duree
disponibles dans l'historique du ticker (pas uniquement autour des dates
de dividende), echantillonnees tous les 10 jours calendaires pour
limiter le volume de calcul. Trois references par ticker, une par duree.

## Donnees

- Memes sources qu'E2.7-A (CSV dividendes + REST v_historical_prices)
- Univers : tous les 49 tickers
- Repertoire de travail : `tools/experiments/E2_7B/`
- Aucune ecriture en base, aucune modification de script existant

## Specification

### Etape 1 — Rendement par cycle x offset x duree

Pour chacune des 12 combinaisons (offset, duree), pour chaque cycle
dividende exploitable :
1. `date_entree` = date_annonce + offset
2. `date_sortie_calc` = date_entree + duree (jours calendaires)
3. `rendement_cycle` = variation du titre entre dernier cours <=5j avant
   date_entree et dernier cours <=5j avant date_sortie_calc, dividende(s)
   inclus s'il y en a dans la fenetre (peut inclure le dividende source
   ET un dividende suivant si la fenetre le capture — a signaler si ca
   arrive, ne pas exclure).

Sortie `E2_7B_rendement_par_combinaison.csv` : ticker, fiscal_year,
offset, duree, date_entree, date_sortie_calc, rendement_cycle.

### Etape 2 — Reference aleatoire par ticker x duree

Pour chaque ticker ayant au moins un cycle dividende exploitable, pour
chacune des 3 durees (35j, 47j, 70j) : rendement moyen sur toutes les
fenetres glissantes de cette duree, echantillonnees tous les 10 jours
calendaires sur toute la periode ou le ticker a des prix disponibles.

Sortie `E2_7B_reference_aleatoire.csv` : ticker, duree, n_fenetres,
rendement_moyen.

### Etape 3 — Ecart par combinaison (offset x duree)

Pour chacune des 12 combinaisons : ecart moyen = moyenne, sur tous les
cycles de cette combinaison, de (rendement_cycle - reference_aleatoire
du ticker/duree correspondant). Reporter n, ecart moyen, ecart median,
% de cycles ou l'entree-dividende bat la reference aleatoire.

Produire un tableau recapitulatif 4x3 (offset x duree), meme format que
le tableau d'E2.7-A.

## Regles d'interpretation (textuelles)

Appliquer dans l'ordre, s'arreter a la premiere qui declenche :

- **Timing dividende confirme** si au moins 9 des 12 combinaisons ont un
  ecart median positif ET, parmi les 4 offsets, au moins 2 des 3 durees
  associees a l'offset le plus proche de l'annonce (J0 ou J-5) ont un %
  de cycles battant la reference >=55%.
  -> « Timing d'entree autour de l'annonce de dividende ameliore le
  rendement vs entree aleatoire, de facon robuste a travers les durees
  testees. Combinaison(s) a discuter avec Jocelyn : [lister les
  meilleures]. »

- **Pas d'effet timing detectable** si moins de 6 des 12 combinaisons
  ont un ecart median positif, ou si l'ecart existe mais le % de cycles
  gagnants est <55% pour la quasi-totalite des combinaisons (effet
  moyen tire par quelques gros cycles, pas un edge fiable).
  -> « Aucun effet de timing fiable detecte au-dela du mecanisme deja
  documente par E2.6. Pour une strategie de detention longue, le moment
  d'entree autour d'une annonce de dividende n'apporte pas d'avantage
  mesurable et robuste a travers les durees testees. »

- **Cas limite** — entre 6 et 8 combinaisons positives, ou resultats
  contradictoires entre offsets/durees (ex: J0/35j positif et fiable,
  J+10/70j negatif et fiable, pas de tendance coherente).
  -> « Resultats incoherents entre combinaisons — escalade au modele
  avance, aucune conclusion ecrite. »

## Interdits specifiques

- Ne pas choisir "la meilleure case" de la grille 4x3 sans passer par
  la regle d'interpretation ci-dessus.
- Ne pas tester de combinaison hors grille (offsets et durees fixes).
- Ne pas calculer frais, IRVM — hors perimetre.
- Ne pas exclure de cycles pour "nettoyer" un resultat qui deçoit.

## Criteres d'acceptation

1. `E2_7B_rendement_par_combinaison.csv` et
   `E2_7B_reference_aleatoire.csv` produits.
2. Tableau recapitulatif 4x3 (offset x duree) produit et affiche.
3. Une regle d'interpretation appliquee textuellement, ou escalade.
4. Resultat consigne dans `EXPERIMENTS_LOG.md`.
5. Aucune ecriture hors `tools/experiments/E2_7B/` et `EXPERIMENTS_LOG.md`.
