# KrokCut — dérush et montage automatiques pour Krok et Mil

Tu déposes les deux POV (3–4 h chacun), KrokCut sort :

- une **vidéo montée de 10–15 min** (MP4) : blancs coupés, changements de POV, zooms, bruitages, personnages incrustés, textes à l'écran, musique de fond qui baisse quand vous parlez, volume calé pour YouTube ;
- une **timeline XML** à ouvrir dans **Premiere Pro** ou **DaVinci Resolve** pour faire les finitions au lieu de partir de zéro ;
- les **sous-titres** (SRT), les **chapitres YouTube**, et un **récap** avec idées de titres et de miniatures.

Tout tourne sur ton PC. Les vidéos ne quittent jamais la machine : seule la **transcription texte** (et quelques images basse résolution des moments retenus) est envoyée à Claude.

---

## Comment ça marche

```
POV A (Krok) ─┐
              ├─► 1. Synchro des deux caméras (par le son)
POV B (Mil) ──┘   2. Analyse du son : pics, cris, rires, blancs
                  3. Transcription (Whisper, en local) + qui parle (micro le plus fort)
                  4. Dérush par Claude : il lit TOUT le live et note chaque moment drôle
                  5. Construction de l'histoire : choix des moments pour tenir en 10–15 min,
                     teaser d'ouverture, chapitres, titres
                  6. Montage par Claude : plan A/B/écran partagé, zooms, bruitages, persos,
                     textes, musique — en piochant dans VOTRE bibliothèque
                  7. Rendu ffmpeg  →  MP4 + XML Premiere/DaVinci + SRT + chapitres
```

Entre l'étape 5 et 6 tu peux (si tu veux) **valider la sélection** : cocher / décocher / réordonner les moments, voir la transcription de chacun, et relancer. Seules les étapes suivantes sont refaites.

Chaque étape est mise en cache : si le PC s'éteint pendant la transcription, ça reprend où ça s'était arrêté.

---

## Installation

### Windows

1. Installe **Python 3.11 ou 3.12** depuis [python.org](https://www.python.org/downloads/) (coche **« Add python.exe to PATH »**).
2. Double-clique sur **`installer.bat`** (il installe aussi ffmpeg via winget si besoin, relance-le une fois après).
3. Double-clique sur **`lancer.bat`** : l'interface s'ouvre dans le navigateur (http://localhost:8765).

### Mac (une seule commande)

1. Ouvre l'app **Terminal** (Cmd + Espace, tape « Terminal », Entrée).
2. Colle cette ligne puis Entrée :
   ```bash
   curl -fsSL https://raw.githubusercontent.com/facon63/BrandOS/claude/upbeat-fermi-qf074j/krokcut/install-mac.sh | bash
   ```
   Elle télécharge tout ce qu'il faut (Python, ffmpeg, dépendances) dans le dossier `~/KrokCut`, sans rien installer ailleurs ni demander de mot de passe, puis crée l'app **KrokCut** (dans Applications et sur le Bureau) et l'ouvre.
3. Les fois suivantes : **double-clic sur KrokCut**. Pour fermer : bouton **⏻ Quitter** en haut de l'interface.

- **Mettre à jour** : recolle la même commande (épisodes et réglages sont conservés).
- **Désinstaller** : supprime le dossier `KrokCut` de ton dossier personnel et l'app KrokCut.
- Si macOS demande l'autorisation d'accéder à un dossier (Téléchargements, disque externe…), clique sur **Autoriser** : c'est pour lire les rush.
- Pendant un traitement, KrokCut empêche le Mac de se mettre en veille (l'écran peut s'éteindre, ça continue).

Sur Mac, la transcription tourne sur le processeur (Whisper n'utilise pas la puce graphique d'Apple) : choisis le modèle **medium** ou **small** dans Réglages si c'est trop long. Sur Mac Apple Silicon (M1 à M4…), l'encodeur **« H.264 Mac »** accélère le rendu final.

### Linux

```bash
sudo apt install ffmpeg python3-venv
bash installer.sh
bash lancer.sh
```

### Carte graphique NVIDIA (fortement conseillé pour la transcription)

La transcription est la seule étape longue : à titre indicatif, de l'ordre de 10 à 30 min pour un live de 4 h avec une carte NVIDIA récente, plusieurs heures sur le processeur (elle tourne sans surveillance et reprend où elle s'est arrêtée). Pour activer la carte sous Windows, installe les bibliothèques CUDA 12 dans l'environnement :

```bat
.venv\Scripts\activate
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*
```

Si la carte n'est pas utilisable, KrokCut bascule tout seul sur le processeur (c'est écrit dans le journal). Sans carte NVIDIA, choisis le modèle **small** ou **medium** dans Réglages pour aller plus vite.

---

## Premier réglage (10 minutes, une seule fois)

### 1. La clé Claude
Réglages → colle ta clé API (à créer sur [console.anthropic.com](https://console.anthropic.com/)). Elle reste dans `workspace/config.yaml` sur le PC.

Coût indicatif avec Claude Opus 5.5 : **environ 2 à 5 $ par épisode** de 3–4 h (le dérush lit tout le live). Le coût exact est affiché dans le journal et dans le récap. Les réponses sont mises en cache : relancer un rendu ne recoûte rien, et quand tu retouches la sélection seuls les moments ajoutés sont redemandés à Claude.

Sans clé, KrokCut marche quand même en **mode hors ligne** (il repère les pics sonores), mais c'est nettement moins malin : c'est Claude qui comprend les blagues.

### 2. La bibliothèque (sound design, persos, memes)
Onglet **Bibliothèque** → indique le dossier → **Scanner**. Organisation conseillée :

```
Bibliotheque/
├── sfx/                  bruitages (.wav .mp3 .ogg…), sous-dossiers libres : sfx/fails/, sfx/transitions/…
├── musiques/             musiques de fond
├── personnages/
│   ├── Krok/             actions du perso de Krok : krok_rire.webm, krok_choque.mov, krok_danse.gif…
│   └── Mil/              idem pour Mil
└── memes/                images et petits clips (.png .gif .mp4 fond vert…)
```

- **Les noms de fichiers sont la description** que Claude lit : `mil_facepalm_degoute.webm` est bien plus utile que `anim_03.webm`. Tu peux aussi corriger les tags dans le tableau (ils sont conservés aux scans suivants) et désactiver ce qui ne doit pas servir.
- Transparence : `.webm` VP9 avec alpha, `.mov` ProRes 4444, `.png`, `.gif` sont incrustés tels quels. Les vidéos **sur fond vert** sont détectées et détourées automatiquement.
- Un son dont le nom contient `whoosh`, `swoosh` ou `transition` sert aux changements de partie.

### 3. La bible de la chaîne
Réglages → **Bible de la chaîne** : qui est Krok, qui est Mil, vos personnages, vos running gags, votre vocabulaire, ce que vous coupez toujours, des exemples de moments qui ont cartonné… Un modèle est pré-rempli. **C'est ce qui fait la plus grosse différence sur la qualité du dérush.**

### 4. (Optionnel) Le rythme de vos vidéos publiées
Mesure le nombre de changements de plan par minute de vos vidéos déjà montées, et le donne à Claude comme repère :

```bash
python -m krokcut style "D:\KrokEtMil\Publiees\episode1.mp4" "D:\KrokEtMil\Publiees\episode2.mp4"
```

Le style de montage (densité de zooms, de bruitages, de persos, taille des persos, volume musique, POV seul / incrustation / écran partagé…) se règle dans Réglages → **Style de montage**, et peut être ajusté épisode par épisode.

---

## Utilisation

1. **+ Nouvel épisode** → nom, puis pour chaque POV : glisse le fichier (il est copié) **ou** « Choisir sur le disque » (pas de copie, recommandé pour les gros rush). Si une caméra a coupé l'enregistrement en plusieurs fichiers, ajoute-les tous dans l'ordre.
2. Règle la durée cible et, si tu veux, coche « Faire une pause après la sélection des moments ».
3. **Lancer**. Tu peux fermer l'onglet, ça continue tant que la fenêtre `lancer.bat` est ouverte.
4. Quand c'est fini : regarde l'**aperçu** (720p, rapide), retouche la **sélection des moments** si besoin (**Enregistrer et remonter**), puis **Rendu final pleine qualité**.
5. Télécharge les fichiers, ou importe la timeline dans ton logiciel :
   - **Premiere Pro** : Fichier → Importer → `timeline_premiere_davinci.xml`
   - **DaVinci Resolve** : Fichier → Importer → Timeline → `timeline_premiere_davinci.xml`

   La timeline contient : V1 = POV choisi plan par plan (zooms = échelle sur les morceaux zoomés), V2 = incrustation / écran partagé, V3+ = persos et memes, A1–A2 = voix, puis bruitages et musique sur leurs pistes. Les textes à l'écran et les chapitres sont des **marqueurs**.

Tout ce que produit un épisode est dans `workspace/projects/<épisode>/out/`.

---

## Ce qu'il faut savoir (honnêtement)

- **C'est un très bon premier montage, pas le montage final.** Claude choisit bien les moments drôles et cohérents quand il a la bible de la chaîne, mais il « voit » les rush surtout à travers la transcription (et une image par moment). Comptez une passe de finition dans Premiere/DaVinci — mais une passe de 1 h au lieu d'une journée de dérush.
- **Les rires et cris non transcrits** sont repérés par le son (« son fort sans parole ») : Claude sait qu'il s'y passe quelque chose, sans savoir exactement quoi.
- **Qui parle** est déduit du micro le plus fort. Si vous êtes dans la même pièce avec un seul micro, ça peut se tromper ; Claude s'en sert quand même comme indice.
- **Synchro** : faite automatiquement par le son (gère l'écho Discord). Si un jour elle échoue (aucun son commun), saisis le décalage dans « Outils avancés » : (instant du clap dans B) − (instant du clap dans A). Un clap au début de l'enregistrement aide toujours.
- **Son du montage** : par défaut le son suit le POV affiché (pas d'écho Discord ni de jeu en double). Si vous êtes dans la même pièce, le mode « Mix des deux POV » peut sonner mieux.
- **Positions dans le XML** : les persos et l'incrustation sont placés au bon endroit dans le MP4 ; dans Premiere/DaVinci leur position/échelle peut demander un petit ajustement selon la résolution de vos fichiers.
- **Les sources en 1440p/4K** sont réduites en 1080p dans le MP4 (réglable dans `workspace/config.yaml`, section `render`).

---

## Ligne de commande (optionnel)

```bash
python -m krokcut serve                      # interface web (par défaut)
python -m krokcut run --name "Ep 12" --a krok.mp4 --b mil.mp4 --name-a Krok --name-b Mil
python -m krokcut resume ep-12 --from-step edit          # relance à partir d'une étape
python -m krokcut resume ep-12 --from-step render --quality final
python -m krokcut library "D:\KrokEtMil\Bibliotheque"
```

Étapes : `probe audio sync features transcribe derush story edit render export`.

## Réglages avancés

`workspace/config.yaml` (créé au premier lancement) :

| Clé | Rôle |
|---|---|
| `model` | modèle Claude (`claude-opus-5-5` par défaut) |
| `effort.derush / story / edit` | profondeur de réflexion de Claude par étape |
| `whisper.model`, `whisper.device` | modèle de transcription, `auto` / `cuda` / `cpu` |
| `render.width/height/fps` | format de sortie (fps 0 = celui du POV A) |
| `render.video_codec` | `libx264`, `h264_nvenc` (NVIDIA), `h264_videotoolbox` (Mac) |
| `render.font_file` | police des textes à l'écran |
| `render.loudness_lufs` | volume final (−14 LUFS = YouTube) |

`workspace/projects/<épisode>/style.yaml` : le style de cet épisode (durée, densité des effets, réalisation, consignes libres pour Claude).

`workspace/projects/<épisode>/work/` contient tout l'intermédiaire, lisible : `transcription.json`, `moments.json` (tous les moments repérés et leurs notes), `histoire.json` (la sélection), `decisions.json` (choix d'effets de Claude), `timeline.json` (le montage plan par plan, modifiable à la main avant un `--from-step render`).

## Développement

```bash
pip install -r requirements-dev.txt
python -m pytest            # ~1 min : faux rush générés, rendu ffmpeg réel, Claude simulé
```

Structure : `audio.py` (synchro, niveaux), `transcribe.py` (Whisper, qui parle), `derush.py` (passes 1 et 2 avec Claude), `editing.py` (passe 3), `cutting.py` (coupe des blancs), `timeline.py` (plan → plans à l'image près), `render.py` (ffmpeg), `export.py` (XML, SRT, chapitres), `pipeline.py` (enchaînement avec reprise), `server.py` + `web/` (interface).
