# Où passe l'argent, et ce qui peut baisser

  

## Contexte

  

Le coût paraît élevé : ****2,067 €/L en option B****, 207,44 € de trésorerie pour

6 brassins (90 L). Demande : analyser ce qui pourrait être optimisé, ****sans**

**toucher au code ni aux recettes****, et ****sans changer de boutique**** (une seule

commande).

  

Ce document est donc une ****analyse, pas un plan d'implémentation****. Aucun

fichier à modifier. Le résultat exploitable est une liste de gestes d'achat et

de procédé, chiffrés.

  

## Décomposition du coût actuel (option B, mix par défaut, 90 L)

  

| Poste | € | part | €/L |

|---|---|---|---|

| Houblon | 74,59 | 40 % | 0,829 |

| Malt | 61,77 | 33 % | 0,686 |

| Consommables | 49,70 | 27 % | 0,552 |

| Concassage | 0,00 | — | — |

| ****Total**** | ****186,06**** | | ****2,067**** |

  

Deux choses sautent aux yeux : ****le houblon est le premier poste****, pas le malt,

et ****les consommables pèsent plus que le concassage n'a jamais pesé**** — dont

33,00 € de levure seule (5,50 € × 6 brassins), soit 66 % du poste.

  

## Ce qui n'est PAS un levier (vérifié, à écarter)

  

****Brasser plus gros.**** C'est la première idée et elle est fausse ici. Le keg

fermenteur de 18,9 L sature avant la cuve, sur *_toutes_* les recettes :

  

| Recette | Volume keg max | Contrainte |

|---|---|---|

| Blonde 5.0 | 16,22 L | keg fermenteur |

| West Coast 6.5 | 16,06 L | keg fermenteur |

| NEIPA sans alcool 0.5 | 15,67 L | keg fermenteur |

| NEIPA legere 4.5 | 15,45 L | keg fermenteur |

| Hazy ananas 6.5 | 15,02 L | keg fermenteur |

| NEIPA forte 8.0 | ****14,71 L**** | keg fermenteur |

  

(garde de 1,5 L pour le krausen, empâtage plafonné à 33,5 L dans la cuve de 35)

  

Les 15 L actuels sont déjà le maximum tenable, et la NEIPA forte est même

****au-dessus**** de ce que son houblonnage à cru permet. Passer à 16 L ne

gagnerait que 0,087 €/L et ne passerait pas sur 4 recettes sur 6.

  

****Changer de boutique.**** `brewshop.db` contient bien un second fournisseur

(`lecomptoirdubrasseur`, 204 produits, scrapé le 2026-08-05) absent des CSV de

prix, et il vend du ****malt au poids, au gramme près, concassé à la demande****

(Extra Pale 2,60 €/kg, Munich 2,30, Blé 2,60) — donc zéro sur-achat, zéro

dormant, zéro moulin. Mais ****sous la contrainte « une seule boutique », c'est**

**fermé**** :

  

- ****Azacca n'existe pas chez Le Comptoir**** (65 houblons, pas celui-là), et il

  sert dans 3 recettes sur 6 — NEIPA forte, Hazy ananas, sans alcool.

- Les ****flocons d'avoine y sont en rupture**** (au poids *_et_* en 25 kg). Le seul

  avoine en stock est du malt d'avoine 5 EBC, un autre ingrédient.

  

Autobrasseur reste donc obligatoire. À noter pour plus tard : en acceptant deux

commandes, le panier mixte tombait à 165,96 € au lieu de 207,44 € — mais les

frais de port ne sont modélisés nulle part, donc le gain n'est pas prouvé.

  

## Les leviers réels, par ordre de rendement

  

### 1. Réutiliser la levure — −0,275 €/L (−13 %)

  

Le plus gros levier, et il ne coûte rien. 5,50 € par brassin de levure neuve,

alors que la lie d'un brassin repitche 3 à 5 fois. Amortie sur 4 brassins :

5,50 → 1,38 €, soit ****−24,75 € par tournée de 6****.

  

Ce qui rend la chose facile ici : ****4 recettes sur 6 partagent la Verdant /**

**London Ale III**** (légère, forte, Hazy, Blonde). Il suffit de les enchaîner du

moins dense au plus dense — Blonde 5,0 → NEIPA légère 4,5 → Hazy 6,5 → NEIPA

forte 8,0 — et de récolter la lie à chaque transfert.

  

La West Coast (US-05) et la sans-alcool (LA-01) restent sur leur propre sachet :

la LA-01 ne se repitche pas raisonnablement, un moût sucré peu alcoolisé ne se

défend pas.

  

### 2. Acheter le houblon au kilo et congeler — −0,190 €/L (−9 %)

  

Le houblon est acheté en 100 g et 250 g, à 61,80–74,50 €/kg, alors que les

mêmes variétés existent en kilo à 48,95–57,00 €/kg chez le même fournisseur :

  

| Houblon | Besoin/tournée | Format actuel | Meilleur format | Gain/tournée |

|---|---|---|---|---|

| Citra | 485,3 g | 250 g → 65,40 €/kg | 1 kg Yakima → 49,95 | 7,50 € |

| Mosaic | 221,5 g | 250 g → 69,80 €/kg | 1 kg Yakima → 48,95 | 4,62 € |

| Azacca | 282,7 g | 100 g → 74,50 €/kg | 250 g → 61,80 | 3,59 € |

| Columbus | 87,2 g | 100 g → 72,50 €/kg | 250 g → 57,00 | 1,35 € |

| | | | ****total**** | ****17,06 €**** |

  

Le modèle refuse ces formats parce que `SUR_ACHAT_MAX = 1,75` interdit d'acheter

plus de 1,75 × le besoin d'une tournée. C'est la bonne règle pour un achat isolé,

mais ****le houblon sous vide au congélateur tient 2 ans**** : un kilo de Citra couvre

2 tournées, un kilo de Mosaic en couvre 4,5. Sur cet horizon le sur-achat n'en est

pas un.

  

Cas particulier ****Azacca**** : le besoin est de 282,7 g, et le format 250 g est

rejeté pour 5,3 g — 2 × 250 g = 500 g dépasse le plafond de 494,7 g. Acheter

quand même les 2 × 250 g coûte 8,55 € de trésorerie en plus et met 200 g de côté

à un tarif 17 % meilleur. Ça se rentabilise dès la tournée suivante.

  

### 3. Recaler le rendement — −0,046 €/L (−2 %)

  

`RENDEMENT = 0.70` est plat alors que le rapport grain:eau varie de 2,6× entre

les recettes. Passer à 75 % réel (mouture plus fine, empâtage plus long, sac

mieux essoré) économise 4,11 € de malt par tournée. Faible, parce que le malt en

sac de 25 kg est déjà bon marché — mais c'est gratuit, ****et ça corrige surtout un**

**défaut de justesse**** : à 70 % supposé et 75 % réel, les bières sortent au-dessus

du degré annoncé, ce qui est un problème d'étiquette sur la sans-alcool.

  

## Où ça mène

  

| | Malt | Houblon | Conso. | Total | €/L |

|---|---|---|---|---|---|

| Aujourd'hui (option B) | 61,77 | 74,59 | 49,70 | 186,06 | ****2,067**** |

| + levure réutilisée ×4 | 61,77 | 74,59 | 24,95 | 161,31 | ****1,792**** |

| + houblon au kilo, congelé | 61,77 | 57,53 | 24,95 | 144,25 | ****1,603**** |

| + rendement recalé à 75 % | 57,66 | 57,53 | 24,95 | 140,14 | ****1,557**** |

  

****−0,51 €/L, soit −25 %****, sans toucher une recette, sans changer de boutique,

sans matériel neuf. Les deux tiers du gain viennent de la levure et du format de

houblon.

  

## Contrepartie à accepter

  

Le levier 2 se paie en trésorerie et en place au congélateur : acheter Citra et

Mosaic au kilo, c'est ~99 € de houblon d'avance au lieu de ~50 €, immobilisés sur

2 à 4 tournées. Le levier 1 impose un ordre de brassage et une hygiène de récolte

de lie. Ni l'un ni l'autre ne change une recette.

  

## Vérification

  

Tous les chiffres ci-dessus sortent du modèle en place, sans le modifier :

  

```bash

python3 cout-biere/calcul.py          # 2.07 EUR/L option B, base de comparaison

python3 -c "import sys;sys.path.insert(0,'cout-biere');import modele;\

e=modele.charger();print(modele.calculer(e,dict(e['mix_defaut']))['options']['B']['eur_par_L'])"

```

  

Les volumes max par recette se rejouent avec `eau.volumes()` en faisant varier

`modele.VOLUME_L` sous la double contrainte fermenteur ≤ 17,4 L / empâtage ≤ 33,5 L.

Le catalogue du second fournisseur se relit dans `brewshop.db`, table `variants`

jointe à `products` sur `source = 'lecomptoirdubrasseur'`.

  

## Suites possibles (hors périmètre, non demandées)

  

- Ajouter les frais de port au modèle, seul moyen de trancher honnêtement la

  question des deux boutiques.

- Intégrer `lecomptoirdubrasseur` aux CSV de prix, avec le malt au poids comme

  troisième scénario d'achat à côté de A et B.

- Rendre `SUR_ACHAT_MAX` sensible à un horizon de tournées plutôt qu'à une seule.