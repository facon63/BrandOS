# Altherion · VSL motion design

Vidéo de présentation d'**Altherion, studio de jeux** : 58 secondes en 1920×1080 à 30 i/s.
Elle présente la promesse (*de zéro à studio*), les valeurs, les lignes rouges et l'ambition du
studio, annonce YouTube et Instagram, puis se termine par un appel à l'action.

| Fichier | Rôle |
|---|---|
| `out/altherion-vsl.mp4` | La vidéo rendue, muette et prête pour la voix-off |
| `out/altherion-vsl.srt` | Sous-titres calés sur le script voix-off |
| `script-voix-off.md` | Script à enregistrer : texte, intentions, timecodes, conseils d'enregistrement |
| `index.html` | Source de l'animation, avec un lecteur, un prompteur et la prévisualisation de la voix |
| `render.mjs` | Rendu image par image vers MP4 (Playwright + ffmpeg) |
| `fonts/` | Cormorant Garamond et Manrope (licence SIL OFL, fichiers inclus) |

## Charte appliquée

Source : la présentation Canva « Présentation - Identité de Marque » (Altherion).

- **Palette nocturne :** nuit `#0E1030`, violet cosmique `#3B2A6B`, or `#E8C46A`,
  blanc stellaire `#F4F1E8` et cyan pâle `#8FD8E8`. Aucun blanc pur. Seuls des mélanges nuit/violet
  sont dérivés, pour les dégradés de montagnes.
- **Typographies :** Cormorant Garamond pour le logo et les titres, en capitales, graisse Light ou Regular,
  avec un interlettrage de +200 à +300. Manrope pour les sous-titres et les incrustations.
- **Territoire éther céleste et conception épurée :** ciel étoilé, montagnes au trait d'or, beaucoup d'espace négatif.
- **Logo « Le Sommet Étoilé » :** un A-sommet avec une étoile unique légèrement au-dessus. C'est
  une **reconstruction de travail** : la charte prévoit encore de vectoriser le logo. Remplacez
  `MARK` / `markSVG()` dans `index.html` par le tracé officiel quand il existera.
- **Posture :** épique (la montagne, l'ascension), autodérision (les bugs qui « buggent »,
  0 abonné · 0 jeu · 0 €) et sincérité (les vrais chiffres).
- **Anonymat :** aucun visage, aucun nom. Le fondateur n'apparaît qu'à travers sa voix.
- **Réseaux :** les comptes n'existent pas encore, donc aucun @pseudo n'est affiché. La vidéo tape
  « Altherion » dans une barre de recherche (constante `HANDLE`). Les pictogrammes YouTube et Instagram
  sont dans leurs versions monochromes officielles, en blanc stellaire.

## Découpage

| Temps | Scène |
|---|---|
| 0:00 | Accroche : pas de studio, pas d'équipe, un rêve et une montagne |
| 0:07 | Origine : un refuge de cubes, puis des îlots-mondes |
| 0:14,2 | Révélation du logo et de la promesse : *de zéro à studio* |
| 0:19,6 | Je partage tout : victoires, bugs, chiffres |
| 0:26,3 | Manifeste : des jeux qui laissent sans voix |
| 0:28,9 | Les valeurs en constellation : émerveillement, persévérance, sincérité, artisanat |
| 0:34,4 | Lignes rouges : jamais de jeu bâclé, jamais le profit avant l'émotion |
| 0:38,9 | Ambition : le sentier vers le sommet (2 à 3 jeux, puis un vrai studio) |
| 0:45,4 | Réseaux : YouTube et Instagram |
| 0:49,0 | Appel à l'action : S'abonner, puis « Rejoignez l'ascension » |
| 0:52,6 | Signature : logo, ALTHERION, *de zéro à studio* |

## Prévisualiser et enregistrer la voix

Ouvrez `index.html` dans Chrome. Si les polices ne se chargent pas en `file://`, lancez
`npx serve .` puis ouvrez l'adresse affichée.

- **Espace :** lecture ou pause. **← / →** : ±1 s (avec **Maj** : ±1 image). Cliquez un chapitre pour y sauter.
- **P :** affiche le prompteur (phrase en cours, intention, phrase suivante).
- **R :** décompte 3-2-1, puis lecture depuis 0 avec le prompteur, pour enregistrer la voix en synchro.
- **Glisser un fichier audio** sur la page pour écouter la voix-off avec l'animation.
- `index.html?t=33.5` ouvre la vidéo directement à 33,5 s.

## Re-rendre la vidéo

Prérequis : Node 18 ou plus, ffmpeg dans le PATH, puis une seule fois :

```bash
npm install
npx playwright install chromium
```

```bash
npm run render                              # out/altherion-vsl.mp4 + .srt (~6 min sur 4 cœurs)
node render.mjs --audio=voix-off.wav        # même vidéo, avec votre voix-off
node render.mjs --stills=16.4,44.6          # captures PNG de contrôle dans out/stills/
```

Options : `--workers=4`, `--crf=18` (qualité, plus bas = meilleur), `--fps=30`,
`--from=` et `--to=` pour un extrait, `--out=` pour le fichier de sortie.

## Modifier

Tout se trouve dans `index.html` :

- **Les textes à l'écran** sont dans le HTML, une `<div>` par scène (`#s1` à `#s11`).
- **Les timings** sont dans la timeline (`reveal`, `show`, `hide`, `tween`, en secondes), regroupés par scène.
- **Le script voix-off** est le tableau `CUES`. Il alimente le prompteur et le `.srt`.
- **Les couleurs** sont les variables CSS de `:root`.

L'animation est entièrement déterministe (`VSL.seek(t)`). Le rendu donne donc exactement ce que
montre le lecteur.
