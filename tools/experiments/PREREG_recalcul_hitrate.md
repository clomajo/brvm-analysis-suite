# Pre-enregistrement — recalcul du hit rate V1 sur donnees BOC

**Date** : 05/09/2026
**Redige AVANT tout calcul.** Aucun resultat n'a ete consulte.

## Contexte

`brvm_decisions_results` contient 4 075 verifications, toutes datees du
03/04 au 15/08/2026 — soit integralement dans la fenetre ou `historical_data`
etait corrompue (ADR-052). `prix_signal` et `prix_verification` proviennent
tous deux de cette table polluee.

Hit rate actuellement en base, sur donnees polluees :
- ACHAT      : 775 / 1 232 = 62,9 %
- SURVEILLER : 1 251 / 2 460 = 50,9 %
- EVITER     : 181 / 383 = 47,3 %

## Objet

Recalculer les memes verifications en prenant les prix dans `boc_cote`
(source officielle, datation certaine) au lieu de `historical_data`.

Ce que ceci mesure : **la performance des signaux reellement emis**, evaluee
avec les vrais prix. Ce n'est PAS la performance qu'aurait eue V1 sur donnees
saines — les signaux eux-memes ont ete generes a partir de prix decales et
auraient porte sur d'autres titres.

## Regles fixees avant lecture

**Perimetre** : signaux ACHAT uniquement pour le seuil principal. Les autres
categories sont rapportees sans seuil.

**Exclusions** : tout signal dont `signal_date` ou `verification_date`
n'existe pas dans `boc_cote` est **exclu et compte**. Aucun rattachement a une
seance voisine.

**Seuils d'interpretation** — hit rate ACHAT recalcule :

| Resultat | Interpretation |
|---|---|
| > 60 % | V1 tient. On poursuit. |
| 50 – 60 % | V1 plus faible qu'estime. A investiguer avant tout usage. |
| < 50 % | V1 ne bat pas le hasard. Statut du modele a remettre en question. |

**Aucune echappatoire.** Si le resultat tombe sous 50 %, on ne cherchera pas
un sous-perimetre plus favorable (par secteur, par tier de liquidite, par
horizon) pour sauver le chiffre. Toute analyse par sous-groupe sera une
question distincte, posee apres.

**Limites reconnues d'avance** :
- Population de signaux non representative (generes sur prix faux)
- Aucune comparaison au benchmark marche — un hit rate brut ne dit pas si le
  modele bat l'indice
- Fenetre courte (4,5 mois) et observations correlees en coupe

---

# RESULTAT — 05/09/2026

Calcul execute apres commit du pre-enregistrement (`18877a2`).

## Exclusions

| Motif | Lignes |
|---|---|
| `signal_date` absente de `boc_cote` | 1 457 |
| `verification_date` absente | 834 |
| **Total exclu** | **2 291 / 4 075 (56,2 %)** |

Le calcul porte sur **1 784 verifications**, pas 4 075.

## Hit rate recalcule sur prix BOC

| Signal | Correct / total | Taux | Base polluee | Ecart |
|---|---|---|---|---|
| ACHAT | 346 / 547 | **63,3 %** | 62,9 % | +0,3 pt |
| SURVEILLER | 672 / 1 069 | 62,9 % | 50,9 % | +12,0 pts |
| EVITER | 60 / 168 | 35,7 % | 47,3 % | −11,5 pts |

**Verdicts individuels changes : 730 / 1 784 (40,9 %).**

## Verdict selon le pre-enregistrement

ACHAT a **63,3 %**, au-dessus du seuil de 60 %. Regle appliquee : **V1 tient,
on poursuit**. Aucun sous-perimetre n'a ete cherche.

## Ce que le resultat montre reellement

**1. La stabilite d'ACHAT est fortuite.** 0,3 point d'ecart alors que 40,9 %
des verdicts individuels ont bascule. Les erreurs de datation se compensaient :
bruit symetrique, pas biais directionnel. L'agregat etait stable par accident,
pas parce que la mesure etait bonne.

**2. Les trois categories ont le meme taux de hausse sous-jacent.**

- ACHAT : 63,3 % de hausses
- SURVEILLER : 62,9 % de hausses
- EVITER : 35,7 % de reussite = **64,3 % de hausses**

Environ 63 % dans les trois cas. **V1 ne discrimine pas** : quel que soit le
signal emis, le titre monte dans ~63 % des cas sur la periode. Ce chiffre n'est
pas la performance du modele, c'est le **taux de base du marche**.

**3. Le seuil du pre-enregistrement etait le mauvais indicateur.** Un seuil
absolu (60 %) ne pouvait pas detecter ce probleme : le modele passe le test tout
en montrant qu'il ne separe pas ses categories. Le seuil aurait du etre relatif
au taux de base de l'univers. Erreur de conception du test, notee et non
corrigee a posteriori — le pre-enregistrement reste ce qu'il etait.

## Limites

- Population de signaux non representative : generes sur prix faux, V1 aurait
  selectionne d'autres titres sur donnees saines
- 56,2 % d'exclusions
- Fenetre de 4,5 mois, observations correlees en coupe
- Aucune comparaison au benchmark marche

## Suite

Test distinct, avec son propre pre-enregistrement : comparer le taux de hausse
des signaux ACHAT a celui de **l'univers entier sur les memes dates**. C'est la
seule mesure qui dira si V1 selectionne, ou s'il decrit la tendance generale.

Ce test remplace la question "quel est le hit rate de V1" par "V1 fait-il mieux
que prendre 47 titres au hasard". C'est la question qui compte.
