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
