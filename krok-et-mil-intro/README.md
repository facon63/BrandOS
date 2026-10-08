# Krok et Mil — intro YouTube (10 s)

Intro animée générique de la chaîne gaming **Krok et Mil** : 2D cartoon, 4 univers, musique
chiptune/funk originale et SFX, rendue en MP4.

> **État : preuve de concept (étape 2), en attente de validation.**
> Les 4 images clés, la planche de modèle et l'extrait audio sont dans [`poc/`](poc/).
> L'animation complète, le logo PNG, le stinger et le README définitif viennent après validation.

## Contenu

| Chemin | Rôle |
|---|---|
| `CHARACTER_SHEET.md` | Analyse des références : couleurs échantillonnées, proportions, règle de hauteur, tenues |
| `assets/refs/` | Références fournies (`83.png` = Krok, `90.png` = Mil) |
| `tools/trace_heads.py` | Vectorise les têtes depuis les références → `src/characters/traced/*.ts` |
| `tools/check_heights.py` | Vérifie automatiquement que Krok et Mil ont la même hauteur (± 2 %) |
| `src/rig/` | Personnages en calques SVG (têtes tracées + corps dessinés), poses, tenues |
| `src/scenes/` | Décors et mises en scène des 4 univers |
| `src/props/`, `src/fx/` | Accessoires, créatures, onomatopées, logo |
| `src/palette.ts`, `src/timing.ts` | Couleurs et grille temporelle (128 BPM, drop à 7,5 s) |
| `audio/` | Synthèse procédurale (numpy/scipy), mixage, mastering ; `cues.json` = instants des SFX |
| `poc/` | Livrables de la preuve de concept |

## Prérequis

- Node 18+ (`npm install`), Python 3.10+ avec `numpy scipy soundfile pyloudnorm`
  (+ `opencv-python-headless pillow vtracer` pour re-tracer les têtes), `ffmpeg`.
- Un Chromium headless : Remotion télécharge le sien, ou bien
  `export REMOTION_BROWSER=/chemin/vers/chrome-headless-shell`.

## Commandes

```bash
npm install
npm run poc            # régénère poc/ : 4 images clés, planche de modèle, extrait audio 3 s, contrôle des hauteurs
npm run studio         # prévisualisation interactive Remotion
npm run trace          # re-vectorise les têtes depuis assets/refs
npm run check:heights  # contrôle de la règle « même hauteur »
python3 audio/compose.py --excerpt 6.5625 3   # musique + SFX complets et un extrait
```
