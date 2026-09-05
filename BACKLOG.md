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

**Suite ADR-040 — décalage d'un an sur les montants de dividendes (une tâche par ligne) :**

- **Corriger `tools/explore_dividend_cycle.py`** et régénérer `dividend_cycle_exploration.csv` : pour toute ligne issue de `DIVIDEND_HISTORY` d'exercice FY, le montant correct est celui de FY−1. Coût : 26 cycles non corrigeables (plus ancien de chaque ticker), ~29% de l'échantillon perdu. Alternative à évaluer : re-scraper depuis les avis BRVM officiels, qui sont la source primaire et publient l'IRVM par titre.
- **Corriger la jointure de `tools/falsification_v2.py`** (lignes 133-145) et **rejouer T9 volet A**. Le verdict de gel de la Phase 13 en dépend.
- **Rejouer T5c-A / E2.7-A / E2.7-B / E2.6** sur le CSV corrigé, une fois celui-ci régénéré.
- **Vérifier `tools/explore_dividend_window60.py`** (mêmes appels à `DIVIDEND_HISTORY`, non audité).
- **Tester l'absence d'ajustement du cours à l'ex-date** en contrôlant les volumes — mécanisme candidat du dividend capture, indépendant du bug.
- **Sensibilité frais/IRVM** : reformulée. Les montants en base sont **nets** d'IRVM (vérifié sur SNTS/BOAB/ONTBF/BOAC contre avis de crédit), donc appliquer un IRVM double-taxerait. Reste à modéliser : les frais de courtage à l'achat et à la vente, absents des backtests.

**Suite ADR-041 — `dividend_per_share` mélange brut et net (production) :**

- **Décision de convention** (Jocelyn) : colonne brute source unique / deux colonnes séparées / colonne nette. Rien ne peut être corrigé avant ce choix.
- **`scrape_boc_pdf.py` ligne 111** : `fy = f"FY{trade_date.year}"` étiquette par année de versement au lieu de l'exercice (dividende exercice 2025 versé mai 2026 → écrit FY2026). À corriger indépendamment de la décision de convention.
- **Versionner la correspondance ticker→pays** si l'option « colonne nette » est retenue — nécessaire pour appliquer le bon taux d'IRVM, actuellement établie manuellement et absente du repo.
- **Auditer les 10 scripts écrivant `dividend_per_share`** — 5 non trackés ou obsolètes (`scrape_fundamentals_v2.py`, `scrape_all_v3.py`, `fix_parser.py`, `backtest_dividend.py`, `calculate_target_price_v3.py`), aucun propriétaire unique de la colonne.

**Suite incident du 06/08/2026 (une tâche par ligne) :**

- **Rattraper `boa_recommendations` du 30/04 au 05/08/2026** : les PDF sont tous encore servis par le CDN (vérifié : 200 sur l'ensemble de la plage), et `parse_boa_letter.py` accepte une date en argument. Une boucle sur les jours ouvrés manquants récupère ~3 mois de données. Attention : contrainte NOT NULL sur `action` — les tickers du groupe BOA sans action lisible échoueront comme lors de l'insertion partielle du 03/08 (27/30 lignes).
- **Migrer `VITE_SUPABASE_ANON_KEY` (Vercel) vers `sb_publishable_...`** — toujours une clé legacy datée du 02/04/2026. Le frontend fonctionne encore mais la panne silencieuse est possible à tout moment (ADR-042).
- **Retirer `gotrue==2.5.0` de `requirements.txt`** — renommé `supabase-auth` dans les versions récentes, tiré en double par `supabase==2.30.0`, et contraint `httpx` à 0.27.2 sans raison.
- **Trancher le sort des deux blocs de log DIAG** ajoutés pour le diagnostic : `scrape_boc_pdf.py:get_company_ids()` (`6f9df46`) et `parse_boa_letter.py:download_pdf()` (`d5930bb`). Les conserver donne un corps de réponse exploitable au prochain incident ; les retirer restaure le code d'origine. Décision, pas urgence.
- **Suivre l'expiration des PAT** : `BRVM_5` expire le 17/12/2026, le nouveau jeton à sa propre échéance. Deux jetons ont déjà expiré sans que personne ne le remarque (`BRVM` 14/04, `BRVM_4` 17/07) — l'échec ne se manifeste qu'au premier push sur un fichier de workflow.
- **Couvrir les échecs de workflows planifiés dans `health_check.py`** : les deux incidents ont duré des semaines parce qu'un run planifié rouge n'alerte personne. `gh` CLI n'est pas installé localement (angle mort récurrent déjà tracé).


### Ajouts session 10/08/2026

- **[HAUTE] `scrape_market_cap.py` possiblement en panne** — `company_fundamentals.market_cap.scraped_at`
  = 27/05/2026 alors que le workflow est censé tourner le 1er lundi de chaque mois.
  2,5 mois sans mise à jour. Seul incident de production potentiel de la session,
  indépendant de la refonte. Vérifier les runs GitHub Actions.
- **[HAUTE] Parser BOC versionné** — gérer les ruptures de schéma (8→7 catégories sectorielles,
  rebase 02/01/2025, passage secteur→compartiment). Prérequis à tout backfill. Cf. ADR-046.
- **[HAUTE] Arbitrage V1 seul vs V1+V2 badgés sur la home** — ADR-044 et ADR-045 se
  contredisent sur ce point. À trancher avant codage de la section « Opportunités du jour ».
- **[MOYENNE] Fallbacks `Math.random()` dans App.jsx** — lignes 399 et 1434 génèrent des volumes
  aléatoires en repli. Un fetch en échec produit un top 5 « plus négociés » entièrement fictif,
  indiscernable du réel, sans aucun signal visuel. À neutraliser ou marquer explicitement.
- **[MOYENNE] `historical_data.value` — colonne morte** — 16 973 / 114 122 lignes (14,9 %),
  NULL sur toutes les lignes récentes. Décider : backfill depuis le BOC (colonne « Valeur »
  présente par ticker) ou suppression. Le BOC rend le backfill trivial.
- **[MOYENNE] Remédiation ADR-040 via BOC** — le BOC donne « Dernier dividende payé :
  montant net + date » par ticker. Source candidate pour corriger l'off-by-one de
  `DIVIDEND_HISTORY.fiscal_year` sans dépendre du scraper fautif.
- **[MOYENNE] Arbitrage ADR-041 via BOC** — le BOC publie explicitement le dividende
  en montant net et le « Rdt. Net ». Argument pour trancher la convention brut/net.
- **[MOYENNE] Automatisation `sector_per_history`** — remplacer `update_sector_per.py`
  (manuel/interactif, BOA Tableau de Bord) par extraction BOC. Gain acquis, indépendant
  de l'usage V2 (cf. ADR-047).
- **[BASSE] Liquidité réelle** — le BOC page 11 publie les quantités résiduelles achat/vente
  par ticker, et définit le ratio de liquidité (titres échangés / volume ordres de vente).
  Source potentielle pour valider ou remplacer le seuil 896 proposé en T5b, jamais validé.
- **[BASSE] Inclusion Breadth / Sector Perf / Heatmap dans la home** — arbitrage éditorial
  de densité, plus de blocage technique. Non tranché.
- **[DOC] Renommer ou documenter `v_latest_market_data`** — nom trompeur, contient
  `predicted_price` (prédictions), pas des données marché.
- **[DOC] `monthly_volume_avg`** — moyenne saisonnière par mois calendaire, sémantiquement
  différente de la moyenne glissante 20j du frontend. Ne pas interchanger.
- **[DOC] `company_fundamentals`** — colonne de date = `scraped_at`, pas d'`updated_at`.
- **[DOC] `new_market_indicators` et `new_market_events`** — tables vides, jamais alimentées.
  Décider : cible de l'ingesteur BOC ou suppression.


### Ajouts session 11/08/2026

- **[HAUTE] `report_generator.py` — tri par `id` au lieu de la date** — les 3 requêtes
  (L96, L119, L143) ordonnent par `id DESC` et la variation journalière compare
  `id` / `id - 1`. Incompatible avec tout backfill : dès qu'on insère de l'historique
  après coup, les variations deviennent silencieusement fausses. **À corriger avant
  le backfill BOC**, pas après. Cf. ADR-048.
- **[HAUTE] `data_collector.py` débranché** — le workflow appelle
  `data_collector_simple.py`. Décider : suppression du code mort, ou réécriture de
  `extract_market_indicators()` sur `tools/parse_boc.py`. Cf. ADR-048.
- **[MOYENNE] `health_check.py` ne couvre pas `new_market_indicators`** — table vide
  depuis l'origine sans alerte. Troisième panne silencieuse après `scrape_market_cap.py`
  et `parse_boa_letter.py`. Élargir les seuils de couverture.
- **[MOYENNE] `requirements.txt` ne déclare pas `pdfminer.six`** — dont dépend
  `parse_boa_letter.py`. Le workflow fait `pip install -r requirements.txt` : le script
  ne devrait pas tourner en CI. Piste sérieuse sur son arrêt du 30/04/2026. `pypdf`
  est déclaré mais utilisé nulle part ; `pymupdf` est déclaré et désormais utilisé
  par `tools/parse_boc.py`.
- **[MOYENNE] Migration `report_generator.py` vers les tables `boc_*`** — la double
  alimentation (`new_market_indicators` + `boc_*`) est une mesure transitoire.
- **[BASSE] Parser BOC v2022** — prérequis au backfill pré-refonte. Nécessite aussi
  un référentiel de correspondance sectorielle 8→7 catégories.
- **[CORRECTION] Entrée du 10/08 sur `new_market_indicators` / `new_market_events`** —
  qualifiées de « jamais alimentées, candidates à la suppression ». Inexact : elles
  sont référencées par `data_collector.py` (écriture) et `report_generator.py`
  (lecture). Ne pas supprimer.


### Ajouts session 12/08/2026

- **[CRITIQUE] `dividend_per_share` : convention brut/net à trancher puis homogénéiser** —
  `scrape_boc_pdf.py` écrit du **net** (BOC, colonne « Montant net »), l'autre écrivain
  écrit du brut. La valeur d'une ligne dépend de l'ordre d'exécution. Décider quelle
  convention fait autorité, corriger les deux écrivains, puis recalculer l'existant.
  Impact : E2.6, E2.7-A, E2.7-B, T5c-A, T9 volet A. Cf. ADR-049.
- **[HAUTE] `scrape_boc_pdf.py` : `ex_dividend_date` reçoit une date de paiement** —
  la colonne BOC utilisée est la date de paiement, pas de détachement. Pivot de la
  stratégie de capture de dividende. Cf. ADR-049.
- **[HAUTE] `scrape_boc_pdf.py` : `fiscal_year` off-by-one** — `FY{année du bulletin}`
  au lieu de l'année d'exercice. Même effet qu'ADR-040, sur `company_fundamentals`.
- **[MOYENNE] `scrape_boc_pdf.py` : vérification TLS désactivée** (`ssl.CERT_NONE`).
  Non nécessaire — `tools/parse_boc.py` télécharge les mêmes PDF avec vérification.
- **[MOYENNE] `scrape_boc_pdf.py` : `except:` nu** L26 — masque les échecs structurels
  en « bulletin non trouvé ». Ajouter le traitement 404 = jour non ouvré d'ADR-046.
- **[MOYENNE] `scrape_boc_pdf.py` : upsert sans `on_conflict`.**
- **[MOYENNE] Workflow d'ingestion BOC page 1 non créé** — `tools/ingest_boc.py`
  fonctionne et l'historique est backfillé jusqu'au 11/08/2026, mais rien ne
  l'exécute automatiquement. Étape à ajouter dans `brvm-analysis.yml` (cron 06:00 UTC,
  donc J-1, cohérent avec le reste du pipeline) avec fenêtre de rattrapage de 5 jours
  ouvrés via `--from`/`--to` (l'idempotence rend le rejeu sans coût).
- **[BASSE] `sector_per_history` alimentable depuis `boc_indices`** — 7 secteurs × 142
  dates de PER officiels désormais en base, contre une saisie mensuelle manuelle.
  Indépendant du gel V2 (ADR-047).
- **[BASSE] Fichiers `.yml.backup` et `.yml.bak` dans `.github/workflows/`** — sans effet
  (GitHub n'exécute que `.yml`), mais source de confusion. Nettoyer.
- **[RAPPEL] ADR-044 : ÉTAPES 3e et 4 (GRU) tournent toujours** — leur débranchement
  est conditionné au retrait préalable de l'onglet Prévisions du frontend.


### Ajouts session 12/08/2026 — suite

- **[HAUTE] Aucun mécanisme ne vérifie qu'un ADR atteint le code** — deux écarts
  décision/implémentation constatés sur `calculate_target_price.py` (liste d'exclusion
  statique, ADR-011 ; filtre ROE/P-B, ADR-050), découverts tous deux par hasard.
  Piste : pour tout ADR modifiant un comportement de modèle, exiger la référence du
  commit d'implémentation dans le corps de l'ADR — ADR-029 le fait déjà (« Implémenté :
  commit 7a069ae »), mais ce n'est pas une règle.
- **[MOYENNE] ADR-022 : trancher à la reprise de V2** — appliquer le filtre ROE>15 %
  et P/B<2.5, l'abandonner formellement, ou rejouer T9 avec le filtre et des seuils
  pré-enregistrés. Cf. ADR-050.
- **[MOYENNE] `DECISIONS.md` a perdu 24 ADR le 04/06/2026** — restaurés le 12/08
  (commit `a005dd9`). Cause : commit `0412529` qui réécrivait le fichier au lieu de
  l'enrichir. Les patchs documentaires passent depuis par des scripts idempotents,
  mais rien ne l'impose formellement.
- **[BASSE] Vérifier l'implémentation des 13 autres ADR restaurés** — seul ADR-022
  a été contrôlé. ADR-024 (`fix_splits.py` source de vérité), ADR-025 (backup avant
  correction de masse), ADR-027 (date signal V2 = 30 avril), ADR-028 (pas de plafond
  de décote) n'ont pas été vérifiés contre le code.
- **[BASSE] `SKILL.md` toujours pas à jour** — tableau des ADR arrêté à ADR-021 alors
  que le projet est à ADR-050 ; pièges de colonnes de la session non reportés ;
  contrainte `fundamental_analysis` décrite comme `UNIQUE(company_id)` alors qu'ADR-019
  l'a remplacée par `UNIQUE(report_url)` ; mention « Palm Oil + Rubber retirés » sans
  explication, alors que le caoutchouc est l'exposition la plus pure de SOGB/SAPH.


- **[MOYENNE] Formule V2 de `SKILL.md` : cinq filtres documentés, un seul implémenté** —
  ROE > 15 %, P/B < 2.5, cap 150-500B, volume_20j, J-10 ex-dividende sont absents de
  `calculate_target_price.py`. Seul `evaluer_qualite_eps()` (ADR-011) tourne.
  Avertissement ajouté dans `SKILL.md` le 12/08/2026 ; formule non corrigée, V2 étant
  gelé. À trancher à la reprise de V2 — cf. ADR-050.


### Ajouts session 15/08/2026

- **[HAUTE] `upsert_management()` echoue en 409 sur les 47 tickers** — meme defaut
  que l'upsert `company_fundamentals` corrige le 12/08 : `resolution=merge-duplicates`
  sans parametre `on_conflict`. `company_management` n'est donc plus alimentee.
  Verifier la contrainte unique de la table avant de corriger.
- **[HAUTE] Listes de tickers codees en dur, divergentes de `companies`** — trois
  occurrences constatees cette semaine : `SECTOR_TICKERS` dans App.jsx (39/47),
  `TICKERS` dans `scrape_all_v4.py` (46/47), et les trois mappings sectoriels
  concurrents. Ces listes devraient etre lues depuis `companies` au demarrage,
  ou au minimum validees contre elle avec une alerte en cas d'ecart.
- **[MOYENNE] `company_fundamentals` : 10 tickers sans EPS** — BNBC, ETIT, NEIC,
  SEMC, SICC, STAC, UNLC, UNXC restent sans EPS apres rescraping du 15/08 : la
  donnee n'existe pas chez stockanalysis (societes en perte, sans dividende recent).
  SIVC et BICB ont ete recuperes. Ces titres ne peuvent etre valorises ni par PE
  ni par DDM — l'absence de fair value est le comportement correct.
- **[MOYENNE] Onglet Fair Value de `FinancialAnalysis.jsx` lit V2** — bascule vers
  V3 decidee le 15/08, non implementee. V3 couvre 39 tickers contre 22 pour V2, et
  fournit un intervalle (borne_basse/borne_haute) et la methode de calcul.
  Attention : `decote_pct` n'a pas le meme sens dans les deux tables — en V3
  c'est la decote de prudence appliquee, l'equivalent de la decote V2 est `upside_pct`.


### Ajouts session 15/08/2026 — V1 par secteur

- **[CRITIQUE] Exécuter le backfill alpha (ADR-039 / T16-backfill)** — ouvert depuis
  juillet, il devient bloquant : ADR-051 constate une dégradation de V1 sur trois mois
  (74,6 % → 63,6 % → 53,7 %) sans pouvoir l'imputer au modèle faute de comparateur de
  marché. `alpha` et `benchmark_return` sont NULL avant le 28/07/2026.
  `tools/backfill_alpha.py` existe, n'a jamais été lancé.
- **[HAUTE] Rejouer la série V1_SECTEURS sur l'alpha** — une fois le backfill fait.
  Les trois scripts sont écrits et n'ont qu'à changer de métrique.
- **[HAUTE] V1 : dégradation à surveiller** — la médiane de variation des signaux
  tombe à +0,41 % en juillet quand le Composite fait +5,50 %. Si l'alpha confirme,
  c'est le modèle de production qui est en cause, pas un secteur.
- **[MOYENNE] Industriels : écart persistant** — seul secteur divergent sur les deux
  signaux, à chaque mois. Déficit réparti sur cinq des six titres. Aucune action tant
  que la dégradation générale n'est pas élucidée (cf. ADR-051).
- **[BASSE] `verify_decisions.py` : définition conditionnelle du hit rate** —
  `> 0` pour ACHAT, `< 0` pour ÉVITER, `|var| < 5` pour SURVEILLER. Ces trois taux
  ne sont pas comparables entre eux, ce qui complique toute analyse transversale.
  Envisager une colonne supplémentaire avec une définition uniforme.


### Correction 16/08/2026 — analyses fondamentales BOA bloquees

- **[RESOLU] BOAB, BOABF et BOAC sans analyse depuis le 03/05/2026** — leurs trois
  lignes de `fundamental_analysis` contenaient l'URL de la **page de listing**
  (`brvm.org/fr/rapports-societe-cotes/bank-africa-ci`) au lieu d'un PDF de rapport.
  Or `fundamental_analyzer.py` skippe definitivement par `report_url` (L134-135) :
  ces trois societes etaient donc ecartees a chaque run.

  Residu d'une version anterieure du script — les deux strategies de collecte
  actuelles (L312 et L368) filtrent sur `.pdf` et ne peuvent plus produire ce cas.
  Verification faite : le parseur actuel trouve 20 PDF sur la page BOAC, dont les
  etats financiers 2025 et le rapport T1 2026.

  3 lignes supprimees (ids 890, 892, 894), filtre `report_url=not.like.*.pdf` pour
  ne pas toucher d'analyse valide. Table passee de 176 a 173 lignes. Les trois
  societes seront analysees au prochain run des etapes 5/6 (1er septembre).

- **[A VERIFIER] Volumetrie des analyses en aout** — 8 analyses generees en aout
  contre 123 en juillet et 39 en juin. Les BOA n'expliquent pas cet ecart (bloquees
  depuis mai). Soit regime de croisiere normal — peu de nouveaux rapports publies —
  soit limitation cote fournisseur IA. Verifiable dans le log de l'etape 5 du run
  du 15/08 (onglet Actions).

- **[NOTE] Aucune cle API IA dans le .env local** — DEEPSEEK, GEMINI et MISTRAL ne
  sont configures que dans les secrets GitHub Actions. `fundamental_analyzer.py`
  n'est donc pas executable en local, et toute correction sur ce script ne peut
  etre testee qu'en CI.

### 02/09/2026 — Datation `historical_data` (ADR-052)

- **[P0] `data_collector_simple.py` : `session_date = now()` ligne 56** rend le
  parseur regex de la date BRVM (ligne 71) inatteignable. Ecrit les week-ends,
  lundi = recopie du vendredi. Depuis 24/03/2026, tous tickers. Inclut le DELETE
  non conditionnel non verifie dans `insert_data()`. **A CORRIGER AVANT TOUTE
  PURGE.**

- **[P0] Mesurer l'ampleur du decalage** — permanent J-1 (cron 6h UTC = avant
  publication BRVM) ou week-end seulement ? Croiser `historical_data` vs BOC sur
  5 seances. Determine la forme de la purge : suppression de lignes ou redatation
  globale.

- **[P1] Purger `historical_data`** selon le resultat de la mesure. SQL Editor
  (ADR-026).

- **[P1] `health_checks.py` : regle "aucun `trade_date` samedi/dimanche"** —
  aurait detecte ce defaut en avril. Renforce l'item existant du backlog.

- **[P2] Relire ADR-051 a la lumiere d'ADR-052** — la degradation temporelle de V1
  constatee pourrait etre partiellement artefactuelle si elle porte sur la periode
  post-11/04.

- **[P2] Envisager le BOC comme source des cours** — le PDF porte la date de seance
  dans son nom, l'infrastructure d'ingestion existe deja (`tools/ingest_boc.py`).
  Decision d'architecture, distincte du correctif.

### 04/09/2026 — Amendement ADR-052 (croisement BOC)

- **[P0] Rupture de collecte depuis le 31/08/2026** — volumes `historical_data`
  inferieurs d'un facteur ~10 au BOC, 49 tickers presents. Defaut distinct du
  decalage de datation, apparu il y a 5 jours. A investiguer.

- **[P1] Redatation** (remplace l'item "purge") — decalage +1 jour permanent
  confirme, 18/25 correspondances. Appariement par volume contre
  `boc_market_stats`, pas de soustraction mecanique (3 dates sont correctement
  datees).

- **[P2] Evaluer richbourse.com** — cours et volumes journaliers par titre, cours
  ajustes des fractionnements, export disponible. Source de controle pour la
  redatation, voire de collecte. Lien avec `fix_splits.py` (non suivi, racine).

- **[NOTE] La page brvm.org/fr/jours-feries n'est pas fiable** (annonce Maouloud
  au 26/08, la fete legale etait le 25 ; se presente comme "calendrier 2023").
  **Utiliser le BOC comme calendrier de seances** : un bulletin numerote = une
  seance.

### 04/09/2026 soir — ADR-052 amendement 2

**Ferme aujourd'hui**

- ~~[P0] Mesurer l'ampleur du decalage~~ — fait. Cause unique : le script
  photographie la page a l'heure ou il tourne et etiquette avec `now()`.
  Trois regimes selon l'heure (avant ouverture / pendant seance / apres
  cloture), pas trois defauts.
- ~~[P0] Correctif urgent~~ — cron a `0 18 * * 1-5` + gardes week-end et
  horaire. Deploye sur `main` (`6c17474`). Prochain run lundi 18h UTC.
- ~~[P1] Reconstitution~~ — `boc_cote` : 108 seances, 5 103 lignes, 26/03 au
  04/09, 0 echec. La purge/redatation envisagee est remplacee par un
  remplacement depuis la source officielle.

**Ouvert**

- **[P1] Comparer `boc_cote` x `historical_data`** titre par titre sur la
  periode. Resoudre les symboles vers `companies` (reperer les inconnus :
  SAFCA, nouveaux titres). Mesurer l'ampleur reelle de la divergence avant
  toute bascule.

- **[P1] Basculer `historical_data`** 26/03 -> 04/09 depuis `boc_cote`.
  **Export prealable obligatoire** — plan Supabase gratuit, aucun backup
  automatique. Decider aussi du sort de `brvm_decisions` et
  `brvm_decisions_results` sur la periode : regenerer, ou marquer non fiables
  et repartir du 05/09. Regenerer des signaux a posteriori sur donnees
  corrigees, c'est du backtest, pas du forward test — decision de methode.

- **[P1] Correctif de fond `data_collector_simple.py`** : `session_date` reste
  a `now()`, le parseur regex de la date (L71) reste inatteignable. Demande de
  valider le regex contre la page actuelle. **Ou** basculer la collecte
  quotidienne sur le BOC et rendre ce script secondaire — l'infrastructure
  existe desormais.

- **[P1] Reevaluer V1** sur mars-septembre une fois les donnees corrigees, et
  **relire ADR-051** : la degradation constatee (74,6 % mai -> 63,6 % juin ->
  53,7 % juillet) tombe exactement dans la fenetre polluee.

- **[P1] `health_checks.py` — controles croises externes.** Les 12 tests de
  `test_pipeline.py` sont tous internes : ils verifient la coherence de la base
  avec elle-meme. Aucun ne confronte la donnee a une source independante, d'ou
  cinq mois d'invisibilite. Pire : `last_trading_day()` (L46) ramene au vendredi
  le week-end, donc les lignes fautives n'etaient jamais lues, et T4 (variation
  <40 %) comme T8 (donnees <3j) etaient *ameliores* par le defaut.
  Trois regles a ajouter :
  - T13 : `sum(historical_data.volume)` du jour == `boc_market_stats.volume_echange`
  - T14 : aucune `trade_date` en samedi/dimanche
  - T15 : toute `trade_date` existe dans `boc_market_stats.date_seance`
  T13 aurait alerte le 25 mars.

- **[P2] `EXPECTED_TICKERS = 47`** dans `test_pipeline.py` alors que `companies`
  en compte 49. La condition etant `nb < EXPECTED`, le test passe toujours.
  Comparer au compte reel en base.

- **[P2] `valeur_transigee` non fiable** au-dela de 1 milliard (troncature
  d'affichage du BOC) et sur les droits. Documenter la limite partout ou la
  colonne est lue. Ne pas reconstruire la valeur — la marquer.

- **[P2] Bulletins des 24 et 25/03/2026 absents** cote BRVM : `boc_cote`
  commence au 26/03 et non au 24/03. Verifier si feries ou PDF manquants.

- **[P3] Fichiers non suivis** : ~50 a la racine, dont 4 `.bak` crees
  aujourd'hui (`parse_boc.py.bak2/3/4`, `data_collector_simple.py.bak_adr052`)
  et `tools/scrape_dates_publication_t1.py` d'origine inconnue. Git est la
  sauvegarde ; les `.bak` sont a supprimer.

### 04/09/2026 nuit — comparaison faite, bascule a executer

- ~~[P1] Comparer `boc_cote` x `historical_data`~~ — fait (ADR-052 amendement 3).
  **10,1 % de lignes identiques** sur 4 926 cles communes. 57 dates sans seance
  BOC dont 46 week-ends. Correction selective exclue.

- **[P1] BASCULE — a executer a froid, seule etape destructive du chantier.**
  Procedure detaillee en ADR-052 amendement 3, section 5. Points de vigilance :
  - export JSON prealable (plan gratuit, aucun backup automatique)
  - **DELETE en excluant `company_id` 48 et 49** — ce sont les indices BRVMC et
    BRVM30, alimentes par `update_index.py`, hors perimetre (281 lignes)
  - exclure `est_droit` (SAFCA, 27 lignes)
  - `non_cote` (3 lignes UNLC) : `price = cours_reference`, `volume = 0`
  - verification finale : 5 076 actions + 281 indices, aucune date week-end,
    volumes concordants avec `boc_market_stats`

- **[P1] Decision de methode : sort de `brvm_decisions` 26/03 -> 04/09.**
  Regenerer les signaux sur donnees corrigees en ferait du backtest, pas du
  forward test. Recommandation : marquer la periode non fiable et repartir du
  05/09. A trancher explicitement, pas par defaut.

- **[P2] 2 seances BOC sans aucune ligne dans `historical_data`** : 03/06 et
  23/07. Le pipeline n'a rien ecrit ces jours-la — verifier les logs GitHub
  Actions si encore disponibles.
