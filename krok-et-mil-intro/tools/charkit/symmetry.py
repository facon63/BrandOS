"""Symétrisation des bras.

Les références sont dessinées de trois-quarts : un bras est nettement plus fin que l'autre
(Krok : manche droite vue de profil, ~20 px contre ~45 ; Mil : bras gauche ~22 px contre ~37).
En animation cet écart saute aux yeux. Le bras fin est donc remplacé par le miroir du bras
complet, placé à l'épaule opposée (axe de symétrie = milieu des deux épaules).

`shading="mirror"` : le modelé est retourné avec la forme (cas de Krok : le liseré clair passe
sur le bord extérieur du bras droit, côté de sa lumière de contre-jour).
`shading="keep"` : la silhouette et les traits sont retournés mais l'ombrage intérieur garde
le sens d'origine (cas de Mil, éclairé par la gauche : le reflet reste à gauche de chaque bras).
"""
import numpy as np

from .img import luminance


def mirror_x(L, axis):
    """Miroir horizontal exact (par indices) d'un calque autour de x = axis (px src)."""
    h, w = L.shape[:2]
    out = np.zeros_like(L)
    k = int(round(2 * axis)) - 1  # x' = k - x
    xs = np.arange(w)
    src = k - xs
    ok = (src >= 0) & (src < w)
    out[:, xs[ok]] = L[:, src[ok]]
    return out


def mirror_point(p, axis):
    return (2 * axis - p[0], p[1])


def _row_extent(alpha_row, thr=0.5):
    xs = np.where(alpha_row > thr)[0]
    if len(xs) == 0:
        return None
    return xs.min(), xs.max()


def mirror_keep_shading(L, axis, line_lum=0.28):
    """Silhouette et traits retournés, ombrage intérieur conservé dans son sens d'origine."""
    M = mirror_x(L, axis)
    out = M.copy()
    h, w = L.shape[:2]
    lumM = luminance(M[..., :3])
    for y in range(h):
        eM = _row_extent(M[y, :, 3])
        eL = _row_extent(L[y, :, 3])
        if eM is None or eL is None:
            continue
        cM = 0.5 * (eM[0] + eM[1])
        cL = 0.5 * (eL[0] + eL[1])
        xs = np.arange(eM[0], eM[1] + 1)
        inner = (M[y, xs, 3] > 0.9) & (lumM[y, xs] > line_lum)
        if not inner.any():
            continue
        src = np.clip(np.round(cL + (xs - cM)).astype(int), eL[0], eL[1])
        srcok = (L[y, src, 3] > 0.9) & (luminance(L[y, src, :3]) > line_lum)
        sel = inner & srcok
        out[y, xs[sel], :3] = L[y, src[sel], :3]
    return out


def symmetrize(layers, parts_meta, rule):
    """Remplace layers[rule['part']] par le miroir de layers[rule['of']] ; met à jour pivot et os.

    rule = {"part": "arm_R", "of": "arm_L", "axis": 256.0, "shading": "mirror"|"keep"}
    """
    if "patch_under" in rule:
        n = rule["patch_under"]
        layers[n] = mirror_patch_under(layers[n], rule["poly"], float(rule["axis"]))
        return layers
    src, dst, axis = rule["of"], rule["part"], float(rule["axis"])
    fn = mirror_x if rule.get("shading", "mirror") == "mirror" else mirror_keep_shading
    layers[dst] = fn(layers[src], axis)
    if src + "__seam" in layers:
        layers[dst + "__seam"] = mirror_x(layers[src + "__seam"], axis)
    smeta = next(m for m in parts_meta if m["name"] == src)
    dmeta = next(m for m in parts_meta if m["name"] == dst)
    if "pivot" in smeta:
        dmeta["pivot"] = mirror_point(smeta["pivot"], axis)
    if "bones" in smeta:
        dmeta["bones"] = {k: mirror_point(v, axis) for k, v in smeta["bones"].items()}
    for k in ("blend", "widen"):
        dmeta.pop(k, None)
        if k in smeta:
            dmeta[k] = smeta[k]
    dmeta["mirror_of"] = src
    return layers


def mirror_patch_under(L, poly, axis):
    """Recopie en miroir une zone du calque (polygone, côté source) SOUS le calque existant :
    seuls les vides du côté opposé sont comblés (ex. haut de capuche au-dessus d'une épaule)."""
    from .layers import aa_poly_mask
    m = aa_poly_mask(L.shape[:2], poly)
    src = L.copy()
    src[..., 3] *= m
    P = mirror_x(src, axis)
    a, pa = L[..., 3:4], P[..., 3:4]
    oa = a + pa * (1 - a)
    oc = (L[..., :3] * a + P[..., :3] * pa * (1 - a)) / np.maximum(oa, 1e-6)
    return np.concatenate([oc, oa], 2)
