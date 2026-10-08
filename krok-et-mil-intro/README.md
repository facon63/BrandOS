# Krok et Mil — intro YouTube (10 s)

Intro animée générique de la chaîne gaming **Krok et Mil** : 2D cartoon, 4 univers, musique
chiptune/funk originale et SFX, tout généré par du code (aucun asset externe hormis les deux
références des personnages et trois polices libres).

## Livrables (`out/`)

| Fichier | Contenu |
|---|---|
| `intro_10s.mp4` | Intro complète : 10,000 s, 1920×1080, 30 fps, H.264 + AAC 48 kHz stéréo, −14 LUFS, −1,3 dBTP |
| `intro_3s.mp4` | Version courte : accroche + atterrissage + logo + stinger (3,000 s) |
| `logo_krok_et_mil.png` | Logo seul, fond transparent, 2732 × 697 px |
| `stinger.wav` | Jingle final (~1 s + queue de réverbe, 1,8 s), 48 kHz / 24 bits, −14 LUFS |
| `rapport_rendu.json` | Contrôle automatique : durées, codecs, sonie, pic, instant du drop |

## Déroulé

Grille : 128 BPM, 1 temps = 0,46875 s. Chaque changement de plan tombe sur un temps fort, avec une
transition « glitch pixel » de ~0,18 s aux couleurs de l'univers d'arrivée (motif différent à chaque fois).

| Temps | Séquence | Mouvement / cadrage | Onomatopées |
|---|---|---|---|
| 0,00 → 0,47 s | Accroche : noir, « coin », un seul éclat violet/vert, Krok et Mil surgissent | Pop avec rebond | — |
| 0,47 → 2,81 s | Univers 1, cartoon (tenue de base) : course, rebond sur un champignon-ressort, Mil saute un rocher, pièces | Diagonale fond-gauche → avant-droite, parallaxe | HOP ! |
| 2,81 → 5,16 s | Univers 2, post-apo : mutants qui surgissent, tirs de blasters, nuages de confettis | Travelling latéral, course droite → gauche | PAN ! · ZAP ! |
| 5,16 → 7,50 s | Univers 3, médiéval : le dragon plonge, boule de feu esquivée, saut du tronc ; demi-tour et saut vers la caméra, **gel** sur le temps 15 (break) | Caméra derrière eux, vers l'horizon | GRRR · FWOOSH ! |
| 7,50 → 10,00 s | **DROP**. Univers 4 : atterrissage, « ouf », regard blasé de Mil, high-five discret, logo lettre par lettre puis scintillement (complet à 8,62 s, soit 1,38 s lisible) | Lent zoom arrière, légère descente | bulle « ouf » |

Krok et Mil ne parlent jamais : aucune voix dans le mix, réactions uniquement visuelles.

## Rendu

Prérequis : Node 18+, Python 3.10+, `ffmpeg`, un Chromium headless (Remotion télécharge le sien ;
sinon `export REMOTION_BROWSER=/chemin/vers/chrome-headless-shell`).

```bash
npm install
pip install -r requirements.txt
npm run render          # -> out/ (≈ 1 min 30) : audio, vidéos 10 s et 3 s, mux ffmpeg, logo PNG, rapport
```

Autres commandes :

```bash
npm run studio          # prévisualisation interactive (compositions Intro, Intro3s, LogoPNG, stills de la preuve de concept)
npm run audio           # musique + SFX seuls -> build/audio/ (intro_mix.wav, intro_3s_mix.wav, stinger.wav)
npm run check:heights   # vérifie que Krok et Mil ont la même hauteur dans chaque tenue (± 2 %)
npm run poc             # régénère les images de la preuve de concept (poc/)
npm run trace           # re-vectorise les têtes depuis assets/refs (après changement des références)
npm run typecheck
```

`scripts/render.sh` enchaîne : `audio/compose.py` → `remotion render` (vidéo muette, CRF 16) →
`ffmpeg` (assemblage AAC 256 kb/s, 48 kHz, `+faststart`) → logo → `tools/finalize.py` (contrôles).
Le rendu est déterministe : la même commande produit les mêmes fichiers.

## Structure

```
timeline.json           Minutage unique (BPM, durée, sections, instants de chaque SFX) lu par l'image ET le son
CHARACTER_SHEET.md      Analyse des références (couleurs échantillonnées, proportions, règle de hauteur, tenues)
assets/refs/            Références : 83.png (Krok), 90.png (Mil)
src/
  Intro.tsx, Intro3s.tsx   Compositions vidéo (enchaînement des plans + transitions glitch)
  palette.ts               Couleurs des personnages et du logo
  timeline.ts              Lecture de timeline.json (ev('nom') = instant d'un événement)
  anim.ts                  Courbes d'animation (rebond, squash & stretch, images clés)
  rig/                     Personnages : Krok.tsx, Mil.tsx (corps en calques, tenues), heads.tsx (têtes, accessoires,
                           expressions, vues de dos), pose.ts (poses, cycle de course), parts.tsx (membres, mains, chaussures)
  characters/traced/       Têtes vectorisées (fichiers générés par tools/trace_heads.py)
  scenes/                  Hook, U1Cartoon, U2Wasteland, U3Medieval, U4Sunset (décor + animation de chaque univers)
  props/                   Créatures (mutants, dragon, boule de feu), accessoires (blasters, bouclier, épée)
  fx/                      Logo, onomatopées, transition glitch
  stills/                  Logo PNG, planche de modèle, images de la preuve de concept
audio/
  synth.py                 Oscillateurs, filtres, enveloppes, réverbe (numpy/scipy)
  compose.py               Arrangement, SFX, mixage, mastering, exports
tools/                     Vectorisation des têtes, contrôle des hauteurs, contrôle des livrables, planches contact
public/fonts/              Luckiest Guy (Apache 2.0), Bangers (OFL), Fredoka (OFL) + licences
out/                       Livrables
```

## Modifier

### Les tenues

- Chaque personnage prend une prop `outfit` : `'base' | 'wasteland' | 'medieval'` (`src/rig/Krok.tsx`,
  `src/rig/Mil.tsx`). Les vêtements sont dans le corps du composant (torse, manches, jambes) ; tout ce qui
  touche la tête (lunettes, casquette abîmée, capuche, casque rouillé, antenne, garde-oreilles, plumet) est
  dans `src/rig/heads.tsx`.
- Ajouter une tenue : étendre le type (`KrokOutfit` / `MilOutfit`), ajouter les branches correspondantes,
  puis l'utiliser dans la scène voulue (`<Krok outfit="..." />`).
- Règles à respecter (voir `CHARACTER_SHEET.md`) : au moins un élément violet (Krok) / vert (Mil), et les
  éléments signature conservés (cheveux blonds + casquette à l'envers + bouc ; épis + casque audio sur les
  oreilles + bouc + regard mi-clos).
- Après modification, `npm run check:heights` vérifie que les deux restent à la même hauteur et
  `npm run studio` → `ModelSheet` montre toutes les tenues côte à côte.

### Les couleurs

- Personnages et logo : `src/palette.ts` (`KROK.identity`, `MIL.identity`, `LOGO.*`). Les hex actuels sont
  échantillonnés sur les références : `#83327F` (violet de Krok) et `#9ABB24` (vert de Mil).
- Décors : en tête de chaque fichier `src/scenes/U*.tsx` (dégradés de ciel, sols, objets).
- Transitions : palettes de `GLITCH_STYLES` dans `src/fx/Glitch.tsx` (une par univers d'arrivée).
- Les têtes sont des tracés : leurs couleurs viennent des références. Pour les changer, modifier
  `assets/refs/` puis `npm run trace`.

### Le tempo

- `bpm` dans `timeline.json`. Les sections, les SFX et toute la musique sont exprimés en temps musicaux :
  ils se recalent automatiquement (image et son). Le drop tombe au temps 16 (7,5 s à 128 BPM).
- Contrainte : la musique dure 20 temps (`musicEndBeat`) + la queue de réverbe ; il faut
  `20 × 60 / bpm ≤ duration − 0,4`. À 10 s, garder le BPM entre 128 et ~135, ou allonger `duration`.
- Quelques gestes internes aux scènes sont exprimés en secondes (ex. visée des blasters, esquive) :
  ils restent corrects pour une variation de quelques BPM ; au-delà, relire les `keys(...)` des scènes.

### La durée

- `duration` dans `timeline.json` (durée de la composition et du mix, fondu final sur les 0,45 dernières
  secondes). Pour raccourcir réellement l'intro, retirer ou décaler des sections dans `timeline.json`
  (`sections`) et dans `sceneAt()` de `src/Intro.tsx`, puis supprimer les mesures correspondantes dans
  `compose()` (`audio/compose.py`, blocs commentés « U1 », « U2 »…).
- La version courte suit la même logique : `time_map('short')` dans `audio/compose.py` et `src/Intro3s.tsx`.

### La musique et les SFX

- Arrangement : `compose()` dans `audio/compose.py`, un bloc par univers. Les accords et mélodies sont des
  numéros de notes MIDI (60 = do central) placés sur des temps ; les instruments (`kick`, `clap`, `slap_bass`,
  `dist_bass`, `chip`, `lead`, `pad`, `riser`…) sont des fonctions en haut du fichier.
- Stinger : bloc « STINGER signature » (temps 18 → 20), exporté seul dans `stinger.wav`.
- SFX : liste `events` de `timeline.json` (`kind`, `beat`, `offset` en secondes, `gain`, `pan`). Les
  animations qui doivent coïncider (tirs, rebond, lettres du logo…) lisent les mêmes événements via `ev('nom')`.
- Mixage : `master()` règle les SFX 5 dB sous la musique (sonie intégrée), puis sonie −14 LUFS et limiteur
  true-peak à −1,3 dBTP. Aucune voix n'est générée.

## Notes de fabrication

- **Personnages** : les têtes sont vectorisées depuis les références (ressemblance garantie), les corps sont
  redessinés en calques SVG articulés. Méthode et mesures dans `CHARACTER_SHEET.md`.
- **Polices** libres embarquées dans `public/fonts/` avec leurs licences. Aucun logo, personnage ou morceau
  existant n'est repris ; l'univers post-apo n'évoque qu'une ambiance générique.
- **Accessibilité** : un seul éclat lumineux (accroche), transitions de 0,18 s espacées de plus de 2 s,
  pas de secousse de caméra.
