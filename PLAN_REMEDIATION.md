# PLAN DE REMÉDIATION — BRVM Analytics
**Version 1.2 — 02/07/2026**
*(1.0 : plan initial · 1.1 : patches revue croisée externe · 1.2 : phases 11-13 — mesure, protection et évolutions du modèle V2)*
**Conçu pour exécution par un modèle Claude moins avancé (Sonnet/Haiku)**

---

## Comment utiliser ce plan

Chaque tâche est atomique : une session = une tâche. Le modèle exécutant n'a **aucune décision de conception à prendre** — tout est spécifié. Son rôle : écrire le code selon la spec, exécuter les commandes, vérifier les critères d'acceptation, s'arrêter.

**Règles de délégation :**
1. Une seule tâche par session. Ne jamais enchaîner.
2. Coller le bloc GARDE-FOUS + la tâche complète en début de session.
3. Si le modèle propose autre chose que la spec → refuser, recadrer.
4. Si un critère d'acceptation échoue → le modèle documente l'échec et s'arrête. Pas d'improvisation corrective.
5. Commit uniquement si TOUS les critères passent.

**Prompt template (à coller en début de chaque session) :**
```
Tu travailles sur le projet BRVM Analytics. Exécute UNIQUEMENT la tâche
ci-dessous, exactement comme spécifiée. Ne prends aucune initiative hors
du périmètre. Si un critère d'acceptation échoue, documente et arrête-toi.

[COLLER LE BLOC GARDE-FOUS]
[COLLER LA TÂCHE]
```

---

## GARDE-FOUS (à coller dans chaque session)

```
CONTRAINTES NON NÉGOCIABLES :
- Supabase : REST API uniquement (https://lynevvhmstpcffobwudr.supabase.co/rest/v1/
  avec headers apikey + Authorization: Bearer). JAMAIS psycopg2 (ADR-004).
- Corrections de masse en base : SQL Editor Supabase uniquement,
  JAMAIS de PATCH REST ligne par ligne (ADR-026).
- App.jsx : JAMAIS d'édition directe. Modifications via script Python
  patch exécuté en terminal (ADR-002).
- Ne pas installer react-markdown (ADR-031). Ne pas upgrader Vite 3.2.7
  ni Node v16.20.2.
- Python en heredoc : load_dotenv(find_dotenv(usecwd=True)) obligatoire.
- Colonnes pièges : companies.symbol (pas ticker) · historical_data.trade_date
  et .price (pas date/close_price, pas de colonne ticker) ·
  brvm_decisions.date/.signal/.market_regime.
- Nouveau code : ne rien casser du pipeline quotidien. Tout nouveau script
  est additif, jamais une réécriture d'un script existant sauf si la tâche
  le spécifie.
- Tout nouveau script utilise le module logging (INFO/WARNING/ERROR,
  sortie stderr). Jamais de print pour les erreurs, jamais d'except
  silencieux (un except sans log ni re-raise est INTERDIT).
```

---

# PROTOCOLE ERREURS (à coller dans chaque session, avec les garde-fous)

Les erreurs sont attendues et abondantes. Ce qui protège le projet n'est
pas leur absence, c'est ce protocole.

```
RÈGLE DES 3 TENTATIVES :
0. TRIAGE D'ABORD : si l'erreur est d'environnement (clé API expirée,
   timeout réseau, quota atteint, DNS, permission fichier) → 1 seul
   retry après 30 s, puis STOP immédiat avec le message "erreur
   d'infrastructure — intervention humaine requise". Ces erreurs ne
   consomment PAS les 3 tentatives : le modèle ne peut pas les corriger.
1. Toujours fournir au modèle le traceback COMPLET (jamais un résumé).
2. Avant toute correction, le modèle doit énoncer son hypothèse sur la
   cause. Pas d'hypothèse = pas de correction.
3. Une correction = un diff minimal sur le fichier concerné.
   INTERDIT : réécrire le fichier entier · supprimer ou commenter le code
   ou le test qui échoue · try/except silencieux · assouplir un critère
   d'acceptation · toucher un fichier hors périmètre de la tâche.
4. La correction doit être EXÉCUTÉE et son résultat montré. "Cela devrait
   fonctionner maintenant" sans exécution ne compte pas comme tentative.
5. Après 3 tentatives échouées sur la MÊME erreur : STOP définitif de
   la session. Ne pas insister.
```

**Après un STOP :**
```bash
git diff                    # regarder ce qui a été modifié
git checkout -- .           # tout jeter (rien n'était committé)
```
Puis ouvrir une session avec un modèle avancé (Fable) en collant : la
tâche, le traceback complet, et le diff de la dernière tentative. Le
modèle avancé débogue le point dur ; le modèle léger reprend l'exécution
ensuite.

**Signaux que le modèle tourne en rond → STOP immédiat, sans attendre
la 3e tentative :**
- Il repropose la même correction reformulée.
- Il ajoute du code au lieu d'en corriger.
- L'erreur change à chaque tentative (il casse plus qu'il ne répare).
- Il modifie des fichiers non mentionnés dans la tâche.

**Filet permanent :**
- Zéro commit tant que les critères d'acceptation ne passent pas →
  une session ratée coûte exactement `git checkout -- .`, rien de plus.
- Dès que T2 existe : `pytest -v` obligatoire avant CHAQUE commit, même
  pour une tâche sans rapport avec les fonctions testées.
- Jamais de `git push --force`, jamais de travail direct sur main.

**Économie du système :** le modèle léger exécute, le modèle avancé
débogue les blocages. Abandonner une session coûte 5 minutes ; un mauvais
fix silencieux coûte un bug en prod découvert des semaines plus tard
(cf. BACKLOG corrompu pendant un mois).

---

# PHASE 0 — Préparation (15 min)

## T0 — Branche de travail et snapshot

**Objectif :** pouvoir revenir en arrière sur tout.

**Étapes :**
```bash
cd ~/Desktop/brvm-analysis-suite
git checkout -b remediation-2026-07
git push -u origin remediation-2026-07
```
Puis dans Supabase Dashboard → Database → Backups : vérifier qu'un backup
automatique < 24h existe. Noter sa date dans `REMEDIATION_LOG.md`, créé
à la racine du repo pipeline et versionné (commité à chaque fin de tâche).

**Critères d'acceptation :** branche poussée, date de backup notée.

---

# PHASE 1 — P0 : Health report quotidien

## T1 — Script `health_check.py` + intégration workflow

**Contexte :** un run Actions peut sortir en exit 0 sans avoir rien inséré
(cf. BACKLOG corrompu 1 mois sans détection). Objectif : chaque run quotidien
se termine par un bilan chiffré, et échoue bruyamment (→ email GitHub) si
une anomalie est détectée.

**Fichier à créer :** `health_check.py` (racine du repo pipeline).

**Spécification exacte du script :**
1. Charger `.env` via `load_dotenv(find_dotenv(usecwd=True))`.
2. Via REST API (module `requests`), calculer pour AUJOURD'HUI (UTC) :
   - `nb_prices` : lignes `historical_data` avec `trade_date = date du jour`
     (utiliser `Prefer: count=exact` + header `Range: 0-0` pour ne compter
     que sans télécharger).
   - `nb_targets` : lignes `target_prices` avec `calcul_date = date du jour`.
   - `nb_decisions` : lignes `brvm_decisions` avec `date = date du jour`.
   - `missing_tickers` : liste des `companies.symbol` sans ligne
     `historical_data` aujourd'hui (jointure via `v_historical_prices`).
3. Seuils (constantes en tête de script) :
   - `MIN_PRICES = 35` (sur 47 tickers ; certains ne cotent pas chaque jour)
   - `MIN_TARGETS = 30`
   - `MIN_DECISIONS = 30`
4. Écrire un résumé Markdown dans `$GITHUB_STEP_SUMMARY` si la variable
   d'environnement existe (tableau : métrique / valeur / seuil / statut ✅❌,
   plus la liste `missing_tickers`). Sinon (exécution locale) : écrire le
   même résumé dans `health_report.md` — le script doit être testable
   hors CI.
5. Si un seuil échoue OU si le jour est ouvré (lundi-vendredi) et
   `nb_prices == 0` : `sys.exit(1)`. Sinon `sys.exit(0)`.
6. Week-end ET jours fériés : le script s'exécute mais ne fail jamais
   (la BRVM est fermée). Week-end : `datetime.utcnow().weekday() >= 5`.
   Jours fériés : constante `JOURS_FERIES_BRVM_2026` (liste de dates ISO)
   en tête de script — **valeurs à remplir par Jocelyn depuis le
   calendrier officiel BRVM (brvm.org), jamais devinées par le modèle**
   (les fêtes musulmanes varient chaque année). Si date du jour dans la
   liste → exit 0 avec note "jour férié".
7. Extension optionnelle (session séparée, après validation de T1) :
   insérer chaque bilan dans une table Supabase `pipeline_health`
   (run_date, nb_prices, nb_targets, nb_decisions, missing_count, statut)
   pour suivre la tendance dans le temps et l'afficher plus tard dans
   le frontend.

**Intégration workflow :** dans le YAML du run quotidien, ajouter en
**dernier step** :
```yaml
      - name: Health check
        if: always()
        run: python health_check.py
```
`if: always()` garantit l'exécution même si un step antérieur a échoué.

**Critères d'acceptation :**
1. Exécution locale `python health_check.py` → affiche le tableau, exit code
   cohérent (`echo $?`).
2. Un run manuel du workflow (workflow_dispatch) montre le résumé dans
   l'onglet Summary du job.
3. Test négatif : mettre temporairement `MIN_PRICES = 999`, relancer →
   le job échoue et GitHub envoie l'email. Puis remettre 35 et re-commit.

**Piège :** ne pas compter en téléchargeant 110k lignes — utiliser
`Prefer: count=exact` avec `Range: 0-0`.

---

# PHASE 2 — P0 : Tests automatisés

## T2 — Suite pytest sur les fonctions critiques

**Contexte :** tous les bugs récents (EPS, contrainte parasite,
`_find_all_reports`) ont été découverts en prod. On fige le comportement
actuel par des tests avant toute refonte (T4 en dépend).

**Fichiers à créer :** `tests/test_eps.py`, `tests/test_parsing.py`,
`tests/conftest.py`, plus `pytest` ajouté à `requirements.txt`
(version épinglée `pytest==8.*`).

**Spécification :**
1. `tests/conftest.py` : aucune connexion réseau. Toutes les données de test
   sont des dicts/fixtures en dur.
2. `test_eps.py` — cibler `check_eps_coherence()` et `evaluer_qualite_eps()` :
   - Cas cohérent : EPS scrapé ≈ net_income/shares (écart < 10%) → pas de warning.
   - Cas NTLC historique : ratio ~20x → warning déclenché.
   - Cas SOGC : ratio 0.73x → warning déclenché.
   - Qualité EPS : 1 an exploitable → accepté ; 2 ans non consécutifs →
     rejeté ; collapse > 80% YoY → rejeté.
   - Division par zéro : `shares_outstanding = 0` ou `None` → pas de crash,
     warning.
3. `test_parsing.py` — cibler `_parse_date_from_titre()` :
   - Au moins 6 titres réels de rapports BRVM en français (formats variés :
     "Rapport annuel 2024", "États financiers au 31 décembre 2024",
     "T1 2025", etc.) → date attendue.
   - Titre sans date → retour `None` sans exception.
4. Workflow : créer `.github/workflows/tests.yml` déclenché sur `push` et
   `pull_request`, Python 3.11, `pip install -r requirements.txt`,
   `pytest -v`.

**Critères d'acceptation :**
1. `pytest -v` local : 100% pass, ≥ 12 tests.
2. Le workflow tests passe au vert sur la branche.
3. Test de non-régression volontaire : casser une assertion, vérifier que
   le workflow échoue, réparer.

**Découpage obligatoire en 2 sessions distinctes :**
- **T2a — extraction** : si les fonctions actuelles lisent Supabase
  directement, les refactorer *a minima* pour accepter les données en
  paramètre (injection), sans changer la logique. Le diff complet est
  montré à Jocelyn et validé AVANT commit. Aucun test dans ce commit,
  aucune autre modification des scripts de prod.
- **T2b — tests** : écriture des tests uniquement, zéro modification
  des scripts de prod. Ajouter aussi `tests/test_health.py` : logique
  week-end / jour férié de T1 avec dates mockées (un samedi, un férié,
  un jour ouvré vide).

---

# PHASE 3 — P1 : Vérification NTLC (split vs erreur de scraping)

## T3 — Investigation scriptée + décision par arbre

**Contexte :** correction shares_outstanding 1.1M → 22.07M (facteur ~20x).
Si c'est un split/division du nominal, les prix historiques pré-split dans
`historical_data` sont peut-être non ajustés → graphiques et backtests NTLC
faux.

**Fichier à créer :** `investigate_ntlc.py` (script jetable, dossier `tools/`).

**Spécification :**
1. Récupérer via REST tout l'historique NTLC :
   `v_historical_prices?ticker=eq.NTLC&order=trade_date.asc`
   (paginer par 1000 avec `Range`).
2. Calculer les variations journalières. Lister toute journée avec
   `|variation| > 40%`.
3. Afficher : prix min/max par année, et les 10 plus fortes variations
   avec leurs dates.
4. Récupérer `corporate_events?ticker=eq.NTLC` et afficher tous les
   événements.
5. Format de sortie IMPOSÉ : fichier `tools/ntlc_report.csv` avec colonnes
   exactes `trade_date,price,variation_pct` (tout l'historique), puis en
   fin d'exécution un bloc texte en 3 sections : TOP 10 variations
   (date, %), min/max par année, liste brute des corporate_events.
   Aucune phrase d'interprétation dans la sortie — les données seules.

**Arbre de décision (à appliquer par Jocelyn, pas par le modèle) :**
- **Aucune discontinuité ~÷20 dans les prix** → l'ancien 1.1M était une
  erreur de scraping pure. Aucune action sur les prix. Fermer le sujet
  par une note dans DECISIONS.md (ADR-0xx : "NTLC — pas de split,
  erreur de saisie source").
- **Discontinuité ~÷20 trouvée à une date D** → split réel. Action :
  ajustement des prix pré-D **via SQL Editor uniquement** :
  ```sql
  -- APRÈS backup vérifié. Remplacer <COMPANY_ID> et <DATE_D>.
  UPDATE historical_data
  SET price = price / 20.064
  WHERE company_id = <COMPANY_ID> AND trade_date < '<DATE_D>';
  ```
  (facteur exact = 22 070 400 / 1 100 000 = 20.064). Vérifier ensuite la
  continuité du graphique NTLC sur le frontend, et noter l'ADR.

**Critères d'acceptation :** le script tourne, la sortie est collée dans
`REMEDIATION_LOG.md`, la branche de l'arbre est tranchée et documentée.

---

# PHASE 4 — P1 : Refonte EPS (recompute au lieu de scrape)

## T4 — `scrape_all_v4.py` : EPS calculé, scrapé en cross-check

**Prérequis : T2 terminée (les tests protègent la refonte).**

**Contexte :** ADR-018 a mis une détection. La correction structurelle :
l'EPS stocké devient `net_income / shares_outstanding` ; l'EPS scrapé
(stockanalysis.com) ne sert plus que de vérification.

**Spécification :**
1. Dans `scrape_all_v4.py`, localiser l'écriture de l'EPS vers
   `company_fundamentals`.
2. Nouvelle logique, dans cet ordre strict :
   - Si `net_income` ET `shares_outstanding` disponibles et > 0 :
     `eps_final = net_income / shares_outstanding` (arrondi 2 décimales).
   - Sinon : `eps_final = eps_scrape` (fallback) + log
     `WARNING EPS_FALLBACK <ticker> <fiscal_year>`.
   - Si les deux existent et divergent de > 10% : log
     `WARNING EPS_DIVERGENCE <ticker> <fiscal_year> calc=<x> scrape=<y>`.
     On stocke le calculé.
3. Ne PAS toucher aux données historiques déjà en base dans cette tâche
   (le prochain run les mettra à jour naturellement).
4. Ajouter 3 tests dans `tests/test_eps.py` couvrant les 3 branches.

**Critères d'acceptation :**
1. `pytest -v` : tout passe, y compris les 3 nouveaux tests.
2. Dry-run local sur 3 tickers (NTLC, BICC, SOGC) : la valeur calculée
   correspond aux valeurs corrigées connues (NTLC FY2024 = 822.37).
3. Après le premier run planifié : zéro `EPS_DIVERGENCE` inattendue sur
   les 3 tickers historiquement affectés.

**Piège :** unités. Vérifier que `net_income` est en FCFA (pas en millions)
avant de diviser — contrôler sur SONATEL dont l'EPS est connu publiquement.

---

# PHASE 5 — P1 : Backtest net de frais + calibration liquidité

## T5a — Paramètres de coûts réels

**Action Jocelyn (pas le modèle) :** remplir dans un nouveau fichier
`config/costs.py` les valeurs exactes depuis la documentation BOA Capital
Direct :
```python
FRAIS_COURTAGE_PCT = 0.0    # à remplir — % par ordre, aller ET retour
FRAIS_FIXE_FCFA = 0         # à remplir — minimum par ordre s'il existe
IRVM_PCT = 0.0              # à remplir — taux retenu à la source sur dividendes
```
Ne PAS laisser le modèle deviner ces valeurs.

## T5b — Script `backtest_net.py`

**Contexte :** les performances V2 (+7.8% médian J+90) et dividend capture
sont brutes. L'illiquidité BRVM + frais + IRVM peuvent manger une part
importante de l'alpha.

**Spécification :**
1. Nouveau script `backtest_net.py` qui rejoue les 25 signaux V2 du backtest
   existant (réutiliser la même source de signaux que le backtest V2 actuel —
   identifier le script source et le citer en commentaire).
2. Pour chaque signal, calculer le rendement **net** :
   `rendement_net = rendement_brut - 2×FRAIS_COURTAGE_PCT - (dividende_encaissé × IRVM_PCT / prix_achat)`.
3. Pénalité de non-exécution : paramètre `FILL_RATE` (défaut 0.75 —
   pas arbitraire : c'est le taux de fill historique validé de la
   stratégie dividend capture).
   Rendement espéré ajusté = `rendement_net × FILL_RATE + 0 × (1-FILL_RATE)`
   (le capital non exécuté est supposé à rendement nul sur la période).
   Sensibilité OBLIGATOIRE : produire le tableau final pour
   `FILL_RATE ∈ {0.60, 0.75, 0.90}`.
4. Sortie : tableau comparatif brut vs net vs net×fill (médiane, moyenne,
   % positifs, pire cas) écrit dans `REMEDIATION_LOG.md`.
5. Calibration `seuil_liquidite` : pour chaque ticker de la watchlist,
   calculer `volume_20j` médian sur 12 mois (via `v_historical_prices`).
   Proposer `seuil = médiane des volume_20j des 6 tickers dividend-capture
   validés (BOAB, BOAC, ECOC, SMBC, NSBC, NTLC) × 0.5`. C'est une proposition
   chiffrée à valider par Jocelyn, pas à écrire dans le pipeline.

**Critères d'acceptation :** tableau brut/net produit ; valeur de seuil
proposée avec les données qui la justifient ; aucune modification du
pipeline de prod dans cette tâche.

---

# PHASE 6 — P1 : Stress-test statistique V2

## T6 — Scripts d'analyse à interprétation pré-définie

**Contexte :** n=25 (backtest) et "100% win rate" (signaux évaluables récents)
sont trop petits pour être fiables. Le modèle exécutant fait tourner les
scripts ; l'interprétation suit des règles écrites ici, pas son jugement.

**Fichier :** `tools/stress_test_v2.py`. Dépendances : numpy, pandas
(déjà présents), pas de scipy si absent — bootstrap à la main.

**Spécification :**
1. **Bootstrap (10 000 tirages)** sur les rendements J+90 des 25 signaux :
   IC 95% de la médiane et de la moyenne.
   *Règle d'interprétation :* si la borne basse de l'IC95 de la médiane < 0
   → inscrire dans REMEDIATION_LOG : "V2 non prouvé statistiquement —
   plafonner la taille de position par signal à un montant défini par
   Jocelyn jusqu'à n ≥ 60 signaux vérifiés."
2. **Walk-forward** : découper les 25 signaux en 3 tiers chronologiques,
   stats par tiers.
   *Règle :* si un tiers a une médiane < 0 → noter "instabilité temporelle,
   revalider trimestriellement."
3. **Sensibilité aux seuils** : grille ROE ∈ {12, 15, 18}%,
   P/B ∈ {2.0, 2.5, 3.0}, en rejouant la sélection des signaux.
   *Règle :* si le nombre de signaux ou la médiane varie de > 50% entre
   cases adjacentes de la grille → noter "seuils probablement surajustés
   (overfitting), ne pas resserrer davantage les critères."
4. **Biais de survivance** : compter combien des 10 tickers exclus l'ont été
   après avoir généré des signaux perdants dans le backtest. Rapporter le
   chiffre brut, sans conclusion (interprétation par Jocelyn).

**Critères d'acceptation :** les 4 sorties dans REMEDIATION_LOG.md, chaque
règle d'interprétation appliquée textuellement.

---

# PHASE 7 — P2 : Constantes figées → paramètres

## T7 — Centralisation `config/params.py`

**Spécification :**
1. Créer `config/params.py` :
   ```python
   TAUX_ACTUALISATION = 0.08   # ADR-009 — à revoir si taux BCEAO bouge
   POIDS_PER = 0.70            # mix cours cible
   POIDS_DIVIDENDE = 0.30
   ```
2. Inventaire préalable : `grep -rn "0\.08\|0\.70\|0\.30" --include="*.py" .`
   — coller TOUTES les occurrences dans REMEDIATION_LOG.md. Dans cette
   tâche, ne modifier QUE `calculate_target_price.py` ; toute autre
   occurrence pertinente devient un item BACKLOG, pas une modification.
3. Dans `calculate_target_price.py`, remplacer les littéraux par ces imports.
   Aucun autre changement.
3. Test de non-régression : avant/après, les `cours_cible` produits pour
   5 tickers témoins (SONATEL + 4 autres) doivent être identiques au
   centime. Script de comparaison jetable dans `tools/`.
4. Rafraîchissement PER sectoriels : exécuter `update_sector_per.py`
   manuellement, comparer les nouvelles valeurs aux valeurs du skill
   (Banque 12.4x, Agro 10.2x, Industrie 13.2x, Telecom 13.3x,
   Distribution 16.1x). Si écart > 15% sur un secteur → le noter,
   ne rien changer d'autre (le pipeline les met à jour lui-même).

**Critères d'acceptation :** cours_cible identiques avant/après ;
écarts PER documentés.

---

# PHASE 8 — P2 : Consolidation providers AI

## T8 — Audit factuel d'abord, décision ensuite

**Tâche modèle (audit uniquement, zéro modification) :**
1. Lister où DeepSeek, Gemini et Mistral sont appelés (grep dans le repo),
   ce que chacun produit, et où chaque sortie est consommée
   (table Supabase, frontend).
2. Sortie IMPOSÉE : `docs/audit_ai_providers.csv` avec colonnes exactes :
   `provider,script,fonction,ligne,modele,max_tokens,frequence_appels,
   table_supabase_cible,consommateur_frontend,cout_estime_mensuel`.
   Le modèle remplit tout sauf `cout_estime_mensuel` : il fournit
   nb d'appels/mois × tokens estimés par appel, Jocelyn applique les
   tarifs des providers.

**Décision Jocelyn ensuite.** Si consolidation décidée : la migration fera
l'objet d'un mini-plan séparé — ne pas la déléguer telle quelle à un modèle
moins avancé.

---

# PHASE 9 — P3 : App.jsx — NE PAS déléguer

Le découpage du monolithe (~3500 lignes) exige de tenir tout le graphe de
dépendances en tête. **Risque trop élevé pour un modèle moins avancé**,
même en procédure mécanique : une extraction ratée casse le build Vercel.

À faire avec un modèle avancé, composant par composant, plus tard.
Seule exception délégable : extraire des **constantes pures** (thème,
labels) vers `src/constants.js` — zéro logique, zéro hook.

---

# PHASE 10 — P3 : B2B / RLS — différé

Ne rien faire tant que l'ambition B2B n'est pas active. Le jour venu :
auth Supabase + RLS par utilisateur + table d'audit — plan séparé.

---

# PHASE 11 — V2 : mesurer avant de modifier

**Doctrine :** aucun changement du modèle en production avant les résultats
de T6 (stress-test) et T9 (falsification). Séquence imposée :
mesurer (T9, T14) → protéger (T10) → améliorer seulement ensuite (Phase 13).

## T9 — Test de falsification : V2 vs benchmarks réels

**Contexte :** le vrai benchmark de V2 n'est pas le BRVMC. C'est (A) la
stratégie dividende naïve déjà validée, et (B) les recommandations BOA
déjà présentes en base. Si V2 ne bat ni l'une ni l'autre, la machinerie
de valorisation n'ajoute rien.

**Fichier :** `tools/falsification_v2.py` — aucune modification du
pipeline de prod.

**Spécification :**
1. **Volet A — stratégie naïve.** Reconstituer les trades de la règle
   validée : tickers {BOAB, BOAC, ECOC, SMBC, NSBC, NTLC}, yield ≥ 8%
   au moment de l'achat, achat J-19 avant ex-date (`corporate_events`,
   FY2022-FY2025), sortie J+90, rendement = variation de prix + dividende.
2. **Volet B — recos BOA.** Table `boa_recommendations` : pour chaque
   `action = BUY`, rendement J+90 depuis la date de la reco (prix via
   `v_historical_prices`). N'évaluer que les recos dont la fenêtre J+90
   est entièrement écoulée ; reporter le n retenu.
3. **Volet C — V2.** Les 25 signaux du backtest, même horizon J+90
   (réutiliser la source de signaux existante, la citer en commentaire).
4. Tableau comparatif A / B / C : n, médiane, moyenne, % positifs,
   pire cas → REMEDIATION_LOG.md.

**Règles d'interprétation (textuelles — aucun jugement du modèle) :**
- Médiane C ≤ médiane A ET % positifs C ≤ A → inscrire : "V2 non
  différencié de la stratégie naïve — GELER la Phase 13, envisager la
  simplification du pipeline."
- Médiane C > médiane A + 2 points ET médiane C > médiane B →
  "edge valorisation confirmé — Phase 13 débloquée."
- Tout cas intermédiaire → escalade vers le modèle avancé, aucune
  conclusion écrite.

**Critères d'acceptation :** tableau produit, règle appliquée
textuellement, sortie collée dans REMEDIATION_LOG.md.

## T14 — Diagnostic concentration sectorielle (15 min, SQL Editor)

**Contexte :** hypothèse à vérifier — V2 serait en réalité un
"long banques UEMOA avec timing dividende".

**Action :** dans SQL Editor, compter la répartition par secteur
(7 catégories BRVM, mapping utilisé par `update_sector_per.py`) de :
(a) les 25 signaux du backtest, (b) les signaux ACHAT actuels de
`target_prices`.

**Règle :** si un secteur > 60% des signaux → noter dans DECISIONS.md :
"V2 = exposition sectorielle concentrée ; plafond d'exposition par
secteur à fixer par Jocelyn (proposition de départ : 50% du capital
alloué à V2)."

---

# PHASE 12 — V2 : protections (avant d'accumuler des positions réelles)

## T10 — Règle de sortie + kill-switch ex-ante

**Contexte :** V2 sait acheter, pas vendre, et aucun seuil de suspension
n'existe. Les deux doivent être figés AVANT les premières positions
réelles — pas après les premières pertes.

**Volet A — Règle de sortie (décision Jocelyn ; propositions à valider,
jamais laissées au choix du modèle) :**
- Sortie cible : cours ≥ 95% du `cours_cible` du jour.
- Sortie temps : J+90 (aligné sur l'horizon backtesté).
- Sortie fondamentale : le ticker sort des critères (ROE, collapse EPS)
  au refresh suivant → sortie au prochain point de liquidité.
- Pas de stop-loss prix serré : sur la BRVM, l'exécution d'un stop est
  illusoire (illiquidité). La protection vient du sizing (T11) et du
  kill-switch — pas du stop.
→ Valeurs choisies figées dans DECISIONS.md (nouvel ADR).

**Volet B — Kill-switch (délégable) :** script `tools/killswitch_check.py` :
1. Lit `brvm_decisions_results` (vérifications J+20, actives depuis 07/2026).
2. Constantes en tête de script : `N_MIN = 15`, `SEUIL_POSITIFS = 0.50`,
   `SEUIL_MEDIANE = 0.0` — valeurs par défaut, Jocelyn les confirme
   dans l'ADR du volet A.
3. Si `n ≥ N_MIN` ET (`% positifs < SEUIL_POSITIFS` OU
   `médiane < SEUIL_MEDIANE`) → afficher "KILL-SWITCH DÉCLENCHÉ —
   suspendre les achats V2" et `sys.exit(1)`. Sinon afficher le statut
   courant (n, % positifs, médiane) et exit 0.
4. Exécution : step hebdomadaire GitHub Actions (lundi, `if: always()`) —
   l'échec déclenche l'email. Exécutable aussi manuellement.

**Critères d'acceptation :** ADR commité AVANT toute nouvelle position ;
script testé sur données factices (un cas déclenché, un cas sain).

---

# PHASE 13 — V2 : évolutions du modèle — GATE OBLIGATOIRE

**Gate : n'exécuter cette phase QUE si T9 conclut "edge confirmé" ET si
T6 n'a pas déclenché l'alerte overfitting. Sinon : geler et simplifier.**

## T11 — Sizing continu (décote × liquidité)

**Contexte :** une décote de 30% et une de 8% reçoivent aujourd'hui la
même mise. Le sizing concentre le capital sur la meilleure espérance et
plafonne l'illiquide.

**Spécification :**
1. Dans `calculate_target_price.py` (diff revu par Jocelyn avant commit) :
   `facteur_liquidite = min(1, volume_20j / seuil_liquidite)` ;
   `score_position = min(decote_pct, 40) / 40 × facteur_liquidite`.
2. Mapping en 3 paliers de mise (proposition, Jocelyn valide) :
   score ≥ 0.6 → mise pleine · 0.3-0.6 → 2/3 · < 0.3 → 1/3.
3. Colonne `score_position` ajoutée à `target_prices` via SQL Editor.
   Information affichée uniquement — AUCUNE automatisation d'ordres.

**Critère :** le signal ACHAT reste strictement identique avant/après
(snapshot d'un run complet) — seul le score s'ajoute.

## T12 — Découplage signal_valeur / signal_timing

**Spécification :**
1. SQL Editor : ajouter à `target_prices` deux colonnes booléennes —
   `signal_valeur` (conditions de valorisation seules : décote, ROE,
   P/B, cap, liquidité) et `signal_timing` (fenêtre J-10 ex-div seule).
2. `signal_v2` devient dérivé : `signal_valeur AND signal_timing`.
   Comportement strictement identique — zéro changement de signal.
3. Bénéfice : attribution de la performance à chaque jambe, et jambe
   valeur observable toute l'année en paper trading avant toute décision
   de l'activer seule.

**Critère :** `signal_v2` identique avant/après sur un run complet
(comparaison snapshot des 47 tickers).

## T13 — Cours cible : pondérations et cycle (tests offline UNIQUEMENT)

**Fichier :** `tools/test_target_variants.py` — AUCUNE modification du
pipeline dans cette tâche.

**Spécification :** recalculer les cours cibles des 25 signaux backtest
selon 3 variantes, rejouer les rendements J+90 pour chacune :
1. EPS pondéré 50/30/20 (récent d'abord) vs moyenne égale actuelle —
   défense contre les value traps (résultat en dégradation qui gonfle
   la cible pendant 3 ans).
2. Mix cible : grille {80/20, 70/30, 60/40} (PER/dividende) — le 70/30
   n'a jamais été testé en sensibilité.
3. Garde-fou procyclique : cible avec PER sectoriel courant vs PER
   sectoriel médian 3 ans (via `sector_per_history`) — mesurer l'écart
   après le rally +18%, sans décision dans cette tâche.

Sortie : tableau médiane / % positifs par variante → REMEDIATION_LOG.md.

**Règle de promotion :** une variante ne passe en prod (tâche séparée +
ADR) que si elle améliore À LA FOIS la médiane ET le % positifs vs la
baseline actuelle.

---

## Ordre d'exécution recommandé

| Semaine | Tâches | Charge estimée |
|---|---|---|
| Sem. 1 (cette semaine) | T0 → T1 → T2a → T2b · T14 (15 min) | 4 sessions courtes |
| Weekend | T6 + T9 (avec la régression dividend capture prévue) | 1-2 sessions |
| Sem. 2 | T10 (seuils : toi) → T3 → T4 | 3 sessions |
| Sem. 3 | T5a (toi) → T5b → T7 | 2 sessions |
| Sem. 4 | T8 · puis GATE Phase 13 : si T6 + T9 favorables → T12 → T13 → T11 | 1 + 3 sessions |

**Dépendances dures :** T0 avant tout. T2a/T2b avant T4. T5a avant T5b.
T6 ET T9 avant toute la Phase 13 (gate). T10 avant d'accumuler des
positions V2 réelles — c'est la seule tâche dont la date limite est
dictée par ton portefeuille, pas par le plan.

## Fin de chaque tâche (règle opérationnelle existante)

Mettre à jour SKILL.md / CHANGELOG.md / BACKLOG.md / DECISIONS.md si
pertinent, commit unique `docs: ...`, et reporter le statut de la tâche
dans REMEDIATION_LOG.md (✅ / ❌ + critères).
