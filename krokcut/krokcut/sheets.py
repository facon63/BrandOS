"""Planches d'images pour Claude (onglet « Comparer ») : choix des cases, extraits, planches, planche de contrôle.

Claude regarde la vidéo sur des planches : des cases (images réduites) rangées de gauche à droite puis de
haut en bas, chacune avec un bandeau « T0412 7:42.5 P118 » (id de case, temps, plan). Claude cite les ids
de case : le temps vient toujours de la case, jamais d'un texte écrit par Claude. Même couleur de bandeau
= même plan ; un liseré blanc marque la première case d'un plan ; des étiquettes jaunes rappellent ce qui
a été mesuré (Z+ zoom avant, Z- retour, FL flash ou image brève, FIG figé, NOIR, NB noir et blanc, S son).

Les cases sont tirées d'une grille régulière, complétée pour que chaque plan et chaque effet mesuré ait sa
case. Tout est fait avec numpy et ffmpeg (police bitmap 5×7 intégrée, ni Pillow ni drawtext).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .ffmpeg_utils import FFmpegError, FFmpegUnavailable, decode_jpegs, encode_rgb_jpeg, extract_padded

SHEETS_VERSION = 1  # change quand les planches changent : l'analyse Claude est à refaire


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    grid_s: float  # une case toutes les `grid_s` secondes
    tile_w: int
    tile_h: int
    cols: int
    rows: int
    band_h: int  # bandeau au-dessus de l'image
    font_scale: int
    chunk_s: float  # durée visée d'un extrait (un appel à Claude)
    max_per_min: int  # plafond de cases par minute
    observe_effort: str

    @property
    def per_sheet(self) -> int:
        return self.cols * self.rows

    @property
    def sheet_w(self) -> int:
        return self.cols * self.tile_w + (self.cols - 1) * GUTTER

    @property
    def sheet_h(self) -> int:
        return self.rows * (self.band_h + self.tile_h) + (self.rows - 1) * GUTTER


GUTTER = 4
PRESETS = {
    "eco": Preset("eco", "Économique", 2.0, 384, 216, 6, 6, 18, 2, 240.0, 45, "low"),
    "standard": Preset("standard", "Standard", 1.0, 448, 252, 5, 5, 24, 3, 180.0, 90, "medium"),
    "detaille": Preset("detaille", "Détaillée", 0.5, 560, 315, 4, 4, 24, 3, 120.0, 160, "medium"),
}
MAX_SHEETS_PER_CALL = 14
MAX_SHEET_SIDE = 2576  # au-delà, l'API réduit l'image (et les étiquettes deviennent illisibles)
MAX_EXTRACTED = 150  # extractions à la demande par vidéo (plans très courts, transitoires)
TOKENS_PER_PIXEL = 750  # tokens d'une image ≈ ⌈largeur × hauteur / 750⌉

# ------------------------------------------------------------- choix des cases (§3.7)
CANDIDATE_FPS = 4  # images candidates (images4/f_%06d.jpg, k / 4 s)
MEASURE_FPS = 30  # cadence des mesures de l'image (vision.FPS) : les transitoires y sont datés
EXTRACT_LEAD = 0.005  # extraction à la demande : 5 ms avant l'image voulue
CANDIDATE_DIR = "images4"
SNAP_MAX = 0.125  # calage sur une image candidate à ±0,125 s, dans le même plan
PLAN_MARGIN = 0.05  # un plan « a sa case » si une case tombe dans [début + 0,05 ; fin − 0,05]
EVENT_GAP = 0.35  # un effet a sa case si une case du même plan est à moins de 0,35 s
TAG_WINDOW = 0.35  # étiquettes Z+, Z-, FL, S : effet à ±0,35 s
EVENT_OFFSETS = {"zoom": 0.10, "fige": 0.20, "bandes": 0.30, "nb": 0.30, "son": 0.15, "musique": 0.20, "silence": 0.10}
FADE_TYPES = ("fondu_noir", "fondu_depuis_noir", "noir")
TRANSIENT_TYPES = ("flash_blanc", "noir_bref", "image_inseree")
PROTECTED_REASONS = ("plan", "zoom", "flash", "fige", "fondu", "nb", "bandes")  # jamais retirées par le plafond
SOUND_REASONS = ("son", "musique", "silence")
TAG_ORDER = ("Z+", "Z-", "FL", "FIG", "NOIR", "NB", "S")

# ------------------------------------------------------------------- extraits (§3.7)
CHUNK_SNAP_S = 15.0  # borne calée sur une coupe à ±15 s...
SPEECH_GAP_S = 0.3  # ... de préférence dans un trou de parole d'au moins 0,3 s
LAST_CHUNK_MIN = 0.4  # un dernier extrait de moins de 0,4 × chunk_s rejoint le précédent

# -------------------------------------------------------------------- dessin (§3.8)
BAND_COLORS = ("#7a1f1f", "#1f4f7a", "#2f6b2f", "#6b4f1f", "#5a2f6b", "#1f6b66")  # alternent avec le plan
TEXT_COLOR = "#ffffff"
TAG_COLOR = "#ffd400"
EMPTY_COLOR = "#202020"
GUTTER_COLOR = "#000000"
NEW_PLAN_EDGE = 4  # liseré blanc à gauche de l'image, première case d'un plan
TEXT_PAD = 4  # marge du texte dans le bandeau
TAG_SPACE = 1  # espaces entre le texte et les étiquettes (au moins)
JPEG_Q = 3
JPEG_Q_SMALL = 6
MAX_REQUEST_B64 = 24 * 1024 * 1024  # base64 des planches d'un extrait : au-delà, réencodées en -q:v 6
SHEET_DIR = "planches"
EXTRACT_DIR = "extraits"

# ------------------------------------------------------- planche de contrôle (§3.8)
CONTROL_FILE = "controle.jpg"
CONTROL_W, CONTROL_H = 320, 180
CONTROL_COLS, CONTROL_ROWS = 4, 6
CONTROL_BAND = 18
CONTROL_SCALE = 2
CONTROL_DRAW = (("cut", 8), ("zoom", 8), ("transient", 4), ("still", 4))  # 8 coupes, 8 zooms, 4 F, 4 G ou N

# --------------------------------------------------------- police bitmap 5×7 (§3.8)
GLYPH_W, GLYPH_H, GLYPH_STEP = 5, 7, 6
GLYPHS = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "N": ("10001", "10001", "11001", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    " ": ("00000",) * 7,
}

Progress = Callable[[float, str], None]


# =========================================================================== outils
def sheet_tokens(w: int, h: int) -> int:
    """Tokens d'image comptés par l'API pour une planche de w × h pixels."""
    return math.ceil(w * h / TOKENS_PER_PIXEL)


def rgb(color: str | tuple) -> tuple[int, int, int]:
    if isinstance(color, str):
        c = color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return tuple(int(v) for v in color)  # type: ignore[return-value]


def fmt_tile_time(t: float) -> str:
    """7:42.5 (minutes:secondes.dixièmes)."""
    tenths = int(math.floor(max(0.0, t) * 10 + 0.5))
    m, rest = divmod(tenths, 600)
    return f"{m}:{rest // 10:02d}.{rest % 10}"


def _glyph_mask(ch: str) -> np.ndarray:
    rows = GLYPHS.get(ch, GLYPHS[" "])  # caractère hors police : un blanc
    return np.array([[c == "1" for c in row] for row in rows], bool)


def text_width(text: str, scale: int) -> int:
    """Largeur en pixels : 6 px par caractère à l'échelle 1 (5 px de glyphe et 1 px d'espace)."""
    return len(text) * GLYPH_STEP * scale


def text_mask(text: str, scale: int) -> np.ndarray:
    mask = np.zeros((GLYPH_H, len(text) * GLYPH_STEP), bool)
    for i, ch in enumerate(text):
        mask[:, i * GLYPH_STEP : i * GLYPH_STEP + GLYPH_W] = _glyph_mask(ch)
    return np.repeat(np.repeat(mask, scale, axis=0), scale, axis=1)


def render_text(text: str, scale: int, fg, bg) -> np.ndarray:
    """Texte en police bitmap 5×7 : tableau uint8 (7·scale, text_width, 3)."""
    mask = text_mask(text, scale)
    out = np.empty((*mask.shape, 3), np.uint8)
    out[:] = rgb(bg)
    out[mask] = rgb(fg)
    return out


def _items(data, key: str) -> list[dict]:
    """Contenu d'un fichier JSON du contrat ({…, key: [...]}) ou directement la liste."""
    if isinstance(data, dict):
        return list(data.get(key) or [])
    return list(data or [])


def plan_index(plan_id: str) -> int:
    try:
        return int(plan_id[1:]) - 1
    except (ValueError, IndexError):
        return 0


# ================================================================ choix des cases
def _plan_finder(plans: list[dict]):
    starts = np.array([p["start"] for p in plans], np.float64)

    def find(t: float) -> int:
        if not plans:
            return -1
        return int(np.clip(np.searchsorted(starts, t, side="right") - 1, 0, len(plans) - 1))

    return find


def _event_instants(image_events: list[dict], sound_events: list[dict], music: list[dict],
                    silences: list[dict]) -> list[dict]:
    """Instants des cases d'effets (table du §3.7) : {t, lo, hi, reason, plan, salience, transient}.

    [lo, hi] : où une case déjà choisie suffit (elle montre l'effet et porte son étiquette) : après le
    zoom, le son ou le silence (à 0,35 s au plus), ou à l'intérieur du figé, du fondu, du N&B, des bandes.
    """
    out = []

    def point(t: float, offset: float, reason: str, **kw) -> None:
        out.append({"t": t + offset, "lo": t, "hi": t + EVENT_GAP, "reason": reason, **kw})

    def span(t: float, dur: float, at: float, reason: str, **kw) -> None:
        out.append({"t": at, "lo": t, "hi": t + dur, "reason": reason, **kw})

    for e in image_events:
        kind = e.get("type", "")
        t, dur = float(e["t"]), float(e.get("dur", 0.0))
        kw = {"plan": e.get("plan")}
        if kind == "zoom":
            point(t, EVENT_OFFSETS["zoom"], "zoom", **kw)
        elif kind in TRANSIENT_TYPES:  # l'image du milieu du transitoire (instant de son début, pas entre deux images)
            frames = max(1, int(round(dur * MEASURE_FPS)))
            span(t, dur, t + (frames // 2) / MEASURE_FPS, "flash", transient=True, **kw)
        elif kind == "fige":
            span(t, dur, t + EVENT_OFFSETS["fige"], "fige", **kw)
        elif kind in FADE_TYPES:
            span(t, dur, t + dur / 2, "fondu", **kw)
        elif kind == "noir_et_blanc":
            span(t, dur, t + EVENT_OFFSETS["nb"], "nb", **kw)
        elif kind == "bandes_cinema":
            span(t, dur, t + EVENT_OFFSETS["bandes"], "bandes", **kw)
    for snd in sound_events:
        if snd.get("cat") != "autre":  # seuls les sons éditoriaux ont leur case
            point(float(snd["t"]), EVENT_OFFSETS["son"], "son", salience=float(snd.get("salience", 0.0)))
    for m in music:
        for t in (m["start"], m["end"]):
            point(float(t), EVENT_OFFSETS["musique"], "musique", salience=0.0)
    for c in silences:
        point(float(c["t"]), EVENT_OFFSETS["silence"], "silence", salience=0.0)
    return out


def _snap(t: float, plan: dict | None, candidates: int, end: float, window: tuple[float, float] | None = None) -> float | None:
    """Image candidate (k / 4 s) la plus proche de t, dans le même plan (et dans `window`), à ±0,125 s ; sinon None."""
    if candidates <= 0:
        return None
    k = int(round(t * CANDIDATE_FPS))
    best = None
    for kk in (k - 1, k, k + 1):
        tk = kk / CANDIDATE_FPS
        if not 0 <= kk < candidates or abs(tk - t) > SNAP_MAX + 1e-9:
            continue
        if plan is not None and not (plan["start"] <= tk < plan["end"]):
            continue
        if tk > end or (window is not None and not window[0] - 1e-9 <= tk <= window[1] + 1e-9):
            continue
        if best is None or abs(tk - t) < abs(best - t):
            best = tk
    return best


def select_tiles(duration: float, plans, image_events, sound_events, music, silences, preset: Preset | str, *,
                 candidates: int | None = None, max_extracted: int = MAX_EXTRACTED) -> list[dict]:
    """Cases de la vidéo (§3.7), dans l'ordre du temps : grille, couverture des plans, effets, calage, plafond.

    `plans` … `silences` : contenus de plans.json, image_evenements.json, son_evenements.json, musique.json,
    silences.json (ou directement leurs listes). `candidates` : nombre d'images candidates à 4 i/s.
    Chaque case : {id, t, plan, new_plan, reasons, tags, source} (« images4 » ou « extrait »).
    """
    preset = PRESETS[preset] if isinstance(preset, str) else preset
    plan_list = _items(plans, "plans") or [{"id": "P001", "start": 0.0, "end": duration, "cut_in": "debut"}]
    events = _items(image_events, "events")
    sounds = _items(sound_events, "events")
    segs = _items(music, "segments")
    sil = _items(silences, "silences")
    if candidates is None:
        candidates = int(math.floor(duration * CANDIDATE_FPS)) + 1
    find = _plan_finder(plan_list)
    raw: list[dict] = []

    def add(t: float, reason: str, p: int | None = None, *, transient: bool = False, salience: float | None = None,
            window: tuple[float, float] | None = None) -> dict:
        """Nouvelle case, calée tout de suite sur l'image candidate la plus proche du même plan (±0,125 s, dans
        `window` pour un effet) ; sinon (plan très court, transitoire) : extraction à l'instant exact."""
        t = float(min(max(t, 0.0), max(0.0, duration - 1e-3)))
        p = find(t) if p is None else p
        plan = plan_list[p] if p >= 0 else None
        snapped = None if transient else _snap(t, plan, candidates, duration, window)
        tile = {"t": t if snapped is None else snapped, "want": t, "p": p, "reasons": [reason], "salience": salience,
                "source": "extrait" if snapped is None else "images4", "transient": transient}
        raw.append(tile)
        by_plan.setdefault(p, []).append(tile)
        return tile

    by_plan: dict[int, list[dict]] = {}
    # 1. grille
    k = 0
    while (k + 0.5) * preset.grid_s < duration:
        add((k + 0.5) * preset.grid_s, "grille")
        k += 1
    # 2. couverture des plans : chaque plan a une case à l'intérieur
    for i, p in enumerate(plan_list):
        inside = [x for x in by_plan.get(i, []) if p["start"] + PLAN_MARGIN <= x["t"] <= p["end"] - PLAN_MARGIN]
        if inside:  # la case la plus proche du milieu tient lieu de case de plan (jamais retirée)
            mid = (p["start"] + p["end"]) / 2
            min(inside, key=lambda x: abs(x["t"] - mid))["reasons"].append("plan")
        else:
            add((p["start"] + p["end"]) / 2, "plan", i)
    # 3. effets : une case à moins de 0,35 s dans le même plan, sinon une case à l'instant du tableau
    for ev in sorted(_event_instants(events, sounds, segs, sil), key=lambda e: e["t"]):
        t = float(min(max(ev["t"], 0.0), max(0.0, duration - 1e-3)))
        p = find(t)
        if ev.get("plan"):
            p = next((i for i, x in enumerate(plan_list) if x["id"] == ev["plan"]), p)
        transient = bool(ev.get("transient"))
        near = [x for x in by_plan.get(p, []) if abs(x["t"] - t) < EVENT_GAP and ev["lo"] - 1e-9 <= x["t"] <= ev["hi"] + 1e-9
                and (x["transient"] or not transient)]
        if near:
            tile = min(near, key=lambda x: abs(x["t"] - t))
            tile["reasons"].append(ev["reason"])
            if ev.get("salience") is not None:
                tile["salience"] = max(tile["salience"] or 0.0, ev["salience"])
        else:
            add(t, ev["reason"], p, transient=transient, salience=ev.get("salience"), window=(ev["lo"], ev["hi"]))
    # 4. au plus 150 extractions (transitoires et plans très courts d'abord) ; au-delà, la candidate la plus
    # proche, ou rien pour une simple case de grille
    extracted = 0
    for tile in sorted((x for x in raw if x["source"] == "extrait"), key=lambda x: (not x["transient"], x["t"])):
        if extracted < max_extracted:
            extracted += 1
            continue
        if tile["reasons"] == ["grille"] or candidates <= 0:
            tile["drop"] = True
        else:
            k = int(np.clip(round(tile["want"] * CANDIDATE_FPS), 0, candidates - 1))
            tile["t"], tile["source"] = k / CANDIDATE_FPS, "images4"
            tile["p"] = find(tile["t"])
    tiles = [x for x in raw if not x.get("drop")]
    # deux cases sur la même image du même plan : une seule
    merged: dict[tuple, dict] = {}
    for tile in sorted(tiles, key=lambda x: x["t"]):
        key = (tile["p"], round(tile["t"], 3), tile["source"])
        if key in merged:
            keep = merged[key]
            keep["reasons"] += [r for r in tile["reasons"] if r not in keep["reasons"]]
            if tile["salience"] is not None:
                keep["salience"] = max(keep["salience"] or 0.0, tile["salience"])
        else:
            merged[key] = tile
    tiles = sorted(merged.values(), key=lambda x: (x["t"], x["source"]))
    # 5. plafond par minute : cases de grille d'abord (uniformément), puis sons les moins saillants
    tiles = _apply_cap(tiles, duration, preset.max_per_min)
    # 6. ids, nouveau plan, étiquettes
    out = []
    seen_plans: set[int] = set()
    tags_of = _tagger(events, sounds, plan_list, find)
    for i, tile in enumerate(tiles):
        plan = plan_list[tile["p"]] if tile["p"] >= 0 else {"id": "P001"}
        reasons = list(dict.fromkeys(tile["reasons"]))
        out.append({"id": f"T{i + 1:04d}", "t": round(tile["t"], 3), "plan": plan["id"],
                    "new_plan": tile["p"] not in seen_plans, "reasons": reasons, "tags": tags_of(tile["t"], tile["p"]),
                    "source": tile["source"]})
        seen_plans.add(tile["p"])
    return out


def _removable(tile: dict) -> str:
    """« grille » : simple case de grille ; « son » : case de son, musique ou silence ; « » : protégée."""
    reasons = set(tile["reasons"])
    if reasons & set(PROTECTED_REASONS):
        return ""
    if reasons <= {"grille"}:
        return "grille"
    return "son"


def _apply_cap(tiles: list[dict], duration: float, per_min: int) -> list[dict]:
    keep = list(tiles)
    n_min = max(1, int(math.ceil(duration / 60)))
    for m in range(n_min):
        a, b = m * 60.0, min(duration, (m + 1) * 60.0)
        cap = int(math.ceil(per_min * (b - a) / 60)) if b - a < 60 else per_min
        inside = [t for t in keep if a <= t["t"] < b]
        excess = len(inside) - cap
        if excess <= 0:
            continue
        drop: set[int] = set()
        grid = [t for t in inside if _removable(t) == "grille"]
        if grid:  # éclaircir uniformément : n indices régulièrement espacés parmi les cases de grille
            n = min(excess, len(grid))
            picks = np.floor((np.arange(n) + 0.5) * len(grid) / n).astype(int)
            drop |= {id(grid[i]) for i in picks}
            excess -= n
        if excess > 0:
            sounds = sorted((t for t in inside if _removable(t) == "son"), key=lambda t: t["salience"] or 0.0)
            drop |= {id(t) for t in sounds[:excess]}
        keep = [t for t in keep if id(t) not in drop]
    return keep


def _tagger(events: list[dict], sounds: list[dict], plans: list[dict], find):
    zooms_in = [float(e["t"]) for e in events if e.get("type") == "zoom" and e.get("dir") == "avant"]
    zooms_out = [float(e["t"]) for e in events if e.get("type") == "zoom" and e.get("dir") == "arriere"]
    zooms_out += [float(e["end"]) for e in events if e.get("type") == "zoom" and e.get("dir") == "avant" and e.get("returned")]
    transients = [(float(e["t"]), float(e["t"]) + float(e.get("dur", 0.0))) for e in events if e.get("type") in TRANSIENT_TYPES]
    spans = {
        "FIG": [(float(e["t"]), float(e["t"]) + float(e.get("dur", 0.0))) for e in events if e.get("type") == "fige"],
        "NOIR": [(float(e["t"]), float(e["t"]) + float(e.get("dur", 0.0))) for e in events if e.get("type") in FADE_TYPES],
        "NB": [(float(e["t"]), float(e["t"]) + float(e.get("dur", 0.0))) for e in events if e.get("type") == "noir_et_blanc"],
    }
    editorial = [(float(s["t"]), find(float(s["t"]) + EVENT_OFFSETS["son"])) for s in sounds if s.get("cat") != "autre"]

    def tags(t: float, p: int) -> list[str]:
        out = []
        if any(abs(t - z) <= TAG_WINDOW for z in zooms_in):
            out.append("Z+")
        if any(abs(t - z) <= TAG_WINDOW for z in zooms_out):
            out.append("Z-")
        if any(a - TAG_WINDOW <= t <= b + TAG_WINDOW for a, b in transients):
            out.append("FL")
        for tag in ("FIG", "NOIR", "NB"):
            if any(a <= t <= b for a, b in spans[tag]):
                out.append(tag)
        if any(abs(t - s) <= TAG_WINDOW and sp == p for s, sp in editorial):
            out.append("S")
        return out

    return tags


# ===================================================================== extraits
def _speech_gap(c: float, words: list[tuple[float, float]]) -> float:
    """Longueur du trou de parole qui contient l'instant c (0 si c tombe dans un mot)."""
    before = max((e for s, e in words if e <= c), default=-math.inf)
    after = min((s for s, e in words if s >= c), default=math.inf)
    if any(s < c < e for s, e in words):
        return 0.0
    return after - before


def make_chunks(duration: float, cuts, words, preset: Preset | str, *, tiles: list[dict] | None = None) -> list[dict]:
    """Extraits (un appel à Claude chacun) : bornes toutes les chunk_s secondes, calées sur la coupe la plus
    proche à ±15 s située dans un trou de parole d'au moins 0,3 s (sinon la coupe la plus proche, sinon la
    cible). Le petit dernier rejoint le précédent. Avec `tiles`, un extrait qui dépasserait 14 planches est
    coupé en deux à sa coupe médiane. Renvoie [{n, t0, t1}]."""
    preset = PRESETS[preset] if isinstance(preset, str) else preset
    cut_times = sorted(float(c["t"]) if isinstance(c, dict) else float(c) for c in _items(cuts, "cuts"))
    words = sorted((float(s), float(e)) for s, e in words)
    bounds = [0.0]
    target = preset.chunk_s
    while target < duration - 1e-6:
        lo = bounds[-1] + 1.0
        near = [c for c in cut_times if abs(c - target) <= CHUNK_SNAP_S and lo < c < duration]
        quiet = [c for c in near if _speech_gap(c, words) >= SPEECH_GAP_S]
        pick = min(quiet or near, key=lambda c: abs(c - target)) if near else target
        bounds.append(pick)
        target = pick + preset.chunk_s
    if len(bounds) > 1 and duration - bounds[-1] < LAST_CHUNK_MIN * preset.chunk_s:
        bounds.pop()  # petit dernier extrait : avec le précédent
    bounds.append(duration)
    spans = list(zip(bounds[:-1], bounds[1:]))
    if tiles is not None:  # au plus 14 planches par extrait
        out: list[tuple[float, float]] = []
        stack = spans[::-1]
        while stack:
            a, b = stack.pop()
            n = sum(1 for t in tiles if a <= t["t"] < b)
            if math.ceil(n / preset.per_sheet) <= MAX_SHEETS_PER_CALL or b - a < 2.0:
                out.append((a, b))
                continue
            inner = [c for c in cut_times if a + 0.5 < c < b - 0.5]
            mid = inner[len(inner) // 2] if inner else (a + b) / 2
            stack += [(mid, b), (a, mid)]
        spans = out
    return [{"n": i, "t0": round(a, 3), "t1": round(b, 3)} for i, (a, b) in enumerate(spans)]


def layout(tiles: list[dict], chunks: list[dict], preset: Preset) -> tuple[list[dict], list[dict]]:
    """Range les cases en planches (jamais à cheval sur deux extraits) : complète chunk, sheet, cell.
    Renvoie (planches sans fichier, extraits avec la liste de leurs planches)."""
    sheets: list[dict] = []
    out_chunks = []
    for ch in chunks:
        last = ch is chunks[-1]
        inside = [t for t in tiles if ch["t0"] <= t["t"] < ch["t1"] or (last and t["t"] >= ch["t1"])]
        numbers = []
        for i in range(0, len(inside), preset.per_sheet):
            group = inside[i : i + preset.per_sheet]
            n = len(sheets)
            for cell, tile in enumerate(group):
                tile.update(chunk=ch["n"], sheet=n, cell=cell)
            w, h = preset.sheet_w, preset.sheet_h
            sheets.append({"n": n, "file": f"{SHEET_DIR}/planche_{n:03d}.jpg", "w": w, "h": h, "tokens": sheet_tokens(w, h),
                           "chunk": ch["n"], "t0": group[0]["t"], "t1": group[-1]["t"],
                           "first": group[0]["id"], "last": group[-1]["id"]})
            numbers.append(n)
        out_chunks.append({**ch, "sheets": numbers})
    return sheets, out_chunks


# ========================================================================= dessin
def _band(tile: dict, preset: Preset) -> np.ndarray:
    """Bandeau d'une case : « T0412 7:42.5 P118 » en blanc, étiquettes jaunes alignées à droite."""
    bg = rgb(BAND_COLORS[plan_index(tile["plan"]) % len(BAND_COLORS)])
    band = np.empty((preset.band_h, preset.tile_w, 3), np.uint8)
    band[:] = bg
    s = preset.font_scale
    y = (preset.band_h - GLYPH_H * s) // 2
    label = tile_label(tile)
    text = render_text(label, s, TEXT_COLOR, bg)
    x_end = min(preset.tile_w, TEXT_PAD + text.shape[1])
    band[y : y + text.shape[0], TEXT_PAD:x_end] = text[:, : x_end - TEXT_PAD]
    tags = list(tile.get("tags") or [])
    while tags:  # étiquettes qui ne tiennent pas : on retire les dernières
        tag_text = " ".join(tags)
        ink = text_width(tag_text, s) - s  # sans l'espace qui suit le dernier caractère
        x = preset.tile_w - TEXT_PAD - ink
        if x >= x_end + TAG_SPACE * GLYPH_STEP * s:
            band[y : y + GLYPH_H * s, x : x + ink] = render_text(tag_text, s, TAG_COLOR, bg)[:, :ink]
            break
        tags.pop()
    return band


def tile_label(tile: dict) -> str:
    return f"{tile['id']} {fmt_tile_time(tile['t'])} {tile['plan']}"


def compose_sheet(tiles: list[dict], images: np.ndarray, preset: Preset) -> np.ndarray:
    """Planche (h, w, 3) : cases de gauche à droite puis de haut en bas ; cellules vides en #202020."""
    sheet = np.empty((preset.sheet_h, preset.sheet_w, 3), np.uint8)
    sheet[:] = rgb(GUTTER_COLOR)
    empty = rgb(EMPTY_COLOR)
    for cell in range(preset.per_sheet):
        r, c = divmod(cell, preset.cols)
        x = c * (preset.tile_w + GUTTER)
        y = r * (preset.band_h + preset.tile_h + GUTTER)
        if cell >= len(tiles):
            sheet[y : y + preset.band_h + preset.tile_h, x : x + preset.tile_w] = empty
            continue
        tile = tiles[cell]
        sheet[y : y + preset.band_h, x : x + preset.tile_w] = _band(tile, preset)
        iy = y + preset.band_h
        sheet[iy : iy + preset.tile_h, x : x + preset.tile_w] = images[cell]
        if tile.get("new_plan"):
            sheet[iy : iy + preset.tile_h, x : x + NEW_PLAN_EDGE] = 255
    return sheet


def candidate_path(work: Path, t: float) -> Path:
    return Path(work) / CANDIDATE_DIR / f"f_{int(round(t * CANDIDATE_FPS)):06d}.jpg"


def _tile_images(tiles: list[dict], work: Path, preset: Preset) -> np.ndarray:
    paths = [Path(work) / tile["_file"] for tile in tiles]
    return decode_jpegs(paths, preset.tile_w, preset.tile_h)


# ============================================================ planche de contrôle
def _seed(video_id: str) -> int:
    return int.from_bytes(hashlib.sha256(video_id.encode("utf-8")).digest()[:8], "little")


def control_items(plans, image_events, video_id: str) -> list[dict]:
    """Tirage déterministe (graine = id de la vidéo) : 8 coupes, 8 zooms, 4 transitoires, 4 figés ou noirs."""
    rng = np.random.default_rng(_seed(video_id))
    plan_list = _items(plans, "plans")
    events = _items(image_events, "events")
    pools = {
        "cut": [{"t": p["start"], "label": p["id"]} for p in plan_list[1:]],
        "zoom": [{"t": e["t"], "label": e["id"]} for e in events if e.get("type") == "zoom"],
        "transient": [{"t": e["t"], "label": e["id"]} for e in events if e.get("type") in TRANSIENT_TYPES],
        "still": [{"t": e["t"], "label": e["id"]} for e in events if e.get("type") == "fige" or e.get("type") in FADE_TYPES],
    }
    out = []
    for kind, count in CONTROL_DRAW:
        pool = pools[kind]
        picks = rng.choice(len(pool), size=min(count, len(pool)), replace=False) if pool else []
        out += [{**pool[int(i)], "kind": kind} for i in sorted(picks)]
    return sorted(out, key=lambda x: x["t"])


def build_control(work: Path, plans, image_events, video_id: str, candidates: int) -> Path | None:
    """controle.jpg : 24 paires avant / après (320×180) des détections, pour vérifier à l'œil. Jamais envoyée à Claude."""
    work = Path(work)
    if candidates <= 0:
        return None
    items = control_items(plans, image_events, video_id)[: CONTROL_COLS * CONTROL_ROWS]
    pair_w = 2 * CONTROL_W
    w = CONTROL_COLS * pair_w + (CONTROL_COLS - 1) * GUTTER
    h = CONTROL_ROWS * (CONTROL_BAND + CONTROL_H)
    sheet = np.empty((h, w, 3), np.uint8)
    sheet[:] = rgb(EMPTY_COLOR)
    paths = []
    for it in items:
        t = float(it["t"])
        before = int(np.clip(math.ceil(t * CANDIDATE_FPS) - 1, 0, candidates - 1))  # dernière image avant
        after = int(np.clip(math.ceil(t * CANDIDATE_FPS + 1e-6), 0, candidates - 1))  # première image après
        paths += [work / CANDIDATE_DIR / f"f_{before:06d}.jpg", work / CANDIDATE_DIR / f"f_{after:06d}.jpg"]
    images = decode_jpegs(paths, CONTROL_W, CONTROL_H) if paths else np.zeros((0, CONTROL_H, CONTROL_W, 3), np.uint8)
    for i, it in enumerate(items):
        r, c = divmod(i, CONTROL_COLS)
        x = c * (pair_w + GUTTER)
        y = r * (CONTROL_BAND + CONTROL_H)
        bg = rgb(BAND_COLORS[i % len(BAND_COLORS)])
        sheet[y : y + CONTROL_BAND, x : x + pair_w] = bg
        text = render_text(f"{it['label']} {fmt_tile_time(float(it['t']))}", CONTROL_SCALE, TEXT_COLOR, bg)
        ty = (CONTROL_BAND - text.shape[0]) // 2
        tw = min(text.shape[1], pair_w - TEXT_PAD)
        sheet[y + ty : y + ty + text.shape[0], x + TEXT_PAD : x + TEXT_PAD + tw] = text[:, :tw]
        sheet[y + CONTROL_BAND : y + CONTROL_BAND + CONTROL_H, x : x + CONTROL_W] = images[2 * i]
        sheet[y + CONTROL_BAND : y + CONTROL_BAND + CONTROL_H, x + CONTROL_W : x + pair_w] = images[2 * i + 1]
        sheet[y + CONTROL_BAND : y + CONTROL_BAND + CONTROL_H, x + CONTROL_W : x + CONTROL_W + 2] = rgb(TAG_COLOR)  # avant | après
    dst = work / CONTROL_FILE
    encode_rgb_jpeg(sheet, dst, q=JPEG_Q)
    return dst


# =================================================================== tout ensemble
def build_sheets(src: Path, work: Path, *, quality: str, duration: float, plans, image_events, sound_events, music,
                 silences, words: list[tuple[float, float]], progress: Progress = lambda f, m: None,
                 video_id: str | None = None) -> dict:
    """Cases, extraits et planches d'une vidéo (§3.7–3.8) : écrit planches/planche_###.jpg, planches.json et
    controle.jpg dans `work` (qui contient images4/), et renvoie le contenu de planches.json."""
    src, work = Path(src), Path(work)
    preset = PRESETS[quality]
    candidates = len(list((work / CANDIDATE_DIR).glob("f_*.jpg")))
    out_dir = work / SHEET_DIR
    shutil.rmtree(out_dir, ignore_errors=True)
    (out_dir / EXTRACT_DIR).mkdir(parents=True, exist_ok=True)
    progress(0.0, "Choix des cases")
    tiles = select_tiles(duration, plans, image_events, sound_events, music, silences, preset, candidates=candidates)
    # extractions à la demande (plans très courts, transitoires), au même cadrage que les candidates
    todo = [t for t in tiles if t["source"] == "extrait"]
    extracted = 0
    for i, tile in enumerate(todo):
        dst = out_dir / EXTRACT_DIR / f"x_{tile['id']}.jpg"
        ok = False
        try:  # ffmpeg rend la première image à partir de l'instant demandé : un peu avant, pour avoir celle-là
            ok = extract_padded(src, max(0.0, tile["t"] - EXTRACT_LEAD), dst, 640, 360)
        except FFmpegUnavailable:
            raise
        except (FFmpegError, OSError):
            ok = False
        if ok:
            tile["_file"] = f"{SHEET_DIR}/{EXTRACT_DIR}/{dst.name}"
            extracted += 1
        else:  # image introuvable à cet instant : la candidate la plus proche
            tile["source"] = "images4"
        progress(0.3 * (i + 1) / max(1, len(todo)), "Images des plans très courts")
    for tile in tiles:
        if tile["source"] == "images4":
            k = int(np.clip(round(tile["t"] * CANDIDATE_FPS), 0, max(0, candidates - 1)))
            tile["_file"] = f"{CANDIDATE_DIR}/f_{k:06d}.jpg"
    cuts = [c["t"] for c in _items(plans, "cuts")]
    chunks = make_chunks(duration, cuts, words, preset, tiles=tiles)
    sheets, chunks = layout(tiles, chunks, preset)
    by_sheet: dict[int, list[dict]] = {}
    for tile in tiles:
        by_sheet.setdefault(tile["sheet"], []).append(tile)
    for sh in sheets:
        group = sorted(by_sheet.get(sh["n"], []), key=lambda t: t["cell"])
        images = _tile_images(group, work, preset)
        encode_rgb_jpeg(compose_sheet(group, images, preset), work / sh["file"], q=JPEG_Q)
        progress(0.3 + 0.6 * (sh["n"] + 1) / max(1, len(sheets)), "Planches d'images")
    for ch in chunks:  # requête trop lourde : planches de l'extrait réencodées plus compressées
        files = [work / sheets[n]["file"] for n in ch["sheets"]]
        if sum(f.stat().st_size for f in files) * 4 / 3 > MAX_REQUEST_B64:
            for f in files:
                encode_rgb_jpeg(decode_jpegs([f], preset.sheet_w, preset.sheet_h)[0], f, q=JPEG_Q_SMALL)
    shutil.rmtree(out_dir / EXTRACT_DIR, ignore_errors=True)
    progress(0.95, "Planche de contrôle")
    try:
        build_control(work, plans, image_events, video_id or work.name, candidates)
    except FFmpegUnavailable:
        raise
    except FFmpegError:
        pass  # la planche de contrôle n'est qu'une aide visuelle
    data = {
        "version": SHEETS_VERSION, "quality": preset.id, "tile_w": preset.tile_w, "tile_h": preset.tile_h,
        "cols": preset.cols, "rows": preset.rows,
        "tiles": [{k: t[k] for k in ("id", "t", "plan", "new_plan", "reasons", "tags", "chunk", "sheet", "cell", "source")}
                  for t in tiles],
        "sheets": sheets, "chunks": chunks,
        "image_tokens": sum(s["tokens"] for s in sheets), "extracted": extracted,
    }
    _write_json(work / "planches.json", data)
    progress(1.0, "")
    return data


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)
