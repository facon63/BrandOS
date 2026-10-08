# CHARACTER SHEET — Krok et Mil

Sources : `assets/refs/83.png` (Krok) et `assets/refs/90.png` (Mil), 500 × 500 px, fond transparent.
Les couleurs ci-dessous sont **échantillonnées** sur ces images (médiane de zones homogènes, script
d'analyse dans l'historique du projet). Quand elles diffèrent de la description du brief, ce sont les images qui font foi.

## Style commun (les deux références)

| Élément | Constat sur les références | Règle pour l'intro |
|---|---|---|
| Contour | Noir quasi pur `#030202`, 2,5 à 3 px sur une image de 500 px, régulier, plus épais sur la silhouette extérieure | `INK = #0B0909`, 4 unités de rig sur le corps ; silhouette des têtes renforcée de 2,2 unités |
| Remplissage | Aplats + ombrage cel-shading discret (une teinte d'ombre, une teinte de lumière), léger grain de texture | Aplats + **une** ombre franche côté droit (lumière en haut à gauche) + reflets ponctuels ; pas de grain |
| Proportions | Cartoon adulte façon sitcom animée, grosse tête : Krok ≈ 3,2 têtes de haut | Identiques ; Mil ramené à la même grammaire (≈ 3,3 têtes) |
| Yeux | Contour noir épais, iris sombres, petit reflet blanc | Jamais redessinés : visages issus du tracé des références |
| Orientation | Les deux corps et visages sont en léger 3/4 tourné vers la gauche de l'image | Vue 3/4 gauche = vue « de face » du rig ; vue de dos dessinée pour l'univers 3 |

## Échelle et hauteur (règle absolue)

- Unité du rig = pixel de `83.png`. **Hauteur des deux personnages = 427 unités**, du sol au sommet
  (casquette de Krok, épis de Mil compris).
- Krok : sommet y = 46, semelles y = 473 sur `83.png` → 427 px, utilisé tel quel (échelle 1).
- Mil : `90.png` est un plan buste dessiné ≈ 1,33 × plus grand ; il est ramené à l'**échelle 0,75**.
  Sommet des épis y = 88 ; le sol (hors image) est placé à y = 88 + 427 / 0,75 ≈ 657 → 427 unités.
  Avec ce facteur, sa tête (130 u) a la taille de celle de Krok (134 u), ses épaules sont à la même
  hauteur (≈ −275 u), son t-shirt s'arrête à −129 u et ses jambes (dessinées, absentes de la référence)
  mesurent ≈ 129 u contre ≈ 140 u pour Krok.
- Vérification automatique : `python3 tools/check_heights.py` rend chaque tenue seule et mesure la
  hauteur en pixels. Résultat actuel : écart Mil / Krok entre −0,23 % et +0,70 % (tolérance ± 2 %).
  Les accessoires qui dépassent volontairement du crâne (antenne, plumet de Mil) sont exclus de la mesure.
- Placement à l'écran : un perso placé avec l'échelle `s` mesure `427 × s` px. Les deux sont toujours
  placés avec le même `s` lorsqu'ils sont à la même profondeur. Aucun gag de taille.

## KROK — couleur d'identité : violet `#83327F`

Silhouette **ronde et trapue**, en forme de poire (le hoodie s'élargit vers le ventre : 190 px au plus large).

| Zone | Description | Hex échantillonné |
|---|---|---|
| Hoodie (identité) | Violet ample, capuche autour du cou, 2 cordons, poche kangourou, poignets et bas côtelés | `#83327F` |
| Hoodie ombre | Côtés, dessous de poche | `#45194A` |
| Hoodie lumière | Reflets sur les bras | `#D69DC6` (référence), `#A65AA0` (aplat utilisé) |
| Cordons | Violet très sombre, embouts clairs | `#2A0F2B` |
| Casquette | Noire / anthracite, **portée à l'envers** : visière vers l'arrière-gauche, patte de réglage à l'avant avec une mèche blonde qui passe dans l'ouverture | `#35322B` |
| Cheveux | Blond vif, longs, ondulés jusqu'aux épaules, mèches cernées de noir | `#F9CC11`, ombre `#D09409` |
| Peau | Claire, joues rondes | `#FDC292`, ombre `#E1856E` |
| Yeux | En amande, iris brun très foncé avec reflet, sourcils noirs épais | iris `#2B2110`, sourcils `#140E0A` |
| Pilosité | Moustache fine + mouche + bouc, blond-brun | moustache `#A7712A`, bouc `#BA8A34` |
| Bouche | Simple trait, léger sourire | — |
| Col | T-shirt sombre visible dans l'encolure | `#3A3633` |
| Pantalon | Anthracite olive, ample, droit | `#413D34`, ombre `#242320` |
| Chaussures | Noires arrondies | `#3D3830` |

Repères (pixels de `83.png`) : sommet casquette 46 · sourcils 104-108 · yeux 112-122 · bas du bouc 180 ·
épaules 190 · bas du hoodie 333-340 · entrejambe 362 · bas du pantalon 445 · semelles 473.

**Éléments signature à garder dans tous les univers** : cheveux blonds ondulés, casquette à l'envers
(visible même sous la capuche médiévale : bande avant au front + visière qui dépasse), bouc, silhouette ronde, violet.

## MIL — couleur d'identité : vert `#9ABB24`

Silhouette **plus fine** (≈ 30 % plus étroite que Krok), bras longs et minces.

| Zone | Description | Hex échantillonné |
|---|---|---|
| T-shirt (identité) | Vert lime, manches courtes, col rond | `#9ABB24` |
| T-shirt ombre | Côté droit, plis | `#628513` |
| T-shirt lumière | Bord gauche | `#D5E05D` (référence), `#C9DD4E` (aplat utilisé) |
| Cheveux | Bruns, en épis désordonnés qui partent vers la droite, reflets plus clairs | `#583827`, reflet `#9F866D` |
| Casque audio | Grand casque gris sur les deux oreilles, arceau par-dessus les épis | `#575C5F`, sombre `#2B2F30`, clair `#8A8788` |
| Peau | Claire | `#F7CAAA`, ombre `#DE9572` |
| Yeux | Grands ronds blancs, **paupières mi-closes** (trait horizontal à mi-hauteur), petites pupilles noires : regard blasé | blanc `#FEFEFE` |
| Sourcils | Noirs, droits, épais | `#020201` |
| Nez | Pointu, avec trait d'aile | — |
| Pilosité | Bouc brun : moustache reliée au menton, mouche | `#704629` |
| Bouche | Trait droit, inexpressif | — |
| Pantalon | Non visible en entier : départ d'un pantalon sombre gris-bleu en bas de l'image ; dessiné dans le même style ample que celui de Krok | `#2E3639` |
| Chaussures | Absentes de la référence → mêmes chaussures noires arrondies que Krok | `#3D3830` |

Repères (pixels de `90.png`) : pointe des épis 88 · arceau 97-103 · sourcils 170 · yeux 175-200 ·
menton 263 · col 270-285 · épaules 290 · ourlet des manches 350-360 · bas du t-shirt 485.

**Éléments signature** : épis bruns, casque audio gris sur les oreilles (personnalisable : rouillé,
scotché, antenne, version « chevalier »), bouc, regard mi-clos. Le regard blasé est l'expression de base ;
il ne change que pendant une action (surprise, effort) et revient dès que ça se calme.

## Tenues par univers (seuls vêtements et accessoires changent)

| Univers | Krok (garde du violet) | Mil (garde du vert) |
|---|---|---|
| 1 · cartoon | Tenue de référence exacte | Tenue de référence exacte |
| 2 · post-apo | Hoodie violet rapiécé et poussiéreux, bas effiloché, casquette à l'envers abîmée (déchirure + pièce), lunettes de protection relevées sur la casquette, gants de cuir, épaulette de récupération | T-shirt vert + veste de cuir rapiécée ouverte, un gant, casque audio rouillé, scotché, avec antenne |
| 3 · médiéval | Tunique violette ceinturée, chaperon violet (capuche + petite cape) sur la casquette — visière et bande avant visibles —, bouclier rond en bois à emblème violet | Tunique verte ceinturée, casque audio devenu garde-oreilles de chevalier avec plumet vert, épée en bois |
| 4 · conclusion | Tenue de référence exacte | Tenue de référence exacte |

## Méthode de fabrication (et pourquoi)

1. **Têtes vectorisées depuis les références** (`tools/trace_heads.py`) : isolement de la tête par
   masque de couleur (on retire le violet du hoodie / le vert du t-shirt), agrandissement × 4,
   tracé couleur `vtracer`, puis contour de silhouette régulier. Résultat : visages, yeux, barbes,
   casquette et casque identiques aux références, nets à toute taille. Testé contre un redessin et un
   tracé « trait + aplats » séparés : c'est l'option qui garde le mieux la ressemblance.
2. **Corps redessinés en SVG, en calques** (`src/rig/Krok.tsx`, `src/rig/Mil.tsx`) : torse, bras
   (épaule / coude / poignet), mains, jambes (hanche / genou), chaussures. Formes, couleurs et repères
   relevés sur les références ci-dessus. Permet de poser, d'animer (squash & stretch) et de changer de tenue.
3. **Vues de dos** (univers 3) : dessinées dans le même style à partir des volumes de face.
4. **Expressions** : calques superposés au visage tracé (yeux fermés heureux pour Krok, yeux
   écarquillés pour les deux) ; l'expression de base reste le tracé d'origine.
