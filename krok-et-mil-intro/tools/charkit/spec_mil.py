"""Découpe de Mil (90.png). Coordonnées en pixels de la référence 500×500.

La référence s'arrête à la taille (y=499) : jambes, bas du pantalon, poignets et mains sont
construits par `construct_mil.py` sur une toile étendue à 500×700 (PAD_BOTTOM).
"""

SRC = "assets/refs/90.png"
NAME = "mil"
PAD_BOTTOM = 200

# Sommet de l'épi le plus haut (y=89). La semelle construite est placée pour que la hauteur
# totale, ramenée à l'échelle de Krok, soit identique (voir CHARACTER_SHEET.md).
TOP_Y = 89

parts = [
    {
        "name": "pelvis", "z": 7, "parent": "torso",
        "polys": [[(178, 484), (314, 484), (314, 500), (178, 500)]],
        "pivot": (247, 492),
    },
    {
        "name": "torso", "z": 10, "parent": None,
        "polys": [[(150, 258), (350, 258), (350, 490), (150, 490)]],
        "pivot": (247, 480),
        "hidden": [
            # cou sous le menton
            {"poly": [(222, 230), (280, 230), (283, 274), (219, 274)], "fill": [0.95, 0.72, 0.58],
             "ink": [[(224, 236), (222, 268)], [(279, 236), (281, 266)]]},
            # flanc gauche sous la manche et l'avant-bras
            {"poly": [(208, 281), (194, 289), (186, 304), (184, 325), (186, 346), (188, 366), (188, 486), (204, 486), (204, 281)],
             "fill": "diffuse"},
            # flanc droit
            {"poly": [(294, 282), (311, 290), (318, 305), (318, 330), (311, 351), (306, 367), (305, 486), (290, 486), (290, 282)],
             "fill": "diffuse"},
        ],
    },
    {
        "name": "arm_L", "z": 20, "parent": "torso", "seam_overlay": True,
        "polys": [[(150, 288), (198, 290), (192, 310), (190, 360), (189, 500), (150, 500)]],
        "pivot": (186, 302),
        "bones": {"shoulder": (186, 302), "elbow": (178, 392), "wrist": (174, 506), "hand": (176, 520)},
    },
    {
        "name": "arm_R", "z": 20.1, "parent": "torso", "seam_overlay": True,
        "polys": [[(300, 290), (352, 290), (352, 500), (306, 500), (300, 366), (297, 330)]],
        "pivot": (314, 304),
        "bones": {"shoulder": (314, 304), "elbow": (324, 392), "wrist": (322, 506), "hand": (322, 520)},
    },
    {
        "name": "hair_back", "z": 29, "parent": "head", "polys": [], "pivot": (250, 258),
        "hidden": [
            {"poly": [(150, 84), (305, 84), (332, 150), (334, 236), (170, 236), (150, 160)], "fill": [0.25, 0.16, 0.10]},
        ],
    },
    {
        "name": "head", "z": 30, "parent": "torso", "absorb": {"from": ["torso"], "dist": 1, "lum": 0.40},
        "polys": [[(182, 142), (296, 142), (300, 228), (284, 246), (262, 262), (238, 262), (206, 246), (186, 226), (178, 160)]],
        "pivot": (250, 258),
        "hidden": [
            # front / crâne sous la frange
            {"poly": [(184, 166), (188, 146), (204, 132), (240, 126), (276, 130), (292, 142), (300, 166)], "fill": "diffuse"},
            # côtés du visage sous les écouteurs (chevauchent le front)
            {"poly": [(172, 152), (198, 152), (198, 232), (176, 232)], "fill": "diffuse"},
            {"poly": [(276, 140), (304, 146), (304, 236), (276, 236)], "fill": "diffuse"},
        ],
    },
    {
        "name": "hair", "z": 32, "parent": "head", "absorb": {"from": ["head"], "dist": 2, "lum": 0.2},
        "polys": [[(150, 84), (300, 84), (318, 150), (300, 176), (286, 178), (282, 150), (250, 144), (215, 146), (186, 152), (182, 172), (166, 172), (150, 150)]],
        "pivot": (240, 150),
        "hidden": [
            # cheveux sous l'arceau du casque
            {"poly": [(236, 90), (276, 98), (304, 112), (324, 136), (330, 160), (306, 160), (296, 130), (272, 108), (240, 100)], "fill": "diffuse"},
        ],
    },
    {
        "name": "headphones", "z": 35, "parent": "head",
        "polys": [[(154, 156), (192, 156), (192, 236), (154, 236)],
                  [(286, 150), (346, 150), (346, 238), (286, 238)],
                  [(232, 86), (268, 88), (300, 100), (322, 122), (334, 150), (318, 158), (300, 128), (276, 108), (240, 98)]],
        "pivot": (250, 180),
    },
]

barriers = [
    # haut de la manche gauche (le tissu est continu avec le corps du t-shirt)
    [(207, 274), (204, 281), (197, 291), (192, 302), (189, 314), (189, 324)],
    # haut de la manche droite
    [(302, 274), (301, 282), (299, 296), (298, 312), (297, 328), (297, 338)],
]

overrides = []

spec = {"name": NAME, "src": SRC, "parts": parts, "barriers": barriers, "overrides": overrides,
        "top_y": TOP_Y, "pad_bottom": PAD_BOTTOM, "rim_w": 2.4, "underlay": 3,
        # bras gauche = miroir du bras droit (le gauche de la référence est ~1,7× plus fin) ;
        # axe = milieu des deux épaules ; modelé symétrique (bords extérieurs plus sombres)
        "symmetry": [{"part": "arm_L", "of": "arm_R", "axis": 250.0, "shading": "mirror"}]}
