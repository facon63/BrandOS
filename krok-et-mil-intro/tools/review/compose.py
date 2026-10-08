"""Recomposition au repos des calques ×4 exportés (vérification et planches)."""
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_rig(name):
    d = os.path.join(ROOT, "assets", "characters", name)
    rig = json.load(open(os.path.join(d, "rig.json")))
    for p in rig["parts"]:
        p["img"] = np.array(Image.open(os.path.join(d, p["file"])).convert("RGBA")).astype(np.float32) / 255.0
    return rig


def compose_rest(rig, bg_rgb, variants=(), skip=()):
    up = rig["upscale"]
    W, H = rig["src_size"][0] * up, rig["src_size"][1] * up
    out = np.zeros((H, W, 3), np.float32)
    out[:] = bg_rgb
    alpha = np.zeros((H, W), np.float32)
    for p in sorted(rig["parts"], key=lambda q: q["z"]):
        if p.get("variant") and p["name"] not in variants:
            continue
        if p["name"] in skip:
            continue
        L = p["img"]
        x0, y0 = p["offset_src"][0] * up, p["offset_src"][1] * up
        h, w = L.shape[:2]
        a = L[..., 3:4]
        out[y0:y0 + h, x0:x0 + w] = L[..., :3] * a + out[y0:y0 + h, x0:x0 + w] * (1 - a)
        alpha[y0:y0 + h, x0:x0 + w] = a[..., 0] + alpha[y0:y0 + h, x0:x0 + w] * (1 - a[..., 0])
    return out, alpha


def to_img(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))
