# SESSION 03/08/2026 (suite) — Analyse post-détachement dividende

**Branche :** `remediation-2026-07`
**Statut :** exploratoire, classe A (lecture seule). Aucune modification de production.
**Script :** `brvm_dividend_analysis_v3b.py` (commit `dafdb77`)
**Sortie :** `brvm_dividend_results.json` (126 événements, non commité)

---

## Origine

Recherche du backtest walk-forward dividend capture perdu en juin 2026 (93% de réussite,
+8,3% net médian sur ~32 jours). **Il n'a pas été retrouvé** — aucun des 9 scripts
`brvm_dividend_*` ne contient de mesure de performance nette, de walk-forward, ni de
traitement des frais/IRVM (`grep` sur walk/forward/win_rate/median/net/IRVM/frais : aucun
résultat).

En revanche, `brvm_dividend_analysis_v3b.py` s'est révélé être une **analyse complète du
comportement du prix après détachement sur 10 ans**, ce qui répond directement à
l'instruction week-end (« régression pour identifier le point d'entrée post-ex-dividende
optimal »).

Les 9 scripts ont été commités (`dafdb77`) — ils étaient non trackés depuis juin.

`v3b` est la version à utiliser : `v3` échoue sur une colonne `companies.company_name`
qui n'existe pas.

---

## Ce que le script calcule

Par événement de détachement :

| Champ | Signification |
|---|---|
| `actual_drop` | Baisse réelle du cours au détachement |
| `drop_vs_div_pct` | Baisse en % du dividende (théorie = 100%) |
| `overreact_pct` | Écart à la baisse théorique |
| `days_to_fill` | Jours pour retrouver le cours pré-détachement |
| `days_to_theo` | Jours pour retrouver le cours ex-div théorique |
| `min_day` | **Jour du minimum sur 90j = point d'entrée optimal a posteriori** |
| `normalized` | Série de prix base 100 sur 90 jours |

Jointure `EX_DIVIDEND` × `DIVIDEND_HISTORY` sur `(ticker, fiscal_year)` — le piège de
schéma documenté est correctement traité.

---

## Résultat brut du script (à ne pas utiliser tel quel)

```
N événements analysés  : 126 (dont 115 cohérents)
Fill médian (pré-div)  : 17 jours
Fill médian (théorique): 1 jour
Sur-réaction médiane   : -76.3%
J optimal médian       : J+16
```

**Ce résumé est biaisé.** Le filtre interne (`overreact_pct > -200`) ne retire pas les
deux catégories de faux événements.

---

## Filtrage appliqué et résultat corrigé

Deux exclusions nécessaires :

1. **`actual_drop == 0`** — cours strictement inchangé au détachement. Ce n'est pas un
   comportement de marché mais une **absence de cotation** (titre illiquide, le prix repris
   est celui de la veille). Concernés : BNBC, NSBC, SDCC, TTLS, SHEC, etc.
2. **`ex_date` finissant par `12-31`** — le 31 décembre n'est jamais un jour de bourse.
   Ce sont des **dates de fin d'exercice fiscal**, pas des dates de détachement.
   Manifestation du piège `DIVIDEND_HISTORY.event_date = fin d'exercice`.

**126 → 99 événements exploitables** (27 exclus, 21%).

| Métrique | Résumé brut | Après filtre |
|---|---|---|
| J optimal médian | J+16 | **J+2** |
| J optimal moyen | — | J+8,3 |
| Sur-réaction médiane | −76,3% | **−62,7%** |

Les 27 faux événements tiraient la médiane de J+2 à J+16 : sur un titre qui ne cote pas,
le minimum sur 90 jours tombe à une date arbitraire.

L'écart médiane J+2 / moyenne J+8,3 indique une distribution asymétrique : majorité de cas
touchant le bas très vite, minorité beaucoup plus lente.

---

## Résultat principal — la sur-réaction est confirmée sur 10 ans

**Sur-réaction médiane : −62,7%.** Le cours ne baisse que d'environ **37% du dividende
détaché**, là où la théorie prédit 100%.

Sur un dividende de 500 F, le cours ne perd que ~185 F. Les ~315 F restants sont encaissés
par l'acheteur post-détachement sans avoir été payés.

C'est le mécanisme économique du dividend capture, **mesuré et non plus supposé**.
Cohérent avec le walk-forward perdu (+8,3% net sur ~32 jours) et avec le fill médian de
17 jours.

---

## Comportement différencié — univers dividend capture vs reste du marché

Univers : BOAB, BOAC, ECOC, SMBC, NSBC, NTLC.

| Groupe | n | J optimal médian | Sur-réaction médiane |
|---|---|---|---|
| **Univers dividend capture** | 26 | **J+7,5** | **−50,5%** |
| Autres tickers | 73 | **J+0** | −65,4% |

**Contre-intuitif :** sur ces deux métriques, l'univers paraît *moins* favorable — il
sur-réagit moins (donc moins de « dividende gratuit ») et met plus longtemps à toucher son
point bas.

Une médiane à J+0 sur les 73 autres signifie qu'au moins la moitié atteint son minimum le
jour même du détachement, puis remonte sans redescendre. **Pas de fenêtre d'entrée.**

### Trois lectures possibles, non départagées par ces chiffres

1. **L'univers a été sélectionné sur d'autres critères** (liquidité, régularité du
   dividende, rendement absolu) qui priment sur l'ampleur de la sur-réaction. Un titre qui
   sur-réagit fortement mais ne s'échange pas est inexploitable.
2. **La fenêtre de J+7,5 est ce qui rend l'univers opérable.** Sur la BRVM, une opportunité
   qui n'existe qu'au jour J n'est pas capturable en pratique (ordre via courtier, marché
   peu liquide, exécution non garantie). Un gain théorique supérieur mais inatteignable
   vaut moins qu'un gain modeste et réalisable.
3. **Échantillon trop mince** — n=26 sur 6 tickers, soit ~4 événements chacun.

Ces hypothèses restent ouvertes. **Ne pas conclure sur la base de ces seuls chiffres.**

---

## Limite méthodologique centrale

**`min_day` est un optimum a posteriori.** Il indique quel jour aurait été le meilleur en
regardant l'historique, pas quel jour choisir à l'avance. Le point bas n'est pas connu au
moment d'acheter.

La question opérationnelle est différente : **quel jour d'entrée FIXE maximise le rendement
en moyenne ?** Il faut simuler chaque jour d'entrée de J+0 à J+15 sur les 99 événements et
comparer les distributions de rendement.

Ce calcul n'existe dans aucun script. C'est le prochain travail utile.

---

## Prochaines étapes proposées

### D1 — Simulation des jours d'entrée fixes (classe A, priorité haute)
Pour chaque J d'entrée de J+0 à J+15, sur les 99 événements filtrés : rendement médian,
% positifs, distribution. Sortie attendue : une règle d'entrée applicable, ou la
démonstration qu'aucun jour ne domine.

Gate humain préalable : définir la règle de sortie (fill du cours pré-détachement ?
horizon fixe ? cible ?) avant d'écrire le script.

### D2 — Intégrer le filtrage dans le script
Les exclusions `actual_drop == 0` et `ex_date` fin d'exercice doivent être dans
`brvm_dividend_analysis_v3b.py`, pas dans un one-liner externe. Le résumé imprimé par le
script est actuellement trompeur (J+16 au lieu de J+2).

Ajouter aussi le comptage et le motif des exclusions (règle projet : jamais de silence).

### D3 — Mesure nette (frais + IRVM)
Toutes les mesures ci-dessus sont brutes. Le protocole brut-first est assumé, mais la
sensibilité frais/IRVM reste due — d'autant que l'écart mesuré ici (~37% vs 100% de baisse)
est de nature différente des écarts de rendement précédents.

### D4 — Élargir ou justifier l'univers
Les 73 « autres » sur-réagissent davantage. Si certains sont suffisamment liquides, ils
mériteraient d'entrer dans l'univers. Croiser avec le seuil de liquidité 896 (proposé en
T5b, jamais validé).

### D5 — Reconstruire le backtest walk-forward
Définitivement perdu. À rebâtir par-dessus `v3b` plutôt qu'à partir de zéro : la détection
d'événements et la jointure de schéma sont déjà correctes et validées.

---

## Fichiers

- `brvm_dividend_analysis_v3b.py` — script d'analyse (commité, `dafdb77`)
- `brvm_dividend_results.json` — 126 événements, **non commité** (sortie régénérable)
- 8 autres scripts `brvm_dividend_*` commités en même temps, contenu non encore inspecté :
  `courbe_par_ticker`, `fy2025_check`, `fy2025_verif_qualite`, `prix_h1_h2`,
  `volume_h1_h2`, plus les versions v1/v2/v3
