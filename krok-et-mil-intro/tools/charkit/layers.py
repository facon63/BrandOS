"""Construction des calques raster d'un personnage à partir de la carte de segmentation."""
import numpy as np
import cv2
from scipy import ndimage

from .img import diffuse_fill, luminance, smoothstep
from .segment import ink_matte, raster_poly

INK = np.array([0.020, 0.012, 0.012], np.float32)


def aa_poly_mask(shape, pts, ss=8):
    """Masque de polygone anti-aliasé (sur-échantillonnage)."""
    h, w = shape
    p = np.round(np.array(pts, np.float64) * ss * 16).astype(np.int32)
    m = np.zeros((h * ss, w * ss), np.uint8)
    cv2.fillPoly(m, [p], 255, lineType=cv2.LINE_8, shift=4)
    return cv2.resize(m.astype(np.float32) / 255.0, (w, h), interpolation=cv2.INTER_AREA)


def aa_stroke_mask(shape, pts, width=2.2, ss=8, closed=False):
    """Trait anti-aliasé à bouts ronds (sur-échantillonnage)."""
    h, w = shape
    p = np.round(np.array(pts, np.float64) * ss * 16).astype(np.int32)
    m = np.zeros((h * ss, w * ss), np.uint8)
    t = max(1, int(round(width * ss)))
    cv2.polylines(m, [p], closed, 255, thickness=t, lineType=cv2.LINE_AA, shift=4)
    for q in (p[0], p[-1]):
        cv2.circle(m, (int(q[0]), int(q[1])), t // 2, 255, -1, lineType=cv2.LINE_AA, shift=4)
    return cv2.resize(m.astype(np.float32) / 255.0, (w, h), interpolation=cv2.INTER_AREA)


def grain_like(rgb, mask, region, seed=0):
    """Bruit de grain dont l'écart-type imite le résidu haute fréquence de `mask`."""
    hf = rgb - cv2.GaussianBlur(rgb, (0, 0), 1.2)
    if mask.sum() < 20:
        return np.zeros_like(rgb)
    std = np.median(np.abs(hf[mask]), axis=0) * 1.4826
    std = np.clip(std, 0.0, 0.018)
    rng = np.random.RandomState(seed)
    n = rng.normal(0, 1, rgb.shape[:2]).astype(np.float32)
    n = cv2.GaussianBlur(n, (0, 0), 0.6)
    n /= max(n.std(), 1e-6)
    return (n[..., None] * std[None, None, :]) * region[..., None]


def build_layers(img, labels, line, lum, spec, ink_width=2.2):
    """Retourne dict nom -> RGBA float32 (taille image) au repos, avec zones cachées reconstruites.

    Passe 1 : couverture d'encre de chaque calque débordant sur la bande de 1 px des calques du dessous.
    Passe 2 : construction ; les pixels d'un calque recouverts par l'encre d'un calque du dessus sont
    « dé-mélangés » (encre retirée) pour ne pas laisser de fantôme de trait quand le dessus bouge.
    """
    rgb = img[..., :3]
    a = img[..., 3]
    h, w = a.shape
    parts = spec["parts"]
    zs = np.array([p["z"] for p in parts])
    order = np.argsort(zs)
    n = len(parts)
    lower_of = lambda i: np.isin(labels, [j + 1 for j in range(n) if zs[j] < zs[i]])
    upper_of = lambda i: np.isin(labels, [j + 1 for j in range(n) if zs[j] > zs[i]])

    # passe 1 : mattes
    mattes = {}
    for i in range(n):
        cov, near = ink_matte(img, labels, line, lum, i + 1, lower_of(i), band=1)
        mattes[i] = (cov, near)
    layers = {}
    for i in order:
        p = parts[i]
        idx = i + 1
        own = labels == idx
        upper = upper_of(i)
        L = np.zeros((h, w, 4), np.float32)
        L[..., :3] = rgb
        L[..., 3] = np.where(own, a, 0)
        # encre qui nous appartient et déborde sur les calques du dessous
        cov, near = mattes[i]
        if near is not None:
            L[..., :3][near] = INK
            L[..., 3][near] = np.maximum(L[..., 3][near], cov[near] * a[near])
        # couverture par l'encre des calques du dessus sur nos pixels
        ucov = np.zeros((h, w), np.float32)
        for j in range(n):
            if zs[j] > zs[i] and mattes[j][1] is not None:
                ucov = np.maximum(ucov, np.where(mattes[j][1] & own, mattes[j][0], 0))
        k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        up_d = cv2.dilate(upper.astype(np.uint8), k2).astype(bool)
        clean = own & ~line & ~up_d & (a > 0.9)
        if not clean.any():
            clean = own & ~line
        band = own & (ucov > 0.02)
        if band.any():
            filled = diffuse_fill(rgb, clean, band)
            unmix = np.clip((rgb - ucov[..., None] * INK) / np.maximum(1 - ucov[..., None], 0.2), 0, 1)
            wmix = smoothstep(0.5, 0.8, ucov)[..., None]
            dec = unmix * (1 - wmix) + filled * wmix
            L[..., :3][band] = dec[band]

        # zones cachées
        hid_alpha = np.zeros((h, w), np.float32)
        hid_color = np.zeros((h, w, 3), np.float32)
        ink_alpha = np.zeros((h, w), np.float32)
        shade_band = np.zeros((h, w), np.float32)
        ups = (upper & (a > 0.97)).astype(np.float32)
        for hd in p.get("hidden", []):
            pm = aa_poly_mask((h, w), hd["poly"])
            clipm = ups.copy()
            if hd.get("allow_outside", False):
                clipm = np.maximum(clipm, (a < 0.5).astype(np.float32))
            region = pm * clipm * (~own).astype(np.float32)
            # traits orphelins : nos pixels de trait collés au calque du dessus (son contour) dans la zone
            stray = np.zeros((h, w), bool)
            if hd.get("clean_lines"):
                near_up = cv2.dilate(upper.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
                stray = (pm > 0.5) & own & near_up & (luminance(rgb) < 0.45)
            fill = hd.get("fill", "diffuse")
            if fill == "diffuse":
                col = diffuse_fill(rgb, clean & ~stray, (region > 0) | stray)
            else:
                col = np.broadcast_to(np.array(fill, np.float32), (h, w, 3)).copy()
            if stray.any():
                L[..., :3][stray] = col[stray]
            hid_color = np.where((region > hid_alpha)[..., None], col, hid_color)
            hid_alpha = np.maximum(hid_alpha, region)
            for poly in hd.get("ink", []):
                sm = aa_stroke_mask((h, w), poly, ink_width)
                ink_alpha = np.maximum(ink_alpha, sm * (1 - own) * clipm)
                sb = aa_stroke_mask((h, w), poly, ink_width * 4.5)
                shade_band = np.maximum(shade_band, sb * clipm)
        if hid_alpha.any():
            g = grain_like(rgb, clean, hid_alpha > 0, seed=idx)
            hc = np.clip(hid_color + g, 0, 1)
            hc = hc * (1 - 0.22 * shade_band[..., None])
            base_a = L[..., 3]
            out_a = base_a + hid_alpha * (1 - base_a)
            out_c = (L[..., :3] * base_a[..., None] + hc * hid_alpha[..., None] * (1 - base_a[..., None])) / np.maximum(out_a, 1e-6)[..., None]
            m = hid_alpha > 0
            L[..., :3] = np.where(m[..., None], out_c, L[..., :3])
            L[..., 3] = out_a
        if ink_alpha.any():
            ia = ink_alpha
            base_a = L[..., 3]
            out_a = ia + base_a * (1 - ia)
            out_c = (INK * ia[..., None] + L[..., :3] * base_a[..., None] * (1 - ia[..., None])) / np.maximum(out_a, 1e-6)[..., None]
            m = ia > 0
            L[..., :3] = np.where(m[..., None], out_c, L[..., :3])
            L[..., 3] = out_a
        L[..., 3] = np.clip(L[..., 3], 0, 1)
        layers[p["name"]] = L
    return layers


def composite(layers, spec, bg=None, offsets=None):
    """Compose les calques au repos dans l'ordre z (vérification)."""
    parts = sorted(spec["parts"], key=lambda p: p["z"])
    first = next(iter(layers.values()))
    h, w = first.shape[:2]
    out = np.zeros((h, w, 3), np.float32) if bg is None else bg.copy()
    acc_a = np.zeros((h, w), np.float32)
    for p in parts:
        L = layers[p["name"]]
        al = L[..., 3:4]
        out = L[..., :3] * al + out * (1 - al)
        acc_a = al[..., 0] + acc_a * (1 - al[..., 0])
    return out, acc_a


def bbox(alpha, margin=2):
    ys, xs = np.where(alpha > 0.002)
    if len(xs) == 0:
        return 0, 0, 1, 1
    h, w = alpha.shape
    return max(0, xs.min() - margin), max(0, ys.min() - margin), min(w, xs.max() + 1 + margin), min(h, ys.max() + 1 + margin)
