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

from .img import diffuse_fill, luminance
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
PANTS_SY = (SOLE_Y - M_HEM) / (KROK_SOLE - K_HEM)
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


def shoe_matrix(k_pivot, k_sole=KROK_SOLE):
    """Chaussure à l'échelle uniforme, centrée sous la cheville transformée, semelle au sol de Mil."""
    px, py = pants_pt(*k_pivot)
    s = SHOE_K
    # x' = px + (x - kx) * s ; y' = SOLE_Y + (y - k_sole) * s
    return np.array([[s, 0, px - k_pivot[0] * s],
                     [0, s, SOLE_Y - k_sole * s]])


def hand_matrix(k_top_center, m_top_center, s, mirror=False):
    kx, ky = k_top_center
    mx, my = m_top_center
    sx = -s if mirror else s
    return np.array([[sx, 0, mx - kx * sx],
                     [0, s, my - ky * s]])


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
    # --- jambes
    Mp = pants_matrix()
    for side in ("L", "R"):
        leg = warp_layer(recolor(krok_layers["leg_" + side], src, dst), Mp, out_shape)
        new["leg_" + side] = leg
    # entrejambe (dans le torse de Krok) -> intégré au bassin de Mil
    kt = krok_layers["torso"].copy()
    crotch = aa_poly_mask(kt.shape[:2], [(252, 336), (276, 336), (270, 360), (256, 360)])
    kt[..., 3] *= crotch
    crotch_m = warp_layer(recolor(kt, src, dst), Mp, out_shape)

    # --- chaussures
    for side, piv in (("L", (210, 450)), ("R", (285, 449))):
        Ms = shoe_matrix(piv)
        shoe = warp_layer(krok_layers["shoe_" + side], Ms, out_shape)
        # le haut caché de la chaussure n'existe que sous le pantalon (plus étroit chez Mil)
        y_vis = SOLE_Y + (444 - KROK_SOLE) * SHOE_K
        leg_a = cv2.dilate(new["leg_" + side][..., 3], np.ones((3, 3), np.uint8))
        yy = np.arange(H)[:, None]
        keep = np.where(yy < y_vis + 1.0, leg_a, 1.0)
        shoe[..., 3] *= keep
        # liseré d'encre sur le haut de chaussure exposé à côté du pantalon
        top_band = (yy >= y_vis + 0.5) & (yy < y_vis + 2.6) & (shoe[..., 3] > 0.3) & (leg_a < 0.4)
        shoe[..., :3][top_band] = INK
        new["shoe_" + side] = shoe
    info["ankle_L"] = pants_pt(210, 450)
    info["ankle_R"] = pants_pt(285, 449)

    # --- bassin : bande d'origine de Mil, bas adouci + entrejambe
    pel = pel.copy()
    yy = np.arange(H)[:, None]
    fade = np.clip((500 - yy) / 6.0, 0, 1)  # fondu sur les 6 dernières lignes (coupe du cadre)
    pel[..., 3] *= fade
    pel = over(crotch_m, pel)
    new["pelvis"] = pel

    # --- mains
    # main gauche de Krok (sous le poignet du hoodie), largeur du haut de la main ≈ 30 px
    ka = krok_layers["arm_L"]
    hand = ka.copy()
    # contour de la main seule (sans le bas de la manche violette)
    hm = aa_poly_mask(hand.shape[:2], [(178, 322.5), (208, 322.5), (214, 341), (208, 355), (186, 360), (172, 346), (174, 331)])
    hand[..., 3] *= hm
    K_HAND_TOP = (191.0, 322.0)
    K_HAND_TOP_W = 30.0
    yy_idx = np.arange(H)[:, None].astype(np.float32)
    xx_idx = np.arange(W)[None, :].astype(np.float32)
    for side, (fx0, fx1), mirror in (("L", (160.0, 187.5), False), ("R", (305.5, 340.0), True)):
        arm = mil_layers["arm_" + side].copy()
        cx = 0.5 * (fx0 + fx1)
        fw = fx1 - fx0
        # largeur visée au poignet : légère conicité (avant-bras -> poignet)
        ww = fw * (0.94 if side == "L" else 0.90)
        s = (ww + 1.5) / K_HAND_TOP_W
        E = 9.0                          # prolongement de l'avant-bras (px)
        y_src = 496.0                    # ligne profil de référence (avant la coupe du cadre)
        y_cut = 499.0
        # prolongement : on étire horizontalement la ligne profil autour de l'axe, conicité linéaire
        t = np.clip((yy_idx - y_cut) / E, 0, 1)
        wt = fw + (ww - fw) * t
        map_x = (cx + (xx_idx - cx) * (fw / wt)).astype(np.float32)
        map_y = np.full((H, W), y_src, np.float32)
        a = arm[..., 3:4]
        pre = np.concatenate([arm[..., :3] * a, a], 2).astype(np.float32)
        ext = cv2.remap(pre, np.broadcast_to(map_x, (H, W)).copy(), map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        ext_a = ext[..., 3:4]
        ext_rgb = ext[..., :3] / np.maximum(ext_a, 1e-5)
        band = ((yy_idx >= y_cut - 2) & (yy_idx < y_cut + E)).astype(np.float32)
        fade = np.clip((y_cut + E - yy_idx) / 3.0, 0, 1)  # bas adouci sur 3 px, par-dessus la main
        ext_l = np.concatenate([np.clip(ext_rgb, 0, 1), ext_a * (band * fade)[..., None]], 2)
        # main : haut caché sous le prolongement (recouvrement 3 px)
        top_y = y_cut + E - 3.0
        Mh = hand_matrix(K_HAND_TOP, (cx, top_y), s, mirror)
        hand_m = warp_layer(hand, Mh, out_shape)
        arm_cut = arm.copy()
        arm_cut[..., 3] *= (yy_idx < y_cut).astype(np.float32)
        comp = over(hand_m, ext_l)
        comp = over(comp, arm_cut)
        new["arm_" + side] = comp
        info["hand_" + side] = (cx, top_y + 18 * s)
        info["hand_scale_" + side] = s
    return new, info
