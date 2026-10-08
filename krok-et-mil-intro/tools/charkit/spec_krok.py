"""Découpe de Krok (83.png). Coordonnées en pixels de la référence 500×500.

z : ordre d'empilement (petit = derrière). Les polygones sont approximatifs : ils votent pour
les zones fermées par le trait. Les barrières referment le trait là où il est ouvert.
`hidden` : zones cachées à reconstruire sous les calques du dessus (remplissage par diffusion
ou couleur unie) avec, le cas échéant, un contour d'encre tracé sur les bords spécifiés.
"""

SRC = "assets/refs/83.png"
NAME = "krok"

# Hauteur de référence : sommet de la casquette (y=47) -> semelle (y=473)
TOP_Y = 47
SOLE_Y = 473

parts = [
    {
        "name": "leg_L", "z": 5, "parent": "torso",
        "polys": [[(175, 328), (262, 328), (262, 482), (175, 482)]],
        "pivot": (226, 338),
        "bones": {"hip": (225, 352), "knee": (221, 402), "ankle": (213, 452)},
        "hidden": [
            # haut de jambe sous l'ourlet du hoodie
            {"poly": [(199, 300), (260, 300), (262, 348), (194, 348)], "fill": "diffuse"},
            # pantalon sous la main gauche
            {"poly": [(190, 322), (222, 322), (222, 360), (190, 360)], "fill": "diffuse",
             "ink": [[(191, 334), (190, 342), (189, 357)]]},
        ],
    },
    {
        "name": "leg_R", "z": 5.1, "parent": "torso",
        "polys": [[(262, 328), (335, 328), (335, 482), (262, 482)]],
        "pivot": (292, 338),
        "bones": {"hip": (291, 352), "knee": (293, 402), "ankle": (291, 452)},
        "hidden": [
            {"poly": [(262, 300), (316, 300), (319, 348), (260, 348)], "fill": "diffuse"},
            {"poly": [(312, 322), (321, 322), (322, 360), (312, 360)], "fill": "diffuse",
             "ink": [[(321, 334), (322, 342), (322, 360)]]},
        ],
    },
    {
        "name": "shoe_L", "z": 4, "parent": "leg_L", "prio": 60,
        "polys": [[(180, 445), (238, 445), (240, 478), (180, 478)]],
        "pivot": (210, 450),
        "hidden": [
            {"poly": [(184, 436), (236, 436), (237, 448), (183, 448)], "fill": "diffuse"},
        ],
    },
    {
        "name": "shoe_R", "z": 4.1, "parent": "leg_R", "prio": 60,
        "polys": [[(262, 444), (332, 444), (332, 474), (262, 474)]],
        "pivot": (285, 449),
        "hidden": [
            {"poly": [(266, 435), (307, 435), (311, 447), (265, 447)], "fill": "diffuse"},
        ],
    },
    {
        "name": "torso", "z": 10, "parent": None,
        "polys": [[(145, 160), (355, 160), (355, 342), (145, 342)],
                  # entrejambe (petite zone entre les deux jambes, sous l'ourlet)
                  [(254, 326), (274, 326), (268, 358), (258, 358)]],
        "pivot": (262, 330),
        "hidden": [
            # flanc gauche du corps sous la manche gauche
            {"poly": [(212, 192), (186, 192), (178, 215), (175, 255), (177, 295), (186, 322), (214, 330), (214, 192)],
             "fill": "diffuse", "ink": [[(186, 194), (178, 215), (175, 255), (177, 295), (186, 322)]]},
            # flanc droit sous la manche droite
            {"poly": [(306, 192), (318, 198), (330, 230), (335, 268), (334, 302), (328, 322), (305, 326)],
             "fill": "diffuse", "ink": [[(318, 198), (330, 230), (335, 268), (334, 302), (328, 322)]]},
            # cou sous le menton (colonne de peau ombrée, bords encrés)
            {"poly": [(243, 150), (285, 150), (287, 192), (241, 192)], "fill": [0.86, 0.52, 0.42], "clean_lines": True,
             "ink": [[(243, 152), (242, 186)], [(285, 152), (286, 182)]]},
            # intérieur de capuche autour du cou
            {"poly": [(226, 166), (243, 160), (241, 196), (226, 196)], "fill": "diffuse"},
            {"poly": [(285, 160), (300, 164), (300, 196), (287, 196)], "fill": "diffuse"},
            # capuche sous les mèches (sous le contour plausible de la capuche)
            {"poly": [(184, 178), (200, 176), (222, 172), (234, 168), (234, 200), (182, 200)], "fill": "diffuse"},
            {"poly": [(292, 168), (306, 172), (318, 178), (322, 200), (292, 200)], "fill": "diffuse"},
            # sous les cordons
            {"poly": [(244, 188), (288, 188), (288, 248), (244, 248)], "fill": "diffuse"},
        ],
    },
    {
        "name": "strings", "z": 12, "parent": "torso",
        "polys": [[(244, 194), (259, 194), (259, 247), (244, 247)],
                  [(270, 194), (285, 194), (285, 247), (270, 247)]],
        "pivot": (264, 196),
    },
    {
        "name": "arm_L", "z": 20, "parent": "torso",
        "polys": [[(148, 186), (200, 188), (209, 215), (208, 300), (212, 322), (212, 345), (204, 357), (186, 358), (170, 352), (148, 300)]],
        "pivot": (190, 206),
        "bones": {"shoulder": (190, 206), "elbow": (182, 266), "wrist": (190, 322), "hand": (192, 342)},
    },
    {
        "name": "arm_R", "z": 20.1, "parent": "torso",
        "polys": [[(312, 196), (352, 196), (350, 330), (340, 358), (322, 360), (316, 352), (319, 330), (324, 305), (318, 250)]],
        "pivot": (322, 214),
        "bones": {"shoulder": (322, 214), "elbow": (332, 266), "wrist": (333, 320), "hand": (331, 340)},
    },
    {
        "name": "cap_brim", "z": 22, "parent": "head", "prio": 50,
        "polys": [[(160, 104), (192, 100), (194, 136), (160, 140)]],
        "pivot": (200, 112),
        "hidden": [
            {"poly": [(186, 104), (198, 99), (207, 101), (205, 114), (191, 124)], "fill": "diffuse"},
        ],
    },
    {
        "name": "hair_L", "z": 25, "parent": "head",
        "polys": [[(165, 96), (228, 92), (228, 158), (222, 166), (222, 200), (212, 193), (204, 185), (195, 178), (186, 174), (176, 171), (165, 168)]],
        "pivot": (214, 104),
        "hidden": [
            # cheveux sous le bord du visage et sous la casquette
            {"poly": [(212, 92), (236, 90), (240, 168), (222, 168)], "fill": "diffuse"},
        ],
    },
    {
        "name": "hair_R", "z": 25.1, "parent": "head",
        "polys": [[(294, 92), (342, 92), (342, 178), (328, 182), (318, 188), (310, 194), (300, 197), (294, 197)]],
        "pivot": (305, 102),
        "hidden": [
            {"poly": [(286, 92), (304, 92), (304, 168), (284, 168)], "fill": "diffuse"},
        ],
    },
    {
        "name": "head", "z": 30, "parent": "torso",
        "polys": [[(224, 92), (302, 92), (304, 160), (292, 170), (285, 179), (270, 184), (255, 184), (244, 178), (228, 162), (224, 150)]],
        "pivot": (262, 186),
        "hidden": [
            # crâne sous la casquette
            {"poly": [(230, 94), (234, 82), (246, 74), (262, 71), (280, 74), (292, 82), (296, 94)], "fill": [0.87, 0.67, 0.04]},
        ],
    },
    {
        "name": "cap", "z": 35, "parent": "head",
        "polys": [[(185, 38), (312, 38), (312, 96), (226, 92), (205, 100), (192, 104), (185, 100)]],
        "pivot": (262, 84),
    },
]

barriers = [
    # bord droit de la main gauche sur le pantalon (trait noir sur fond sombre, non détecté)
    [(203, 320), (204, 326), (206, 331), (209, 336), (211, 341), (208, 344), (205, 345), (205, 350), (203, 355), (199, 358), (189, 358)],
    # bord gauche de la main droite sur le pantalon
    [(321, 321), (319, 330), (319, 340), (316, 345), (314, 350), (314, 356), (318, 359), (327, 358)],
    # bord intérieur de la manche droite (le trait est dédoublé / ouvert en haut)
    [(303, 183), (306, 189), (309, 199), (312, 212), (315, 228), (318, 243), (321, 255), (324, 266), (326, 279), (327, 292), (327, 304), (326, 312), (325, 319)],
]

overrides = [
    ("arm_L", [(176, 321), (204, 321), (211, 341), (205, 352), (186, 357), (176, 340)]),
    ("arm_R", [(321, 322), (338, 322), (337, 350), (326, 357), (315, 355), (318, 340)]),
]

spec = {"name": NAME, "src": SRC, "parts": parts, "barriers": barriers, "overrides": overrides,
        "top_y": TOP_Y, "sole_y": SOLE_Y}
