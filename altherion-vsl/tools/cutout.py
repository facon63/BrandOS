"""Détourage local de la photo du fondateur (fond mur uni) → assets/img/founder_cutout.png

Le mur est modélisé par un polynôme (luminance + chrominance) ; tout ce qui s'en écarte
est le sujet. Les cheveux fins gardent une opacité partielle, et la couleur du mur est
retirée des bords semi-transparents (despill). Aucun service externe n'est utilisé.

Usage : python3 tools/cutout.py   (lit assets/img/founder.jpg)
"""
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"


def feats(y, x, H, W):
    y, x = y / H, x / W
    return np.stack([np.ones_like(x), x, y, x * x, y * y, x * y, x ** 3, y ** 3, x * x * y, x * y * y], -1)


def main():
    im = cv2.imread(str(IMG / "founder.jpg"))
    H, W = im.shape[:2]
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    # 1) échantillons de mur certain
    bg0 = (np.sqrt((a - 128) ** 2 + (b - 135) ** 2) < 5) & (L > 180)
    bg0[int(H * 0.72):, :] = False
    ys, xs = np.nonzero(bg0)
    sel = np.random.default_rng(0).choice(len(ys), min(20000, len(ys)), replace=False)
    F = feats(ys[sel].astype(np.float32), xs[sel].astype(np.float32), H, W)
    coef = {k: np.linalg.lstsq(F, ch[ys[sel], xs[sel]], rcond=None)[0] for k, ch in (("L", L), ("a", a), ("b", b))}
    # 2) modèle du mur sur toute l'image
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    FF = feats(yy.ravel(), xx.ravel(), H, W)
    wL, wa, wb = ((FF @ coef[k]).reshape(H, W) for k in ("L", "a", "b"))
    # 3) opacité : écart de chrominance ou pixel plus sombre que le mur
    dab = np.sqrt((a - wa) ** 2 + (b - wb) ** 2)
    alpha = np.clip(np.maximum((dab - 4) / 9.0, (wL - L - 14) / 26.0), 0, 1)
    # 4) nettoyage : plus grande composante, trous bouchés, coeur opaque
    solid = (alpha > 0.5).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    mask = (lbl == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    ff = mask.copy()
    cv2.floodFill(ff, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 1)
    mask[ff == 0] = 1
    near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    alpha = np.where(mask == 1, np.maximum(alpha, cv2.erode(mask, np.ones((5, 5), np.uint8)).astype(np.float32)), alpha * near)
    alpha[cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) == 1] = 1
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    # 5) despill
    wall = cv2.cvtColor(np.dstack([wL, wa, wb]).clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    A = alpha[..., None]
    rgb = im.astype(np.float32)
    fg = np.where(A > 0.05, (rgb - (1 - A) * wall) / np.maximum(A, 0.05), rgb).clip(0, 255)
    cv2.imwrite(str(IMG / "founder_cutout.png"), np.dstack([fg, alpha * 255]).astype(np.uint8))
    print("→ assets/img/founder_cutout.png")


if __name__ == "__main__":
    main()
