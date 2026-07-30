# Backlog BRVM Analytics

> **Note (25/06/2026) :** Ce fichier a été accidentellement écrasé par une
> page d'erreur Cloudflare (commit `78ff24a`, 04/06/2026) et restauré depuis
> l'historique Git (commit `dd25f47`) le 25/06/2026. Les items des sessions
> du 21/06 et du 23/06/2026 — documentés séparément dans
> `BACKLOG_nouveaux_items_21-06-2026.md` et
> `BACKLOG_nouveaux_items_23-06-2026.md` faute de pouvoir lire ce fichier à
> l'époque — sont réintégrés ci-dessous. Si ce fichier est de nouveau
> illisible un jour, vérifier `git log --follow -p -- BACKLOG.md` avant de le
> considérer comme perdu.

---

## 🟢 COMPLÉTÉS — 2026-06-25

### ✅ ADR-017 — Doublon Fair Value FinancialAnalysis.jsx corrigé
`FinancialAnalysis.jsx` lit désormais `target_prices` au lieu de recalculer
en JS (P/E 10x fixe). Courbe historique réelle (forward-fill), texte de
méthode dynamique (`per_ref`/`per_source`). Commit `c7294f6`.

### ✅ ADR-018 (partiel) — Détection eps non recalculé ajoutée
`check_eps_coherence()` dans `scrape_all_v4.py` — log un warning si `eps`
scrapé diverge de `net_income×1M/shares_outstanding` (>10%), sans jamais
corriger automatiquement. Commit `654bfd2`. **Correction des données
elle-même NON faite — voir item actif ci-dessous.**

---

## 🟢 COMPLÉTÉS — 2026-06-28

### ✅ ADR-019 — Analyse fondamentale débloquée (contrainte SQL + titre)
Contrainte parasite `unique_company_fundamental` (`UNIQUE(company_id)`)
supprimée — elle bloquait tout 2e rapport par société (SONATEL figé sur
Q3 2025 malgré T1 2026 publié). Extraction du titre corrigée (`<strong>` au
lieu du lien "Télécharger"), `_parse_date_from_titre()` ajoutée. Commit
`d2c0a13` + SQL en base.

### ✅ ADR-020 — Prompts Mistral sans valorisation chiffrée
P/E 10x retiré des 3 prompts ; le cours cible vient exclusivement du modèle V2.
Commit `0a8deab`.

### ✅ ADR-021 — Sobriété quota Mistral
Mode UPSERT retiré (plus de régénération quotidienne de tout l'historique) +
étapes 5 et 6 en bi-hebdomadaire (1er et 15). Commits `0a8deab` + `29dfde2`.

---

## 🔴 BACKLOG ACTIF — PRIORITÉ HAUTE

### ADR-018 — Corriger eps NTLC/BICC/SOGC en base (après logs du 29/06)
- **Contexte :** `eps` scrapé tel quel depuis stockanalysis.com par
  `scrape_all_v4.py`, jamais recalculé depuis `net_income/shares_outstanding`.
  Confirmés incohérents au 25/06/2026 : NTLC (~20x, 3 années), BICC (~1.5x,
  4 années), SOGC (~0.73x, FY2021-2022 seulement — FY2023+ sains).
  **Lien avec DATA-19 (ci-dessous, déjà complété le 04/06/2026) :** un
  recalcul `eps = net_income×1M/shares_outstanding` avait déjà été fait une
  fois sur 20/47 tickers (`fill_eps_corrected.sql`) — probablement écrasé
  depuis par un run `scrape_all_v4.py --full` (chaque lundi), ce qui
  expliquerait pourquoi le problème est revenu sans qu'aucune session n'ait
  introduit de nouveau bug entre-temps.
- **Action :**
  1. Attendre les logs du run du lundi 29/06/2026 (`check_eps_coherence`,
     commit `654bfd2`) pour avoir la liste complète des tickers incohérents
     sur les 47, pas seulement les 3 déjà confirmés manuellement.
  2. Corriger `eps` en base par requête SQL ciblée pour chaque ticker confirmé
     (cf. ADR-026 — SQL Editor Supabase, jamais PATCH REST ligne par ligne).
  3. **Vérifier après coup que la correction persiste après le run suivant**
     du lundi d'après (06/07/2026) — c'est l'étape qui avait été oubliée pour
     ADR-012, et qui a permis au bug de revenir silencieusement pendant
     3 semaines sans être détecté.
  4. Si le problème touche un grand nombre de tickers (pas seulement 3),
     reconsidérer l'option rejetée en ADR-018 : recalcul automatique
     systématique de `eps` dans `scrape_all_v4.py` plutôt qu'un simple log.
- **Source :** Conversation du 25/06/2026, ADR-017/ADR-018.

### MODEL-01 — Modèle pragmatique BRVM (prochaine session)
- **Priorité:** Haute — à construire avant bascule 01/07/2026
- **Description:** Signal combiné : BOA_action + BOA_potential + ROE_relatif + momentum_MA20
- **Logique:**
  ```python
  signal_achat = (
      boa_action in ["BUY", "HOLD"]     # BOA pas négatif
      AND boa_potential > 5              # upside BOA > 5%
      AND roe > roe_median_secteur       # qualité relative
      AND prix > ma20                    # momentum positif
  )
  ```
- **Avantage vs V3 :** Utilise ce qu'on a réellement · backtestable · transparent · indépendant de BOA
- **Dépendance :** ROE sectoriel médian (calculable depuis company_fundamentals)
- **⚠️ À recroiser avec le modèle V2 (cours cible PER+Gordon, ADR-009/010/011)
  qui a depuis été construit et calibré entre le 20 et le 23/06/2026 — vérifier
  si ce MODEL-01 est encore pertinent en parallèle du V2 ou s'il est superseded.**

### V2-01 — Cours cible via rendement cible sectoriel
- **Priorité:** Haute — post-dégel
- **Description:** cours_cible = dividend_per_share / rendement_cible_sectoriel
- **Source rendement:** boa_recommendations.rendement (en %, diviser par 100)
- **Note:** rendement BOA confirmé colonne `rendement` dans `boa_recommendations`
- **⚠️ Possiblement déjà couvert par le modèle V2 actuel (composante Gordon
  30%, `calculate_target_price.py`, ADR-009) — à vérifier si distinct ou
  redondant avant de retravailler.**

### V2-03 — Filtre liquidité binaire dans generate_decisions.py
- **Priorité:** Haute — post-dégel
- **Description:** Bloquer tout signal ACHAT si volume_20j < seuil
- **Calibration:** ratio volume/shares_outstanding · seuils : >0.1%=liquide · 0.01-0.1%=peu liquide · <0.01%=illiquide
- **Note:** Ne pas modifier avant 01/07/2026 (ADR-001)

### V2-04 — Intégrer signaux V2 complets dans l'interface
- **Priorité:** Haute — post-dégel
- **Description:** Afficher signal J-10, cours_cible, décote dans Opportunités et fiche ticker
- **Note:** badge Fair Value V2 sur DecisionCards ✅, page "AI Fundamental
  Analysis" (`FinancialAnalysis.jsx`) ✅ corrigée le 25/06 (ADR-017)
- **Reste:** onglet Opportunités à vérifier/compléter avec les colonnes V2

### DATA-17 — Calibrer seuil volume_20j pour filtre liquidité V2
- **Priorité:** Haute — juillet 2026
- **Action:** Analyser distribution volume_20j par liquidity_tier après dégel

### Forward test V2 — Checkpoint juillet 2026
- **Priorité:** Haute
- **Description:** Valider signal SPHC FY2025 + positions BOAB/BOAC/BOABF/SNTS/NTLC
- **Échéance:** Juillet 2026
- **⚠️ NTLC est exclu du calcul V2 depuis ADR-011 — vérifier que ce checkpoint
  est toujours pertinent tel que formulé, ou l'ajuster en conséquence.**

### Mise à jour mensuelle des PER sectoriels (rituel — déjà en cours)
- **Contexte :** `sector_per_history` alimentée manuellement chaque mois via
  `update_sector_per.py`, depuis le P/E 2024 du Tableau de Bord BOA Capital
  Securities (Lettre quotidienne, page 2).
- **Action :** Rituel mensuel à tenir — sans mise à jour, fallback sur valeurs
  figées (datées du 18/06/2026), avec warning visible mais sans blocage.
- **Source :** ADR-010, conversation du 20-21/06/2026.

---

## 🟠 BACKLOG ACTIF — PRIORITÉ MOYENNE

### Logging fort des échecs de sauvegarde après appel API réussi (issu d'ADR-019)
- **Contexte :** Le bug ADR-019 (SONATEL figé sur Q3 2025) a duré ~3 semaines
  car l'échec SQL `duplicate key` était noyé en ligne `ERROR` parmi des
  centaines, sans rien faire remonter. L'appel Mistral réussissait (donc était
  facturé) puis la sauvegarde échouait silencieusement.
- **Action :** Dans `_save_to_db()` (et équivalents), faire remonter un échec de
  sauvegarde survenant APRÈS un appel API réussi comme un signal visible
  (compteur d'échecs en fin de run, ou résumé dédié), pas une simple ligne ERROR.
  Un appel IA payant qui ne produit aucune ligne en base est une anomalie à
  surveiller activement.
- **Source :** Session du 28/06/2026, ADR-019.

### Dédupliquer les 3 prompts IA dans fundamental_analyzer.py (issu d'ADR-020)
- **Contexte :** Le même prompt géant est copié-collé 3 fois (DeepSeek, Gemini,
  Mistral). Tout changement de méthode doit être fait à 3 endroits — exactement
  le type de divergence qui a causé ADR-017 (et le P/E 10x oublié dans les
  prompts, corrigé en ADR-020). Risque de re-divergence à chaque évolution.
- **Action :** Extraire le prompt commun dans une seule constante/méthode
  paramétrée, que les 3 fonctions `_analyze_with_*` réutilisent.
- **Source :** Session du 28/06/2026, ADR-020.

### Vérifier le bug d'extraction de date dans d'autres scripts (issu d'ADR-019)
- **Contexte :** Le bug "titre lu depuis le lien au lieu du `<strong>`" + date
  retombant au 31/12 était dans `fundamental_analyzer.py`. D'autres scripts qui
  scrapent brvm.org (ex. `scrape_corporate_events.py`, `scrape_boc_pdf.py`)
  pourraient avoir un schéma d'extraction de date similaire à vérifier.
- **Action :** Auditer les autres scrapers pour un bug analogue d'extraction de
  date/titre depuis le HTML brvm.org.
- **Source :** Session du 28/06/2026, ADR-019.

### Intégration du pattern pré/post ex-dividende dans le signal V2
- **Contexte :** Intuition de Jocelyn (20/06/2026) — distincte de la stratégie
  de capture de dividende déjà validée (achat J-19, fill rate ≥75%).
  Intégrer la hausse anticipative pré-ex-div et la baisse mécanique post-ex-div
  directement comme composante du signal V2, plutôt que comme stratégie de
  timing séparée.
- **Action :**
  - Attendre les résultats de la régression 10 ans (weekend du 20-21/06) sur
    le point d'achat optimal post-ex-div.
  - Quantifier le pattern avant intégration — actuellement une intuition.
  - Ne pas traiter avant le 01/07/2026.
- **Source :** Conversation du 20-21/06/2026.

### Tickers à 1 seule année EPS — risque de représentativité
- **Contexte :** Le filtre ADR-011 accepte sans contrôle les tickers à 1 seule
  année EPS (ORAC, ECOC, SIVC, STBC au 21/06/2026) — risque résiduel assumé
  d'EPS atypique non représentatif.
- **Action (si matérialisé après le 01/07/2026) :** Surveiller les signaux V2
  sur ces tickers lors de la vérification live (dès 07/2026). Si signal
  erroné détecté : capper le poids du signal pour les tickers à 1 an, ou
  vérification manuelle ponctuelle.
- **Source :** Conversation du 21/06/2026 (ADR-011).

### DATA-20 — Compléter ROE/EPS pour 21 tickers manquants
- **Description:** 21/47 tickers sans ROE · 27/47 sans EPS après session 04/06
- **Sources possibles :** rapports annuels BRVM · BOC PDF archivés · saisie manuelle pour tickers clés
- **Tickers prioritaires :** BOAC, CIEC, SMBC, CFAC, ETIT (ROE extrait mais EPS manquant)
- **⚠️ À recouper avec ADR-018 avant de relancer un script de remplissage EPS
  — s'assurer que le nouveau remplissage ne sera pas écrasé par
  `scrape_all_v4.py` comme cela semble être arrivé pour DATA-19.**

### DATA-10 — Corriger prix corrompus SICC et ONTBF
- **SICC:** Prix ~10x trop élevés — source Sikafinance à corriger
- **ONTBF:** Négociation suspendue — données à vérifier
- **Impact:** Fausse le hit rate ACHAT

### PRED-03 — Scorecard GRU auditable dans l'app
- Afficher taux direction correcte par ticker · MAPE réel vs théorique
- Alimenté par predictions_results
- **Note (25/06/2026) :** Un Scorecard GRU live existe déjà dans le dashboard
  (47% direction correcte global, détail par ticker visible) — vérifier si
  cet item est déjà couvert ou s'il reste un écart fonctionnel.

### FUND-08 — Gouvernance/Risk tab — données réelles
- extract_governance.py — re-parser 158 analyses Mistral → company_governance
- Priorité basse jusqu'à réactivation des tabs archivés

### GRU — Réentraînement sur données corrigées
- Relancer sur historical_data post-splits + SNTS corrigé
- Prérequis : vérifier MAPE réel vs théorique post juillet 2026

### PRED-04 — GRU multi-features (prix + RSI + volume)
- Features dynamiques (RSI, volume) à tester post juillet 2026
- Features statiques (Mistral) prouvées nuisibles (ADR-015)

### Automatisation complète du parsing du Tableau de Bord BOA
- **Contexte :** `parse_boa_dashboard.py` écrit et testé (clustering de
  coordonnées, validation stricte 7 secteurs + bornes 1x-50x). Fonctionne sur
  le PDF du 18/06/2026. Non branché — document source arrive par lien email,
  pas par pièce jointe, complexité d'authentification non résolue avant 01/07.
- **Action :**
  - Vérifier si le lien pointe vers un PDF direct ou une visionneuse web.
  - Vérifier si une connexion à un portail BOA Capital est requise.
  - Si résolu : email (Gmail + Apps Script) → Drive → GitHub Actions →
    `parse_boa_dashboard.py --write`, alerte si échec validation.
- **Données source :** `sql_create_sector_per.sql`, `parse_boa_dashboard.py`
  déjà prêts. Saisie manuelle mensuelle via `update_sector_per.py` en attendant.
- **Source :** Conversation du 21/06/2026.

---

## 🟡 BACKLOG ACTIF — PRIORITÉ BASSE

### SCORE-05 — Bonus dividende imminent dans score V2
### SCORE-06 — Bonus AG dans score V2
### FUND-06 — Notations BloomField Investment
### DATA-08 — Calendrier AG depuis brvm.org
### DATA-09 — Commodités tab — données réelles
### DATA-15 — FTSC dividende aberrant (75.73% rdt_net)
### DATA-16 — Enrichir EPS historique FY2019-FY2020
### SIGNAL-02 — Déduplication sectorielle BOA
### GÉOPOLITIQUE-01 — Migrer GEO_MULTIPLIER vers table Supabase
### Ajouter RPC Supabase apply_split
### Documents BRVM manquants (CABC 2017, CIEC 2018, SIVC 2017)

---

## 🟢 COMPLÉTÉS — 2026-06-23

### ✅ ADR-012 — shares_outstanding NTLC corrigé (partiellement)
`shares_outstanding` corrigé en base (1 100 000 → 22 070 400), confirmé
persistant. **⚠️ Correction du 25/06/2026 : `eps` lui-même n'avait PAS été
recalculé/persisté malgré l'affirmation initiale — cf. ADR-018, item actif
ci-dessus.**

### ✅ Mettre à jour ARCHITECTURE.md/SKILL.md — composants frontend réels
Documenté `BOAComparison.jsx`, `Opportunities.jsx`, `FinancialAnalysis.jsx`
comme composants distincts. Complété définitivement le 25/06/2026 avec le
statut à jour d'ADR-017 (corrigé) et ADR-018.

---

## 🟢 COMPLÉTÉS — 2026-06-21

### ✅ ADR-009 — Taux d'actualisation 8% maintenu (documenté, pas modifié)
### ✅ ADR-010 — PER sectoriels migrés vers 7 secteurs officiels BRVM
### ✅ ADR-011 — Filtre data-quality EPS remplace liste d'exclusion statique
### ✅ update_sector_per.py — script de saisie mensuelle créé

---

## 🟢 COMPLÉTÉS — 2026-06-04

### ✅ DATA-18 — Extraction ROE depuis analyses Mistral
Script `extract_roe_eps.py` — lit `analysis_summary` (pas `analysis_text`).
26/47 tickers avec ROE dans company_fundamentals FY2025.

### ✅ DATA-19 — Calcul EPS depuis net_income/shares_outstanding
`fill_eps_corrected.sql` exécuté. EPS = net_income × 1M / shares_outstanding.
20/47 tickers avec EPS. ROE calculé pour tickers manquants via net_income/total_equity.
**⚠️ Voir ADR-018 (25/06/2026) : ce recalcul semble avoir été écrasé depuis
par un run `scrape_all_v4.py --full` — le même type de correction est
nécessaire à nouveau pour NTLC/BICC/SOGC à ce jour.**

### ✅ RESEARCH-01 — Exploration modèle Fair Value V3
Prototype DDM/PE hybride testé. Rejeté (ADR-033). Modèle pragmatique identifié.

---

## 🟢 COMPLÉTÉS — 2026-05-30

### ✅ V2-06 — Retirer Palm Oil et Rubber de scrape_commodities.py
### ✅ DATA-14 — pymupdf dans requirements.txt
### ✅ fix_snts_updates.sql archivé
### ✅ ADR-029 — scrape_market_cap.py mensuel automatisé
### ✅ UI-02 — Supprimer tab BOA vs BRVM
### ✅ DATA-11 — Nettoyer doublons fundamental_analysis
### ✅ DATA-12 — Fondamentaux clés connectés à Supabase
### ✅ V2-07 — EPS moyenne glissante 3 ans
### ✅ V2-05 — Table target_prices + upsert quotidien
### ✅ V2-02 — verify_decisions.py horizon J+20
### ✅ CHART-01 — Ligne Fair Value style Morningstar
### ✅ UI-03 — Badge Fair Value V2 sur DecisionCards
### ✅ STYLE-01 — FERMÉ (react-markdown incompatible)

---

## 🟢 COMPLÉTÉS — sessions précédentes

### ✅ DATA-05/06 — Correction splits historiques (29/05/2026)
### ✅ SNTS historique corrigé (29/05/2026)
### ✅ scrape_market_cap.py (29/05/2026)
### ✅ DATA-10 — SICC/ONTBF données corrompues (05/05/2026)
### ✅ PRED-01 — GRU via Supabase REST (03/05/2026)
### ✅ PRED-02 — Tracking record prédictions (03/05/2026)
### ✅ SCORE-07 — verify_decisions.py Scorecard live (05/05/2026)
### ✅ FUND-07 — Signal fondamental dans brvm_decisions (03/05/2026)
### ✅ UI-01 — Badge signal_combine + data_completeness (03/05/2026)
### ✅ UI-04 — Badge "vs clôture J-1" (16/05/2026)
### ✅ DATA-13 — scrape_boc_pdf.py (26/05/2026)

- [ ] NTLC : investiguer l'écart entre ratio de split officiel (20)
      et ratio shares_outstanding utilisé pour la correction FY
      (20.064 = 22 070 400 / 1 100 000). Écart ~70 400 actions (0.32%).
      Non bloquant, mais shares_outstanding pourrait nécessiter une
      révision séparée si l'écart n'est pas un simple arrondi source.

## [BLOQUANT] Fiabilisation shares_outstanding — découvert en session T4 (11/07/2026)

- **Bug parse_val()** : suffixe `'M'` non géré (seuls `'T'` et `'B'` multiplient) —
  impacte `shares_outstanding` et potentiellement d'autres champs scrapés en overview.
- **shares_outstanding non ajusté du split NTLC 20:1 (2017)** à la source
  (stockanalysis.com) — la valeur correcte (22 070 400) n'existe qu'en base Supabase,
  corrigée manuellement (ADR-012), et sera écrasée au prochain run scraper si
  `scrape_overview()` continue d'écrire `shares_outstanding` sans distinction.
  **Risque actif de régression silencieuse** sur ce champ précis (pas seulement
  sur eps) — à vérifier : le scraper écrit-il `shares_outstanding` en base
  actuellement, ou seulement `eps` ? À auditer avant le prochain `--full` run.
- Probablement même problème pour BICC, SOGC (cf. docstring `check_eps_coherence`,
  divergences ~1.5x et ~0.73x mentionnées).
- **Pistes de correction (non tranchées) :** (a) lire shares_outstanding depuis
  Supabase au lieu de re-scraper pour les tickers connus comme affectés, avec table
  de référence/override (pattern ADR-032) ; (b) corriger le bug `'M'` dans
  `parse_val()` en amont, ce qui résoudrait une partie du problème mais pas le split
  non répercuté à la source.
- **Bloque :** atteinte du critère d'acceptation initial T4 (NTLC FY2024 EPS = 822.37 FCFA).

- [ ] Confirmer taux courtage SGI BOA Capital (1%) via source primaire CREPMF ou avis d'opéré réel (actuellement source Scribd non-primaire) — bloque la précision de T5b
- [ ] SMBC : identifier avis de dividende (statut brut/net + montant), aucune donnée trouvée à ce jour
- [ ] NTLC, NSBC : re-vérifier une fois l'avis exercice 2025 publié par la BRVM (non disponible au 13/07/2026)
- [ ] Vérifier si les montants de dividende déjà stockés dans `corporate_events` (DIVIDEND_HISTORY) reflètent le brut ou le net selon le ticker — risque de double-comptage ou d'omission de l'IRVM dans les calculs de rendement historiques

## [T7] Constantes de scoring non centralisées (hors périmètre T7)

Repérées lors de l'inventaire T7 (grep `0\.08\|0\.70\|0\.30`), non modifiées
car sans rapport avec le modèle cours cible V2 :

- `generate_decisions.py` (lignes 112, 234, 293) : poids scoring technique/fondamental
- `opportunity_scorer.py`, `opportunity_scorer_all.py`, `opportunity_scorer_v2.py` :
  `WEIGHT_FUND = 0.30` (3 versions du même scorer —à consolider, cf. aussi T8)
- `report_generator.py` (lignes 1144, 1147) : `vol_score * 0.30`
- `generate_decisions_backup.py`, `backtest_honest_v2.py`, `backtest_step5.py` :
  scripts backup/backtest, pas de prod active

Action potentielle future : centraliser aussi ces poids dans un fichier config
dédié (ex. `config/scoring_params.py`), si une refonte V1/scoring est engagée.
Priorité basse — aucune de ces valeurs n'est actuellement documentée comme
non-traçable ou problématique (contrairement à TAUX_ACTUALISATION/ADR-009).

## [T7] Doublon de fichiers calculate_target_price_v3

`calculate_target_price_v3.py` et `"calculate_target_price_v3 (1).py"` existent
à la racine, non actifs (absents de `.github/workflows/*.yml`), non importés
ailleurs. Le second n'a aucun historique git (probable doublon de téléchargement
local). Action à décider : supprimer, ou clarifier s'ils doivent remplacer
`calculate_target_price.py` un jour. Non traité dans T7 (hors périmètre).

## [T8] Violation ADR-004 — psycopg2 dans 2 scripts de prod actifs

Découvert lors de l'audit T8 (13/07/2026) : `fundamental_analyzer.py` et
`report_generator.py` utilisent `import psycopg2` avec connexions directes
(`conn.commit()`, `cur.execute(...)`) pour écrire respectivement dans
`fundamental_analysis` et `report_summary`/`report_company_analysis`.

Ceci viole ADR-004 ("Supabase : REST API uniquement... JAMAIS psycopg2"),
un garde-fou non-négociable du plan de remédiation. Contrairement aux
violations déjà connues et corrigées ailleurs dans le projet, celle-ci
n'avait pas été détectée avant T8 — ces deux scripts sont actifs en
production (bi-hebdo, 1er et 15 du mois).

**Décision à prendre par Jocelyn :**
- (a) Migrer les deux scripts vers REST API (upsert via `Prefer: resolution=merge-duplicates`,
  cohérent avec le pattern déjà utilisé dans `update_sector_per.py`) — tâche
  de refactor à spécifier séparément, testée sur les contraintes UNIQUE
  existantes (`report_url` pour fundamental_analysis, `report_date` pour
  report_summary).
- (b) Documenter une exception explicite à ADR-004 pour ces deux scripts
  si une raison technique valable justifie psycopg2 ici (volume d'écritures,
  transactions multi-tables) — mise à jour de DECISIONS.md avec un nouvel ADR.

Priorité à définir par Jocelyn — ce n'est pas un incident actif (les scripts
fonctionnent), mais un écart de conformité aux garde-fous du projet.

## [T8] extract_fundamental_signals.py — script orphelin, appelle Mistral, non intégré au workflow

Appelle Mistral (`mistral-small-latest`) et peuple
`company_fundamentals.signal_fondamental`, colonne lue en aval par
`generate_decisions.py` (donc potentiellement influente sur les décisions
ACHAT/SURVEILLER/EVITER affichées). N'apparaît dans aucun workflow YAML —
absent de tout déclenchement automatique. Dernier commit (`a8145ec`)
suggère une exécution manuelle ponctuelle (45 tickers), pas un job récurrent.

Risque : `signal_fondamental` reste figé sans alerte si le script n'est pas
relancé manuellement — non couvert par `health_check.py`.

Décision à prendre : (a) intégrer au workflow avec une cadence définie,
(b) documenter comme processus manuel volontaire, ou (c) déprécier si
remplacé fonctionnellement par `fundamental_analyzer.py`.

## [BLOQUANT] Frontend affiche la mauvaise analyse fondamentale sur 35/46 tickers (76%)

**Découvert :** 16/07/2026, via inspection visuelle de la page SNTS en prod
(badge "LIVE" affichant un rapport T1 2025 daté d'un an alors qu'un rapport
T1 2026 existe et a été analysé plus tôt).

**Cause racine confirmée** (`src/App.jsx:188`, fonction `fetchFundamentalAnalysis`,
repo `brvm-analytics`) :

```js
`company_id=eq.${companyId}&select=report_title,report_date,analysis_summary,created_at,updated_at&order=updated_at.desc&limit=1`
```

Le tri se fait sur `updated_at` (quand la ligne a été modifiée en base —
donc quand l'IA a *traité* le PDF) et non sur `report_date` (quand le
rapport a été *publié*). La contrainte `UNIQUE(report_url)` avec upsert
(`fundamental_analyzer.py::_save_to_db`) met à jour `analysis_timestamp`
(qui alimente `updated_at`) à chaque nouvelle passe sur un même rapport —
y compris un vieux rapport ré-analysé par erreur ou par un run étendu.
Résultat : un vieux rapport ré-touché récemment "gagne" l'affichage
devant un rapport plus récent jamais retouché depuis son premier passage.

**Mesure d'ampleur** (script one-off, 16/07/2026, comparaison
`sorted by updated_at.desc` vs `sorted by report_date.desc` par ticker) :

- 46 tickers ont au moins une analyse en base
- **35 tickers (76%) affichent actuellement une analyse dont le
  `report_date` n'est PAS le plus récent disponible** pour ce ticker
- Écarts observés : de quelques mois (SEMC, SICC) à **plus de 3 ans**
  (UNLC : affiche un rapport de mars 2022 alors qu'un rapport de
  décembre 2023 existe déjà en base)
- Cas emblématique SNTS : affiche T1 2025 (analysé le 15/07/2026) alors
  que T1 2026 est disponible et analysé depuis le 01/07/2026

**Correction proposée** (à valider par Jocelyn avant exécution — hors
périmètre de cette découverte, nécessite une tâche dédiée) :

```js
`...&order=report_date.desc&limit=1`
```

Remplacer `updated_at.desc` par `report_date.desc` dans la requête
`fetchFundamentalAnalysis` (`src/App.jsx:188`). Changement d'une seule
ligne, mais impact direct sur l'app en production (76% des tickers
affichés changeraient de contenu) — nécessite : (1) vérification que
`report_date` est fiable/non-null pour toutes les lignes concernées,
(2) test sur quelques tickers avant déploiement, (3) probablement un
commit séparé sur le repo `brvm-analytics` (frontend), pas
`brvm-analysis-suite`.

**Priorité : haute** — impacte la crédibilité de l'information affichée
aux utilisateurs sur la majorité des tickers couverts.

- **Aligner `verify_decisions.py` sur la clé de cohorte du backfill** (issu d'ADR-039) : la prod groupe le benchmark par `verification_date` seul, l'historique par `(signal_date, verification_date)`. Sans effet aujourd'hui, mais au prochain jour de rattrapage la prod écrira un benchmark mélangeant deux fenêtres de détention, incohérent avec l'historique. Correctif d'une ligne, mais modification de production → tâche séparée.
