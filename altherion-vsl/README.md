# Altherion — VSL motion design

Vidéo de présentation du studio Altherion : 59,5 s en 1920 × 1080 et 60 i/s,
avec voix off, musique et sound design. Le script et le storyboard sont dans
[`SCRIPT.md`](SCRIPT.md).

Tout est généré par du code. L'animation est un canvas déterministe : chaque
image ne dépend que du temps `t`. Le son est synthétisé par Python à partir des
mêmes repères que l'image. Aucun logiciel de montage n'est nécessaire, et la
vidéo peut être régénérée à l'identique.

## Charte appliquée

| Élément | Valeur (Canva « Identité de marque ») |
|---|---|
| Nuit | `#0E1030` (fonds) |
| Violet cosmique | `#3B2A6B` (montagne, voxels, golem) |
| Or | `#E8C46A` (accents, logo, CTA) |
| Blanc stellaire | `#F4F1E8` (texte ; jamais de blanc pur) |
| Cyan pâle | `#8FD8E8` (technique, HUD, lumière du golem) |
| Titres | Cormorant Garamond, capitales, Light ou Regular, interlettrage +200 à +300 |
| Texte et incrustations | Manrope, Regular et SemiBold |
| Logo | Le sommet étoilé : un « A » en sommet, une ligne de neige, une étoile unique légèrement au-dessus |
| Personnages | Golem de lumière évolutif et fondateur (narrateur) |
| Ton | Épique, autodérisoire, sincère |

Le logo est reconstruit en vectoriel à partir de la description de la charte
(`src/world.js` → `LOGO`), le fichier vectorisé n'existant pas encore. Il
suffira de remplacer cette géométrie quand il sera prêt.

## Anonymat du fondateur

La charte impose l'anonymat (avatar stylisé, comptes séparés). Ce dépôt est
**public**, donc :

- la photo du fondateur et ses dérivés reconnaissables sont exclus de Git
  (`.gitignore`) ;
- la version **avatar** (silhouette en contre-jour, « Identité protégée ») est
  celle qui se régénère depuis le dépôt ;
- la version **photo** se régénère en local, une fois la photo déposée dans
  `assets/img/founder.jpg`.

## Chaîne de production

```bash
pip install numpy scipy opencv-python-headless pyloudnorm pillow
# (Chromium via Playwright et ffmpeg sont requis)

python3 tools/build_vo.py                 # VO : silences resserrés → audio/vo.wav + src/timeline.json + .srt
python3 tools/cutout.py                   # (version photo) détourage local de assets/img/founder.jpg
python3 tools/prep_founder.py             # (version photo) étalonnage, halo, avatar
node tools/render.mjs --events            # repères sonores exportés par l'animation → audio/events.json
python3 tools/sound.py                    # musique + SFX + ducking + master −14 LUFS → out/mix.wav
node tools/render.mjs --fps 60            # image (ajouter --founder avatar pour la variante anonyme)
tools/mux.sh avatar                       # → out/ + livrables/ (la variante photo, `photo`, reste dans out/)
```

- Aperçu interactif avec le son : servir le dossier (`npx serve .`) puis ouvrir
  `/src/index.html` (`?founder=avatar` pour la variante).
- Images de contrôle : `node tools/render.mjs --stills 3.6,22.8,51.2`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/engine.js` | Utilitaires : easing, texte lettre à lettre, étoiles, halos, calques |
| `src/world.js` | Ciel, montagne low-poly ombrée, logo, voxels, golem, pictogrammes |
| `src/scenes.js` | Les 10 scènes, le HUD gamifié et les repères sonores |
| `src/timeline.json` | Début et fin de chaque phrase de la VO (calcul automatique) |
| `tools/sound.py` | Synthèse : nappes, chœur, arpèges, impacts, whooshs, UI, réverbération, ducking, limiteur |
| `audio/vo_raw.mp3` | Voix off brute (synthèse ElevenLabs « George », via vidIQ) |
| `livrables/altherion-vsl_avatar.mp4` | Vidéo finale, variante anonyme |
| `livrables/altherion-vsl_musique-sfx.wav` | Stem musique + SFX sans voix, pour monter la vraie voix |
| `livrables/altherion-vsl.fr.srt` | Sous-titres français |

Les rendus intermédiaires (`out/`) ne sont pas versionnés. La version photo
(`out/altherion-vsl_photo.mp4`) reste en local et n'est jamais copiée dans
`livrables/`.

## Remplacer la voix

`tools/build_vo.py` découpe la voix brute sur ses silences. Il attend 34
segments (liste `SEGMENTS`) séparés par 33 silences, et impose à chacun une
durée cible (liste `GAPS`). Avec un nouvel enregistrement, ajuster le seuil de
`silencedetect` ou ces deux listes si le nombre de silences diffère, puis
relancer la chaîne. Les animations, les repères sonores et le mixage se
recalent seuls.

## Réseaux

Les comptes YouTube et Instagram n'existent pas encore. La vidéo affiche le nom
**Altherion** avec une mention « Bientôt », sans pseudo. Quand les comptes
seront créés, remplacer `SOCIAL_NAME` dans `src/scenes.js`.
