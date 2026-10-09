#!/usr/bin/env python3
"""Planches de validation de l'étape 2 (détourage + découpe en calques).

Usage : python3 tools/review/make_sheets.py
Sorties : review/etape2_*.png
"""
import os
import sys

import numpy as np
import skia
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from compose import load_rig, compose_rest  # noqa: E402
from engine.puppet import Puppet, placement, surface_rgba, snapshot_rgba  # noqa: E402

OUT = os.path.join(ROOT, "review")
os.makedirs(OUT, exist_ok=True)

FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(sz, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT_R, sz)
    except OSError:
        return ImageFont.load_default()


# fonds saturés et contrastés pour révéler tout halo (clair, sombre, complémentaire)
BGS = [(255, 43, 214), (0, 213, 255), (124, 255, 59), (26, 31, 92), (255, 138, 0), (17, 17, 17), (255, 255, 255), (255, 230, 0)]
PAGE_BG = (28, 26, 38)
TXT = (240, 240, 245)
DIM = (170, 170, 185)


def over_bg(L, bg):
    a = L[..., 3:4]
    return L[..., :3] * a + np.array(bg, np.float32) / 255.0 * (1 - a)


def to_pil(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))


def fit(img, maxw, maxh):
    s = min(maxw / img.width, maxh / img.height, 1.0)
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS), s


def header(draw, W, title, sub):
    draw.text((40, 28), title, font=font(40, True), fill=TXT)
    draw.text((40, 82), sub, font=font(20), fill=DIM)


def layer_sheet(name, title, notes):
    rig = load_rig(name)
    parts = sorted(rig["parts"], key=lambda p: p["z"])
    up = rig["upscale"]
    cols, tw, th = 5, 420, 470
    rows = (len(parts) + cols - 1) // cols
    W, H = cols * tw + 80, rows * th + 200
    page = Image.new("RGB", (W, H), PAGE_BG)
    d = ImageDraw.Draw(page)
    header(d, W, title, notes)
    for i, p in enumerate(parts):
        bg = BGS[i % len(BGS)]
        tile = Image.new("RGB", (tw - 20, th - 60), bg)
        img, s = fit(to_pil(over_bg(p["img"], bg)), tw - 40, th - 80)
        ox, oy = (tile.width - img.width) // 2, (tile.height - img.height) // 2
        tile.paste(img, (ox, oy))
        td = ImageDraw.Draw(tile)
        # pivot et os (repère src -> tuile)
        def tp(pt):
            return (ox + (pt[0] - p["offset_src"][0]) * up * s, oy + (pt[1] - p["offset_src"][1]) * up * s)
        if "bones" in p:
            names = list(p["bones"].keys())
            pts = [tp(p["bones"][n]) for n in names]
            td.line(pts, fill=(255, 255, 255), width=3)
            td.line(pts, fill=(0, 0, 0), width=1)
            for q in pts:
                td.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], outline=(0, 0, 0), fill=(255, 255, 255))
        if "pivot" in p:
            q = tp(p["pivot"])
            td.line([q[0] - 9, q[1], q[0] + 9, q[1]], fill=(0, 0, 0), width=3)
            td.line([q[0], q[1] - 9, q[0], q[1] + 9], fill=(0, 0, 0), width=3)
            td.line([q[0] - 8, q[1], q[0] + 8, q[1]], fill=(255, 255, 255), width=1)
            td.line([q[0], q[1] - 8, q[0], q[1] + 8], fill=(255, 255, 255), width=1)
        x, y = 40 + (i % cols) * tw, 130 + (i // cols) * th
        page.paste(tile, (x, y))
        tag = ""
        if p.get("constructed"):
            tag = "  construit en code"
        elif p.get("constructed_partly"):
            tag = "  complété en code"
        elif p.get("variant"):
            tag = "  variante (code)"
        d.text((x, y + th - 56), p["name"], font=font(20, True), fill=TXT)
        if tag:
            d.text((x + d.textlength(p["name"], font=font(20, True)) + 4, y + th - 54), tag, font=font(16, True), fill=(255, 200, 60))
        d.text((x, y + th - 30), f"z={p['z']}  {p['size_px'][0]}×{p['size_px'][1]} px  parent={p.get('parent')}", font=font(15), fill=DIM)
    path = os.path.join(OUT, f"etape2_{name}_calques.png")
    page.save(path, optimize=True)
    return path


def control_sheet():
    k, m = load_rig("krok"), load_rig("mil")
    W, H = 2400, 2050
    page = Image.new("RGB", (W, H), PAGE_BG)
    d = ImageDraw.Draw(page)
    header(d, W, "Étape 2 — contrôle : recomposition, halo, hauteur, variantes",
           "Recomposition des calques ×4 au repos vs référence ; zooms 100 % des bords sur fonds clair/sombre ; même hauteur Krok/Mil.")
    # 1) référence vs recomposition (Krok, Mil)
    y0 = 130
    x = 40
    for rig, ref_path, label in ((k, "assets/refs/83.png", "Krok"), (m, "assets/refs/90.png", "Mil")):
        ref = np.array(Image.open(os.path.join(ROOT, ref_path)).convert("RGBA")).astype(np.float32) / 255
        refc = over_bg(ref, (0, 213, 255))
        rec, _ = compose_rest(rig, np.array([0, 213, 255], np.float32) / 255)
        rec_s = np.array(Image.fromarray((rec * 255).astype(np.uint8)).resize((rig["src_size"][0], rig["src_size"][1]), Image.LANCZOS)).astype(np.float32) / 255
        h = min(refc.shape[0], rec_s.shape[0])
        diff = np.abs(rec_s[:h] - refc[:h]).max(2)
        a = to_pil(refc).resize((380, 380))
        b = to_pil(rec_s[:500]).resize((380, 380))
        dm = to_pil(np.repeat(np.clip(diff[:500] * 4, 0, 1)[..., None], 3, 2)).resize((380, 380))
        for j, (im, cap) in enumerate(((a, "référence"), (b, "recomposition calques"), (dm, f"écart ×4 (moy {diff[:500].mean() * 255:.2f}/255)"))):
            page.paste(im, (x + j * 390, y0 + 30))
            d.text((x + j * 390, y0 + 418), cap, font=font(17), fill=DIM)
        d.text((x, y0), label, font=font(24, True), fill=TXT)
        x += 1190
    # 2) zooms 100 % (pixels des calques ×4) sur fonds sombre et clair
    y1 = 620
    d.text((40, y1), "Bords à 100 % de la résolution de travail (×4) — aucun liseré blanc ni frange colorée", font=font(24, True), fill=TXT)
    rk_dark, _ = compose_rest(k, np.array([0.04, 0.04, 0.10], np.float32))
    rk_light, _ = compose_rest(k, np.array([1.0, 1.0, 1.0], np.float32))
    rm_dark, _ = compose_rest(m, np.array([0.04, 0.04, 0.10], np.float32))
    rm_mag, _ = compose_rest(m, np.array([1.0, 0.17, 0.84], np.float32))
    crops = [(rk_dark, (640, 360, 960, 680), "Krok — mèches (fond nuit)"),
             (rk_light, (640, 160, 960, 480), "Krok — casquette/visière (fond blanc)"),
             (rk_dark, (650, 1250, 970, 1570), "Krok — main gauche (fond nuit)"),
             (rm_mag, (600, 330, 920, 650), "Mil — épis (fond magenta)"),
             (rm_dark, (1160, 560, 1480, 880), "Mil — casque audio (fond nuit)"),
             (rm_dark, (600, 1960, 920, 2280), "Mil — main construite (fond nuit)")]
    for i, (img, (cx0, cy0, cx1, cy1), cap) in enumerate(crops):
        tile = to_pil(img[cy0:cy1, cx0:cx1])
        xx, yy = 40 + (i % 6) * 390, y1 + 50
        page.paste(tile.resize((370, 370), Image.NEAREST), (xx, yy))
        d.text((xx, yy + 378), cap, font=font(16), fill=DIM)
    # 3) même hauteur
    y2 = 1110
    d.text((40, y2), "Même hauteur (sommet casquette / épi → semelle), même sol", font=font(24, True), fill=TXT)
    surf = surface_rgba(1100, 860)
    c = surf.getCanvas()
    c.clear(skia.Color4f(0.36, 0.72, 0.98, 1))
    K, M = Puppet("krok"), Puppet("mil")
    Hpx = 760
    K.draw(c, {}, placement(K.rig, 330, 820, Hpx))
    M.draw(c, {}, placement(M.rig, 780, 820, Hpx))
    arr = snapshot_rgba(surf)
    duo = to_pil(arr[..., :3])
    dd = ImageDraw.Draw(duo)
    for yy_, col in ((820 - Hpx, (230, 20, 20)), (820, (0, 0, 0))):
        dd.line([0, yy_, 1100, yy_], fill=col, width=2)
    page.paste(duo, (40, y2 + 40))
    hk = (K.rig["sole_y"] - K.rig["top_y"])
    hm = (M.rig["sole_y"] - M.rig["top_y"]) * M.rig["scale_vs_krok"]
    d.text((40, y2 + 910), f"Hauteur Krok = {hk:.1f} u, Mil = {hm:.1f} u (u = px de la réf. de Krok) → écart {abs(hk - hm) / hk * 100:.2f} %",
           font=font(19), fill=TXT)
    # 4) variantes d'yeux
    xv = 1200
    d.text((xv, y2), "Variantes d'yeux dessinées en code (même trait)", font=font(24, True), fill=TXT)
    vk, _ = compose_rest(k, np.ones(3, np.float32))
    vkc, _ = compose_rest(k, np.ones(3, np.float32), variants=("eyes_closed",))
    vm, _ = compose_rest(m, np.ones(3, np.float32))
    vmo, _ = compose_rest(m, np.ones(3, np.float32), variants=("eyes_open",))
    vmc, _ = compose_rest(m, np.ones(3, np.float32), variants=("eyes_closed",))
    items = [(vk, (880, 380, 1240, 560), "Krok — référence"), (vkc, (880, 380, 1240, 560), "Krok — yeux fermés (ouf / clignement)"),
             (vm, (700, 640, 1140, 860), "Mil — référence (blasé)"), (vmo, (700, 640, 1140, 860), "Mil — yeux ouverts (action)"),
             (vmc, (700, 640, 1140, 860), "Mil — yeux fermés")]
    for i, (img, (cx0, cy0, cx1, cy1), cap) in enumerate(items):
        tile, _ = fit(to_pil(img[cy0:cy1, cx0:cx1]), 540, 250)
        xx, yy = xv + (i % 2) * 570, y2 + 50 + (i // 2) * 290
        page.paste(tile, (xx, yy))
        d.text((xx, yy + tile.height + 6), cap, font=font(16), fill=DIM)
    path = os.path.join(OUT, "etape2_controle.png")
    page.save(path, optimize=True)
    return path


def poses_sheet():
    K, M = Puppet("krok"), Puppet("mil")
    poses = [
        ("repos", {}),
        ("bras écartés", {"arm_L": (78, -22, 0), "arm_R": (-62, 26, 0), "head": -5, "sway": {"hair_L": 6, "hair_R": -4, "strings": 8, "hair": 3}}),
        ("course", {"lean": -6, "arm_L": (-25, -35, 0), "arm_R": (-30, 40, 0), "leg_L": (18, -28, 8), "leg_R": (-12, 20, 0), "sway": {"hair_L": -5, "hair_R": -7}}),
        ("saut (squash)", {"squash": 1.07, "arm_L": (110, -15, 0), "arm_R": (-100, 15, 0), "leg_L": (10, 22, 0), "leg_R": (-10, -22, 0), "head": 4, "eyes": "open"}),
        ("atterrissage", {"squash": 0.9, "arm_L": (35, 20, 0), "arm_R": (-35, -20, 0), "head": 3, "eyes": "closed"}),
    ]
    W, H = 2400, 1600
    surf = surface_rgba(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color4f(0.11, 0.10, 0.15, 1))
    paint = skia.Paint(Color=skia.Color4f(0.20, 0.55, 0.95, 1))
    c.drawRect(skia.Rect.MakeXYWH(0, 130, W, 700), paint)
    paint2 = skia.Paint(Color=skia.Color4f(0.98, 0.45, 0.20, 1))
    c.drawRect(skia.Rect.MakeXYWH(0, 860, W, 700), paint2)
    for i, (nm, pose) in enumerate(poses):
        x = 240 + i * 480
        pk = dict(pose)
        if pk.get("eyes") == "open":
            pk["eyes"] = None
        K.draw(c, pk, placement(K.rig, x, 800, 620, mirror=(i == 2)))
        M.draw(c, pose, placement(M.rig, x, 1530, 620, mirror=(i == 2)))
    arr = snapshot_rgba(surf)
    page = to_pil(arr[..., :3])
    d = ImageDraw.Draw(page)
    d.text((40, 28), "Étape 2 — poses test du rig (déformation par maillage, zones cachées reconstruites)", font=font(40, True), fill=TXT)
    d.text((40, 82), "« course » est rendue en miroir horizontal. Contrôle automatique sur 34 poses : voir etape2_controles_auto.png.", font=font(20), fill=DIM)
    for i, (nm, _) in enumerate(poses):
        d.text((240 + i * 480 - 80, 140), nm, font=font(24, True), fill=(255, 255, 255))
    path = os.path.join(OUT, "etape2_poses_test.png")
    page.save(path, optimize=True)
    return path


if __name__ == "__main__":
    for f in (layer_sheet("krok", "Étape 2 — Krok : calques raster (×4)", "Chaque calque sur un fond saturé différent (révèle tout halo). Croix = pivot ; ronds = os du skinning."),
              layer_sheet("mil", "Étape 2 — Mil : calques raster (×4)", "Jambes, chaussures, poignets et mains construits en code (même trait/grain que Krok, pantalon recoloré)."),
              control_sheet(), poses_sheet()):
        print(f)
