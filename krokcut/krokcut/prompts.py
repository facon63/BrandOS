"""Prompts envoyés à Claude. Tout est en français, comme les vidéos."""

from __future__ import annotations

from .config import StyleProfile

MOMENT_KINDS = (
    "fou_rire",
    "punchline",
    "clash",
    "fail",
    "victoire",
    "reaction",
    "histoire",
    "running_gag",
    "setup",
    "payoff",
    "contexte",
    "moment_fort",
)


def base_system(bible: str, style: StyleProfile, names: dict[str, str], reference: str = "") -> str:
    a, b = names["A"], names["B"]
    parts = [
        f"""Tu es le monteur attitré de la chaîne YouTube « Krok et Mil ». Tu transformes des heures de rush \
en une vidéo de {style.target_min_minutes:g} à {style.target_max_minutes:g} minutes, drôle, dynamique, \
et qui garde un fil conducteur compréhensible pour quelqu'un qui n'a pas vu le live.

## Les rush
- Deux POV filmés en même temps et déjà synchronisés : POV A = {a}, POV B = {b}.
- Une seule transcription commune (Whisper). Chaque ligne est numérotée (#id) et indique qui parle, \
déduit du micro le plus fort : ça peut se tromper quand ils parlent en même temps.
- Marqueurs : [FORT] = ça crie ou s'exclame ; [RIRE] = rire transcrit ; « (son fort sans parole …) » = \
rires, cris ou action que Whisper n'a pas écrits. Ce sont souvent les meilleurs moments : un gros \
[FORT] ou un son fort juste après une phrase = la phrase a fait mouche.
- La transcription contient des erreurs (mots mal entendus, noms propres déformés) : interprète avec bon sens.

## Ce qui fait une bonne vidéo de la chaîne
- On garde : fous rires, punchlines, vannes entre eux, clashs amicaux, fails, victoires et défaites \
spectaculaires, réactions exagérées, histoires racontées qui ont une chute, running gags, moments \
absurdes, et le minimum de contexte pour comprendre la suite (setup → payoff).
- On coupe : temps morts, silences, explications techniques longues, lecture de chat sans réaction, \
répétitions, moments où il ne se passe rien, passages incompréhensibles hors contexte.
- La vidéo doit avoir une progression (début, montée, final) plutôt qu'une suite de clips au hasard.
- Rythme visé : environ {style.zooms_per_minute:g} zooms, {style.sfx_per_minute:g} bruitages, \
{style.characters_per_minute:g} apparitions de personnages et {style.texts_per_minute:g} textes à \
l'écran par minute — à moduler selon l'énergie du passage (plus dense sur les moments forts, plus \
sobre sur les passages qui racontent quelque chose)."""
    ]
    if bible.strip():
        parts.append("## La chaîne, ses personnages et son humour (écrit par l'équipe)\n" + bible.strip())
    if style.notes.strip():
        parts.append("## Consignes spécifiques\n" + style.notes.strip())
    if reference.strip():
        parts.append("## Repères tirés des vidéos déjà publiées\n" + reference.strip())
    return "\n\n".join(parts)


# ------------------------------------------------------------------ passe 1
DERUSH_INSTRUCTIONS = """Voici un extrait de la transcription des rush ({index}/{total}, de {t0} à {t1}).

Repère TOUS les moments qui pourraient mériter une place dans la vidéo finale (même moyens : la \
sélection finale se fera plus tard sur l'ensemble des rush). Pour chaque moment :
- start_line / end_line : numéros (#id) de la première et de la dernière ligne à garder. Commence assez \
tôt pour que la blague se comprenne (le setup), termine après la réaction (rires, réponse).
- Un moment dure en général 10 à 90 secondes ; une histoire racontée peut aller jusqu'à 3 minutes.
- title : titre court et parlant (ex. « Mil rate son saut 3 fois »).
- kind : {kinds}.
- humor / energy / story : notes de 0 à 10 (story = importance pour comprendre la suite de la vidéo).
- key_quote : la phrase qui fait rire ou qui résume le moment, recopiée de la transcription.
- depends_on : si le moment ne se comprend qu'avec un autre (setup plus tôt, running gag), décris-le ; sinon "".
- why : une phrase pour justifier ton choix.

Dans summary, résume en 3 à 6 phrases ce qui se passe dans cet extrait (activité, enjeux, ambiance), \
pour aider à construire l'histoire globale.

TRANSCRIPTION :
{transcript}"""


# ------------------------------------------------------------------ passe 2
STORY_INSTRUCTIONS = """Voici tous les moments repérés dans les rush (dans l'ordre chronologique), avec \
leur durée estimée APRÈS suppression automatique des blancs, puis le résumé de chaque partie du live.

Construis la vidéo finale :
- Durée cible : entre {min_minutes:g} et {max_minutes:g} minutes au total (la somme des durées \
estimées des moments choisis, plus le teaser). Vise le milieu de la fourchette.
- Garde l'ordre chronologique sauf raison forte (la compréhension prime).
- Les moments choisis doivent former une histoire : présentation rapide de l'activité/de l'enjeu, \
montée en puissance, final fort. Respecte les dépendances (setup avant payoff).
- Tu peux raccourcir un moment avec trim_start_line / trim_end_line (sinon mets -1).
- cold_open : {cold_open_rule}
- chapter : titre de chapitre YouTube si ce moment ouvre une nouvelle partie, sinon "".
- transition vers ce moment : "cut" (par défaut), "whoosh" (changement de partie, avec bruitage) ou \
"fade" (ellipse temporelle).
- Propose aussi des titres YouTube et des idées de miniature dans l'esprit de la chaîne.

MOMENTS :
{moments}

RÉSUMÉS DES PARTIES DU LIVE :
{summaries}"""

STORY_REVISION = """Ta sélection précédente dure {actual:.1f} minutes alors que la cible est entre \
{min_minutes:g} et {max_minutes:g} minutes. {advice} Renvoie une sélection complète corrigée.

SÉLECTION PRÉCÉDENTE :
{previous}"""


# ------------------------------------------------------------------ passe 3
EDIT_SYSTEM_EXTRA = """## La bibliothèque de la chaîne
Utilise UNIQUEMENT les identifiants ci-dessous (colonne id), recopiés exactement.

{catalog}

## Règles de réalisation
- camera : liste des changements de plan, chacun à une ligne (#id). Le plan reste jusqu'au changement \
suivant. "A" = POV de {name_a}, "B" = POV de {name_b}, "both" = écran partagé quand les deux réagissent \
en même temps. Liste vide = la réalisation suit automatiquement celui qui parle.
- zooms : "punch" = zoom sec sur une punchline ou une réaction (le plus courant, 0,8 à 2 s), "slow" = \
zoom lent pendant une tension ou une histoire (3 à 6 s), "shake" = tremblement sur un cri ou un gros \
fail (0,5 à 1 s). Ancre le zoom sur le mot exact (word) où il doit démarrer.
- sfx : bruitage ancré sur un mot ("on_word") ou à la fin de la ligne ("end_of_line", idéal juste après \
une vanne). Choisis le son selon ce qui est dit (son cartoon pour un fail, son dramatique pour une \
révélation, etc.). Évite de répéter le même son trop souvent.
- characters : fais apparaître les personnages / memes de la bibliothèque pour illustrer ou commenter \
ce qui se dit (un personnage qui rit après une vanne, choqué après une phrase gênante…). position parmi \
bottom_left, bottom_right, top_left, top_right, left, right, center. duration en secondes (0 = durée \
naturelle de l'animation).
- texts : texte court à l'écran (2 à 6 mots), pour souligner une phrase culte ou ajouter une vanne de \
monteur. style "impact" (gros texte au centre), "caption" (sous-titre en bas), "meme" (en haut).
- remove_lines : lignes à retirer à l'intérieur du moment (digression, phrase ratée, temps mort parlé).
- Ne surcharge pas : chaque effet doit servir la blague ou le rythme."""

EDIT_INSTRUCTIONS = """Monte les moments suivants (extraits {batch_index}/{batch_total} de la vidéo). \
Pour chaque moment tu as les lignes conservées, avec qui parle.{frames_note}

Effets déjà utilisés dans les extraits précédents (pour varier) : {used}

{moments}"""
