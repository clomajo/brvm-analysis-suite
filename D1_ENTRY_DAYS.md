# D1 — Simulation des jours d'entrée fixes post-détachement

**Date :** 03-04/08/2026
**Branche :** `remediation-2026-07`
**Script :** `tools/simulate_entry_days.py` (331 lignes)
**Sortie :** `d1_entry_days_results.json` (régénérable)
**Classe A** — lecture seule, aucune modification de production.

> **STATUT : EXPLORATION, PAS VALIDATION.**
> Ne pas utiliser ces chiffres comme base de décision d'investissement
> sans la validation décrite en section 5.

---

## 1. Question posée

`min_day` (analyse v3b) est un optimum **a posteriori** : il indique quel jour aurait été
le meilleur en regardant l'historique, pas quel jour choisir à l'avance.

D1 pose la question opérationnelle : **quel jour d'entrée FIXE (J+0 à J+15) après
détachement donne le meilleur résultat en moyenne ?**

---

## 2. Spécification (validée avant écriture du script)

| Paramètre | Choix |
|---|---|
| Entrée | Clôture du jour J+N ; cotation suivante si jour non coté |
| Sortie (a) | Fill du cours pré-détachement |
| Sortie (b) | Horizon fixe J+30 après l'entrée |
| Rendement | Prix seul (l'acheteur post-détachement ne touche pas le dividende) |
| Référence sur-réaction | Prix ex-div théorique |
| Métrique principale | **Alpha** = rendement titre − rendement BRVMC, même fenêtre |
| Benchmark | BRVMC réel (`historical_data`, `company_id=48`), 2 578 séances |
| Univers | Séparés : dividend capture (6 tickers) vs autres |
| Frais / IRVM | Non appliqués (protocole brut-first) |
| Sans fill | Sortie forcée J+90, **comptés et non exclus** (l'exclusion biaiserait vers les événements favorables) |

Filtrage des événements : 126 bruts → **99 retenus**
- 17 exclus : cours inchangé au détachement (absence de cotation)
- 10 exclus : `ex_date` = fin d'exercice fiscal (jamais un jour de bourse)

Répartition : 26 événements univers / 73 autres.

---

## 3. Résultats

### 3.1 Univers dividend capture (n=26) — sortie « fill »

| J entrée | rdt méd | **alpha méd** | % alpha>0 | jours méd |
|---|---|---|---|---|
| J+0 | 3,97 | **−0,13** | 48,0% | 54 |
| J+1 | 4,44 | 0,95 | 61,5% | 59 |
| J+2 | 4,24 | 2,40 | 65,4% | 56 |
| J+3 | 5,17 | 2,84 | 68,0% | 56 |
| J+4 | 5,52 | 3,03 | 68,0% | 54 |
| J+5 | 5,64 | 3,05 | 72,0% | 52 |
| J+6 | 5,62 | 2,58 | 68,0% | 50 |
| J+7 | 5,55 | 2,59 | 72,0% | 49 |
| J+8 | 5,80 | 2,77 | 75,0% | 48 |
| J+9 | 5,67 | 3,50 | 70,8% | 54 |
| J+10 | 5,21 | 3,27 | 73,1% | 52 |
| J+11 | 6,55 | **3,99** | 73,1% | 52 |
| J+12 | 5,95 | 3,15 | 80,0% | 50 |
| J+13 | 7,46 | 3,35 | 80,0% | 50 |
| J+14 | 6,31 | 3,37 | 75,0% | 47 |
| J+15 | 5,72 | 3,84 | 79,2% | 45 |

### 3.2 Univers dividend capture (n=26) — sortie « fixe » J+30

Alpha : **−2,77 à J+0**, −2,62 à J+1, remonte progressivement, passe positif à partir de
J+6 (+0,05) et atteint +1,89 à J+14. % positifs : 38,5% à J+0 → 69,2% à J+14.

### 3.3 Autres tickers (n=65 simulables sur 73)

| Sortie | Alpha médian | % positifs |
|---|---|---|
| fill | ~0 sur toute la plage | 40-51% |
| fixe | −3,02 (J+0) à +0,46 (J+10), majoritairement négatif | 37-55% |

**Aucun signal.** 8 événements non simulables (fenêtre de prix insuffisante).

---

## 4. Lecture

### Ce qui est encourageant

**Structure en plateau, pas en pic.** L'alpha monte de ~0 à J+0 jusqu'à ~2,5-3 dès J+2,
puis reste stable jusqu'à J+15. Le taux de succès suit la même forme (48% → 65-80%).
Un pic isolé au milieu de voisins médiocres signalerait du sur-ajustement ; un plateau
large est le profil d'un effet réel.

**Cohérence entre les deux règles de sortie.** Les deux montrent le même ordre : J+0/J+1
mauvais, amélioration progressive, stabilisation. Le résultat ne dépend pas du choix de
sortie.

**Contraste net avec le groupe témoin.** Les 65 autres tickers ne montrent rien sous
aucune règle. Le signal est spécifique à l'univers.

**Contre-intuitif et donc informatif :** entrer à J+0 — ce que la théorie du dividend
capture suggère — est la pire option. Cohérent avec le `J optimal médian = J+7,5` mesuré
indépendamment sur l'univers par v3b.

### Règle qui s'en dégage (à valider)

Entrée entre **J+3 et J+10** après détachement, sortie au retour du cours pré-détachement
(~50 jours de détention) : environ **+3 points d'alpha médian, positif dans ~70% des cas**.

---

## 5. Réserves — pourquoi ce n'est pas une preuve

### 5.1 L'historique ne fait pas 10 ans mais 5

Décomposition des 26 événements de l'univers :

| Ticker | n | Dates |
|---|---|---|
| BOAB | 6 | 2022-05-23, 2023-05-23, 2024-05-23, 2025-05-30, **2026-05-14, 2026-05-22** |
| BOAC | 5 | 2022-04-26, 2023-04-26, 2024-04-25, 2025-05-16, 2026-05-05 |
| ECOC | 4 | 2022-04-26, 2023-05-25, 2024-05-28, 2025-05-27 |
| NTLC | 4 | 2022-07-29, 2023-08-03, 2024-08-16, 2025-08-13 |
| SMBC | 4 | 2022-08-22, 2023-08-29, 2024-09-26, 2025-09-11 |
| NSBC | 3 | 2023-07-05, 2024-07-04, 2025-07-07 |

**Aucun événement avant 2022.** `historical_data` remonte à 2016-04-04 mais
`corporate_events` ne fournit d'événements exploitables qu'à partir de 2022.

→ **Le walk-forward classique (calibration 2016-2021 / validation 2022-2026) est
impossible** — il n'y a rien à calibrer sur la première moitié.

### 5.2 Groupement temporel fort

BOAB, BOAC et ECOC détachent tous entre fin avril et fin mai, chaque année. Il existe donc
~5 grappes annuelles où 3-4 titres partagent le même contexte de marché.

**L'échantillon effectif est plus proche de 5-6 périodes indépendantes que de 26
observations.** Tout intervalle de confiance calculé sur n=26 serait très largement
trop étroit.

### 5.3 Période intégralement haussière

2022-2026 couvre une phase de hausse continue de la BRVM (+40,40% en y-t-d 2026 seul).
L'alpha corrige partiellement ce biais, mais la structure temporelle du marché sur la
période reste non contrôlée.

### 5.4 Anomalie de données à vérifier

**BOAB présente deux détachements en 2026** : 14/05 et 22/05. Soit un dividende
exceptionnel, soit une anomalie dans `corporate_events`. À trancher avant toute
exploitation.

### 5.5 Précédent NTLC

En T5c, NTLC était un outlier négatif robuste en détention longue (−4,63 pts d'alpha) mais
positif en rotation courte (+3,14 pts). Avec 4 événements sur 26 ici, **un seul ticker peut
porter une part importante du résultat**. La décomposition par ticker n'a pas été faite.

---

## 6. Bug corrigé en cours de session

`rendement_benchmark` retournait 0 quand `date_debut == date_fin` (titre atteignant le fill
dès le jour d'entrée). L'alpha valait alors mécaniquement 0, et la médiane tombait
exactement sur 0,00 — visible sur 14 des 16 lignes du groupe « autres ».

Correctif : `if d_in == d_out: return None` (alpha non défini sur fenêtre nulle).

Impact sur l'univers : marginal (quelques centièmes, n inchangé à 26). Impact sur les
autres tickers : significatif, leurs fills étant beaucoup plus rapides.

---

## 7. Prochaines étapes

### D1b — Validation par exclusion successive (priorité)
Le walk-forward étant impossible, valider par robustesse :
- **Leave-one-ticker-out** : retirer chacun des 6 tickers, vérifier que le plateau survit.
  Détecte le cas où un seul ticker porte le résultat (précédent NTLC).
- **Leave-one-year-out** : retirer chaque millésime 2022→2026.
  Détecte le cas où une seule année porte le résultat.

Méthode faible mais c'est la seule disponible avec cet historique.

### D1c — Anomalie BOAB 2026
Deux `ex_date` en mai 2026. Vérifier dans `corporate_events` s'il s'agit d'un dividende
exceptionnel ou d'un doublon.

### D1d — Étendre l'historique
Chercher si `corporate_events` peut être alimenté avant 2022 (BRVM, richbourse,
bulletins BOA archivés). Chaque année gagnée renforce directement la validation.

### D1e — Sensibilité frais / IRVM
Toutes les mesures sont brutes. Un alpha de +3 points doit survivre aux frais de courtage
et à l'IRVM pour être exploitable. C'est ici plus critique qu'ailleurs : la marge est mince.

### D1f — Élargir l'univers
Les 65 autres tickers ne montrent rien en agrégé, mais aucun n'a été examiné
individuellement. Croiser avec le seuil de liquidité 896 (proposé T5b, jamais validé) pour
identifier d'éventuels candidats.

---

## 8. Fichiers

- `tools/simulate_entry_days.py` — script D1
- `d1_entry_days_results.json` — sortie détaillée (régénérable, non commitée)
- `brvm_dividend_results.json` — entrée, produite par `brvm_dividend_analysis_v3b.py`
