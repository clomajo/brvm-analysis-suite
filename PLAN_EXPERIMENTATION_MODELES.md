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
