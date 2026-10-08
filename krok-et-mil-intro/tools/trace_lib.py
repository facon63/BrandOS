"""Vectorisation fidèle des références (têtes) de Krok et Mil.

Choix retenu après essais (voir CHARACTER_SHEET.md, section « Méthode ») :
  1. on isole un calque (ex. la tête) par masque de couleur sur la référence ;
  2. agrandissement x4 (Lanczos prémultiplié) pour lisser les courbes ;
  3. tracé couleur empilé avec vtracer -> chemins SVG (détails des yeux, barbe, mèches conservés) ;
  4. contour de silhouette régulier ajouté dessous (trait noir épais et constant, comme les références).
Les coordonnées produites sont celles des pixels de la référence (0..500).
"""
import os, re, tempfile
import numpy as np, cv2, vtracer
from PIL import Image

S = 4  # facteur d'agrandissement avant tracé
INK = '#0b0909'


def upscale_rgba(arr, s=S):
    a = arr[..., 3:4].astype(float) / 255
    pm = np.concatenate([arr[..., :3] * a, arr[..., 3:4]], -1).astype(np.uint8)
    up = np.array(Image.fromarray(pm).resize((arr.shape[1] * s, arr.shape[0] * s), Image.LANCZOS)).astype(float)
    ua = up[..., 3:4] / 255
    rgb = np.where(ua > 0.02, up[..., :3] / np.maximum(ua, 1e-3), 0)
    return np.clip(rgb, 0, 255).astype(np.uint8), up[..., 3]


def _paths(svg_text):
    return re.findall(r'<path[^>]*/>', svg_text)


def trace_layer(rgba, origin, outline=2.2, speckle=8, color_precision=6, layer_difference=24):
    """rgba : crop (H,W,4) uint8 ; origin : (x0,y0) du crop dans la référence.
    Retourne un fragment SVG (string) en coordonnées de la référence."""
    rgb, alpha = upscale_rgba(rgba)
    H, W = alpha.shape
    solid = cv2.GaussianBlur((alpha > 127).astype(np.float32), (0, 0), 1.5) > 0.5
    tmp = tempfile.mkdtemp()
    img = np.dstack([rgb, np.where(solid, 255, 0).astype(np.uint8)])
    Image.fromarray(img).save(os.path.join(tmp, 'c.png'))
    vtracer.convert_image_to_svg_py(os.path.join(tmp, 'c.png'), os.path.join(tmp, 'c.svg'), colormode='color',
                                    hierarchical='stacked', mode='spline', filter_speckle=speckle,
                                    color_precision=color_precision, layer_difference=layer_difference,
                                    corner_threshold=60, length_threshold=4.0, max_iterations=10,
                                    splice_threshold=45, path_precision=2)
    fills = _paths(open(os.path.join(tmp, 'c.svg')).read())
    # silhouette : contour extérieur régulier
    bw = np.where(solid[..., None], 0, 255).astype(np.uint8).repeat(3, -1)
    Image.fromarray(bw).save(os.path.join(tmp, 's.png'))
    vtracer.convert_image_to_svg_py(os.path.join(tmp, 's.png'), os.path.join(tmp, 's.svg'), colormode='binary',
                                    mode='spline', filter_speckle=20, corner_threshold=60, length_threshold=4.0,
                                    max_iterations=10, splice_threshold=45, path_precision=2)
    sil = _paths(open(os.path.join(tmp, 's.svg')).read())
    sw = outline * 2 * S  # moitié du trait visible à l'extérieur
    sil = [re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{INK}" stroke="{INK}" stroke-width="{sw}" stroke-linejoin="round"', p)
           for p in sil]
    x0, y0 = origin
    return (f'<g transform="translate({x0} {y0}) scale({1 / S})">'
            f'<g class="sil">{"".join(sil)}</g><g class="fills">{"".join(fills)}</g></g>')
