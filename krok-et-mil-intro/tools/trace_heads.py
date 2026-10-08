"""Génère src/characters/traced/*.ts à partir des références assets/refs/83.png (Krok) et 90.png (Mil).

Usage : python3 tools/trace_heads.py
Dépendances : numpy, opencv-python-headless, pillow, vtracer (voir README).
"""
import os, sys
import numpy as np, cv2
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from trace_lib import trace_layer  # noqa: E402

REFS = os.path.join(ROOT, 'assets', 'refs')
OUT = os.path.join(ROOT, 'src', 'characters', 'traced')
DEBUG = os.path.join(ROOT, 'build', 'trace-debug')


def hsv_of(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return [hsv[..., i].astype(int) for i in range(3)]


def keep_mask(im, exclude, y_max, y_free, extra_cut=None):
    """Garde les pixels de la tête : tout ce qui n'est pas le vêtement (exclude),
    et les traits sombres seulement s'ils bordent un pixel coloré de la tête."""
    rgb, a = im[..., :3], im[..., 3]
    H, S, V = hsv_of(rgb)
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    region = yy < y_max
    dark = V < 70
    colored = (a > 128) & ~dark & ~exclude(H, S, V)
    near = cv2.dilate((colored & region).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) > 0
    keep = region & (a > 0) & ~exclude(H, S, V) & (colored | (dark & near) | (yy < y_free))
    if extra_cut is not None:
        keep &= ~extra_cut(xx, yy, H, S, V)
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 60:
            keep[lab == i] = False
    out = im.copy()
    out[..., 3] = np.where(keep, a, 0)
    return out


def write_ts(name, svg, box, comment):
    os.makedirs(OUT, exist_ok=True)
    x0, y0, x1, y1 = box
    with open(os.path.join(OUT, name + '.ts'), 'w') as f:
        f.write('// Fichier généré par tools/trace_heads.py — ne pas éditer à la main.\n')
        f.write(f'// {comment}\n')
        f.write(f'export const box = {{ x: {x0}, y: {y0}, w: {x1 - x0}, h: {y1 - y0} }};\n')
        f.write('export const svg = ' + repr(svg).replace("\\'", "'") + ';\n')


def main():
    os.makedirs(DEBUG, exist_ok=True)
    # --- Krok : tête + cheveux + casquette, sans le hoodie violet ni le t-shirt sombre du col
    k = np.array(Image.open(os.path.join(REFS, '83.png')).convert('RGBA'))
    purple = lambda H, S, V: (H >= 125) & (H <= 170) & (S > 45) & (V > 40)
    neck_tee = lambda xx, yy, H, S, V: (xx > 248) & (xx < 292) & (yy > 176) & (yy < 205) & (S < 90) & (V < 120) & (V >= 40)
    km = keep_mask(k, purple, y_max=205, y_free=136, extra_cut=neck_tee)
    Image.fromarray(km).save(os.path.join(DEBUG, 'krok_head.png'))
    box = (150, 35, 360, 210)
    write_ts('krokHead', trace_layer(km[box[1]:box[3], box[0]:box[2]], box[:2]), box,
             'Tête de Krok (cheveux, casquette à l\'envers, visage, barbe) — coordonnées de 83.png')

    # --- Mil : tête + casque + cou (jusqu'au col), sans le t-shirt vert
    m = np.array(Image.open(os.path.join(REFS, '90.png')).convert('RGBA'))
    green = lambda H, S, V: (H >= 22) & (H <= 50) & (S > 70) & (V > 60)
    mm = keep_mask(m, green, y_max=292, y_free=250)
    Image.fromarray(mm).save(os.path.join(DEBUG, 'mil_head.png'))
    box = (145, 80, 355, 295)
    write_ts('milHead', trace_layer(mm[box[1]:box[3], box[0]:box[2]], box[:2]), box,
             'Tête de Mil (épis, casque audio, visage, bouc, cou) — coordonnées de 90.png')
    print('ok')


if __name__ == '__main__':
    main()
