# CHARACTER SHEET — Krok et Mil

Fiche établie à partir des deux seules références fournies, analysées pixel par pixel
(`assets/refs/83.png` = Krok, `assets/refs/90.png` = Mil). **Les images font foi** : là où elles
contredisent la description du brief, c'est l'image qui est retenue (écarts signalés ⚠).

Méthode : couleurs = médianes de zones (k-means 22 classes en Lab + échantillons ciblés, trait
exclu), proportions = boîtes englobantes de l'alpha (> 0,5), épaisseur de trait = coupes
transversales du contour.

## 0. Les fichiers source

| | 83.png (Krok) | 90.png (Mil) |
|---|---|---|
| Format | PNG RGBA 500×500, fond déjà transparent | PNG RGBA 500×500, fond déjà transparent |
| Cadrage | Plein pied, de face légèrement trois-quarts | **Coupé à la taille** (y = 499) : jambes, bas du pantalon, poignets et mains absents |
| Qualité alpha | Bord net, pixel de transition sombre (pas de halo blanc). Intérieur à alpha 253–254 (bruit) → forcé à 255 ; 2 trous de 1 px dans la chaussure gauche → bouchés | Bord net, propre |
| Texture | Léger grain/papier sur les aplats, cel-shading à 2–3 tons, liseré clair (rim light) | Idem, grain un peu plus visible sur le t-shirt |

## 1. Échelle commune et hauteur (règle absolue)

L'unité **u** = 1 pixel de la référence de Krok.

| | Krok | Mil |
|---|---|---|
| Sommet → semelle | casquette y=47 → semelle y=473 : **426 u** | épi le plus haut y=89 → semelle construite y=674 : 585 px-Mil × 0,728 = **425,9 u** |
| Écart de hauteur | — | **0,03 %** (tolérance demandée : ±2 %) |
| Facteur d'échelle | 1 | **0,728** px-Krok par px-Mil |

Pourquoi 0,728 : c'est le facteur qui donne à la fois des **visages à la même échelle**
(écartement des pupilles : Krok 40 u, Mil 52,6 px-Mil = 38,3 u) et une **longueur de jambe
visible égale** à celle de Krok (≈ 140 u). Dans le moteur, chaque personnage est placé par
« point au sol + hauteur totale en pixels » : la même valeur pour les deux garantit l'égalité
de taille dans tous les plans.

## 2. KROK — rond et trapu

### Silhouette et proportions (u)

| Mesure | Valeur | Remarque |
|---|---|---|
| Hauteur totale | 426 | casquette comprise |
| Largeur max | 190 (x 156→345) | au niveau des manches, y≈290 |
| Tête (sommet casquette → menton) | ≈ 141 (33 % de la hauteur) | grosse tête cartoon |
| Visage seul (bord casquette → menton) | ≈ 95 × 77 | |
| Pupilles (centres) | (244, 117) et (284, 117) → 40 | |
| Épaules / buste | ≈ 182 de large | hoodie ample, arrondi en tonneau |
| Jambes visibles (ourlet → semelle) | ≈ 140 (33 %) | jambes courtes, légèrement écartées, pied droit tourné vers l'extérieur |
| Pose de référence | de face, buste très légèrement tourné vers la gauche de l'image (manche droite vue de profil, étroite) | |

### Palette (hex échantillonnés)

| Élément | Principal | Ombre(s) | Lumière(s) |
|---|---|---|---|
| **Hoodie (couleur d'identité)** | **#833280** | #70296E, #551E59, #431848 | #8C568F, rim light #D69CC6 |
| Intérieur du col (V) | #3C2E33 | | |
| Cheveux | #F9CE10 | #DFAB0B, #C78D09, #A07226 | #FCE62C, #FCF4B8 |
| Peau | #FEC393 | #E08C72 (joues, cou #DE816E) | |
| Moustache / bouc / mouche | #B58432 (≈ #B17C31) | #6C5114 | |
| Iris | #251D0F (brun très foncé) | | blanc de l'œil #F3EAE5 + reflet blanc |
| Casquette | #35322B | #181416 | sangle #3E392F |
| Pantalon | #413E35 | #37332C, #22201E | #5C514B |
| Chaussures | #3C3830 / #262420 | | reflets #847462 |
| Trait | #040203 | | |

⚠ Le brief annonçait un violet « ≈ #6B2D8C » : la référence donne **#833280** (plus
rouge, plus lumineux). C'est #833280 qui sert de couleur d'identité (logo « KROK », tenues).

### Yeux, bouche, visage

- Yeux en **amande**, mi-ouverts, regard légèrement vers la droite de l'image ; paupière
  supérieure épaisse et noire, pli de paupière fin au-dessus, iris brun quasi noir avec un
  petit reflet blanc, cils bas discrets.
- Sourcils noirs épais, légèrement arqués.
- Nez rond dessiné d'un trait ouvert (narines en « c »).
- **Bouche** : petit sourire tranquille (trait fin courbe) sous une **moustache blond-brun
  épaisse** dont les pointes descendent ; mouche brune sous la lèvre ; **bouc** en barbe courte
  dentelée sur le menton.
- Joues pleines avec une ombre rosée (#E08C72) sur les bords du visage.

### Éléments signature (à conserver dans tous les univers)

1. Cheveux **blond vif, longs, ondulés** jusqu'aux épaules, mèches en vagues séparées par des
   traits noirs.
2. **Casquette noire portée à l'envers** : visière vers l'arrière-gauche, ouverture avec mèche
   blonde et sangle à rivets visible sur le front.
3. Moustache + bouc blond-brun.
4. Silhouette ronde : hoodie en tonneau, gros poignets côtelés, poche kangourou, deux cordons.

## 3. MIL — plus fin

### Silhouette et proportions (px de la réf. de Mil → u)

| Mesure | px-Mil | u (×0,728) | Remarque |
|---|---|---|---|
| Hauteur totale (construite) | 585 | 426 | jambes construites |
| Tête (épi → bas de la barbe) | ≈ 173 | ≈ 126 (30 %) | |
| Largeur casque compris | 175 | 127 | |
| Pupilles | (201, 188) et (252,6, 188) → 52,6 | 38,3 | yeux ronds |
| Épaules (t-shirt) | 179 | 130 | **71 % de la largeur de Krok** |
| Taille (ourlet du t-shirt) | y ≈ 483 | | |
| Jambes (ourlet → semelle) | 191 | 139 | construites |

### Palette (hex échantillonnés)

| Élément | Principal | Ombre(s) | Lumière(s) |
|---|---|---|---|
| **T-shirt (couleur d'identité)** | **#95B822** | #8DB01F, #648713 | #9DBE24, liseré #CFEF55 |
| Peau | visage #FBCBA6, bras #FBC399 | #DC9370 | #FCE1C6 |
| Cheveux | #573727 | #3F2818 | #704A2A, #956B51 |
| Bouc / moustache | #71472A | #3F2818 | |
| Casque audio | #585D60 | #434B4E, #2F3639 | #7F7E80, #939696 (arceau #8A8687) |
| Pantalon (bande visible) | #2D3538 (gris-ardoise) | | |
| Yeux | blanc #FEFEFE, pupille #060505, ombre bleutée #C8D4DC | | |
| Sourcils / trait | #020201 / #030302 | | |

⚠ Le brief annonçait un vert « ≈ #8DC63F » : la référence donne **#95B822** (plus jaune,
« vert lime »). C'est #95B822 qui sert de couleur d'identité.

### Yeux, bouche, visage

- Yeux **ronds** cerclés de noir, **paupières lourdes à mi-hauteur** (le tiers supérieur du
  cercle est couleur peau, séparé par un trait épais) : **regard blasé**. Pupilles petites,
  juste sous la paupière, regard vers la droite de l'image.
- Sourcils noirs épais et droits.
- Nez en crochet dessiné d'un seul trait.
- **Bouche** : trait horizontal neutre, entouré d'un **bouc brun** (moustache reliée au bouc
  en « cadenas »), mouche sous la lèvre.
- Visage plus allongé que Krok, mâchoire marquée, cou fin.

### Éléments signature

1. **Épis bruns** désordonnés (pointe haute au centre, mèches qui partent vers la gauche).
2. **Grand casque audio gris** : arceau sur le dessus, coques sur les oreilles (coque droite
   vue de face, coque gauche vue de profil).
3. Bouc brun en cadenas.
4. **Regard mi-clos blasé** (variante « yeux ouverts » dessinée pour l'action, retour au blasé
   dès que ça se calme).

### Parties absentes de la référence → construites en code

| Partie | Construction | Pourquoi ainsi |
|---|---|---|
| Jambes / pantalon | Pantalon de Krok ré-échantillonné à la morphologie de Mil (×0,90 en largeur, ×1,37 en hauteur en px-Mil, soit 69 % de la largeur de Krok en u), recoloré (transfert Lab) vers le gris-ardoise #2D3538 de la bande visible | même trait, mêmes plis, même grain que la référence → style identique |
| Chaussures | Chaussures de Krok, échelle **uniforme** (×1,25 px-Mil = 0,91× Krok), liseré d'encre sur le haut exposé | aucune déformation, noires comme demandé |
| Taille | La bande de pantalon d'origine (y 485–499) est conservée et fondue sur 6 px dans le pantalon construit ; l'entrejambe vient du même pantalon | raccord invisible |
| Poignets | L'avant-bras coupé au cadre est prolongé de 9 px en étirant la dernière ligne (profil, ombrage et contours inclus), avec une légère conicité | raccord sans bracelet visible |
| Mains | Main gauche de Krok (même dessin, peau identique à 2 % près), à l'échelle du poignet de Mil ; main droite = miroir | style identique, aucune main « inventée » d'un autre trait |

## 4. Trait et rendu (commun aux deux)

- **Contour noir** (#030302–#040203) d'environ **2–2,5 px sur 426 px de hauteur**, soit
  **≈ 0,55 % de la hauteur du personnage** (contour extérieur un peu plus épais que les traits
  intérieurs, qui varient de 1 à 2 px). À l'écran : personnage de 700 px de haut → trait ≈ 3,8 px.
- Après mise à l'échelle commune, le trait de Mil est ~25 % plus fin que celui de Krok
  (sa référence est dessinée plus grande) ; écart jugé non gênant, compensable au rendu.
- **Cel-shading** à 2–3 tons + **rim light** clair sur un bord (Krok : manche/flanc droit en
  rose #D69CC6 ; Mil : flanc gauche en #CFEF55) + léger grain d'aplat.
- Règle pour tout ajout dessiné en code (tenues, accessoires, yeux) : **même encre, même
  épaisseur proportionnelle (0,55 % de la hauteur), cel-shading 2 tons, petit grain**.

## 5. Calques et rig (résultat de l'étape 2)

Calques raster ×4 dans `assets/characters/<nom>/layers/`, rig dans `rig.json`
(décalages, pivots, os, ordre z, parents).

| Krok (z croissant) | Mil (z croissant) |
|---|---|
| shoe_L, shoe_R (pivot cheville) | shoe_L, shoe_R *(construits)* |
| leg_L, leg_R (os hanche–genou–cheville) | leg_L, leg_R *(construits)* |
| torso (hoodie, capuche, cou, entrejambe) | pelvis *(bande d'origine + entrejambe)* |
| strings (cordons, balancier) | torso (t-shirt, cou) |
| arm_L, arm_R (os épaule–coude–poignet–main) | arm_L, arm_R (manche + avant-bras + main *construite*) |
| cap_brim (visière, derrière les mèches) | head (visage, barbe, yeux) |
| hair_L, hair_R (mèches, balancier) | eyes_open, eyes_closed *(variantes code)* |
| head (visage, barbe, yeux) | hair (épis, rebond) |
| eyes_closed *(variante code)* | headphones (arceau + coques, recolorable) |
| cap (dôme + mèche + sangle) | |

Zones cachées reconstruites (diffusion de couleur + grain + **contour d'encre redessiné**) :
flancs du buste sous les bras, cou sous le menton, capuche sous les mèches, haut des jambes
sous l'ourlet, pantalon sous les mains, crâne sous la casquette / la frange, haut des
chaussures sous le pantalon, cheveux sous l'arceau du casque.

## 6. Invariants pour les 5 univers

- Ne changent **jamais** : contours, yeux (hors variantes ci-dessus), expressions de base,
  proportions, hauteur commune, couleurs de peau/cheveux.
- Changent par univers : **vêtements et accessoires uniquement**, posés par-dessus les calques
  de base, toujours avec une dominante **violet #833280 (Krok)** et **vert #95B822 (Mil)**.
- Krok : casquette à l'envers toujours identifiable (abîmée, sous la capuche, visible dans le
  casque bulle), cheveux blonds ondulés, bouc, silhouette ronde.
- Mil : casque audio gris toujours **sur les oreilles** (rouillé/scotché, stylisé chevalier,
  visible dans le casque bulle), épis bruns, bouc, regard blasé qui revient.

## 7. Limites connues (franchise)

- Références de face uniquement : pas de vrai profil ni de dos (plans remplacés par
  face/trois-quarts, miroir, échelle, caméra).
- Bras levés au-delà d'environ **110°** : l'épaule se pince (surtout la manche droite de Krok,
  vue de trois-quarts, très étroite). Les poses au-delà seront évitées ou traitées avec un
  pivot d'épaule relevé.
- Inclinaison de tête recommandée ≤ ±6° (au-delà, de petites zones de capuche reconstruites
  apparaissent sous les mèches de Krok).
- Résolution source 500×500 : les calques sont agrandis ×4 avec un upscale « spécial trait »
  (traits re-nettoyés, silhouette nette). Très bon jusqu'à ~900 px de hauteur de personnage à
  l'écran ; au-delà (gros plans visage plein cadre), un léger flou de texture devient visible.
