#!/usr/bin/env python3
"""Construit les calques des personnages : découpe, reconstruction, parties construites, upscale ×4, rig.

Usage : python3 tools/build_characters.py   (depuis la racine du projet)
Sorties : assets/characters/<nom>/layers/*.png + rig.json
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charkit.img import load_spec_image, save_rgba, upscale_lineart  # noqa: E402
from charkit.segment import segment  # noqa: E402
from charkit.layers import build_layers, bbox  # noqa: E402
from charkit import construct_mil as CM  # noqa: E402
from charkit import expressions as EX  # noqa: E402
from charkit import spec_krok, spec_mil  # noqa: E402

UP = 4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_1x(spec):
    img = load_spec_image(spec)
    labels, line, fill, lum = segment(img, spec)
    layers = build_layers(img, labels, line, lum, spec)
    return img, labels, layers


def export(name, img, layers, parts_meta, extra):
    out_dir = os.path.join(ROOT, "assets", "characters", name)
    lay_dir = os.path.join(out_dir, "layers")
    os.makedirs(lay_dir, exist_ok=True)
    rig_parts = []
    # liserés de couture : calques superposés au membre (même maillage), fondus selon l'angle
    for meta in list(parts_meta):
        sn = meta["name"] + "__seam"
        if sn in layers and layers[sn][..., 3].max() > 0.05:
            parts_meta.append({"name": sn, "z": meta["z"] + 0.001, "parent": meta.get("parent"),
                               "pivot": meta.get("pivot"), "overlay_of": meta["name"]})
    for meta in parts_meta:
        L = layers[meta["name"]]
        x0, y0, x1, y1 = bbox(L[..., 3], margin=4)
        crop = L[y0:y1, x0:x1]
        up = upscale_lineart(crop, UP)
        fn = f"layers/{meta['name']}.png"
        save_rgba(os.path.join(out_dir, fn), up)
        entry = {k: v for k, v in meta.items() if k not in ("polys", "hidden", "prio")}
        entry.update({"file": fn, "offset_src": [int(x0), int(y0)], "size_px": [int(up.shape[1]), int(up.shape[0])]})
        rig_parts.append(entry)
    rig = {"name": name, "upscale": UP, "src_size": [int(img.shape[1]), int(img.shape[0])], "parts": rig_parts}
    rig.update(extra)
    with open(os.path.join(out_dir, "rig.json"), "w") as f:
        json.dump(rig, f, indent=1, ensure_ascii=False, default=lambda o: list(o) if isinstance(o, tuple) else float(o))
    return rig


def main():
    t0 = time.time()
    k_img, k_lab, k_layers = build_1x(spec_krok.spec)
    m_img, m_lab, m_layers = build_1x(spec_mil.spec)
    new, info = CM.construct(m_layers, m_img, k_layers, spec_krok.spec, spec_mil.spec)
    m_layers.update(new)

    # variantes d'yeux (dessinées en code)
    k_layers["eyes_closed"] = EX.krok_eyes_closed(k_img.shape[:2])
    m_layers["eyes_open"] = EX.mil_eyes_open(m_img.shape[:2])
    m_layers["eyes_closed"] = EX.mil_eyes_closed(m_img.shape[:2])

    k_meta = [dict(p) for p in spec_krok.spec["parts"]]
    k_meta.append({"name": "eyes_closed", "z": 31, "parent": "head", "pivot": (262, 186), "variant": True})
    krok_extra = {
        "top_y": spec_krok.TOP_Y, "sole_y": spec_krok.SOLE_Y, "ground_x": 256.0,
        "height_src": spec_krok.SOLE_Y - spec_krok.TOP_Y,
        "world_per_src": 1.0 / (spec_krok.SOLE_Y - spec_krok.TOP_Y),
        "identity_color": "#833280",
    }
    export("krok", k_img, k_layers, k_meta, krok_extra)

    m_meta = [dict(p) for p in spec_mil.spec["parts"]]
    m_meta += [
        {"name": "leg_L", "z": 5, "parent": "torso", "pivot": CM.mil_leg_bones("L")["hip"], "constructed": True,
         "bones": CM.mil_leg_bones("L")},
        {"name": "leg_R", "z": 5.1, "parent": "torso", "pivot": CM.mil_leg_bones("R")["hip"], "constructed": True,
         "bones": CM.mil_leg_bones("R")},
        {"name": "shoe_L", "z": 4.9, "parent": "leg_L", "pivot": info["ankle_L"], "constructed": True},
        {"name": "shoe_R", "z": 5.05, "parent": "leg_R", "pivot": info["ankle_R"], "constructed": True},
        {"name": "eyes_open", "z": 31, "parent": "head", "pivot": (250, 258), "variant": True},
        {"name": "eyes_closed", "z": 31.1, "parent": "head", "pivot": (250, 258), "variant": True},
    ]
    for m in m_meta:
        if m["name"] in ("arm_L", "arm_R", "pelvis"):
            m["constructed_partly"] = True
    mil_extra = {
        "top_y": spec_mil.TOP_Y, "sole_y": CM.SOLE_Y, "ground_x": 247.5,
        "height_src": CM.SOLE_Y - spec_mil.TOP_Y,
        "world_per_src": 1.0 / (CM.SOLE_Y - spec_mil.TOP_Y),
        "scale_vs_krok": CM.MIL_SCALE,
        "identity_color": "#95B822",
    }
    export("mil", m_img, m_layers, m_meta, mil_extra)
    print(f"personnages construits en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
