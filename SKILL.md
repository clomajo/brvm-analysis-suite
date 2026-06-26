---
name: brvm-analytics
description: >
  Contexte de développement de BRVM Analytics — plateforme d'analyse quantitative
  de la BRVM (Bourse Régionale des Valeurs Mobilières). Utiliser ce skill dès qu'une
  tâche concerne le frontend React (App.jsx, composants), le pipeline Python
  (brvm-analysis-suite), Supabase, GitHub Actions, les scripts de scoring/décisions,
  les modèles GRU, les analyses Mistral, ou tout déploiement Vercel lié à ce projet.
  Déclencher aussi pour toute question sur l'architecture, les contraintes techniques,
  les règles métier, ou les procédures opérationnelles de BRVM Analytics.
---

# BRVM Analytics — Skill de développement

## Repos

| Repo | Rôle | URL |
|---|---|---|
| `clomajo/brvm-analytics` | Frontend React → Vercel | github.com/clomajo/brvm-analytics |
| `clomajo/brvm-analysis-suite` | Pipeline Python → GitHub Actions | github.com/clomajo/brvm-analysis-suite |

---

## Stack technique

| Composant | Technologie | Version / détail |
|---|---|---|
| Frontend | React + Vite | 18 + **3.2.7** (ne pas upgrader) |
| Base de données | Supabase PostgreSQL | Project ID: `lynevvhmstpcffobwudr` |
| Pipeline CI/CD | GitHub Actions | Python **3.11** |
| Hébergement | Vercel | Auto-deploy sur push |
| AI Fondamentaux | Mistral AI | `mistral-large-latest` |
| AI Extraction | Claude API | `claude-sonnet-4` |
| Env local | macOS Catalina, Node **v16.20.2** | Python 3.8/3.14 local |
| .env pipeline | `~/Desktop/brvm-analysis-suite/.env` | SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, MISTRAL_API_KEY |

---

## Contraintes critiques — lire avant tout changement

### Frontend (brvm-analytics)
- **Ne jamais télécharger App.jsx directement** — toujours modifier via scripts Python patch en terminal
- **App.jsx est le composant principal (~3500 lignes)**, mais PAS le seul fichier frontend — `src/components/` contient aussi `BOAComparison.jsx`, `Opportunities.jsx`, `FinancialAnalysis.jsx` (découverts le 23/06/2026, ADR-017). Toujours vérifier ce dossier en plus de App.jsx avant de conclure qu'un code n'existe pas dans le frontend.
- **Ne pas installer react-markdown** — cause des erreurs Vite 3 — FERMÉ définitivement (ADR-031)
- **Node v16.20.2 sur macOS Catalina** — impossible d'upgrader, imports complexes instables
- **Vite 3.2.7** — contraintes esbuild spécifiques, ne pas supposer comportement Vite 4/5
- **Warning chunk >500 KiB** — normal, dû à l'App.jsx volumineux, non bloquant
- **✅ Calcul Fair Value dupliqué — CORRIGÉ (25/06/2026, ADR-017)** — `FinancialAnalysis.jsx` lit désormais `target_prices` (commit `c7294f6`), comme `App.jsx`. Plus de divergence Dashboard / page "AI Fundamental Analysis". ⚠️ Reste sensible à un `eps` source faux pour certains tickers (cf. contrainte pipeline ci-dessous, ADR-018) — ce n'est plus un bug de duplication de calcul, mais un problème de donnée en amont.

### Pipeline (brvm-analysis-suite)
- **Toujours utiliser Supabase REST API** — psycopg2 échoue en GitHub Actions (ADR-004)
- **Ne pas modifier `generate_decisions.py`** avant le 01/07/2026 — modèle gelé (ADR-001)
- **Features Mistral statiques** → ne pas intégrer dans les modèles GRU (ADR-015, testé et rejeté)
- **GRU fiable J+1/J+2 uniquement** — afficher J+5+ comme indicatif seulement (ADR-014)
- **load_dotenv() dans heredoc** → utiliser `load_dotenv(find_dotenv(usecwd=True))` sinon AssertionError
- **Corrections de masse** → SQL Editor Supabase uniquement, jamais PATCH REST ligne par ligne (ADR-026)
- **`calculate_target_price.py` n'est PAS couvert par le gel ADR-001** — c'est un script V2 indépendant
  de `generate_decisions.py` (V1), modifiable librement avant le 01/07/2026 (calibration normale
  avant mise en prod, pas une rupture du gel — cf. ADR-009/010/011)
- **PER sectoriels non hardcodés** — lus dynamiquement depuis `sector_per_history`, jamais en dur
  dans le code (cf. ADR-010). Alimentation manuelle **mensuelle** via `update_sector_per.py`.
- **Pas de liste d'exclusion statique pour le V2** — un filtre dynamique (`evaluer_qualite_eps()`
  dans `calculate_target_price.py`) gère la qualité EPS par ticker, recalculé à chaque run (ADR-011)
- **`eps` scrapé sans recalcul depuis stockanalysis.com (découvert 25/06/2026, ADR-018)** —
  `scrape_all_v4.py` récupère `eps` tel quel (champ "EPS (Basic)"), jamais recalculé depuis
  `net_income/shares_outstanding`. Une correction manuelle de `shares_outstanding` seule
  (comme ADR-012) NE corrige PAS `eps`, et est écrasée par le scraping suivant si `eps`
  lui-même n'est pas corrigé en base. Détection ajoutée (`check_eps_coherence`, log
  uniquement, jamais de correction automatique) — tickers confirmés incohérents au
  25/06/2026 : NTLC (~20x), BICC (~1.5x), SOGC (FY2021-2022 seulement, ~0.73x).
  `shares_outstanding` n'est disponible par le scraper que pour l'année courante (overview),
  jamais par année historique — toute vérification sur FY2021-2024 est une approximation.

### Workflow de déploiement frontend
```bash
cd ~/Desktop/brvm-analytics
npm run build
git add src/App.jsx
git commit -m "fix: description"
git push
# Vérifier sur brvm-analytics.vercel.app — hard refresh (Cmd+Shift+R)
```

### Workflow mensuel — mise à jour des PER sectoriels
```bash
cd ~/Desktop/brvm-analysis-suite
python3 update_sector_per.py
# Lire le P/E 2024 par secteur dans le "Tableau de Bord" BOA Capital Securities
# (Lettre quotidienne, page 2) et saisir les 7 valeurs demandées.
```

---

## Thème UI

| Token | Valeur |
|---|---|
| Fond global | `#F8F9FA` |
| Cards | `#FFFFFF` |
| Accent principal | `#2B6CB0` |
| Texte principal | `#1A202C` |
| Texte secondaire | `#1A202C` (contraste corrigé — ne pas utiliser #7d8590) |
| Warning / estimé | `#d2a94d` |
| Fair Value line | `#E07B39` (LightweightCharts, lineStyle=2) |

---

## Architecture UI (état au 30/05/2026 — ADR-013)

**Navbar globale :** `[Recherche ticker]` · Marché · Opportunités · Portefeuille · Obligations
**Page par défaut :** Marché
**Fiche ticker :** Aperçu · Prévisions · Backtest
**Tabs archivés (masqués, code non supprimé) :**
BOA vs BRVM · Risque · Législatif · Direction · Macro · Matières 1ères · Scorecard détaillé

---

## Tables Supabase principales

| Table | Contenu | Accès |
|---|---|---|
| `companies` | 47 tickers — colonne `symbol` (pas `ticker`) | lecture publique |
| `historical_data` | 110,594+ lignes — company_id, trade_date, price, volume | lecture publique |
| `brvm_decisions` | Signaux — colonnes : ticker, date, score, signal, market_regime, liquidity_tier, confidence | lecture publique |
| `target_prices` | Cours cible V2 quotidien — ticker, cours_cible, decote_pct, signal_v2, calcul_date, **per_source** (ajouté 21/06/2026) | lecture publique |
| `sector_per_history` | **NOUVEAU (21/06/2026)** — P/E sectoriel par secteur officiel BRVM, alimentation mensuelle manuelle (secteur, per_2024, date_releve, source) | lecture publique |
| `fundamental_analysis` | Analyses Mistral FY2025 — 45 lignes, UNIQUE company_id | lecture publique |
| `company_fundamentals` | PER, ROE, EPS, market_cap, dividend_yield, shares_outstanding | lecture publique |
| `corporate_events` | Dividendes + AG — ticker, event_type, event_date | lecture publique |
| `commodity_prices` | Cocoa, coton, or, pétrole, USD/XOF (Palm Oil + Rubber retirés) | lecture publique |
| `brvm_decisions_results` | Vérifications J+20 (dès 07/2026) | — |
| `boa_recommendations` | 547 lignes, 17 semaines déc 2025–avr 2026 | — |
| `user_actions` | Moat data | lecture/écriture user + service_role full |

### Colonnes réelles confirmées (pièges courants)
- `brvm_decisions` : signal_date → **`date`** · decision → **`signal`** · regime → **`market_regime`**
- `companies` : **`symbol`** (pas ticker) · `id` pour jointure avec historical_data
- `historical_data` : **`trade_date`** (pas date) · **`price`** (pas close_price) · pas de colonne ticker
- `company_fundamentals` : filtre `roe=not.is.null` pour obtenir FY2025 (FY2026 = vide)
- `fundamental_analysis` : `updated_at` = date réelle analyse · `report_date` = fin exercice fiscal
- `boa_recommendations` : colonnes `action` (BUY/SELL/HOLD/REDUCE) · `cours_act` · `cours_pot` · `rendement` · `potential`
- `brvm_decisions` : score_technique/fondamental/liquidite/tendance → **NULL en V1** (score composite seulement)
- `sector_per_history` : `secteur` contraint par CHECK aux 7 valeurs officielles BRVM (cf. ci-dessous) ·
  toujours lire la ligne `date_releve` la PLUS RÉCENTE par secteur (plusieurs lignes historisées possibles)

### fundamental_analysis — contrainte UNIQUE
- `UNIQUE (company_id)` ajoutée le 30/05/2026
- 45 lignes, 45 company_id distincts (doublons supprimés)
- Requête frontend : `order=updated_at.desc&limit=1` (redondant mais conservé)

**Vues SQL utiles :**
- `v_ytd_performance` — YTD par ticker vs BRVMC
- `v_historical_prices` — historical_data JOIN companies (expose colonne ticker)

---

## Modèle de scoring V1 (gelé jusqu'au 01/07/2026)

```
Score composite (0-100) =
  Technique (RSI, MACD, SMA)     ~40%
  Fondamental (narratif Mistral) ~25%
  Liquidité (tier: prestige/liquid/illiquid) ~20%
  Tendance (momentum)            ~15%
```

**Seuils :** ACHAT >= 65 (BULL uniquement) · SURVEILLER 30-64 · EVITER < 30
**Performance :** Alpha +1.82% global · +1.02% BULL · -0.72% BEAR
**Verdict :** Signal technique = bruit structurel (AUC 0.51, 22 992 signaux) — ADR-016

---

## Modèle V2 (parallèle silencieux — bascule 01/07/2026)

```
Signal V2 = ACHAT si :
  cours_actuel < cours_cible × (1 - seuil)
  ET ROE > 15% ET P/B < 2.5
  ET cap 150-500B FCFA
  ET volume_20j > seuil_liquidite (à calibrer)
  ET J-10 avant ex_dividend_date (signal optimal)
```

**Cours cible :** EPS moyen (jusqu'à 3 ans, cf. filtre data-quality ci-dessous) × PER sectoriel (70%)
+ dividende / 8% (30%)
**Table :** `target_prices` — upsert quotidien via `calculate_target_price.py`
**Performance backtest :** 25 signaux, médiane J+90 +7.8%, alpha +2.8%, 68% positifs
**Watchlist :** SOGC, SPHC, BOAS, BOABF, ONTBF, TTLC, BOAC

### Nomenclature sectorielle officielle BRVM (7 secteurs, en vigueur depuis 02/01/2025 — ADR-010)
Remplace l'ancienne nomenclature à 5 catégories (Banque/Agro/Industrie/Telecom/Distribution),
qui n'était alignée sur aucune classification officielle ni cohérente avec les PER constatés.

- **Consommation de Base** (9) : NTLC, PALC, SPHC, SICC, STBC, SOGC, SLBC, SCRC, UNLC
- **Consommation Discrétionnaire** (7) : BNBC, CFAC, LNBB, NEIC, ABJC, PRSC, UNXC
- **Énergie** (4) : SMBC, TTLC, TTLS, SHEC
- **Industriels** (6) : SDSC, SEMC, SIVC, FTSC, STAC, CABC
- **Services Financiers** (16) : BOAB, BOABF, BOAC, BOAM, BOAN, BOAS, BICB, BICC, CBIBF, ECOC,
  ETIT, NSBC, ORGT, SAFC, SGBC, SIBC
- **Services Publics** (2) : CIEC, SDCC
- **Télécommunications** (3) : ONTBF, ORAC, SNTS

Mapping complet dans `SECTEUR_OFFICIEL` (dict, `calculate_target_price.py`). Source de
vérité externe : richbourse.com/common/variation/index (filtre "Secteur").

⚠️ **Pièges tickers proches à ne pas confondre :**
- `STAC` (SETAO, Industriels) ≠ `STBC` (Sitab, Consommation de Base)
- `ABJC` (Servair Abidjan) et `PRSC` (Tractafric Motors) sont dans le même secteur
  (Conso Discrétionnaire) mais sont deux tickers distincts — ne pas les confondre
- `CFAC` (CFAO Motors) n'appartient qu'à un seul secteur (Conso Discrétionnaire) — un bug
  préexistant le dupliquait dans Agro ET Distribution avant l'ADR-010, corrigé depuis.

### PER sectoriels — dynamiques, plus jamais hardcodés (ADR-010)
Lus depuis la table `sector_per_history`, alimentée **manuellement, une fois par mois**,
depuis le P/E 2024 affiché par secteur dans le "Tableau de Bord" du bulletin quotidien
BOA Capital Securities (Lettre quotidienne, page 2). Procédure : `update_sector_per.py`.

Si un secteur n'a pas de valeur en base au moment du run (ex: avant la première saisie,
ou un mois oublié) : fallback sur une valeur figée documentée dans le code, avec un
warning explicite affiché ET un champ `per_source = 'fallback'` tracé dans `target_prices`
— jamais de substitution silencieuse.

Dernières valeurs saisies (18/06/2026, source Tableau de Bord BOA, P/E 2024) :
Consommation de Base 6.5x · Consommation Discrétionnaire 10.0x · Énergie 5.1x ·
Industriels 3.5x · Services Financiers 14.7x · Services Publics 6.0x · Télécommunications 14.7x

### Filtre data-quality EPS — remplace la liste d'exclusion statique (ADR-011)
**Il n'existe plus de liste de tickers exclus codée en dur.** L'ancienne liste mentionnée
dans une version antérieure de ce skill (NTLC, SNTS, BOAN, BNBC, SICC, UNLC, ETIT, FTSC,
CFAC, SIVC) n'avait d'ailleurs **jamais été implémentée dans le code** — vérification
faite le 13/06/2026. Elle était aussi partiellement incorrecte (SNTS a des données propres
et n'aurait pas dû y figurer).

Logique actuelle (`evaluer_qualite_eps()` dans `calculate_target_price.py`) :
1. Minimum 1 année EPS exploitable pour être éligible.
2. Si 2+ années disponibles (jusqu'à 3 retenues) : doivent être consécutives, sinon exclu.
3. Collapse EPS >80% YoY → exclu, quel que soit le nombre d'années.
4. **Cas à 1 seule année EPS** : accepté SANS contrôle de consécutivité/collapse
   (mathématiquement impossible à vérifier avec un seul point) — risque résiduel assumé
   pour ne pas exclure des tickers à forte capitalisation (ex: ORAC/Orange CI) uniquement
   par manque de profondeur d'historique.

Chaque exclusion est loggée avec sa raison exacte à chaque run — jamais de silence.

---

## Session 25/06/2026 — Résumé des changements

### Bug corrigé (ADR-017)
- `FinancialAnalysis.jsx` recalculait sa propre Fair Value en JS (P/E 10x fixe,
  pas de filtre data-quality) — corrigé : lit désormais `target_prices`
  (`select=cours_cible,per_ref,per_source,decote_pct,calcul_date&order=
  calcul_date.desc&limit=180`), via script de patch `patch_adr017_fairvalue.py`.
- Graphique "Cours vs Fair Value — 3 ans" : remplacement de la ligne plate
  par une vraie courbe (forward-fill depuis l'historique `target_prices`).
- Texte de méthode : affichage dynamique de `per_ref`/`per_source` au lieu
  du "P/E sectoriel 10x" fixe.
- Tickers exclus ADR-011 (NTLC, etc.) : `target_prices` vide → "N/D" affiché,
  comportement déjà géré par le JSX existant, pas de changement nécessaire.
- Commit `c7294f6` sur `brvm-analytics`.

### Bug découvert — cause racine (ADR-018)
- En vérifiant le fix ADR-017 sur NTLC, Fair Value toujours aberrante (80 007
  FCFA) — pas un bug d'affichage cette fois, mais une donnée `target_prices`
  elle-même fausse (ligne du 30/05/2026, jamais recalculée depuis).
- Cause racine : `scrape_all_v4.py` scrape `eps` tel quel depuis
  stockanalysis.com, sans jamais le recalculer depuis
  `net_income/shares_outstanding`. La correction `shares_outstanding` d'ADR-012
  n'a donc jamais corrigé `eps` en base (correction à ADR-012 : l'affirmation
  "eps corrigé" était fausse, jamais persistée ou écrasée par le scraping
  hebdomadaire suivant).
- Élargi à 3 tickers confirmés : NTLC (~20x), BICC (~1.5x), SOGC (FY2021-2022
  seulement, ~0.73x — FY2023+ sains).
- Décision : ne pas corriger immédiatement, comprendre la cause racine d'abord
  (éviter de répéter l'erreur ADR-012). Détection ajoutée (`check_eps_coherence`
  dans `scrape_all_v4.py`, commit `654bfd2`) — log uniquement, jamais de
  correction automatique de `eps`. Testé sur les 3 cas confirmés + 4 cas sains
  + cas limites avant déploiement.
- Correction réelle des données reportée à après le run du lundi 29/06/2026,
  pour avoir la liste complète des tickers touchés avant de corriger.

---

## Session 23/06/2026 — Résumé des changements

### Bug découvert et corrigé (ADR-012)
- Signalement utilisateur direct sur l'app : Fair Value NTLC affichait +433%
  de décote (cours cible 80 006,67 FCFA vs cours réel 15 005 FCFA).
- Cause racine identifiée : `shares_outstanding` pour NTLC dans
  `company_fundamentals` était stocké à 1 100 000, alors que la vraie valeur
  (confirmée par 3 sources indépendantes : richbourse.com, BOA Capital, et
  Sikafinance) est **22 070 400**. Source du bug : stockanalysis.com
  lui-même affiche cette valeur fausse (probable split d'actions jamais
  répercuté côté agrégateur) — pas un bug du pipeline de scraping.
- Vérification systématique sur les 45 autres tickers : aucun autre cas
  similaire détecté — problème confirmé isolé à NTLC.
- Correction appliquée : `shares_outstanding` et `eps` recalculés et corrigés
  pour NTLC dans `company_fundamentals`. Validation croisée à la décimale
  contre les BNPA Sikafinance (822,37 vs 822,00 pour FY2024, etc.).
- Ligne `target_prices` aberrante (calcul_date 2026-06-21) supprimée
  manuellement par requête SQL ciblée.
- NTLC reste exclu du calcul V2 par ADR-011 (années EPS non consécutives) —
  cette correction ne le fait pas réapparaître dans les signaux, elle
  assainit seulement la donnée de base.

### Bug découvert, NON corrigé — reporté (ADR-017)
- **Doublon de calcul Fair Value** : `src/components/FinancialAnalysis.jsx`
  (page "AI Fundamental Analysis") recalcule sa propre Fair Value en
  JavaScript, indépendamment de `target_prices` — P/E sectoriel fixé à 10x
  en dur, aucun filtre data-quality, aucun garde-fou de plausibilité.
  Continue d'afficher des aberrations pour NTLC (et potentiellement d'autres
  tickers) même après la correction ADR-012.
- Approche de correction retenue pour une session future : faire lire à ce
  composant l'historique déjà présent dans `target_prices` plutôt que de
  recalculer en JS (option B, cf. ADR-017 pour le détail des options
  écartées : duplication JS rejetée, Edge Function jugée disproportionnée).
- Découverte collatérale : `ARCHITECTURE.md`/SKILL.md sous-estimaient
  l'architecture frontend réelle (ADR-002 mentionnait "pas de composants
  séparés", alors que `BOAComparison.jsx`, `Opportunities.jsx`,
  `FinancialAnalysis.jsx` existent bien comme fichiers distincts).

---

## Session 21/06/2026 — Résumé des changements

### Pipeline (brvm-analysis-suite)
- ADR-009 : taux d'actualisation 8% (composante dividende) maintenu sans modification,
  origine non traçable, documenté plutôt que recalibré sans méthode fiable.
- ADR-010 : migration des PER sectoriels de 5 catégories hardcodées (incohérentes avec
  toute nomenclature officielle) vers les 7 secteurs officiels BRVM, lecture dynamique
  depuis la nouvelle table `sector_per_history`.
- ADR-011 : suppression de la liste d'exclusion statique (jamais implémentée dans le
  code malgré la documentation) au profit d'un filtre data-quality dynamique sur l'EPS
  (consécutivité + détection de collapse >80% YoY).
- `calculate_target_price.py` : patché en profondeur — mapping ticker→secteur officiel
  47/47 (corrige un bug de duplication CFAC agro+distribution), lecture PER dynamique
  avec fallback traçable, nouveau filtre EPS.
- Nouveaux scripts : `update_sector_per.py` (saisie mensuelle manuelle des PER sectoriels),
  `parse_boa_dashboard.py` (parsing automatique du Tableau de Bord BOA — écrit et testé
  mais NON branché en production, le document source arrivant par lien et non par pièce
  jointe, ce qui complique l'automatisation de la récupération du fichier).

### Supabase
- `sector_per_history` : table créée, RLS activé, lecture publique, contrainte CHECK
  sur les 7 secteurs officiels.
- `target_prices` : colonne `per_source` ajoutée (traçabilité sector_per_history vs fallback).

### Backlog ajouté
- Intégration du pattern pré/post ex-dividende (hausse anticipative avant ex-date, baisse
  mécanique après) directement comme composante du signal V2 — actuellement distinct de
  la stratégie de capture de dividende déjà validée. Intuition de Jocelyn, à creuser après
  le 01/07/2026 et après les résultats de la régression 10 ans du weekend.
- Automatisation complète du parsing du Tableau de Bord BOA (email→stockage→GitHub Actions)
  si le document source devient accessible par pièce jointe ou URL stable un jour.

---

## Session 30/05/2026 — Résumé des changements

### Pipeline (brvm-analysis-suite)
- V2-06 : Palm Oil + Rubber retirés de scrape_commodities.py (efde604)
- requirements.txt nettoyé — doublons supprimés (9212b00)
- fix_snts_updates.sql archivé dans sql/ (73474e9)
- scrape_market_cap.py automatisé 1er lundi/mois GitHub Actions (7a069ae)
- calculate_target_price.py : EPS moyenne 3 ans + upsert target_prices (b939b53, dc52769)
- verify_decisions.py : VERIFICATION_WINDOW 90 → 20 jours (07f46c6)

### Frontend (brvm-analytics)
- Tab BOA vs BRVM supprimé (25a92a0)
- Fondamentaux clés : FUND_DATA hardcodé → Supabase company_fundamentals (c6a03e8)
- Ligne Fair Value style Morningstar sur graphique (9c65c31)
- Badge Fair Value V2 🎯/📉 sur DecisionCards (965ef99)

### Supabase
- fundamental_analysis : 45 lignes (doublons supprimés) + UNIQUE (company_id)
- target_prices : table créée, RLS activé, lecture publique

---

## ADR clés à retenir

| ADR | Décision |
|---|---|
| ADR-001 | Modèle gelé jusqu'au 01/07/2026 (generate_decisions.py uniquement) |
| ADR-002 | App.jsx = composant principal, mais PAS le seul fichier frontend (corrigé 23/06) |
| ADR-003 | ACHAT désactivé en régime BEAR |
| ADR-004 | Supabase REST API uniquement (pas psycopg2) |
| ADR-009 | Taux d'actualisation 8% maintenu, origine non traçable |
| ADR-010 | PER sectoriels dynamiques, nomenclature officielle BRVM 7 secteurs |
| ADR-011 | Filtre data-quality EPS remplace la liste d'exclusion statique |
| ADR-012 | Bug shares_outstanding NTLC (source stockanalysis.com) corrigé |
| ADR-013 | Tabs décoratifs archivés — nouvelle navbar |
| ADR-014 | GRU fiable J+1/J+2 uniquement |
| ADR-015 | Features Mistral statiques → nuisent au GRU, rejetées |
| ADR-017 | Doublon Fair Value FinancialAnalysis.jsx — corrigé 25/06 (lit target_prices) |
| ADR-018 | eps non recalculé depuis stockanalysis.com (NTLC/BICC/SOGC) — détection ajoutée, correction des données en attente |

---

## Règle opérationnelle — Fin de session

À la fin de chaque session de développement BRVM Analytics, mettre à jour simultanément :
1. SKILL.md — contraintes, ADR, bugs résolus, baselines
2. CHANGELOG.md — entrée datée avec FEAT/INFRA/PERF/FIX
3. BACKLOG.md — nouveaux items identifiés
4. DECISIONS.md — nouveaux ADR
5. ARCHITECTURE.md — changements structurels

Puis commit unique :
```bash
git add SKILL.md CHANGELOG.md BACKLOG.md DECISIONS.md ARCHITECTURE.md
git commit -m "docs: mise à jour documentation session JJ/MM/YYYY"
git push
```
