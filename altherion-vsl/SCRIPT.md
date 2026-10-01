# Altherion — VSL « Jamais l'ascension »

**Durée :** 59,5 s · **Format :** 1920 × 1080, 60 i/s · **Langue :** français

## L'angle

Tous les studios montrent le sommet : le jeu fini, la bande-annonce parfaite.
Altherion montre l'**ascension**. C'est le concept même du projet (« De zéro à
studio », un devlog où chaque épisode est une étape), et c'est déjà inscrit dans
le logo : un sommet, et une étoile juste au-dessus.

La vidéo s'ouvre donc comme une bande-annonce (bandes cinéma, titres
solennels), puis la caméra **redescend au camp de base** et le film devient un
jeu. À partir de là, tout est une partie en cours : HUD, altimètre, niveaux,
chapitres, succès débloqués. On grimpe de 0 m jusqu'au sommet étoilé du logo,
qui sert d'appel à l'action.

Le fil rouge tient d'un bout à l'autre : *sommet → ascension → camp de base →
prises → chutes → paliers → règle de la montagne → objectif → sommet.*

## Script voix off (version montée)

| Temps | Voix off | À l'image |
|---|---|---|
| 0:00 | *(silence, une étoile s'allume)* | Étoile seule dans la nuit |
| 0:01 | Tous les studios vous montrent le sommet. | Montagne low-poly, bandes cinéma |
| 0:03 | Le jeu fini. | Titre « bande-annonce » |
| 0:04 | La bande-annonce parfaite. | Titre « bande-annonce » |
| 0:06 | Jamais l'ascension. | La caméra plonge au pied de la montagne |
| 0:08 | Altherion, c'est l'inverse : | Le HUD s'allume, le logo se trace en plan technique |
| 0:10 | un studio de jeux vidéo qui se construit sous vos yeux. | Mot-symbole décodé, modules du studio validés, compilation |
| 0:13 | À partir de zéro. | Tout s'effondre en un point : NIVEAU 0 |
| 0:14 | Au départ, un enfant qui bâtissait des refuges dans Minecraft. | Un refuge en voxels se construit bloc par bloc |
| 0:18 | Plus chez lui dans les mondes imaginaires que dans le vrai. | Carte de sélection : les mondes imaginaires… puis, sur « le vrai », la photo |
| 0:21 | Aujourd'hui, il construit les siens. | Fiche personnage du fondateur, statistiques, « Bâtisseur de mondes » |
| 0:24 | Chaque ligne de code est une prise. | Les lignes de code forment la paroi, l'étoile grimpe |
| 0:26 | Chaque bug, une chute. | Glitch, chute libre |
| 0:28 | Et chaque chute devient un épisode. | L'image se fige et devient la vignette « Épisode 01 » |
| 0:31 | À ses côtés, un golem de lumière, qui grandit à chaque palier. | Le golem s'assemble, palier 2, palier 3 |
| 0:35 | Une seule règle sur cette montagne : | « Le code de l'expédition » |
| 0:37 | jamais de jeu bâclé. | Carte tranchée par une lame d'or |
| 0:39 | Jamais de mécanique pour vider vos poches. | Les pièces se changent en étoiles |
| 0:41 | Seulement des jeux qui laissent sans voix. | **Silence total** (la musique se coupe sur « sans voix ») |
| 0:44 | Six mois. Deux à trois jeux. | Journal de quête : chrono de 6 mois, 3 emplacements de jeux |
| 0:46 | Les vrais chiffres, les vrais doutes, les vraies victoires. | Cases cochées une à une |
| 0:49 | L'ascension commence. | Remontée jusqu'au sommet, l'étoile s'embrase |
| 0:51 | Rejoignez l'expédition dès le premier épisode, sur YouTube et Instagram. | Bouton « Rejoindre l'expédition », tuiles YouTube / Instagram « Bientôt » |
| 0:56 | Altherion. De zéro à studio. | Signature : logo, mot-symbole, « Bientôt sur YouTube · Instagram » |

## Texte brut (pour enregistrer la vraie voix)

> Tous les studios vous montrent le sommet.
> Le jeu fini. La bande-annonce parfaite.
> Jamais l'ascension.
>
> Altherion, c'est l'inverse : un studio de jeux vidéo qui se construit sous vos yeux. À partir de zéro.
>
> Au départ, un enfant qui bâtissait des refuges dans Minecraft. Plus chez lui dans les mondes imaginaires que dans le vrai.
> Aujourd'hui, il construit les siens.
>
> Chaque ligne de code est une prise. Chaque bug, une chute. Et chaque chute devient un épisode.
> À ses côtés, un golem de lumière, qui grandit à chaque palier.
>
> Une seule règle sur cette montagne : jamais de jeu bâclé. Jamais de mécanique pour vider vos poches.
> Seulement des jeux qui laissent sans voix.
>
> Six mois. Deux à trois jeux. Les vrais chiffres, les vrais doutes, les vraies victoires.
>
> L'ascension commence. Rejoignez l'expédition dès le premier épisode, sur YouTube et Instagram.
>
> Altherion. De zéro à studio.

**Direction :** la posture de la charte, *compagnon épique, sincère*.
Posé et grave sur la bande-annonce, plus chaleureux sur l'enfance, un sourire
dans la voix sur « chaque bug, une chute », un vrai temps de silence après
« sans voix », puis de l'élan jusqu'à la fin. Environ 150 mots, à lire en 52 à
55 secondes.

## Voix off fournie

La voix livrée est une voix de synthèse (ElevenLabs « George », via vidIQ), en
attendant l'enregistrement. La charte prévoit de garder **la vraie voix du
fondateur** avec un ton de narration distinct. Pour la remplacer :

1. Enregistrer le texte ci-dessus (WAV 48 kHz).
2. Le déposer en `audio/vo_raw.mp3` (ou adapter `tools/build_vo.py`).
3. Relancer la chaîne (voir `README.md`) : les pauses sont resserrées, la
   timeline est recalculée et toutes les animations et tous les sons se
   recalent automatiquement sur la nouvelle voix.

Le stem `livrables/altherion-vsl_musique-sfx.wav` (musique et effets sans voix) sert
à monter la vraie voix dans un autre logiciel.
