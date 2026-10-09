"""Marionnette raster (animation découpée) : hiérarchie de calques + skinning par maillage, rendu Skia.

Repère « src » = pixels de l'image de référence du personnage (1×). Les calques exportés sont
à ×`upscale` ; les coordonnées de texture = (src - offset_src) × upscale.

Pose (dict, tout est optionnel, angles en degrés, sens horaire à l'écran = positif) :
  root_rot, root_dx, root_dy     rotation / translation du personnage autour du point au sol
  squash                         écrasement vertical (>1 étire, <1 écrase), volume conservé
  lean                           inclinaison du buste autour des hanches
  head, head_dx, head_dy         tête (rotation autour du cou)
  arm_L, arm_R = (épaule, coude, poignet)
  leg_L, leg_R = (hanche, genou, cheville)
  sway = {nom_de_calque: angle}  balancier secondaire (cheveux, cordons, visière…)
  eyes = None | "closed" | "open"
  hide = {noms}                  calques masqués (remplacés par une tenue, par ex.)
  z = {nom: z}                   ordre d'empilement modifié pour la pose (ex. bras devant les mèches)
"""
import json
import math
import os

import numpy as np
import skia
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def mat_T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], np.float64)


def mat_R(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)


def mat_S(sx, sy):
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], np.float64)


def rot_about(p, deg):
    return mat_T(p[0], p[1]) @ mat_R(deg) @ mat_T(-p[0], -p[1])


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / max(e1 - e0, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def placement(rig, x, y, height_px, mirror=False, rot=0.0):
    """Matrice src -> canevas : point au sol du personnage en (x, y), hauteur totale height_px."""
    s = height_px / rig["height_src"]
    gx, gy = rig["ground_x"], rig["sole_y"]
    return mat_T(x, y) @ mat_R(rot) @ mat_S(-s if mirror else s, s) @ mat_T(-gx, -gy)


def surface_rgba(w, h):
    info = skia.ImageInfo.Make(w, h, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
    return skia.Surface.MakeRaster(info)


def snapshot_rgba(surface):
    """Retourne un tableau float32 RGBA non prémultiplié."""
    arr = surface.makeImageSnapshot().toarray().astype(np.float32) / 255.0
    a = arr[..., 3:4]
    rgb = arr[..., :3] / np.maximum(a, 1e-6)
    return np.concatenate([np.clip(rgb, 0, 1), a], 2)


def skia_image_from_rgba(arr_u8):
    img = skia.Image.fromarray(np.ascontiguousarray(arr_u8), colorType=skia.ColorType.kRGBA_8888_ColorType,
                               alphaType=skia.AlphaType.kUnpremul_AlphaType)
    return img.withDefaultMipmaps()


CHAINS = {
    "arm_L": ("shoulder", "elbow", "wrist", "hand"),
    "arm_R": ("shoulder", "elbow", "wrist", "hand"),
    "leg_L": ("hip", "knee", "ankle"),
    "leg_R": ("hip", "knee", "ankle"),
}
# rayons de fondu des articulations (px src) : épaule souple (manche), coude, poignet
BLEND = {"shoulder": 12.0, "elbow": 9.0, "wrist": 4.0, "hip": 7.0, "knee": 8.0, "ankle": 4.0}


class Puppet:
    def __init__(self, name, cell=5.0):
        d = os.path.join(ROOT, "assets", "characters", name)
        self.rig = json.load(open(os.path.join(d, "rig.json")))
        self.name = name
        self.up = self.rig["upscale"]
        self.parts = {p["name"]: p for p in self.rig["parts"]}
        self.images = {}
        self.arrays = {}
        for p in self.rig["parts"]:
            arr = np.array(Image.open(os.path.join(d, p["file"])).convert("RGBA"))
            self.arrays[p["name"]] = arr
            self.images[p["name"]] = skia_image_from_rgba(arr)
        self.overrides = {}  # nom -> skia.Image de même cadrage que le calque (tenues / recolorations)
        self.cell = cell
        self.meshes = {}
        for n, p in self.parts.items():
            if p.get("overlay_of"):
                continue
            self.meshes[n] = self._mesh(p)
        for n, p in self.parts.items():
            if p.get("overlay_of"):
                base = self.parts[p["overlay_of"]]
                bm = self.meshes[base["name"]]
                # même géométrie : coordonnées de texture recalées sur l'offset de l'overlay
                tex = (bm["pts"] - np.array(p["offset_src"])) * self.up
                self.meshes[n] = dict(bm, tex=tex)

    # ------------------------------------------------------------------ maillage
    def _mesh(self, p):
        up = self.up
        ox, oy = p["offset_src"]
        w, h = p["size_px"][0] / up, p["size_px"][1] / up
        n = p["name"]
        if n in CHAINS or n in ("hair_L", "hair_R", "hair", "strings", "cap_brim"):
            nx = max(2, int(math.ceil(w / self.cell)))
            ny = max(2, int(math.ceil(h / self.cell)))
        else:
            nx, ny = 1, 1
        xs = np.linspace(ox, ox + w, nx + 1)
        ys = np.linspace(oy, oy + h, ny + 1)
        gx, gy = np.meshgrid(xs, ys)
        pts = np.stack([gx.ravel(), gy.ravel()], 1)
        tex = (pts - np.array([ox, oy])) * up
        idx = []
        for j in range(ny):
            for i in range(nx):
                a = j * (nx + 1) + i
                b, c = a + 1, a + nx + 1
                idx += [a, b, c, b, c + 1, c]
        mesh = {"pts": pts, "tex": tex, "idx": idx}
        if n in CHAINS:
            mesh["weights"] = self._chain_weights(p, pts)
        return mesh

    def _chain_weights(self, p, pts):
        bones = p.get("bones", {})
        names = [b for b in CHAINS[p["name"]] if b in bones]
        J = np.array([bones[b] for b in names], np.float64)
        # paramètre d'abscisse curviligne du projeté sur la polyligne des os
        seg_len = np.linalg.norm(J[1:] - J[:-1], axis=1)
        cum = np.concatenate([[0], np.cumsum(seg_len)])
        best_s = np.zeros(len(pts))
        best_d = np.full(len(pts), np.inf)
        best_p = np.zeros_like(pts)
        for k in range(len(J) - 1):
            a, b = J[k], J[k + 1]
            ab = b - a
            t = np.clip(((pts - a) @ ab) / max(ab @ ab, 1e-9), -np.inf if k == 0 else 0, np.inf if k == len(J) - 2 else 1)
            proj = a + t[:, None] * ab
            dd = np.linalg.norm(pts - proj, axis=1)
            s = cum[k] + t * seg_len[k]
            m = dd < best_d
            best_d[m] = dd[m]
            best_s[m] = s[m]
            best_p[m] = proj[m]
        # facteurs de fondu à chaque articulation
        f = []
        blend = dict(BLEND)
        blend.update(p.get("blend", {}))
        for k, b in enumerate(names[:-1] if len(names) > 3 else names):
            r = blend.get(b, 6.0)
            f.append(smoothstep(cum[k] - r, cum[k] + r, best_s))
        # poids LBS : w0 parent, w1 os1, w2 os2, w3 os3
        W = []
        acc = np.ones(len(pts))
        for k in range(len(f)):
            W.append(acc * (1 - f[k]))
            acc = acc * f[k]
        W.append(acc)
        return {"names": names, "W": np.stack(W, 1), "s": best_s, "proj": best_p}  # W : (N, len(f)+1)

    # ------------------------------------------------------------------ squelette
    def transforms(self, pose):
        rig = self.rig
        g = (rig["ground_x"], rig["sole_y"])
        P = self.parts
        T = {}
        sq = pose.get("squash", 1.0)
        root = mat_T(pose.get("root_dx", 0), pose.get("root_dy", 0)) @ rot_about(g, pose.get("root_rot", 0))
        root = root @ mat_T(g[0], g[1]) @ mat_S(1 / math.sqrt(sq), sq) @ mat_T(-g[0], -g[1])
        T["hips"] = root
        torso_piv = P["torso"]["pivot"]
        T["torso"] = T["hips"] @ rot_about(torso_piv, pose.get("lean", 0))
        if "pelvis" in P:
            T["pelvis"] = T["hips"]
        head_piv = P["head"]["pivot"]
        T["head"] = T["torso"] @ mat_T(pose.get("head_dx", 0), pose.get("head_dy", 0)) @ rot_about(head_piv, pose.get("head", 0))
        chains = {}
        for limb in ("arm_L", "arm_R", "leg_L", "leg_R"):
            if limb not in P:
                continue
            parent = T["torso"] if limb.startswith("arm") else T["hips"]
            angles = list(pose.get(limb, (0, 0, 0))) + [0, 0, 0]
            bones = P[limb].get("bones", {})
            names = [b for b in CHAINS[limb] if b in bones]
            mats = [parent]
            cur = parent
            for k, b in enumerate(names[:3]):
                cur = cur @ rot_about(bones[b], angles[k])
                mats.append(cur)
            chains[limb] = mats
            T[limb] = parent
        for side in ("L", "R"):
            leg = "leg_" + side
            if leg in chains:
                T["shoe_" + side] = chains[leg][min(3, len(chains[leg]) - 1)]
        for n, p in P.items():
            if n in T:
                continue
            par = p.get("parent") or "torso"
            base = T.get(par, T["torso"])
            T[n] = base
        return T, chains

    # ------------------------------------------------------------------ rendu
    def positions(self, name, pose, T, chains):
        base = self.parts[name].get("overlay_of")
        if base:
            return self.positions(base, pose, T, chains)
        mesh = self.meshes[name]
        pts = mesh["pts"]
        ph = np.concatenate([pts, np.ones((len(pts), 1))], 1)
        if name in chains and "weights" in mesh:
            mats = chains[name]
            W = mesh["weights"]["W"]
            k = W.shape[1]
            wid = self.parts[name].get("widen")
            if wid:
                # manche vue de profil : elle s'élargit quand le bras se lève (comme s'il pivotait vers la caméra)
                ang = abs(list(pose.get(name, (0,)))[0])
                kk = 1.0 + (wid["k"] - 1.0) * float(smoothstep(wid["a0"], wid["a1"], ang))
                if kk != 1.0:
                    sv = mesh["weights"]["s"]
                    pr = mesh["weights"]["proj"]
                    g = smoothstep(0.0, wid.get("ramp", 14.0), sv)[:, None]
                    fac = 1.0 + (kk - 1.0) * g
                    pts = pr + (pts - pr) * fac
                    ph = np.concatenate([pts, np.ones((len(pts), 1))], 1)
            out = np.zeros((len(pts), 2))
            for i in range(k):
                M = mats[min(i, len(mats) - 1)]
                out += W[:, i:i + 1] * (ph @ M.T)[:, :2]
            return out
        M = T[name]
        sway = pose.get("sway", {}).get(name, 0.0)
        if sway:
            piv = self.parts[name]["pivot"]
            hgt = max(pts[:, 1].max() - piv[1], 1.0)
            w = np.clip((pts[:, 1] - piv[1]) / hgt, 0, 1) ** 1.4
            A = (ph @ M.T)[:, :2]
            B = (ph @ (M @ rot_about(piv, sway)).T)[:, :2]
            return A * (1 - w[:, None]) + B * w[:, None]
        return (ph @ M.T)[:, :2]

    def visible_parts(self, pose):
        hide = set(pose.get("hide", ()))
        eyes = pose.get("eyes")
        zo = pose.get("z", {})
        out = []
        def zkey(q):
            base = q.get("overlay_of")
            if base:
                return zo.get(base, self.parts[base]["z"]) + 0.001
            return zo.get(q["name"], q["z"])
        for p in sorted(self.rig["parts"], key=zkey):
            n = p["name"]
            if n in hide or (p.get("overlay_of") in hide):
                continue
            if p.get("variant"):
                if not eyes or n != "eyes_" + eyes:
                    continue
            out.append(n)
        return out

    def draw(self, canvas, pose, M_place, extra_draw=None, alpha=1.0):
        """Dessine le personnage. extra_draw(canvas, z, ctx) est appelé après chaque calque (tenues)."""
        T, chains = self.transforms(pose)
        ctx = {"T": T, "chains": chains, "M": M_place, "puppet": self, "pose": pose}
        for n in self.visible_parts(pose):
            if extra_draw:
                extra_draw(canvas, self.parts[n]["z"] - 0.001, ctx)
            pos = self.positions(n, pose, T, chains)
            pos = (np.concatenate([pos, np.ones((len(pos), 1))], 1) @ M_place.T)[:, :2]
            mesh = self.meshes[n]
            img = self.overrides.get(n, self.images[n])
            a_part = alpha
            base = self.parts[n].get("overlay_of")
            if base:
                ang = abs(list(pose.get(base, (0,)))[0]) if base in CHAINS else 0.0
                a_part = alpha * float(smoothstep(4.0, 20.0, ang))
                if a_part <= 0.002:
                    continue
            verts = skia.Vertices(skia.Vertices.kTriangles_VertexMode,
                                  [skia.Point(float(x), float(y)) for x, y in pos],
                                  [skia.Point(float(u), float(v)) for u, v in mesh["tex"]], None, mesh["idx"])
            paint = skia.Paint(Shader=img.makeShader(skia.TileMode.kDecal, skia.TileMode.kDecal, SAMPLING), AntiAlias=True)
            if a_part < 1.0:
                paint.setAlphaf(a_part)
            canvas.drawVertices(verts, paint)
        if extra_draw:
            extra_draw(canvas, 1e9, ctx)
        return ctx

    def point(self, name_or_xy, pose, M_place, bone=None, limb=None):
        """Position canevas d'un point src attaché à une partie (ou à l'os d'un membre)."""
        T, chains = self.transforms(pose)
        if limb is not None:
            mats = chains[limb]
            names = [b for b in CHAINS[limb] if b in self.parts[limb]["bones"]]
            k = names.index(bone)
            M = mats[min(k + 1, len(mats) - 1)]
            p = self.parts[limb]["bones"][bone]
        else:
            M = T[name_or_xy[0]]
            p = name_or_xy[1]
        v = M_place @ M @ np.array([p[0], p[1], 1.0])
        return v[:2]
