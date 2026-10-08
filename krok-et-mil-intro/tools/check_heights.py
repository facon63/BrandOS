"""Vérifie automatiquement que Krok et Mil ont la même hauteur (sol -> sommet) dans chaque tenue.

Rend chaque variante seule sur fond transparent (composition HeightProbe, échelle 1 = 427 unités),
mesure la boîte englobante opaque et compare. Tolérance demandée : ±2 %.
Usage : python3 tools/check_heights.py   (REMOTION_BROWSER peut pointer vers un Chromium local)
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'heights')
GROUND = 540  # ligne de sol dans HeightProbe
VARIANTS = [(w, o, v) for o, v in [('base', 'front'), ('wasteland', 'front'), ('medieval', 'front'), ('medieval', 'back')] for w in ('krok', 'mil')]
# Les accessoires qui dépassent volontairement du crâne (antenne, plumet de Mil) sont masqués
# dans HeightProbe (prop noTop) : la règle porte sur « sommet de la tête au sol, casquette et épis compris ».


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {}
    for who, outfit, view in VARIANTS:
        f = os.path.join(OUT, f'{who}_{outfit}_{view}.png')
        props = json.dumps({'who': who, 'outfit': outfit, 'view': view})
        subprocess.run(['npx', 'remotion', 'still', 'src/index.ts', 'HeightProbe', f, f'--props={props}', '--log=error'], cwd=ROOT, check=True)
        img = Image.open(f).convert('RGBA')
        a = np.array(img)[..., 3] > 20
        bottom = np.where(a.sum(1) > 0)[0].max()
        top = np.where(a.sum(1) > 0)[0].min()
        res[(who, outfit, view)] = (GROUND - top, bottom - GROUND)
    ok = True
    print(f'{"variante":28s} hauteur(px)  écart vs Krok')
    for outfit, view in [('base', 'front'), ('wasteland', 'front'), ('medieval', 'front'), ('medieval', 'back')]:
        hk = res[('krok', outfit, view)][0]
        hm = res[('mil', outfit, view)][0]
        d = (hm - hk) / hk * 100
        flag = 'OK' if abs(d) <= 2 else 'HORS TOLÉRANCE'
        ok &= abs(d) <= 2
        print(f'krok {outfit:10s} {view:5s}       {hk:5d}')
        print(f'mil  {outfit:10s} {view:5s}       {hm:5d}      {d:+.2f} %  {flag}')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
