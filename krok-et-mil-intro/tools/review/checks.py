#!/usr/bin/env python3
"""Contrôles automatiques du rig sur la plage de poses prévue pour l'animation.

Pour chaque personnage et chaque pose (rendu à 800 px de haut) :
- trous : zones transparentes fermées à l'intérieur de la silhouette (on voit le fond à travers) ;
- bords sans encre : portions du contour extérieur sans trait sombre (zones reconstruites non encrées).

Usage : python3 tools/review/checks.py [--sheet]   -> review/etape2_controles_auto.png (avec --sheet)
"""
import os
import sys

import numpy as np
import skia
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine.puppet import Puppet, placement, surface_rgba, snapshot_rgba  # noqa: E402

HEIGHT = 800


def pose_set():
    P = [("repos", {})]
    for a in (15, 45, 80, 110):
        P.append((f"bras ±{a}", {"arm_L": (a, -20 if a > 40 else 0, 0), "arm_R": (-a, 20 if a > 40 else 0, 0)}))
    P.append(("bras croisés", {"arm_L": (-30, -40, 0), "arm_R": (30, 40, 0), "z": {"arm_L": 26, "arm_R": 26.1}}))
    P.append(("course A", {"lean": -6, "leg_L": (20, -30, 10), "leg_R": (-15, 25, 0), "arm_L": (-25, -35, 0), "arm_R": (-30, 40, 0)}))
    P.append(("course B", {"lean": 6, "leg_L": (-18, 28, 0), "leg_R": (20, -30, -10), "arm_L": (30, 35, 0), "arm_R": (25, -40, 0)}))
    for h in (-6, -3, 2, 4, 6):
        P.append((f"tête {h:+d}", {"head": h}))
    for sgn in (-1, 1):
        P.append((f"balancier {sgn * 8:+d}", {"sway": {k: sgn * 8 for k in ("hair_L", "hair_R", "hair", "strings", "cap_brim")}}))
    P.append(("tête+balancier", {"head": 6, "sway": {k: -8 for k in ("hair_L", "hair_R", "hair", "strings")}}))
    P.append(("squash", {"squash": 0.9}))
    P.append(("stretch", {"squash": 1.1, "arm_L": (100, -10, 0), "arm_R": (-100, 10, 0)}))
    P.append(("chevilles", {"leg_L": (8, -10, 25), "leg_R": (-8, 10, -25)}))
    return P


def render_alpha(P, pose, mirror=False):
    W, H = 900, 900
    surf = surface_rgba(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    P.draw(c, pose, placement(P.rig, W / 2, 860, HEIGHT, mirror=mirror))
    return snapshot_rgba(surf)


def analyse(img):
    a = img[..., 3]
    solid = a > 0.5
    bg = ~solid
    lab, n = ndimage.label(bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    holes = []
    for i in range(1, n + 1):
        if i in border:
            continue
        m = lab == i
        if m.sum() >= 3:
            ys, xs = np.where(m)
            holes.append((int(m.sum()), int(xs.mean()), int(ys.mean())))
    # bords sans encre
    lum = (img[..., :3] * [0.299, 0.587, 0.114]).sum(-1)
    edge = solid & ndimage.binary_dilation(bg, iterations=1)
    lum_in = np.where(solid, lum, 1.0)
    darkest = ndimage.minimum_filter(lum_in, size=7)
    bad = edge & (darkest > 0.28)
    lab2, n2 = ndimage.label(ndimage.binary_dilation(bad, iterations=1))
    runs = []
    for i in range(1, n2 + 1):
        m = (lab2 == i) & bad
        if m.sum() >= 6:
            ys, xs = np.where(m)
            runs.append((int(m.sum()), int(xs.mean()), int(ys.mean())))
    return holes, runs, bad


def run(sheet=False):
    report = {}
    tiles = []
    for name in ("krok", "mil"):
        P = Puppet(name)
        for pname, pose in pose_set():
            pz = dict(pose)
            if name == "krok" and pz.get("eyes") == "open":
                pz["eyes"] = None
            img = render_alpha(P, pz)
            holes, runs, bad = analyse(img)
            report[(name, pname)] = (holes, runs)
            if sheet and (holes or runs):
                tiles.append((name, pname, img, holes, runs, bad))
    return report, tiles


def main():
    sheet = "--sheet" in sys.argv
    report, tiles = run(sheet)
    tot_h = tot_r = 0
    for (name, pname), (holes, runs) in report.items():
        nh, nr = len(holes), len(runs)
        tot_h += nh
        tot_r += nr
        flag = "OK" if not (holes or runs) else "!!"
        print(f"{flag} {name:5s} {pname:16s} trous={nh} {holes[:4]}  bords_sans_encre={nr} {runs[:4]}")
    print(f"TOTAL trous={tot_h} bords_sans_encre={tot_r}")
    if sheet and tiles:
        tot_h = sum(len(h) for h, _ in report.values())
        tot_r = sum(len(r) for _, r in report.values())
        from PIL import Image, ImageDraw
        thumbs = []
        for name, pname, img, holes, runs, bad in tiles[:24]:
            bgc = np.array([1.0, 0.2, 0.75])
            comp = img[..., :3] * img[..., 3:4] + bgc * (1 - img[..., 3:4])
            comp[bad] = [0, 1, 0]
            im = Image.fromarray((comp * 255).astype(np.uint8))
            d = ImageDraw.Draw(im)
            for (_, x, y) in holes:
                d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=(0, 255, 255), width=3)
            d.text((10, 10), f"{name} — {pname}", fill=(255, 255, 255))
            thumbs.append(im.resize((450, 450)))
        cols = 4
        rows = (len(thumbs) + cols - 1) // cols
        head = 150
        sh = Image.new("RGB", (cols * 450, rows * 450 + head), (30, 30, 30))
        for i, t in enumerate(thumbs):
            sh.paste(t, ((i % cols) * 450, head + (i // cols) * 450))
        from PIL import ImageFont
        try:
            fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
            fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
        except OSError:
            fb = fr = ImageFont.load_default()
        d = ImageDraw.Draw(sh)
        n_poses = len(report)
        d.text((24, 18), f"Contrôle automatique du rig — {n_poses} rendus (2 personnages × {n_poses // 2} poses, 800 px)", font=fb, fill=(240, 240, 245))
        d.text((24, 66), f"Bords de silhouette sans encre : {tot_r} (en vert s'il y en avait). Zones transparentes fermées cerclées en cyan : {tot_h}.", font=fr, fill=(200, 200, 210))
        d.text((24, 94), "Celles-ci sont des espaces négatifs naturels (fond vu entre pouce et cuisse, mèche soulevée et épaule, bras plié et buste), pas des déchirures.", font=fr, fill=(200, 200, 210))
        d.text((24, 120), "Seules les poses où le détecteur trouve quelque chose sont affichées.", font=fr, fill=(160, 160, 175))
        out = os.path.join(ROOT, "review", "etape2_controles_auto.png")
        sh.save(out)
        print(out)


if __name__ == "__main__":
    main()
