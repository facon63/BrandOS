"""Fonctions raster de base : chargement, nettoyage alpha, détection du trait, remplissage par diffusion, upscale."""
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage

LUMA = np.array([0.299, 0.587, 0.114], np.float32)


def load_rgba(path):
    """Charge un PNG en float32 RGBA [0,1] (non prémultiplié)."""
    return np.array(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0


def save_rgba(path, img):
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def luminance(rgb):
    return (rgb[..., :3] * LUMA).sum(-1)


def clean_alpha(img, interior_thresh=0.92):
    """Alpha intérieur bruité (253/254) -> 255 ; petits trous fermés -> bouchés par la couleur voisine."""
    out = img.copy()
    a = out[..., 3]
    solid = a > interior_thresh
    # intérieur = solide érodé de 1 px : on force l'opacité totale
    inner = ndimage.binary_erosion(solid, iterations=1)
    a[inner | solid] = np.where(a[inner | solid] > interior_thresh, 1.0, a[inner | solid])
    # trous fermés (fond non connecté au bord)
    bg = a < 0.5
    lab, n = ndimage.label(bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    holes = np.zeros_like(bg)
    for i in range(1, n + 1):
        if i not in border:
            holes |= lab == i
    if holes.any():
        holes_d = ndimage.binary_dilation(holes, iterations=1)
        fill = diffuse_fill(out[..., :3], ~holes_d & (a > 0.9), holes_d)
        out[..., :3][holes_d] = fill[holes_d]
        a[holes_d] = 1.0
    out[..., 3] = a
    return out


def ink_map(rgb, alpha, kernel=7):
    """Carte « encre » 0..1 : traits sombres fins par rapport au voisinage (black-hat sur luminance)."""
    lum = luminance(rgb) * alpha + (1 - alpha) * 1.0  # composé sur blanc
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    closed = cv2.morphologyEx(lum.astype(np.float32), cv2.MORPH_CLOSE, k)
    bh = closed - lum
    dark = np.clip((0.33 - lum) / 0.25, 0, 1)  # le trait est quasi noir
    return np.clip(bh / 0.18, 0, 1) * dark, lum


def diffuse_fill(rgb, known, region, iters=None):
    """Remplit `region` par diffusion des couleurs `known` (pyramide push-pull, sans fuite des pixels inconnus)."""
    h, w = known.shape
    levels = []
    c = rgb * known[..., None]
    wgt = known.astype(np.float32)
    cur_c, cur_w = c.astype(np.float32), wgt
    while min(cur_w.shape) > 2:
        levels.append((cur_c, cur_w))
        cur_c = cv2.resize(cur_c, (max(1, cur_c.shape[1] // 2), max(1, cur_c.shape[0] // 2)), interpolation=cv2.INTER_AREA)
        cur_w = cv2.resize(cur_w, (max(1, cur_w.shape[1] // 2), max(1, cur_w.shape[0] // 2)), interpolation=cv2.INTER_AREA)
    # remontée
    est = cur_c / np.maximum(cur_w, 1e-6)[..., None]
    for lc, lw in reversed(levels):
        up = cv2.resize(est, (lc.shape[1], lc.shape[0]), interpolation=cv2.INTER_LINEAR)
        lw3 = lw[..., None]
        local = lc / np.maximum(lw3, 1e-6)
        mix = np.clip(lw3 * 2.0, 0, 1)
        est = local * mix + up * (1 - mix)
    out = rgb.copy()
    out[region] = est[region]
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def upscale_lineart(img, f=4, ink_rgb=(0.02, 0.012, 0.012)):
    """Upscale ×f d'un calque RGBA style cartoon : Lanczos prémultiplié + accentuation du trait + silhouette nette.

    - couleur : Lanczos sur RGB prémultiplié, léger unsharp mask
    - trait : la couverture d'encre est lissée puis re-seuillée (smoothstep) => traits nets, anti-aliasés, sans escalier
    - alpha : bicubique puis smoothstep autour de 0.5 => bord net sans halo
    """
    a = img[..., 3:4]
    pre = np.concatenate([img[..., :3] * a, a], 2).astype(np.float32)
    h, w = a.shape[:2]
    up = cv2.resize(pre, (w * f, h * f), interpolation=cv2.INTER_LANCZOS4)
    up = np.clip(up, 0, 1)
    A = up[..., 3:4]
    rgb = up[..., :3] / np.maximum(A, 1e-4)
    rgb = np.clip(rgb, 0, 1)
    # unsharp léger sur la couleur
    blur = cv2.GaussianBlur(rgb, (0, 0), f * 0.5)
    rgb = np.clip(rgb + 0.45 * (rgb - blur), 0, 1)
    # encre : luminance relative au maximum local (remplissage environnant)
    lum = luminance(rgb)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * f + 3, 2 * f + 3))
    lmax = cv2.dilate(lum, k)
    lmax = cv2.GaussianBlur(lmax, (0, 0), f * 0.6)
    ink = np.clip((lmax - lum) / np.maximum(lmax, 0.06), 0, 1)
    ink = cv2.GaussianBlur(ink, (0, 0), f * 0.28)
    s = smoothstep(0.32, 0.62, ink)[..., None]
    ink_c = np.array(ink_rgb, np.float32)
    rgb = rgb * (1 - 0.9 * s) + ink_c * (0.9 * s)
    # alpha : silhouette nette (seuil doux autour de 0.5 sur l'alpha agrandi et légèrement lissé)
    As = cv2.GaussianBlur(A[..., 0], (0, 0), f * 0.22)
    A2 = smoothstep(0.30, 0.70, As)
    return np.concatenate([rgb, A2[..., None]], 2)


def composite_over(bg_rgb, layer, x=0, y=0):
    """Compose un calque RGBA (non prémultiplié) sur un fond RGB en place à (x,y)."""
    h, w = layer.shape[:2]
    H, W = bg_rgb.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return bg_rgb
    l = layer[y0 - y:y1 - y, x0 - x:x1 - x]
    a = l[..., 3:4]
    bg_rgb[y0:y1, x0:x1] = l[..., :3] * a + bg_rgb[y0:y1, x0:x1] * (1 - a)
    return bg_rgb


def load_spec_image(spec):
    """Charge la référence d'un spec, nettoie l'alpha et ajoute la marge basse éventuelle."""
    img = clean_alpha(load_rgba(spec["src"]))
    pad = spec.get("pad_bottom", 0)
    if pad:
        img = np.concatenate([img, np.zeros((pad,) + img.shape[1:], np.float32)], 0)
    return img
