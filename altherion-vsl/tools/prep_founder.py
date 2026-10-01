"""Prépare les visuels du fondateur à partir du détourage :
- founder_graded.png  : photo étalonnée dans la palette (ombres nuit/violet, hautes lumières or)
- founder_glow.png    : halo or (contre-jour) à placer derrière
- founder_avatar.png  : silhouette anonyme (variante « règles d'anonymat » de la charte)

Usage : python3 tools/prep_founder.py   (après le détourage assets/img/founder_cutout.png)
"""
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"

NIGHT = np.array([0x0E, 0x10, 0x30], np.float32)[::-1] / 255   # BGR
VIOLET = np.array([0x3B, 0x2A, 0x6B], np.float32)[::-1] / 255
GOLD = np.array([0xE8, 0xC4, 0x6A], np.float32)[::-1] / 255
STAR = np.array([0xF4, 0xF1, 0xE8], np.float32)[::-1] / 255


def main():
    rgba = cv2.imread(str(IMG / "founder_cutout.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    bgr, a = rgba[..., :3], rgba[..., 3]
    lum = (bgr @ np.array([0.114, 0.587, 0.299], np.float32))[..., None]
    # étalonnage : désature légèrement, teinte les ombres en violet nuit, réchauffe les hautes lumières
    sat = 0.82
    base = lum + (bgr - lum) * sat
    shadow_w = np.clip(1 - lum * 1.8, 0, 1)
    high_w = np.clip((lum - 0.55) * 2.2, 0, 1)
    graded = base * (1 - 0.35 * shadow_w) + VIOLET * 0.35 * shadow_w
    graded = graded * (1 - 0.18 * high_w) + (GOLD * 0.6 + STAR * 0.4) * 0.18 * high_w
    # contraste doux (courbe en S)
    graded = np.clip(graded, 0, 1)
    graded = graded + 0.12 * (graded - 0.5) * (1 - np.abs(graded - 0.5) * 2)
    # lumière de bord or venant du haut-droit
    edge = np.clip(a - cv2.GaussianBlur(cv2.erode(a, np.ones((9, 9), np.uint8)), (0, 0), 6), 0, 1)
    H, W = a.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dirw = np.clip(0.35 + 0.65 * ((xx / W) * 0.6 + (1 - yy / H) * 0.6), 0, 1)
    rim = (edge * dirw)[..., None]
    graded = np.clip(graded + rim * GOLD * 0.9, 0, 1)
    out = np.dstack([graded, a])
    cv2.imwrite(str(IMG / "founder_graded.png"), (out * 255).astype(np.uint8))

    # halo or flou derrière la silhouette
    pad = 120
    ap = cv2.copyMakeBorder(a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    glow = cv2.GaussianBlur(ap, (0, 0), 38) * 0.9 + cv2.GaussianBlur(ap, (0, 0), 12) * 0.5
    glow = np.clip(glow, 0, 1)
    g = np.dstack([np.full_like(glow, GOLD[0]), np.full_like(glow, GOLD[1]), np.full_like(glow, GOLD[2]), glow])
    cv2.imwrite(str(IMG / "founder_glow.png"), (g * 255).astype(np.uint8))

    # avatar anonyme : silhouette nuit/violet, liseré or, sans aucun trait du visage
    sil = cv2.GaussianBlur(a, (0, 0), 1.2)
    grad = (yy / H)[..., None]
    fill = VIOLET * (1 - grad) * 0.85 + NIGHT * (0.15 + grad * 0.85)
    inner = np.clip(sil - cv2.GaussianBlur(cv2.erode(sil, np.ones((7, 7), np.uint8)), (0, 0), 3), 0, 1)[..., None]
    fill = np.clip(fill + inner * GOLD * (0.6 + 0.4 * dirw[..., None]), 0, 1)
    av = np.dstack([fill, sil])
    cv2.imwrite(str(IMG / "founder_avatar.png"), (av * 255).astype(np.uint8))
    print("ok", out.shape, g.shape)


if __name__ == "__main__":
    main()
