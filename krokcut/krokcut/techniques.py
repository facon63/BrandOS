"""Techniques de montage repérées dans les vidéos de référence, et ce que KrokCut sait en faire.

Table figée (et testée) : elle sert à la fois de vocabulaire fermé pour Claude (schémas JSON), de
légende pour l'interface et de base à la feuille de route « Pas encore faisable dans KrokCut ».
Les supports « oui / partiel / non » ont été vérifiés dans render.py, timeline.py, editing.py et
derush.py : ne les changer qu'avec le code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Support = Literal["oui", "partiel", "non"]
Effort = Literal["", "facile", "moyen", "difficile"]

DEFAULT_WORKAROUND = "à faire à la main dans Premiere/DaVinci après l'export XML de KrokCut"


@dataclass(frozen=True)
class Technique:
    id: str
    label: str
    side: Literal["image", "son"]
    support: Support
    how: str  # comment le faire dans KrokCut (support « oui » ou « partiel »)
    todo: str  # ce qu'il faudrait ajouter à KrokCut
    effort: Effort  # taille du chantier pour l'ajouter
    workaround: str  # en attendant
    claude: bool  # dans la liste fermée des techniques que Claude repère sur les planches
    rate_source: str  # d'où vient la fréquence : "claude", "Z", "F:flash_blanc", "S:bip", "C:abrupt"…
    cue: str = ""  # l'indice visuel qui la reconnaît (définition donnée à Claude)


def _t(id, label, side, support, how="", todo="", effort="", workaround="", claude=True, rate_source="claude", cue=""):
    if support != "oui" and not workaround:
        workaround = DEFAULT_WORKAROUND
    return Technique(id, label, side, support, how, todo, effort, workaround, claude, rate_source, cue)


TECHNIQUES: tuple[Technique, ...] = (
    # ------------------------------------------------------------ cadrage
    _t("zoom_sec", "Zoom sec (punch-in)", "image", "oui", how="zoom « punch », réglage punch_scale", rate_source="Z",
       cue="le cadre est soudain plus serré d'une case à la suivante dans le même plan (même couleur de bandeau)"),
    _t("zoom_lent", "Zoom lent", "image", "oui", how="zoom « slow » (×1,15)",
       cue="le cadre se resserre progressivement sur au moins 3 cases du même plan"),
    _t("zoom_cible", "Zoom sur un détail (hors centre)", "image", "partiel", how="zoom punch, toujours centré",
       todo="exposer le centre du zoom (cx, cy de timeline.py) dans les décisions de montage : petit chantier",
       effort="facile", cue="zoom serré sur un coin de l'image (un visage, un détail du jeu), pas sur le centre"),
    _t("tremblement", "Tremblement de l'image", "image", "oui", how="zoom « shake »",
       cue="image décalée ou floue de mouvement d'une case à l'autre, sur un cri ou un choc"),
    _t("changement_pov", "Changement de point de vue", "image", "oui", how="caméra A/B, réglage min_shot",
       cue="on passe d'un joueur (POV) à l'autre"),
    _t("ecran_partage", "Écran partagé", "image", "oui", how="caméra « both » / mise en page split",
       cue="deux POV côte à côte ou l'un au-dessus de l'autre, à parts égales"),
    _t("incrustation_pov", "POV en incrustation", "image", "oui", how="mise en page pip",
       cue="un deuxième POV en petit par-dessus le premier (pas la facecam permanente)"),
    _t("jump_cut", "Jump cut (coupe dans le même plan)", "image", "oui", how="réglages max_silence et keep_pad",
       claude=False, rate_source="P:meme_decor"),
    # --------------------------------------------------------- incrustations
    _t("personnage_detoure", "Personnage ou objet détouré", "image", "oui", how="persos de la bibliothèque",
       cue="personnage, tête ou objet découpé, posé par-dessus l'image"),
    _t("meme_image", "Image ou meme incrusté", "image", "oui", how="images de la bibliothèque",
       cue="image fixe (meme, photo, capture) posée sur une partie de l'écran"),
    _t("meme_video", "Vidéo ou meme vidéo inséré", "image", "partiel",
       how="vidéo de la bibliothèque en position centre : plein cadre avec son propre son",
       todo="couper ou baisser la voix sous le meme vidéo", effort="facile",
       cue="extrait vidéo étranger au jeu (meme, film, clip), en incrustation ou plein écran"),
    _t("sticker_emoji", "Sticker ou emoji", "image", "partiel", how="seulement avec des images de la bibliothèque",
       todo="banque d'emojis et de stickers intégrée", effort="facile", cue="emoji, sticker ou petit dessin ajouté"),
    _t("insert_plein_ecran", "Plan de coupe plein écran", "image", "non",
       todo="insérer un plan étranger (B-roll, capture) en plein écran en coupant le jeu", effort="moyen",
       cue="l'image du jeu disparaît entièrement au profit d'une autre image ou vidéo"),
    # ---------------------------------------------------------------- textes
    _t("texte_impact", "Texte d'impact (gros, centre)", "image", "oui", how="texte « impact » (jaune, centre)",
       cue="mot ou phrase courte en gros au centre de l'écran"),
    _t("texte_meme", "Texte en haut (style meme)", "image", "oui", how="texte « meme » (blanc, haut)",
       cue="texte blanc en haut de l'image, façon meme"),
    _t("texte_legende", "Légende en bas", "image", "oui", how="texte « caption » (blanc, bas)",
       cue="phrase en bas de l'image (commentaire, sous-titre ponctuel)"),
    _t("texte_style_libre", "Texte au style libre (couleurs, animation)", "image", "non",
       todo="textes animés, colorés, mot à mot, à n'importe quelle position", effort="moyen",
       cue="texte dont la couleur, la police, la position ou l'animation sortent des trois styles ci-dessus"),
    _t("sous_titres_continus", "Sous-titres continus", "image", "partiel", how="export SRT (pas incrusté)",
       todo="incruster les sous-titres dans la vidéo", effort="facile",
       cue="toute la parole est sous-titrée en continu"),
    _t("carton_titre", "Carton de titre", "image", "partiel", how="texte impact et chapitres",
       todo="carton plein écran (fond uni ou flouté + titre)", effort="facile",
       cue="écran de titre (début de partie, chapitre) qui masque le jeu"),
    _t("annotation", "Annotation (flèche, cercle)", "image", "non",
       todo="dessiner flèches, cercles et entourages animés", effort="difficile",
       cue="flèche, cercle ou entourage qui désigne quelque chose à l'écran"),
    _t("habillage_graphique", "Habillage graphique (compteur, fausse interface)", "image", "non",
       todo="éléments graphiques sur mesure (compteur, score, fausse notification)", effort="difficile",
       cue="compteur, score, barre ou fausse interface ajoutés au montage (pas l'interface du jeu)"),
    # ------------------------------------------------------- effets de temps
    _t("arret_sur_image", "Arrêt sur image", "image", "non", todo="figer l'image quelques instants (tpad)",
       effort="moyen", cue="la même image reste figée sur plusieurs cases (étiquette FIG), souvent avec un texte ou un zoom"),
    _t("ralenti", "Ralenti", "image", "non", todo="ralentir un passage (setpts/atempo)", effort="moyen",
       cue="mouvement nettement ralenti sur des cases successives"),
    _t("accelere", "Accéléré", "image", "non", todo="accélérer un passage", effort="moyen",
       cue="passage visiblement accéléré"),
    _t("rembobinage_replay", "Rembobinage ou replay", "image", "non", todo="rejouer un passage (avec effet rembobinage)",
       effort="moyen", cue="un passage déjà vu est rejoué, parfois à l'envers ou avec un effet de bande"),
    # ------------------------------------------------------------- transitions
    _t("flash", "Flash blanc", "image", "non", todo="flash blanc de 2 images", effort="facile",
       rate_source="F:flash_blanc", cue="case blanche ou surexposée (étiquette FL)"),
    _t("fondu_noir", "Fondu au noir", "image", "oui", how="transition « fade »", rate_source="N:fondu_noir",
       cue="l'image passe au noir (étiquette NOIR)"),
    _t("fondu_enchaine", "Fondu enchaîné", "image", "non", todo="fondu enchaîné entre deux plans (xfade)",
       effort="moyen", cue="deux images superposées en transparence au passage d'un plan à l'autre"),
    _t("transition_animee", "Transition animée", "image", "non", todo="transitions animées (glissé, volet, zoom)",
       effort="moyen", cue="volet, glissé ou animation graphique entre deux plans"),
    _t("filtre_couleur", "Filtre de couleur (N&B, teinte)", "image", "non", todo="filtres N&B, teinte, vignette",
       effort="facile", rate_source="B:noir_et_blanc", cue="image passée en noir et blanc (étiquette NB) ou teintée"),
    _t("bandes_cinema", "Bandes noires « cinéma »", "image", "non", todo="bandes noires haut et bas",
       effort="facile", rate_source="B:bandes_cinema", cue="bandes noires en haut et en bas, ajoutées pour un effet dramatique"),
    _t("censure_visuelle", "Censure visuelle (flou, pixels)", "image", "non", todo="flou ou pixellisation d'une zone",
       effort="moyen", cue="zone floutée, pixellisée ou masquée par un bandeau"),
    # ------------------------------------------------------------- structure
    _t("teaser", "Teaser en ouverture", "image", "oui", how="réglage cold_open", claude=False, rate_source="profil"),
    _t("chapitrage", "Chapitres", "image", "oui", how="chapitres YouTube", claude=False, rate_source="profil"),
    _t("generique", "Générique (intro ou fin)", "image", "non", todo="générique d'intro ou de fin", effort="facile",
       cue="séquence d'intro ou de fin avec logo, titre animé ou crédits"),
    # ------------------------------------------------------------------- son
    _t("bruitage_ponctuel", "Bruitage ponctuel", "son", "oui", how="bruitage sur le mot ou en fin de ligne",
       claude=False, rate_source="S:montage"),
    _t("transition_whoosh", "Whoosh de transition", "son", "oui", how="réglage transition_sfx", claude=False,
       rate_source="S:whoosh"),
    _t("bip_censure", "Bip de censure", "son", "partiel", how="bip de la bibliothèque, la voix n'est pas coupée",
       todo="couper la voix sous le bip", effort="facile", claude=False, rate_source="S:bip"),
    _t("montee_riser", "Montée (riser)", "son", "partiel", how="son de la bibliothèque, pas calé sur la chute",
       todo="caler la fin de la montée sur la chute", effort="facile", claude=False, rate_source="S:montee"),
    _t("musique_fond", "Musique de fond", "son", "oui", how="réglage music, baisse automatique sous les voix",
       claude=False, rate_source="M"),
    _t("changement_musique", "Changement de musique", "son", "oui", how="musique choisie par moment",
       claude=False, rate_source="M:changes"),
    _t("musique_coupee_net", "Musique coupée net", "son", "non",
       todo="arrêt net de la musique sur une chute (fondu fixe dans render.py aujourd'hui)", effort="facile",
       claude=False, rate_source="M:coupure_nette"),
    _t("silence_comique", "Silence comique (son coupé)", "son", "non", todo="couper tout le son quelques instants",
       effort="facile", claude=False, rate_source="C:abrupt"),
    _t("son_sature", "Son saturé volontaire", "son", "non", todo="saturer un cri ou un son", effort="facile",
       claude=False, rate_source="S:sature"),
    _t("effet_voix", "Effet sur la voix (écho, aigu, robot)", "son", "non",
       todo="effets de voix ; de plus, non mesurable automatiquement", effort="moyen", claude=False, rate_source=""),
)

BY_ID: dict[str, Technique] = {t.id: t for t in TECHNIQUES}
ALL_IDS: tuple[str, ...] = tuple(t.id for t in TECHNIQUES)
VISUAL_IDS: tuple[str, ...] = tuple(t.id for t in TECHNIQUES if t.claude) + ("autre",)
HUMOR_IDS: tuple[str, ...] = (
    "coupe_sur_reaction",
    "contre_pied",
    "repetition",
    "exageration",
    "commentaire_du_monteur",
    "ironie_image_parole",
    "silence_gene",
    "interruption_brutale",
    "reference_meme",
    "absurde",
    "replay_du_fail",
    "censure_comique",
    "callback",
    "vannes_entre_eux",
    "fail_mis_en_scene",
    "autre",
)
HUMOR_LABELS = {
    "coupe_sur_reaction": "coupe sèche sur la réaction",
    "contre_pied": "contre-pied (l'image ou la suite contredit ce qui vient d'être dit)",
    "repetition": "répétition (même plan ou même son rejoué)",
    "exageration": "exagération (effets en cascade sur un petit moment)",
    "commentaire_du_monteur": "commentaire du monteur (texte, meme ou son qui se moque)",
    "ironie_image_parole": "ironie entre l'image et la parole",
    "silence_gene": "silence gêné laissé exprès",
    "interruption_brutale": "interruption brutale (coupe au milieu d'une phrase)",
    "reference_meme": "référence à un meme ou à la culture internet",
    "absurde": "absurde",
    "replay_du_fail": "replay du fail",
    "censure_comique": "censure comique (bip, flou)",
    "callback": "rappel d'un moment précédent",
    "vannes_entre_eux": "vannes entre eux",
    "fail_mis_en_scene": "fail mis en scène par le montage",
    "autre": "autre",
}

# Groupes comptés ensemble (comptes déterministes, §5.4)
TEXT_IDS = ("texte_impact", "texte_meme", "texte_legende", "texte_style_libre")
OVERLAY_IDS = ("personnage_detoure", "meme_image", "meme_video", "sticker_emoji", "insert_plein_ecran")
TIME_EFFECT_IDS = ("arret_sur_image", "ralenti", "accelere", "rembobinage_replay")
ZOOM_IDS = ("zoom_sec", "zoom_lent", "zoom_cible", "tremblement")


def support(tid: str) -> str:
    """« oui », « partiel » ou « non » (« non » pour une technique inconnue : jamais promise au monteur)."""
    t = BY_ID.get(tid)
    return t.support if t else "non"


def label(tid: str) -> str:
    t = BY_ID.get(tid)
    if t:
        return t.label
    return HUMOR_LABELS.get(tid, "autre" if tid == "autre" else tid)


def definitions_text() -> str:
    """Une ligne par technique visuelle et par mécanique d'humour, pour le prompt système des passes vidéo."""
    visual = [f"- {t.id} : {t.label} — {t.cue}" for t in TECHNIQUES if t.claude]
    visual.append("- autre : effet ajouté au montage qui n'entre dans aucune catégorie (décris-le)")
    humor = [f"- {h} : {HUMOR_LABELS[h]}" for h in HUMOR_IDS]
    return "Techniques visuelles :\n" + "\n".join(visual) + "\n\nMécaniques d'humour :\n" + "\n".join(humor)
