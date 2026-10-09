"""Variantes d'yeux dessinées en code, au même trait que les références (calques posés sur la tête).

- Mil « yeux ouverts » : la paupière lourde se relève (action), avant le retour du regard blasé
  de la référence (gag récurrent).
- Krok / Mil « yeux fermés » : clignement et soulagement (« ouf »).
"""
import numpy as np

from .layers import INK, aa_poly_mask, aa_stroke_mask


def circle_pts(cx, cy, r, n=72, a0=0.0, a1=2 * np.pi):
    t = np.linspace(a0, a1, n)
    return [(cx + r * np.cos(u), cy + r * np.sin(u)) for u in t]


def arc_pts(cx, cy, rx, ry, a0, a1, n=24):
    t = np.linspace(a0, a1, n)
    return [(cx + rx * np.cos(u), cy + ry * np.sin(u)) for u in t]


def _paint(L, mask, color):
    m = mask[..., None]
    a = L[..., 3:4]
    oa = m + a * (1 - m)
    oc = (np.array(color, np.float32) * m + L[..., :3] * a * (1 - m)) / np.maximum(oa, 1e-6)
    L[..., :3] = oc
    L[..., 3:4] = oa


# Géométrie mesurée sur 90.png (cercle de l'œil, pupille)
MIL_EYES = [dict(cx=199.6, cy=187.6, r=13.4, px=201.0, py=188.5),
            dict(cx=252.2, cy=187.6, r=13.9, px=252.6, py=188.5)]
MIL_SKIN_LID = (0.98, 0.81, 0.67)
MIL_SKIN_LID_SHADOW = (0.93, 0.70, 0.58)

# Géométrie mesurée sur 83.png (amande de l'œil)
KROK_EYES = [dict(x0=232.0, x1=257.5, cy=117.3, h=6.6), dict(x0=273.0, x1=295.5, cy=117.6, h=6.4)]
KROK_SKIN = (0.99, 0.77, 0.58)
KROK_SKIN_SHADOW = (0.90, 0.56, 0.46)


def mil_eyes_open(shape, ink_w=1.9):
    L = np.zeros(shape + (4,), np.float32)
    for e in MIL_EYES:
        cx, cy, r = e["cx"], e["cy"], e["r"]
        inner = aa_poly_mask(shape, circle_pts(cx, cy, r - 0.6))
        _paint(L, inner, (0.99, 0.99, 0.99))
        # ombre bleutée en bas à droite, comme la référence
        sh = aa_poly_mask(shape, circle_pts(cx + 2.6, cy + 2.2, r - 1.6)) * (1 - aa_poly_mask(shape, circle_pts(cx - 1.2, cy - 1.4, r - 2.2)))
        _paint(L, sh * inner * 0.85, (0.78, 0.84, 0.88))
        # pupille un peu plus grande (regard alerte) + reflet
        _paint(L, aa_poly_mask(shape, circle_pts(cx + 0.6, cy + 0.2, 3.2)), INK)
        _paint(L, aa_poly_mask(shape, circle_pts(cx - 0.6, cy - 1.0, 0.9)), (1, 1, 1))
        _paint(L, aa_stroke_mask(shape, circle_pts(cx, cy, r), ink_w, closed=True), INK)
        # pli de paupière relevé (fin arc au-dessus)
        _paint(L, aa_stroke_mask(shape, arc_pts(cx, cy - 1.0, r + 1.5, r + 1.8, np.pi * 1.20, np.pi * 1.80), 1.3) * 0.8, INK)
    return L


def mil_eyes_closed(shape, ink_w=1.9):
    L = np.zeros(shape + (4,), np.float32)
    for e in MIL_EYES:
        cx, cy, r = e["cx"], e["cy"], e["r"]
        inner = aa_poly_mask(shape, circle_pts(cx, cy, r - 0.4))
        _paint(L, inner, MIL_SKIN_LID)
        _paint(L, aa_poly_mask(shape, circle_pts(cx + 1.8, cy + 2.0, r - 1.5)) * inner * 0.55, MIL_SKIN_LID_SHADOW)
        _paint(L, aa_stroke_mask(shape, circle_pts(cx, cy, r), ink_w, closed=True), INK)
        # paupière fermée : trait légèrement arqué vers le bas, aux deux tiers de l'œil
        _paint(L, aa_stroke_mask(shape, arc_pts(cx, cy + 2.0, r - 1.0, 3.2, 0.12 * np.pi, 0.88 * np.pi), ink_w * 1.1), INK)
    return L


def krok_eyes_closed(shape, ink_w=2.3):
    L = np.zeros(shape + (4,), np.float32)
    for e in KROK_EYES:
        x0, x1, cy, h = e["x0"], e["x1"], e["cy"], e["h"]
        cx, rx = 0.5 * (x0 + x1), 0.5 * (x1 - x0) + 1.0
        lid = aa_poly_mask(shape, arc_pts(cx, cy, rx, h, 0, 2 * np.pi, 48))
        _paint(L, lid, KROK_SKIN)
        _paint(L, aa_poly_mask(shape, arc_pts(cx, cy - 2.5, rx, h * 0.55, 0, 2 * np.pi, 48)) * lid * 0.6, KROK_SKIN_SHADOW)
        # œil fermé souriant : arc vers le bas avec cil extérieur
        _paint(L, aa_stroke_mask(shape, arc_pts(cx, cy - 1.5, rx - 1.5, 3.4, 0.08 * np.pi, 0.92 * np.pi), ink_w), INK)
    return L
