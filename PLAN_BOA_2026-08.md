# PLAN DE TRAVAIL — Exploitation source BOA Capital Securities

**Date de rédaction :** 03/08/2026
**Repo :** `clomajo/brvm-analysis-suite`
**Branche :** `remediation-2026-07`
**Hors plan de remédiation formel** (T0–T17 clos) — item de backlog général.

**Destinataire :** agent d'exécution à capacité réduite. Ce document est un contrat
d'exécution : chaque lot est autosuffisant, avec critères d'acceptation et conditions
d'arrêt explicites. **Ne rien inférer hors de ce qui est écrit.**

---

## 0. Règles d'exécution — s'appliquent à TOUS les lots

Contraintes non négociables (violation = arrêt immédiat) :

- **Supabase via REST API uniquement**, jamais `psycopg2` (ADR-004). Headers : `apikey`
  ET `Authorization: Bearer` avec `SUPABASE_SERVICE_ROLE_KEY`.
- **Corrections de masse en base → SQL Editor Supabase uniquement**, jamais PATCH REST
  ligne par ligne (ADR-026).
- `python3` explicite (le `python` local est Python 2). Environnement `venv311`.
- Tout script Python : `load_dotenv(find_dotenv(usecwd=True))`, module `logging`,
  **jamais de `except:` silencieux**.
- Création de script via `cat >> fichier.py << 'EOF'` en 2–3 segments, avec `wc -l`
  entre chaque segment et `python3 -m py_compile fichier.py` avant exécution.
  Pas d'éditeur interactif.
- **Une tâche par session.** Ne jamais enchaîner deux lots sans validation humaine.
- **Protocole trois tentatives** : erreur d'infrastructure (réseau/clé/DNS) → 1 retry
  puis STOP. Erreur de code → traceback complet + hypothèse écrite avant chaque
  correctif. Après 3 échecs → `git checkout -- .` puis escalade à Jocelyn.
- **Gate humain avant tout code d'expérimentation** : les règles exactes (univers,
  entrée, sortie, définition du net) doivent être validées par écrit d'abord.

### Noms de colonnes réels (pièges confirmés)

| Table | Colonnes correctes |
|---|---|
| `companies` | `symbol` (**pas** `ticker`), `id` |
| `historical_data` | `trade_date` (**pas** `date`), `price` (**pas** `close_price`), `company_id`, `volume` — **pas de colonne ticker** |
| `brvm_decisions` | `date` (**pas** `signal_date`), `signal` (**pas** `decision`), `market_regime` (**pas** `regime`), `ticker`, `score` |
| `target_prices` | `ticker`, `cours_cible`, `decote_pct`, `signal_v2`, `calcul_date` |
| `boa_recommendations` | `action` (BUY/SELL/HOLD/REDUCE), `cours_act`, `cours_pot`, `rendement`, `potential` |

Vue utile : `v_historical_prices` (jointure `historical_data` × `companies`, expose une
colonne `ticker`) — préférer cette vue pour éviter la jointure manuelle.

### Fiabilité de la source — règle absolue

Le bulletin BOA contient **deux niveaux de fiabilité distincts** :

- **Le tableau récapitulatif : fiable.** C'est la seule source à parser.
- **Le commentaire narratif : NON fiable.** Erreurs systématiques de confusion entre
  les colonnes `VAR_SEM`, `RENDEMENT` et `+/- VALUE`, plus des inversions de signe.
  Exemples relevés le 03/08/2026 : ORAC (texte « en baisse de 18,06% » = potentiel, pas
  variation ; VAR_SEM réel = +1,61%), CFAC (colonnes rendement et potentiel
  interverties), TTLS, CABC, ETIT, PALC, BICC, NTLC, SOGC.

**Ne jamais extraire de chiffre depuis le texte narratif.** Le champ `action` peut être
dérivé du texte (ACHETER/CONSERVER/RÉDUIRE/VENDRE) car il est cohérent avec le
code couleur du tableau, mais tout chiffre vient du tableau.

Rappel connexe : boaksdirect.com inverse le signe du YTD (pattern confirmé). Même
famille d'erreur, même éditeur — traiter toute donnée BOA avec contrôle de cohérence.

---

## LOT B0 — Diagnostic de l'existant (lecture seule)

**Classe A** (offline, autonome, aucune écriture). **Durée estimée : 30 min.**

### Objectif
Établir l'état réel de l'actif dormant avant toute décision. Aucune conclusion
analytique attendue à ce stade.

### Questions à trancher, une par une

1. **Contenu de la table.** Nombre exact de lignes, plage de dates couverte, nombre de
   tickers distincts, distribution des valeurs de `action`, taux de NULL par colonne.
2. **Script d'ingestion.** Existe-t-il ? Chercher dans le repo :
   ```bash
   cd ~/Desktop/brvm-analysis-suite
   grep -rn "boa_recommendations" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.md" .
   git log --oneline --all -- '*boa*'
   ```
3. **Cause de l'arrêt en avril 2026.** Le script est-il absent des workflows GitHub
   Actions (même pathologie que l'orphelin `extract_fundamental_signals.py`) ? A-t-il
   été supprimé par commit ? A-t-il échoué silencieusement ?
4. **Tab frontend archivé.** Le code du tab « BOA vs BRVM » (commit `25a92a0`,
   repo `brvm-analytics`) est-il récupérable via `git show` ? Que consommait-il ?
5. **Source du benchmark indiciel.** Identifier où vit la série BRVMC utilisée par
   la colonne `alpha` de `brvm_decisions_results` (T16/ADR-035). **Ne pas supposer** —
   le lot B1 en dépend.
6. **Normalisation des tickers.** Comparer les tickers de `boa_recommendations` à
   `companies.symbol`. Points d'attention connus : `BOANG` (bulletin) vs `BOAN`
   (base) ; `SITAB` apparaît sous le code `STBC`. Produire la liste des non-appariés.

### Livrable
Un compte rendu écrit dans le fil de session (pas de fichier créé). Aucun commit.

### Critère d'acceptation
Les 6 questions ont une réponse factuelle sourcée (requête ou commande git à l'appui).
Une réponse « je ne sais pas » est acceptable et doit être explicite.

### Condition d'arrêt
Si la table `boa_recommendations` est vide ou inaccessible → STOP, escalade. Tout le
plan repose sur cet historique.

---

## LOT B1 — Backtest de l'historique BOA (GATE DÉCISIONNEL)

**Classe A** (offline, lecture seule). **Ne pas démarrer sans validation écrite de B0.**

### Objectif
Répondre à une seule question : **les recommandations BOA ont-elles un edge mesurable ?**
17 semaines × ~32 tickers ≈ 547 observations, déjà en base. Si la réponse est non, les
lots B2 à B4 sont annulés et le sujet est clos — économie de plusieurs sessions.

C'est l'application directe du principe de falsification qui a gelé la Phase 13 via T9.

### Règles à valider par Jocelyn AVANT écriture du script

À soumettre en gate humain, sans code :

- **Univers :** toutes les lignes de `boa_recommendations`, ou exclusion des tickers non
  appariés à `companies.symbol` ?
- **Entrée :** prix de clôture du premier jour ouvré suivant la date de publication.
- **Horizons :** J+20 (cohérent avec `VERIFICATION_WINDOW`, ADR-038) et J+90.
- **Métrique principale :** **alpha** (rendement − rendement du benchmark sur la même
  fenêtre), pas le rendement brut. Justification : distingue « BOA perd de l'argent dans
  un marché baissier » de « BOA ne bat pas le marché » — même raisonnement que le
  kill-switch T10-B.
- **Tolérance d'appariement de dates :** ±5 jours calendaires (aligné sur le choix retenu
  en T16, ADR-035, plutôt que ±3 jours ouvrés).
- **Brut d'abord** (protocole E2.6/E2.7/T5c-A) : pas de frais ni d'IRVM en première
  passe. Sensibilité a posteriori si le résultat est positif.
- **Segmentation :** par `action` (BUY/SELL/HOLD/REDUCE), et par secteur
  `SECTEUR_OFFICIEL` tel que défini dans `calculate_target_price.py` — **pas**
  `companies.sector`, qui est un mapping différent (voir ADR-037, trois mappings
  sectoriels non synchronisés coexistent dans le repo).

### Sorties attendues
Pour chaque `action` × horizon : n, médiane d'alpha, moyenne, % positifs, IC95%.
Test de la hiérarchie attendue : alpha(BUY) > alpha(HOLD) > alpha(REDUCE) > alpha(SELL).

### Script
`tools/backtest_boa_recommendations.py`. Écriture interdite en base.

### Critère d'acceptation
- Le script tourne sans exception et loggue le nombre de lignes exclues **avec le motif**.
- n effectif ≥ 300 sur J+20. Si n < 300, documenter la perte et sa cause.
- Résultat consigné dans `EXPERIMENTS_LOG.md`.

### Gate de sortie — décide de la suite du plan
- **Hiérarchie respectée et alpha(BUY) positif avec IC95% ne franchissant pas 0**
  → poursuivre en B2.
- **Hiérarchie non respectée ou alpha(BUY) non distinguable de 0**
  → **STOP.** Documenter le verdict en ADR, annuler B2/B3/B4, ne pas réactiver
  l'ingestion. B3 peut être conservé isolément (voir note en B3).
- **Résultat ambigu (IC95% chevauchant 0 mais hiérarchie correcte)**
  → escalade à Jocelyn, ne pas trancher seul. Précédent : T6, borne basse d'IC95%
  négative, a conduit à un gel et non à une poursuite.

---

## LOT B2 — Réingestion (conditionnel au gate B1)

**Classe B** (modification de production, gate humain obligatoire).

### Objectif
Reprendre l'alimentation de `boa_recommendations`, à commencer par le bulletin
du 03–06/08/2026 (30 lignes tableau principal + 6 lignes tableau groupe BOA).

### Sous-étapes, une par session

- **B2.1** — Charger manuellement le bulletin du 03/08/2026 via SQL Editor Supabase
  (ADR-026 : insertion de masse en SQL, pas en PATCH REST). Vérifier au préalable la
  contrainte d'unicité de la table pour éviter un échec silencieux à l'insert — piège
  déjà rencontré sur `fundamental_analysis` (`UNIQUE(company_id)` non documentée).
- **B2.2** — Décider du mode d'alimentation durable. Le bulletin arrive par email
  (`opportunites@boacapital.com`), en PDF hébergé sur Adobe cloud. Options à arbitrer
  par Jocelyn : saisie manuelle hebdomadaire, boîte mail dédiée + parsing, ou abandon
  de l'automatisation. **Ne pas coder avant arbitrage.**
- **B2.3** — Si automatisation retenue : rattacher le script à un workflow GitHub Actions
  **dans le même commit** que le script. L'orphelin `extract_fundamental_signals.py`
  (script actif, absent de tout YAML, signal potentiellement périmé sans alerte) est le
  précédent à ne pas reproduire.

### Point de vigilance — traçabilité du tableau groupe BOA
Les 6 lignes BOAS/BOAML/BOAC/BOAB/BOABF/BOANG sont publiées **sans `action` ni
`cours_pot`**, dans un tableau séparé. BOA Capital appartient au groupe : conflit
d'intérêt non déclaré. Les stocker avec `action = NULL` et un flag distinctif ; ne
jamais les imputer en HOLD par défaut.

---

## LOT B3 — `cours_pot` BOA vs `cours_cible` V2

**Classe A** (lecture seule). **Peut être exécuté même si le gate B1 est négatif** — la
question posée est différente : il s'agit d'un contrôle de cohérence externe du modèle
de valorisation, pas d'un pari sur la qualité des recommandations BOA.

### Objectif
`cours_pot` (BOA) et `target_prices.cours_cible` (V2) sont deux estimations
indépendantes de la même grandeur. Leur écart est un test externe de
`calculate_target_price.py`, que rien ne fournissait jusqu'ici.

### Intérêt spécifique
Alimente l'item de backlog **priorité haute** issu de T14 : V2 applique un modèle unique
(PER sectoriel × EPS + dividende/8%) à tous les secteurs, alors que la pratique
professionnelle impose des modèles distincts pour les banques (P/E + P/B, ou dividend
discount / residual income). Si l'écart BOA↔V2 est systématiquement plus large sur
`SERVICES_FINANCIERS` que sur les autres secteurs, c'est un argument empirique direct
en faveur d'un modèle bancaire dédié.

### Sorties
Par ticker : `cours_cible`, `cours_pot`, écart absolu, écart relatif. Agrégation par
`SECTEUR_OFFICIEL`. Test explicite : l'écart médian sur `SERVICES_FINANCIERS` diffère-t-il
de celui des autres secteurs ?

### Réserve méthodologique à documenter
Les deux modèles n'ont ni le même horizon ni la même méthode, et la méthodologie BOA
n'est pas publiée. Une divergence ne prouve pas qu'un modèle a tort. Ce lot produit un
**signal d'investigation**, pas un verdict.

---

## LOT B4 — Matrice recommandations BOA × signaux V1/V2

**Classe A** (lecture seule). Conditionnel au gate B1.

### Objectif
Croiser `boa_recommendations.action` avec `brvm_decisions.signal` (V1) et
`target_prices.signal_v2` (V2) sur les dates communes. Matrice de confusion + taux de
concordance.

### Divergence déjà identifiée à traiter explicitement
Sur le bulletin du 03/08/2026, BOA classe **ECOC, SMBC, NSBC et NTLC en Vendre**, et
BOAB/BOAC sont hors périmètre (tableau groupe, sans recommandation). Soit **la totalité
des 6 tickers de la stratégie dividend capture**, laquelle affiche 93% de réussite en
walk-forward, +8,3% net médian sur ~32 jours.

Lecture à tester, pas à supposer : les horizons diffèrent. BOA raisonne en valorisation
absolue à horizon indéterminé ; le dividend capture exploite une rotation courte autour
de l'ex-dividende. Le précédent NTLC est directement pertinent — négatif en T5c-B
(détention longue, alpha −4,63 pts) mais positif en T5c-A (rotation courte, +3,14 pts,
100% sur 4 cycles). **Des mécanismes distincts ne se généralisent pas d'un horizon à
l'autre.** Une recommandation Vendre de BOA ne contredit donc pas mécaniquement le
dividend capture.

### Sortie
Note d'analyse dans `EXPERIMENTS_LOG.md`. Aucune modification de production.

---

## LOT B5 — Documentation et clôture

**Classe B.**

- ADR dans `DECISIONS.md` (prochain numéro disponible — ADR-038 est pris depuis le
  30/07/2026, commit `c41e507`). Contenu : statut de la source BOA, verdict du gate B1,
  règle « tableau fiable / narratif non fiable », décision d'ingestion.
- `EXPERIMENTS_LOG.md` : résultats B1, B3, B4.
- `BACKLOG.md` : items ouverts restants.
- `CHANGELOG.md` et `SKILL.md` : mise à jour si la table ou le pipeline changent.
- Commit unique de documentation en fin de session.

---

## Séquencement et gates

```
B0  diagnostic               →  [validation Jocelyn]
B1  backtest historique      →  [GATE : edge confirmé ?]
       │
       ├── NON → STOP. ADR de clôture. B3 exécutable isolément. B2/B4 annulés.
       │
       └── OUI → B2 réingestion  →  B3 comparaison  →  B4 matrice  →  B5 doc
```

**Ordre non négociable.** B1 avant B2 : ne pas reconstruire une tuyauterie avant
d'avoir mesuré la valeur de ce qui y transite.

---

## Points ouverts nécessitant un arbitrage de Jocelyn

1. Univers B1 : inclure ou exclure les tickers non appariés à `companies.symbol` ?
2. Mode d'alimentation durable (B2.2) : manuel, semi-automatisé, ou abandon ?
3. La source BOA doit-elle rester une référence d'analyse hors production, ou peut-elle
   à terme alimenter un signal ? (Question à ne pas trancher avant B1.)
4. Lien avec la question de fond V1/V2/combinaison, toujours ouverte : BOA constitue-t-il
   un troisième axe de falsification légitime, aux côtés du benchmark indiciel (alpha,
   T16) et de la stratégie naïve dividende (T9) ?

---

## Annexe — Prompt d'ouverture de session

À coller en tête de chaque session, en remplaçant `[LOT]` par B0, B1, B3, etc.

> Tu exécutes le **lot [LOT]** du fichier `PLAN_BOA_2026-08.md`, projet BRVM Analytics,
> repo `clomajo/brvm-analysis-suite`, branche `remediation-2026-07`.
>
> **Tu exécutes ce lot et rien d'autre.** Même si le lot suivant te paraît trivial ou
> purement en lecture, tu t'arrêtes à la fin de celui-ci et tu attends ma validation
> écrite. Un seul lot par session, sans exception.
>
> Avant d'écrire la moindre ligne de code, tu me restitues : (1) ta compréhension de
> l'objectif du lot, (2) les critères d'acceptation tels que tu les lis, (3) la
> condition d'arrêt. Si un point du plan est ambigu, tu me poses la question au lieu
> de trancher.
>
> Contraintes permanentes : Supabase en REST uniquement, jamais psycopg2. `python3`
> explicite, environnement `venv311`. `load_dotenv(find_dotenv(usecwd=True))`. Module
> `logging`, aucun `except` silencieux. Scripts créés par `cat >> ... << 'EOF'` en
> segments, avec `wc -l` entre chaque et `python3 -m py_compile` avant exécution. Pas
> d'éditeur interactif.
>
> Noms de colonnes : `companies.symbol`, `historical_data.trade_date` / `.price`,
> `brvm_decisions.date` / `.signal` / `.market_regime`. Tu vérifies avant d'écrire une
> requête, tu ne te fies pas à ta mémoire.
>
> Protocole d'erreur : infrastructure (réseau, clé, DNS) → 1 retry puis STOP. Code →
> traceback complet et hypothèse écrite avant chaque correctif. Après 3 échecs →
> `git checkout -- .` et tu m'escalades.
>
> Quand tu me présentes un résultat statistique, tu ne l'interprètes pas dans le sens
> qui permet de continuer. Sur ce projet, un IC95% dont la borne basse est négative a
> déjà conduit à geler une phase entière (T6), et un backtest montrant l'absence
> d'edge différentiel a gelé la Phase 13 (T9). Un résultat ambigu se remonte tel quel,
> il ne se conclut pas.
>
> Enfin : si le lot implique le bulletin BOA, seul le **tableau** est une source de
> chiffres. Le commentaire narratif contient des erreurs systématiques de colonnes et
> de signes. Tu ne cherches pas à réconcilier les deux, tu ignores le narratif.
