"""Construction des parties absentes de la référence de Mil (90.png s'arrête à la taille).

- Jambes : le pantalon de Krok (même style de trait, plis, grain) est ré-échantillonné à la
  morphologie de Mil (plus fin : ×0.90 en largeur, ×1.37 en hauteur en pixels-Mil) puis
  recoloré vers le gris-ardoise du pantalon visible sur la référence de Mil.
- Chaussures : celles de Krok, à l'échelle uniforme (pas de déformation), noires.
- Mains : la main gauche de Krok (même dessin, même peau à 2 % près), mise à l'échelle du poignet
  de Mil ; la main droite est son miroir. Un court « pont » de poignet relie l'avant-bras coupé à
  y=499 à la main, contours compris.
- Hauteur : semelle placée à y = SOLE_Y pour que (SOLE_Y - TOP_Y) × MIL_SCALE = hauteur de Krok.
"""
import numpy as np
import cv2

from .img import diffuse_fill, luminance, smoothstep
from .layers import INK, aa_stroke_mask, aa_poly_mask

# Échelle : 1 px de la référence de Mil = MIL_SCALE px de la référence de Krok.
# Choisie pour que les visages aient la même taille (écartement des yeux : Krok 40 px, Mil 53 px)
# et que la longueur de jambe visible soit celle de Krok (140 px).
KROK_TOP, KROK_SOLE = 47, 473
KROK_HEIGHT = KROK_SOLE - KROK_TOP  # 426
MIL_TOP = 89
MIL_SCALE = 0.728
SOLE_Y = int(round(MIL_TOP + KROK_HEIGHT / MIL_SCALE))  # ≈ 674

# Pantalon : repère de Krok -> repère de Mil
K_HEM, M_HEM = 333.0, 483.0      # ourlet du haut (hoodie / t-shirt)
K_CX, M_CX = 256.0, 247.5        # axe des hanches
PANTS_SX = 0.90                  # Mil plus fin
PANTS_SY = (SOLE_Y + 3 - M_HEM) / (KROK_SOLE - K_HEM)   # ourlet 3 px plus bas : recouvre le haut de la chaussure
SHOE_K = 1.25                    # chaussures : échelle uniforme (≈ 0.91 × Krok en taille monde)


def warp_layer(L, M, out_shape, interp=cv2.INTER_CUBIC):
    """Applique une transformation affine 2×3 à un calque RGBA non prémultiplié."""
    a = L[..., 3:4]
    pre = np.concatenate([L[..., :3] * a, a], 2).astype(np.float32)
    h, w = out_shape
    out = cv2.warpAffine(pre, M.astype(np.float32), (w, h), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    out = np.clip(out, 0, 1)
    A = out[..., 3:4]
    rgb = out[..., :3] / np.maximum(A, 1e-5)
    return np.concatenate([np.clip(rgb, 0, 1), A], 2)


def over(dst, src):
    """dst <- src over dst (RGBA non prémultipliés)."""
    sa = src[..., 3:4]
    da = dst[..., 3:4]
    oa = sa + da * (1 - sa)
    oc = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    return np.concatenate([oc, oa], 2)


def lab_stats(rgb, mask):
    lab = cv2.cvtColor(np.clip(rgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2LAB)
    v = lab[mask]
    return v.mean(0), v.std(0) + 1e-3


def recolor(L, src_stats, dst_stats, protect_dark=0.09):
    """Transfert de couleur (moyenne/écart-type en Lab) en épargnant le trait noir."""
    lab = cv2.cvtColor(np.clip(L[..., :3], 0, 1).astype(np.float32), cv2.COLOR_RGB2LAB)
    ms, ss = src_stats
    md, sd = dst_stats
    out = lab.copy()
    out[..., 0] = (lab[..., 0] - ms[0]) * min(sd[0] / ss[0], 1.2) + md[0]
    out[..., 1] = (lab[..., 1] - ms[1]) * 0.6 + md[1]
    out[..., 2] = (lab[..., 2] - ms[2]) * 0.6 + md[2]
    rgb = cv2.cvtColor(out, cv2.COLOR_LAB2RGB)
    lum = luminance(L[..., :3])
    w = np.clip((lum - protect_dark) / 0.06, 0, 1)[..., None]
    res = L.copy()
    res[..., :3] = np.clip(rgb * w + L[..., :3] * (1 - w), 0, 1)
    return res


def pants_matrix():
    # x' = M_CX + (x - K_CX) * sx ; y' = M_HEM + (y - K_HEM) * sy
    return np.array([[PANTS_SX, 0, M_CX - K_CX * PANTS_SX],
                     [0, PANTS_SY, M_HEM - K_HEM * PANTS_SY]])


def pants_pt(x, y):
    return (M_CX + (x - K_CX) * PANTS_SX, M_HEM + (y - K_HEM) * PANTS_SY)


def pants_matrix_mirror():
    # jambe de Krok retournée (éclairage de Mil venant de la gauche) : x' = M_CX + (K_CX - x) * sx
    return np.array([[-PANTS_SX, 0, M_CX + K_CX * PANTS_SX],
                     [0, PANTS_SY, M_HEM - K_HEM * PANTS_SY]])


def pants_pt_mirror(x, y):
    return (M_CX + (K_CX - x) * PANTS_SX, M_HEM + (y - K_HEM) * PANTS_SY)


def ink_rim(L, width, zone=None):
    """Assombrit vers l'encre une bande anti-aliasée de `width` px à l'intérieur de la silhouette."""
    from .layers import aa_inner_rim
    r = aa_inner_rim(L[..., 3], width)
    if zone is not None:
        r *= zone
    frac = np.clip(r / np.maximum(L[..., 3], 1e-4), 0, 1)[..., None]
    out = L.copy()
    out[..., :3] = L[..., :3] * (1 - frac) + INK * frac
    return out


def keep_main_blob(L, open_r=2):
    """Garde la plus grande composante et retire les épines fines (ouverture morphologique)."""
    from scipy import ndimage
    m = (L[..., 3] > 0.3).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * open_r + 1, 2 * open_r + 1))
    mo = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    lab, n = ndimage.label(mo)
    if n == 0:
        return L
    sizes = ndimage.sum(mo, lab, range(1, n + 1))
    big = (lab == (1 + int(np.argmax(sizes)))).astype(np.uint8)
    keep = cv2.dilate(big, np.ones((3, 3), np.uint8)).astype(np.float32)
    out = L.copy()
    out[..., 3] *= keep
    return out


def shoe_matrix(k_pivot, k_sole=KROK_SOLE):
    """Chaussure à l'échelle uniforme, centrée sous la cheville transformée, semelle au sol de Mil."""
    px, py = pants_pt(*k_pivot)
    s = SHOE_K
    # x' = px + (x - kx) * s ; y' = SOLE_Y + (y - k_sole) * s
    return np.array([[s, 0, px - k_pivot[0] * s],
                     [0, s, SOLE_Y - k_sole * s]])


def hand_matrix(k_top_center, m_top_center, sx, sy, mirror=False):
    kx, ky = k_top_center
    mx, my = m_top_center
    sx = -sx if mirror else sx
    return np.array([[sx, 0, mx - kx * sx],
                     [0, sy, my - ky * sy]])


def shoe_matrix_at(k_pivot, target, k_sole=KROK_SOLE):
    s = SHOE_K
    return np.array([[s, 0, target[0] - k_pivot[0] * s],
                     [0, s, SOLE_Y - k_sole * s]])


# chevilles de Krok (os) ; jambes de Mil = jambes de Krok en miroir (L <- R, R <- L)
K_ANKLE = {"L": (213, 452), "R": (291, 452)}
K_HIP = {"L": (225, 352), "R": (291, 352)}
K_KNEE = {"L": (221, 402), "R": (293, 402)}
MIRROR_SRC = {"L": "R", "R": "L"}


def mil_leg_bones(side):
    k = MIRROR_SRC[side]
    return {"hip": pants_pt_mirror(*K_HIP[k]), "knee": pants_pt_mirror(*K_KNEE[k]), "ankle": pants_pt_mirror(*K_ANKLE[k])}

HAND_SY = 1.27


def construct(mil_layers, mil_img, krok_layers, krok_spec, mil_spec):
    """Complète les calques de Mil. Retourne (layers, parts_extra, info)."""
    H, W = mil_img.shape[:2]
    out_shape = (H, W)
    info = {"mil_scale": MIL_SCALE, "sole_y": SOLE_Y}

    # --- couleurs cibles : pantalon visible de Mil (bande y 485-499)
    pel = mil_layers["pelvis"]
    pm = (pel[..., 3] > 0.95) & (luminance(pel[..., :3]) > 0.10)
    dst = lab_stats(pel[..., :3], pm)
    # couleurs source : pantalon de Krok
    kl = krok_layers["leg_L"]
    km = (kl[..., 3] > 0.95) & (luminance(kl[..., :3]) > 0.10)
    src = lab_stats(kl[..., :3], km)

    new = {}
    yy = np.arange(H)[:, None].astype(np.float32)
    xx = np.arange(W)[None, :].astype(np.float32)
    # --- jambes : pantalon de Krok en miroir (éclairage), recoloré, contour ré-épaissi au calibre de Mil
    Mp = pants_matrix_mirror()
    rim_w = mil_spec.get("rim_w", 2.4)
    for side in ("L", "R"):
        leg = warp_layer(recolor(krok_layers["leg_" + MIRROR_SRC[side]], src, dst), Mp, out_shape)
        new["leg_" + side] = ink_rim(leg, rim_w * 0.9)
    kt = krok_layers["torso"].copy()
    crotch = aa_poly_mask(kt.shape[:2], [(252, 336), (276, 336), (270, 360), (256, 360)])
    kt[..., 3] *= crotch
    crotch_m = warp_layer(recolor(kt, src, dst), Mp, out_shape)

    # --- chaussures : échelle uniforme, haut arrondi et encré là où il dépasse du pantalon
    legs_a = np.maximum(new["leg_L"][..., 3], new["leg_R"][..., 3])
    y_vis = SOLE_Y + (444 - KROK_SOLE) * SHOE_K
    from scipy import ndimage
    for side, kpiv in (("L", (210, 450)), ("R", (285, 449))):
        ankle = pants_pt_mirror(*K_ANKLE[MIRROR_SRC[side]])
        shoe = warp_layer(krok_layers["shoe_" + side], shoe_matrix_at(kpiv, ankle), out_shape)
        leg_a = new["leg_" + side][..., 3]
        under = cv2.dilate((leg_a > 0.4).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32)
        sm = shoe[..., 3] > 0.3
        cols = np.where(sm.any(0))[0]
        xc, hw = 0.5 * (cols.min() + cols.max()), 0.5 * (cols.max() - cols.min())
        # largeur du pantalon juste au-dessus de la chaussure
        row = int(round(y_vis)) - 3
        pc = np.where(leg_a[row] > 0.5)[0]
        pw = 0.5 * (pc.max() - pc.min()) if len(pc) else hw * 0.7
        pcx = 0.5 * (pc.max() + pc.min()) if len(pc) else xc
        ex = np.clip((np.abs(xx - pcx) - pw) / max(hw - pw, 1.0), 0, 1)
        y_top = y_vis + 0.5 + 6.0 * ex ** 1.6           # col arrondi autour de la cheville
        under1 = cv2.dilate((leg_a > 0.4).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)
        keep = np.where(yy < y_top, under1, 1.0)
        # sous l'ourlet (irrégulier) : la chaussure remplit tout jusqu'au bas du pantalon, sans jour
        r0, r1 = int(y_vis) - 18, int(y_vis) + 10
        band = leg_a[r0:r1] > 0.4
        has = band.any(0)
        y_pb = np.where(has, r0 + (r1 - r0 - 1) - np.argmax(band[::-1], 0), 1e9).astype(np.float32)
        keep = np.maximum(keep, ((yy >= y_pb[None, :] - 2.0) & has[None, :]).astype(np.float32))
        shoe[..., 3] *= keep
        # contour du haut exposé (hors pantalon)
        shoe[..., 3] = smoothstep(0.3, 0.7, cv2.GaussianBlur(shoe[..., 3], (0, 0), 0.6))
        from .layers import aa_inner_rim
        r = aa_inner_rim(shoe[..., 3], rim_w) * (yy < y_vis + 9) * np.clip(1 - leg_a * 2, 0, 1)
        frac = np.clip(r / np.maximum(shoe[..., 3], 1e-4), 0, 1)[..., None]
        shoe[..., :3] = shoe[..., :3] * (1 - frac) + INK * frac
        new["shoe_" + side] = shoe
        info["ankle_" + side] = ankle

    # --- bassin : bande d'origine, bas adouci, extrémités suivant le pantalon, + entrejambe
    pel = pel.copy()
    fade = np.clip((500 - yy) / 6.0, 0, 1)
    pel[..., 3] *= fade
    lm = legs_a > 0.5
    span = np.zeros((H, W), np.float32)
    for y in range(470, min(H, 505)):
        c = np.where(lm[y])[0]
        if len(c):
            span[y, max(0, c.min() - 1):c.max() + 2] = 1.0
    span = cv2.GaussianBlur(span, (0, 0), 0.7)
    pel[..., 3] *= np.where(yy >= 484, span, 1.0)
    pel = over(crotch_m, pel)
    new["pelvis"] = pel

    # --- mains : main gauche de Krok, plus longue (doigts fins de Mil), largeur du poignet de Mil
    ka = krok_layers["arm_L"]
    hand = ka.copy()
    hm = aa_poly_mask(hand.shape[:2], [(178, 322.5), (208, 322.5), (214, 341), (208, 355), (186, 360), (172, 346), (174, 331)])
    hand[..., 3] *= hm
    K_HAND_TOP = (191.0, 322.0)
    K_HAND_TOP_W = 30.0
    for side, mirror in (("L", False), ("R", True)):
        arm = mil_layers["arm_" + side].copy()
        # bords de l'avant-bras mesurés juste au-dessus de la coupe du cadre (y=496)
        cols = np.where(arm[496, :, 3] > 0.5)[0]
        fx0, fx1 = float(cols.min()), float(cols.max() + 1)
        cx = 0.5 * (fx0 + fx1)
        fw = fx1 - fx0
        # même main des deux côtés : largeur réglée sur le poignet (avant-bras symétriques)
        sx, sy = round(fw * 0.97 / 30.0, 3), HAND_SY
        ww = K_HAND_TOP_W * sx
        E = 10.0
        y_src, y_cut = 496.0, 499.0
        t = np.clip((yy - y_cut) / E, 0, 1)
        wt = fw + (ww - fw) * t
        map_x = (cx + (xx - cx) * (fw / wt)).astype(np.float32)
        map_y = np.full((H, W), y_src, np.float32)
        a = arm[..., 3:4]
        pre = np.concatenate([arm[..., :3] * a, a], 2).astype(np.float32)
        ext = cv2.remap(pre, np.broadcast_to(map_x, (H, W)).copy(), map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        ext_a = ext[..., 3:4]
        ext_rgb = ext[..., :3] / np.maximum(ext_a, 1e-5)
        band = ((yy >= y_cut - 2) & (yy < y_cut + E)).astype(np.float32)
        fadeh = np.clip((y_cut + E - yy) / 4.0, 0, 1)
        ext_l = np.concatenate([np.clip(ext_rgb, 0, 1), ext_a * (band * fadeh)[..., None]], 2)
        top_y = y_cut + E - 4.0
        Mh = hand_matrix(K_HAND_TOP, (cx, top_y), sx, sy, mirror)
        hand_m = keep_main_blob(warp_layer(hand, Mh, out_shape))
        arm_cut = arm.copy()
        arm_cut[..., 3] *= (yy < y_cut).astype(np.float32)
        comp = over(hand_m, ext_l)
        comp = over(comp, arm_cut)
        new["arm_" + side] = comp
        info["hand_" + side] = (cx, top_y + 18 * sy)
        info["hand_scale_" + side] = (sx, sy)
    return new, info
