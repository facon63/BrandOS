# Intro « Krok et Mil » — 15 s, motion design 2D cartoon, tout en code

État : **étape 2 / 8 — détourage et découpe en calques (en attente de validation)**,
revue adversariale (5 relecteurs + vérificateurs) traitée et contrôle automatique des poses ajouté.

Seules entrées : `assets/refs/83.png` (Krok) et `assets/refs/90.png` (Mil). Tout le reste est
produit par code (aucun asset externe, aucun SVG, aucune vectorisation des références).

## Structure

```
assets/refs/                 références fournies (83.png, 90.png)
assets/characters/<nom>/     calques raster ×4 + rig.json (générés)
tools/charkit/               découpe : segmentation par le trait, reconstruction des zones cachées,
                             parties construites de Mil, variantes d'yeux, upscale « spécial trait »
tools/build_characters.py    génère assets/characters/*
tools/review/                planches de validation + contrôles automatiques (checks.py)
engine/puppet.py             marionnette raster : hiérarchie + skinning par maillage, rendu Skia
review/                      planches de l'étape 2
CHARACTER_SHEET.md           fiche personnages (proportions, hex, trait, signatures, limites)
```

## Commandes

```bash
sudo apt-get install -y libegl1   # bibliothèque système requise par skia-python sous Linux
npm run setup              # dépendances Python (numpy, scipy, opencv, scikit-image, pillow, skia-python)
npm run build:characters   # ~35 s : calques + rig
npm run review:step2       # planches review/etape2_*.png
npm run review:checks      # contrôle automatique : trous / bords sans encre sur 19 poses × 2 personnages
```

La commande unique `npm run render` (vidéo, musique, logo, stinger) sera complétée aux étapes 4 à 6.
