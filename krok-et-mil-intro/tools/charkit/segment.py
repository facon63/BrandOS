"""Segmentation d'une illustration cartoon en parties (calques) à partir du trait noir.

Principe :
1. le trait (encre) sépare l'image en zones de remplissage fermées (composantes connexes) ;
2. chaque zone est attribuée à une partie par vote majoritaire sur des polygones approximatifs
   (priorité croissante dans l'ordre de déclaration) ;
3. des « barrières » (polylignes d'encre virtuelle) referment les zones dont le trait est ouvert ;
4. chaque pixel de trait est attribué à la partie dont le remplissage est le plus proche ;
   à égalité (<= 1 px), le calque du dessus l'emporte (il possède son contour) ;
5. aux coupes internes, l'alpha du calque du dessus est calculé par « matting d'encre » :
   couverture = (lum_remplissage_local - lum_pixel) / (lum_remplissage_local - lum_encre).
"""
import numpy as np
import cv2
from scipy import ndimage

from .img import ink_map, luminance


def raster_poly(shape, pts, value=1, thickness=None):
    m = np.zeros(shape, np.uint8)
    p = np.round(np.array(pts, np.float32) * 16).astype(np.int32)
    if thickness is None:
        cv2.fillPoly(m, [p], value, lineType=cv2.LINE_8, shift=4)
    else:
        cv2.polylines(m, [p], False, value, thickness=thickness, lineType=cv2.LINE_8, shift=4)
    return m


def segment(img, spec, line_thresh=0.35, own_radius=4, tie=1.5):
    """Retourne (labels HxW int, line_mask, fill_mask). labels: 0 = fond, i+1 = spec['parts'][i]."""
    rgb, a = img[..., :3], img[..., 3]
    h, w = a.shape
    ink, lum = ink_map(rgb, a)
    line = (ink > line_thresh) | ((lum < 0.07) & (a > 0.5))
    real_line = line.copy()
    # barrières : encre virtuelle
    for bar in spec.get("barriers", []):
        line |= raster_poly((h, w), bar, 1, thickness=1).astype(bool)
    solid = a > 0.5
    line &= solid
    fill = solid & ~line
    comp, ncomp = ndimage.label(fill)

    parts = spec["parts"]
    names = [p["name"] for p in parts]
    zs = np.array([p["z"] for p in parts])
    # carte approximative par polygones (ordre = priorité)
    rough = np.zeros((h, w), np.int32)
    order = sorted(range(len(parts)), key=lambda i: parts[i].get("prio", i))
    for i in order:
        p = parts[i]
        for poly in p.get("polys", []):
            m = raster_poly((h, w), poly).astype(bool)
            rough[m] = i + 1
    for ov in spec.get("overrides", []):  # polygones prioritaires (nom, poly)
        i = names.index(ov[0])
        rough[raster_poly((h, w), ov[1]).astype(bool)] = i + 1

    # vote par composante
    labels = np.zeros((h, w), np.int32)
    idx = comp[fill]
    rv = rough[fill]
    if ncomp:
        votes = np.zeros((ncomp + 1, len(parts) + 1), np.int64)
        np.add.at(votes, (idx, rv), 1)
        votes[:, 0] = 0  # pixels hors polygones : pas de vote
        win = votes.argmax(1)
        has = votes.max(1) > 0
        win[~has] = 0
        labels[fill] = win[idx]
    # composantes sans vote -> partie la plus proche (pixels de remplissage)
    unl = fill & (labels == 0)
    if unl.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~(labels > 0), return_indices=True)
        labels[unl] = labels[iy[unl], ix[unl]]

    # traits : remplissage le plus proche ; en cas de quasi-égalité (<= 1 px), le calque du dessus l'emporte
    fill_lab = labels.copy()
    INF = 1e9
    dists = np.full((len(parts), h, w), INF, np.float32)
    for i in range(len(parts)):
        m = fill_lab == i + 1
        if m.any():
            dists[i] = ndimage.distance_transform_edt(~m).astype(np.float32)
    dmin = dists.min(0)
    cand = dists <= (dmin[None] + tie) 
    cand &= dists <= own_radius
    zz = np.where(cand, zs[:, None, None], -INF)
    best = zz.argmax(0)
    has = cand.any(0)
    sel = line & has
    labels[sel] = best[sel] + 1
    # pixels de barrière qui ne sont pas de l'encre réelle : remplissage le plus proche, égalité -> dessous
    fake = line & ~real_line & has
    zz2 = np.where(dists <= dmin[None] + 0.5, -zs[:, None, None], -INF)
    best2 = zz2.argmax(0)
    labels[fake] = best2[fake] + 1
    line = real_line & solid
    # traits isolés restants -> plus proche
    rest = solid & (labels == 0)
    if rest.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~(labels > 0), return_indices=True)
        labels[rest] = labels[iy[rest], ix[rest]]
    # pixels semi-transparents du bord extérieur (alpha <= .5) -> partie la plus proche
    edge = (a > 0) & ~solid
    if edge.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~(labels > 0), return_indices=True)
        labels[edge] = labels[iy[edge], ix[edge]]
    return labels, line, fill, lum


def ink_matte(img, labels, line, lum, top_idx, lower_mask, band=2):
    """Couverture d'encre du calque `top_idx` sur les pixels de bord appartenant à `lower_mask`.

    Retourne alpha (HxW) à ajouter au calque du dessus sur la bande de transition, et la couleur d'encre locale.
    """
    h, w = labels.shape
    top = labels == top_idx
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
    near = cv2.dilate(top.astype(np.uint8), k).astype(bool) & lower_mask & ~top
    # seulement les pixels de transition collés au remplissage du dessous (pas les traits propres du dessous)
    dfill = ndimage.distance_transform_edt(~(lower_mask & ~line))
    near &= dfill <= 1.5
    if not near.any():
        return np.zeros((h, w), np.float32), None
    # luminance du remplissage local (pixels non-trait de la partie inférieure, loin du dessus)
    far = lower_mask & ~line & ~cv2.dilate(top.astype(np.uint8), k).astype(bool)
    L = np.where(far, lum, 0).astype(np.float32)
    W = far.astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), 3)
    Wb = cv2.GaussianBlur(W, (0, 0), 3)
    lfill = Lb / np.maximum(Wb, 1e-4)
    lfill = np.where(Wb > 1e-3, lfill, lum.max())
    lin = 0.03
    cov = np.clip((lfill - lum) / np.maximum(lfill - lin, 0.05), 0, 1)
    out = np.zeros((h, w), np.float32)
    out[near] = cov[near]
    return out, near
