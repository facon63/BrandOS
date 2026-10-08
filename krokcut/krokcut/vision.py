"""Mesures locales de l'image d'une vidéo montée : plans, zooms secs, flashs, figés, fondus, N&B, bandes.

Un seul décodage normalisé : 128×72 à 30 i/s pour les mesures, et des images candidates 640×360 à
4 i/s pour les planches de Claude. Une vidéo à 60, 30 ou 25 i/s, en 1080p ou en 360p, est ainsi
mesurée par le même instrument. Pendant le flux, on ne calcule que des descripteurs par image ; les
décisions sont prises ensuite par des fonctions pures sur ces séries (testables sans vidéo).

Repères (ids chronologiques) : P### plans, Z## zooms secs, F## transitoires (flash, image insérée,
noir bref), G## figés, N## noirs et fondus, B## noir et blanc et bandes cinéma.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import statistics
import sys
import warnings
from pathlib import Path
from typing import Callable

import numpy as np

from .ffmpeg_utils import FFmpegError, FFmpegUnavailable, MediaInfo, run_ffmpeg, stream_raw_frames

IMAGE_VERSION = 1  # change quand les mesures changent : les vidéos déjà mesurées sont refaites

# ------------------------------------------------------------------ décodage
FPS = 30  # cadence de mesure, quelle que soit la source
W, H = 128, 72  # image de mesure
THUMB_FPS = 4  # images candidates pour les planches
THUMB_W, THUMB_H = 640, 360
THUMB_DIR = "images4"
THUMB_PATTERN = "f_%06d.jpg"
THUMB_QUALITY = 4
BLOCK = 300  # images par bloc (10 s) : point d'annulation et de progression
HWACCEL = "videotoolbox"  # décodage matériel, seulement sous macOS...
HW_CODECS = ("h264", "hevc")  # ... et pour ces codecs
DECODE_SHARE = 0.9  # part de la progression consacrée au décodage

# ------------------------------------------------------------- descripteurs
HIST_BINS = 4  # histogramme RGB conjoint 4×4×4
BAR_ROWS = 6  # lignes du haut / du bas pour les bandes cinéma
CENTER_BAND = (0.25, 0.75)  # bande centrale (hauteur) pour les bandes cinéma
SERIES_KEYS = ("dpix", "dhist", "pc", "dx", "dy", "luma", "std", "sat", "bar_top", "bar_bot", "center")

# ------------------------------------------------------------------ coupes (§3.3)
BASE_WIN = 15  # demi-fenêtre de la médiane de référence (images)
SPIKE_MIN = 0.02
SPIKE_RATIO = 4.0
STRONG_DHIST = 0.30
STRONG_PC = 0.22
VERY_STRONG_DHIST = 0.50  # les couleurs changent du tout au tout : candidat même si la corrélation de phase résiste
FLAT_STD = 4.0  # deux images unies de suite : fondu, pas coupe
TRANSIENT_MAX = 6  # retour à l'image d'avant en 6 images au plus : flash ou image insérée
TRANSIENT_NCC = 0.80
TRANSIENT_PC = 0.40
TRANSIENT_MARGIN = 0.15  # le retour doit ressembler nettement plus à l'image d'avant que le saut lui-même...
TRANSIENT_RETURN = 0.5  # ... et être lui-même un saut (A-B-A : deux sauts, pas un zoom qui reste)
FLASH_RISE = 0.25
FLASH_STD = 15.0
BLACK_LUMA = 0.06
CHANGE_PC = 0.22
CHANGE_DHIST = 0.25
MERGE_FRAMES = 2
# Zone centrale qui ne change pas plus que d'habitude : un habillage est apparu sur les bords (bandes,
# sticker, cadre de facecam), ce n'est pas une coupe.
SAME_IMAGE_FLOOR = 0.80
SAME_IMAGE_MARGIN = 0.05

# ------------------------------------------------------------------- zoom sec (§3.4)
ZOOM_SCALES = (1.10, 1.15, 1.20, 1.25, 1.33, 1.50, 1.75, 2.00)
ZOOM_CENTERS = (0.3, 0.4, 0.5, 0.6, 0.7)
ZOOM_ZONE = (0.2, 0.8)  # NCC sur la zone centrale : facecams et logos de coin écartés
ZOOM_NCC = 0.85
ZOOM_GAIN = 0.10
# Zone centrale très régulière (barres, décor uni) : l'image d'avant ressemble déjà à 0,9 à celle d'après
# et un gain de 0,10 est impossible. On accepte alors un gain plus petit s'il comble l'essentiel de l'écart.
ZOOM_GAIN_MIN = 0.04
ZOOM_REL_GAIN = 0.6
ZOOM_REFINE_SCALE = (-0.05, 0.05, 0.0125)  # affinage autour de la meilleure hypothèse de la grille
ZOOM_REFINE_CENTER = (-0.04, 0.04, 0.02)
WHOLE_TILES = 4  # « tout le cadre » : aucune case d'une grille 4×4 n'est restée immobile pendant le zoom
WHOLE_STATIC_RATIO = 0.5  # case mieux expliquée par « rien n'a bougé » que par le zoom
WHOLE_STATIC_MAE = 6.0  # niveaux de gris : en dessous, la case est trop unie pour trancher
PAIR_SCALE_TOL = 0.08
PAIR_MAX_S = 10.0

# ------------------------------------------------------------- autres repères (§3.5)
FREEZE_DPIX = 0.0015
FREEZE_MIN = 12
FADE_MIN, FADE_MAX = 6, 60
FADE_MONOTONE = 0.8
FADE_STEP = 0.0015  # pas de luminance minimal pour compter une image du fondu...
FADE_REL_STEP = 0.3  # ... et au moins 30 % de la pente du fondu (une petite variation avant n'en fait pas partie)
FADE_MIN_DROP = 0.08
FADE_PLATEAU = 0.01  # le fondu s'arrête quand le noir est atteint
BLACK_MIN = 2
BW_SAT = 0.03
BW_VIDEO_SAT = 0.12  # vidéo déjà grise (jeu en N&B) : mesure désactivée
BW_MIN_S = 1.0
BARS_LUMA = 0.03
BARS_CENTER = 0.10
BARS_MIN_S = 1.0

ZONE_NAMES = {
    (0, 0): "haut gauche", (1, 0): "haut", (2, 0): "haut droite",
    (0, 1): "gauche", (1, 1): "centre", (2, 1): "droite",
    (0, 2): "bas gauche", (1, 2): "bas", (2, 2): "bas droite",
}

Progress = Callable[[float, str], None]


# ======================================================================= géométrie
def content_box(width: int, height: int, w: int = W, h: int = H) -> tuple[int, int, int, int]:
    """Zone utile (x0, y0, x1, y1) de l'image de mesure : sans les bandes ajoutées par `pad`.

    Même calcul que le filtre scale (force_original_aspect_ratio=decrease) ; une ligne de marge
    côté bande, pour ne jamais mesurer le flou du bord.
    """
    if not width or not height:
        return (0, 0, w, h)
    sw = min(w, int(round(h * width / height)))
    sh = min(h, int(round(w * height / width)))
    x0, y0 = (w - sw) // 2, (h - sh) // 2
    x1, y1 = x0 + sw, y0 + sh
    if sw < w:
        x0, x1 = x0 + 1, x1 - 1
    if sh < h:
        y0, y1 = y0 + 1, y1 - 1
    return (x0, y0, x1, y1)


def _even(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return (x0, y0, x0 + (x1 - x0) // 2 * 2, y0 + (y1 - y0) // 2 * 2)


@functools.lru_cache(maxsize=8)
def _hann(h: int, w: int) -> np.ndarray:
    return np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)


def _small(y: np.ndarray) -> np.ndarray:
    """Moyenne 2×2 (64×36 pour une image 16:9) ; y : (..., h, w) de dimensions paires."""
    h, w = y.shape[-2:]
    return y.reshape(*y.shape[:-2], h // 2, 2, w // 2, 2).mean(axis=(-3, -1))


def _spectra(ys: np.ndarray) -> np.ndarray:
    win = _hann(*ys.shape[-2:])
    centered = ys - ys.mean(axis=(-2, -1), keepdims=True)
    return np.fft.rfft2(centered * win)


def _phase_peak(fa: np.ndarray, fb: np.ndarray, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pic de corrélation de phase entre deux séries de spectres : (valeur, dx, dy)."""
    cross = fb * np.conj(fa)
    cross /= np.abs(cross) + 1e-6
    r = np.fft.irfft2(cross, s=shape)
    flat = r.reshape(len(r), -1)
    k = flat.argmax(axis=1)
    peak = flat[np.arange(len(r)), k]
    dy, dx = np.divmod(k, shape[1])
    dy = np.where(dy > shape[0] // 2, dy - shape[0], dy)
    dx = np.where(dx > shape[1] // 2, dx - shape[1], dx)
    return peak, dx, dy


def phase_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pic de corrélation de phase entre deux images Y (même taille, dimensions paires)."""
    sa, sb = _small(a.astype(np.float32)), _small(b.astype(np.float32))
    peak, _, _ = _phase_peak(_spectra(sa)[None], _spectra(sb)[None], sa.shape)
    return float(peak[0])


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32) - a.mean()
    b = b.astype(np.float32) - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 1e-6 else 0.0


# ===================================================================== descripteurs
def luma_of(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * np.float32(0.299) + rgb[..., 1] * np.float32(0.587) + rgb[..., 2] * np.float32(0.114)


def descriptors(rgb_block: np.ndarray, prev: np.ndarray | None, box: tuple[int, int, int, int]) -> dict:
    """Descripteurs par image d'un bloc (n, H, W, 3) uint8 ; `prev` = dernière image du bloc précédent.

    Renvoie les séries du §3.2 (une valeur par image du bloc) et « y », la luminance uint8 (n, H, W).
    """
    x0, y0, x1, y1 = _even(box)
    rgb_full = rgb_block if prev is None else np.concatenate([prev[None], rgb_block])
    y_full = luma_of(rgb_full.astype(np.float32))
    rgb = rgb_full[:, y0:y1, x0:x1]
    y = y_full[:, y0:y1, x0:x1]
    n_all = len(rgb)
    npix = y.shape[1] * y.shape[2]

    dpix = np.abs(np.diff(y, axis=0)).mean(axis=(1, 2)) / 255
    q = (rgb >> 6).astype(np.int64)
    idx = q[..., 0] * 16 + q[..., 1] * 4 + q[..., 2] + 64 * np.arange(n_all)[:, None, None]
    hist = np.bincount(idx.ravel(), minlength=64 * n_all).reshape(n_all, 64) / npix
    dhist = 0.5 * np.abs(np.diff(hist, axis=0)).sum(axis=1)
    small = _small(y)
    spec = _spectra(small)
    pc, dx, dy = _phase_peak(spec[:-1], spec[1:], small.shape[1:])

    if prev is None:  # première image de la vidéo : rien à comparer
        dpix = np.concatenate([[0.0], dpix])
        dhist = np.concatenate([[0.0], dhist])
        pc = np.concatenate([[1.0], pc])
        dx = np.concatenate([[0], dx])
        dy = np.concatenate([[0], dy])
        cur, cur_rgb = y, rgb
    else:
        cur, cur_rgb = y[1:], rgb[1:]
    h = cur.shape[1]
    c0, c1 = int(h * CENTER_BAND[0]), int(h * CENTER_BAND[1])
    mx = cur_rgb.max(axis=3).astype(np.float32)
    mn = cur_rgb.min(axis=3).astype(np.float32)
    return {
        "dpix": dpix.astype(np.float32),
        "dhist": dhist.astype(np.float32),
        "pc": pc.astype(np.float32),
        "dx": dx.astype(np.float32),
        "dy": dy.astype(np.float32),
        "luma": (cur.mean(axis=(1, 2)) / 255).astype(np.float32),
        "std": cur.std(axis=(1, 2)).astype(np.float32),
        "sat": ((mx - mn).mean(axis=(1, 2)) / 255).astype(np.float32),
        "bar_top": (cur[:, :BAR_ROWS].mean(axis=(1, 2)) / 255).astype(np.float32),
        "bar_bot": (cur[:, -BAR_ROWS:].mean(axis=(1, 2)) / 255).astype(np.float32),
        "center": (cur[:, c0:c1].mean(axis=(1, 2)) / 255).astype(np.float32),
        "y": np.clip(np.rint(y_full[0 if prev is None else 1:]), 0, 255).astype(np.uint8),
    }


# ======================================================================= zoom sec
def _tables_for(hyps: list[tuple[float, float, float]], h: int, w: int):
    """Indices et poids du rééchantillonnage bilinéaire pour des hypothèses (échelle, cx, cy).

    Le recadrage w/s × h/s est borné à l'image ; renvoie les hypothèses avec le centre réel après bornage.
    """
    real, rows, cols = [], [], []
    for s, cx, cy in hyps:
        cw, ch = w / s, h / s
        x0 = min(max(cx * w - cw / 2, 0.0), w - cw)
        y0 = min(max(cy * h - ch / 2, 0.0), h - ch)
        real.append((float(s), (x0 + cw / 2) / w, (y0 + ch / 2) / h))
        cols.append(x0 + (np.arange(w) + 0.5) * cw / w - 0.5)
        rows.append(y0 + (np.arange(h) + 0.5) * ch / h - 0.5)

    def split(coord: list, size: int):
        arr = np.array(coord, np.float32)
        i0 = np.clip(np.floor(arr).astype(np.int64), 0, size - 2)
        frac = np.clip(arr - i0, 0.0, 1.0).astype(np.float32)
        return i0, frac

    yi, fy = split(rows, h)
    xi, fx = split(cols, w)
    return real, (yi, fy, xi, fx)


def _central(h: int, w: int) -> tuple[slice, slice]:
    return (slice(int(round(h * ZOOM_ZONE[0])), int(round(h * ZOOM_ZONE[1]))),
            slice(int(round(w * ZOOM_ZONE[0])), int(round(w * ZOOM_ZONE[1]))))


@functools.lru_cache(maxsize=8)
def _zoom_tables(h: int, w: int):
    """Grille d'hypothèses du §3.4 (sans doublons après bornage), précalculée par taille d'image."""
    hyps, seen = [], set()
    for s in ZOOM_SCALES:
        for cx in ZOOM_CENTERS:
            for cy in ZOOM_CENTERS:
                cw, ch = w / s, h / s
                key = (s, round(min(max(cx * w - cw / 2, 0.0), w - cw), 3), round(min(max(cy * h - ch / 2, 0.0), h - ch), 3))
                if key not in seen:  # le bornage ramène plusieurs centres au même recadrage
                    seen.add(key)
                    hyps.append((s, cx, cy))
    return _tables_for(hyps, h, w)


def _resample(img: np.ndarray, yi, fy, xi, fx) -> np.ndarray:
    """Recadrages bilinéaires (K, h', w') de `img` selon les tables."""
    a = img[yi[:, :, None], xi[:, None, :]]
    b = img[yi[:, :, None], xi[:, None, :] + 1]
    c = img[yi[:, :, None] + 1, xi[:, None, :]]
    d = img[yi[:, :, None] + 1, xi[:, None, :] + 1]
    fx3, fy3 = fx[:, None, :], fy[:, :, None]
    return (a * (1 - fx3) + b * fx3) * (1 - fy3) + (c * (1 - fx3) + d * fx3) * fy3


def _ncc_many(stack: np.ndarray, target: np.ndarray) -> np.ndarray:
    a = stack.reshape(len(stack), -1)
    a = a - a.mean(axis=1, keepdims=True)
    b = target.ravel() - target.mean()
    den = np.sqrt((a * a).sum(axis=1) * float((b * b).sum())) + 1e-6
    return (a @ b) / den


def zone_name(cx: float, cy: float) -> str:
    col = 0 if cx < 1 / 3 else (2 if cx > 2 / 3 else 1)
    row = 0 if cy < 1 / 3 else (2 if cy > 2 / 3 else 1)
    return ZONE_NAMES[(col, row)]


def _central_scores(src: np.ndarray, dst: np.ndarray, tables) -> np.ndarray:
    yi, fy, xi, fx = tables
    rz, cz = _central(*dst.shape)
    return _ncc_many(_resample(src, yi[:, rz], fy[:, rz], xi[:, cz], fx[:, cz]), dst[rz, cz])


def _refine(src: np.ndarray, dst: np.ndarray, hyp: tuple[float, float, float]) -> tuple[float, tuple, tuple]:
    """Affine l'échelle et le centre autour de la meilleure hypothèse de la grille."""
    s, cx, cy = hyp
    ds = np.arange(ZOOM_REFINE_SCALE[0], ZOOM_REFINE_SCALE[1] + 1e-9, ZOOM_REFINE_SCALE[2])
    dc = np.arange(ZOOM_REFINE_CENTER[0], ZOOM_REFINE_CENTER[1] + 1e-9, ZOOM_REFINE_CENTER[2])
    hyps = [(s * (1 + a), cx + b, cy + c) for a in ds for b in dc for c in dc if s * (1 + a) > 1.02]
    real, tables = _tables_for(hyps, *dst.shape)
    scores = _central_scores(src, dst, tables)
    k = int(np.argmax(scores))
    one = tuple(t[k:k + 1] for t in tables)
    return float(scores[k]), real[k], one


def _whole_frame(src: np.ndarray, dst: np.ndarray, tables) -> tuple[bool, float]:
    """Le zoom explique-t-il toute l'image ? NCC sur toute la zone utile, et aucune case restée immobile.

    Une case de la grille 4×4 mieux expliquée par « rien n'a bougé » que par le zoom est un calque fixe
    (facecam, HUD, logo) : seul le calque du dessous a zoomé.
    """
    crop = _resample(src, *tables)[0]
    whole = ncc(crop, dst)
    h, w = dst.shape
    for i in range(WHOLE_TILES):
        for j in range(WHOLE_TILES):
            rs = slice(i * h // WHOLE_TILES, (i + 1) * h // WHOLE_TILES)
            cs = slice(j * w // WHOLE_TILES, (j + 1) * w // WHOLE_TILES)
            mae_zoom = float(np.abs(crop[rs, cs] - dst[rs, cs]).mean())
            mae_still = float(np.abs(src[rs, cs] - dst[rs, cs]).mean())
            if mae_zoom >= WHOLE_STATIC_MAE and mae_still < WHOLE_STATIC_RATIO * mae_zoom:
                return False, whole
    return bool(whole >= ZOOM_NCC), whole


def zoom_test(prev_y: np.ndarray, cur_y: np.ndarray) -> dict | None:
    """Zoom sec entre deux images Y de la zone utile : punch-in (avant) ou punch-out (arrière), sinon None."""
    prev = prev_y.astype(np.float32)
    cur = cur_y.astype(np.float32)
    h, w = cur.shape
    hyps, tables = _zoom_tables(h, w)
    rz, cz = _central(h, w)
    identity = ncc(prev[rz, cz], cur[rz, cz])
    best = None
    for direction, src, dst in (("avant", prev, cur), ("arriere", cur, prev)):
        scores = _central_scores(src, dst, tables)
        k = int(np.argmax(scores))
        if best is None or scores[k] > best[0]:
            best = (float(scores[k]), hyps[k], direction, src, dst)
    score, hyp, direction, src, dst = best
    gain = score - identity
    enough = gain >= ZOOM_GAIN or (gain >= ZOOM_GAIN_MIN and gain >= ZOOM_REL_GAIN * (1 - identity))
    if score < ZOOM_NCC or not enough:
        return None
    score, (s, cx, cy), one = _refine(src, dst, hyp)
    gain = score - identity
    whole, whole_ncc = _whole_frame(src, dst, one)
    return {
        "dir": direction, "scale": round(s, 2), "cx": round(cx, 3), "cy": round(cy, 3),
        "zone": zone_name(cx, cy), "whole_frame": whole, "ncc": round(score, 3), "gain": round(gain, 3),
        "ncc_whole": round(whole_ncc, 3), "identity": round(identity, 3),
    }


# ======================================================================== coupes
def _local_base(dpix: np.ndarray, win: int = BASE_WIN) -> np.ndarray:
    """Médiane des dpix non nuls sur [n−win, n+win] sans [n−1, n+1] (images dupliquées ignorées)."""
    n = len(dpix)
    if n == 0:
        return np.zeros(0, np.float32)
    vals = np.where(dpix > 0, dpix, np.nan).astype(np.float64)
    padded = np.pad(vals, win, constant_values=np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * win + 1).copy()
    windows[:, win - 1 : win + 2] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        base = np.nanmedian(windows, axis=1)
    return np.nan_to_num(base, nan=0.0).astype(np.float32)


def cut_candidates(series: dict) -> np.ndarray:
    """Images candidates à une coupe (pic de dpix ou fort changement de couleurs sans corrélation de phase)."""
    dpix = np.asarray(series["dpix"], np.float32)
    n = len(dpix)
    if n < 2:
        return np.zeros(0, np.int64)
    base = _local_base(dpix)
    padded = np.pad(dpix, 2, constant_values=-1)
    local_max = np.lib.stride_tricks.sliding_window_view(padded, 5).max(axis=1)
    spike = (dpix >= np.maximum(SPIKE_MIN, SPIKE_RATIO * base)) & (dpix >= local_max)
    dhist = np.asarray(series["dhist"])
    strong = ((dhist >= STRONG_DHIST) & (np.asarray(series["pc"]) < STRONG_PC)) | (dhist >= VERY_STRONG_DHIST)
    cand = spike | strong
    cand[0] = False
    std = np.asarray(series["std"])
    flat = np.zeros(n, bool)
    flat[1:] = (std[1:] < FLAT_STD) & (std[:-1] < FLAT_STD)
    return np.flatnonzero(cand & ~flat)


def _transient(y: np.ndarray, series: dict, n: int) -> tuple[int, str] | None:
    """Retour à l'image d'avant en k ≤ 6 images (test A-B-A) : (k, sous-type), sinon None."""
    total = len(y)
    if n + 1 >= total:
        return None
    before = y[n - 1].astype(np.float32)
    jump_ncc = ncc(before, y[n])
    jump_pc = float(series["pc"][n])
    dpix = series["dpix"]
    for k in range(1, TRANSIENT_MAX + 1):
        if n + k >= total:
            break
        if dpix[n + k] < TRANSIENT_RETURN * dpix[n]:
            continue
        after = y[n + k].astype(np.float32)
        back_ncc = ncc(before, after)
        back = back_ncc >= TRANSIENT_NCC and back_ncc - jump_ncc >= TRANSIENT_MARGIN
        if not back:
            back_pc = phase_corr(before, after)
            back = back_pc >= TRANSIENT_PC and back_pc - jump_pc >= TRANSIENT_MARGIN
        if back:
            span = slice(n, n + k)
            luma = float(np.mean(series["luma"][span]))
            std = float(np.mean(series["std"][span]))
            if luma > float(series["luma"][n - 1]) + FLASH_RISE and std < FLASH_STD:
                kind = "flash_blanc"
            elif luma < BLACK_LUMA:
                kind = "noir_bref"
            else:
                kind = "image_inseree"
            return k, kind
    return None


def _same_picture(luma: np.ndarray, n: int) -> bool:
    """La zone centrale ne change pas plus entre n−1 et n qu'entre deux images voisines ordinaires."""
    rz, cz = _central(*luma.shape[1:])

    def center(a: int, b: int) -> float:
        return ncc(luma[a, rz, cz], luma[b, rz, cz])

    jump = center(n - 1, n)
    if jump < SAME_IMAGE_FLOOR:
        return False
    refs = [center(a, a + 1) for a in (n - 3, n - 2, n, n + 1) if 0 <= a and a + 1 < len(luma)]
    return bool(refs) and jump >= float(np.median(refs)) - SAME_IMAGE_MARGIN


def detect_cuts(series: dict, luma: np.ndarray) -> tuple[list[dict], list[dict]]:
    """Coupes (§3.3) et événements dans les plans (transitoires F et zooms secs Z, §3.4).

    `luma` : images Y de la zone utile (N, h, w), uint8 (un memmap convient). Les instants sont
    ceux de l'image de mesure n (t = n/30) : la première image du nouveau plan pour une coupe.
    """
    cuts: list[dict] = []
    events: list[dict] = []
    skip_until = -1
    for n in cut_candidates(series):
        n = int(n)
        if n <= skip_until:
            continue
        tr = _transient(luma, series, n)
        if tr:
            k, kind = tr
            events.append({"type": kind, "n": n, "t": round(n / FPS, 3), "dur": round(k / FPS, 3)})
            skip_until = n + k  # le retour à l'image d'avant n'est pas une coupe
            continue
        zoom = zoom_test(luma[n - 1], luma[n])
        if zoom:
            events.append({"type": "zoom", "n": n, "t": round(n / FPS, 3), **zoom})
            continue
        if _same_picture(luma, n):
            continue  # bandes, sticker, cadre : l'image elle-même n'a pas changé
        pc, dhist = float(series["pc"][n]), float(series["dhist"][n])
        kind = "changement" if pc < CHANGE_PC or dhist >= CHANGE_DHIST else "meme_decor"
        cuts.append({"n": n, "t": round(n / FPS, 3), "kind": kind, "pc": round(pc, 3),
                     "dhist": round(dhist, 3), "dpix": round(float(series["dpix"][n]), 4)})
    merged: list[dict] = []
    for cut in cuts:  # deux coupes à 2 images ou moins : on garde la plus franche
        if merged and cut["n"] - merged[-1]["n"] <= MERGE_FRAMES:
            if cut["dhist"] > merged[-1]["dhist"]:
                merged[-1] = cut
            continue
        merged.append(cut)
    return merged, events


# ========================================================== autres repères (§3.5)
def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Séquences de vrais : liste de (début, fin exclue)."""
    if not len(mask):
        return []
    m = np.concatenate([[False], mask.astype(bool), [False]])
    edges = np.flatnonzero(np.diff(m.astype(np.int8)))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]


def _fade_start(luma: np.ndarray, end: int) -> int:
    """Début d'une baisse monotone de luminance qui aboutit à l'image `end` (≥ 80 % de pas nets), sinon `end`.

    Le fondu commence toujours sur un pas net : un passage plat avant le fondu n'est pas compté.
    """
    best = end
    lo = max(0, end - FADE_MAX)
    steps = np.diff(luma[lo : end + 1])  # steps[i] : de lo+i à lo+i+1
    if len(steps) < FADE_MIN:
        return end
    slope = abs(float(np.median(steps[-FADE_MIN:])))
    down = steps < -max(FADE_STEP, FADE_REL_STEP * slope)
    for length in range(FADE_MIN, end - lo + 1):
        start = end - length
        part = down[start - lo :]
        if part[0] and part.mean() >= FADE_MONOTONE:
            best = start
    if best < end and float(luma[best]) - float(luma[end]) < FADE_MIN_DROP:
        return end
    return best


def detect_static_events(series: dict) -> list[dict]:
    """Figés (G), noirs et fondus (N), noir et blanc et bandes cinéma (B), avec leurs images de début et de fin."""
    dpix = np.asarray(series["dpix"], np.float32)
    luma = np.asarray(series["luma"], np.float32)
    n = len(luma)
    out: list[dict] = []
    # G : image figée
    still = (dpix < FREEZE_DPIX) & (luma > BLACK_LUMA)
    still[0] = False
    for a, b in _runs(still):
        if b - a >= FREEZE_MIN:
            out.append({"type": "fige", "n": a, "end_n": b})
    # N : noirs, fondus au noir et depuis le noir
    for a, b in _runs(luma < BLACK_LUMA):
        if b - a < BLACK_MIN:
            continue
        plateau = float(np.median(luma[a:b])) + FADE_PLATEAU
        flat = np.flatnonzero(luma[a:b] <= plateau)
        first, last = a + int(flat[0]), a + int(flat[-1])
        fade_to = _fade_start(luma, first)
        rev = luma[::-1]
        fade_from_rev = _fade_start(rev, n - 1 - last)
        fade_from_end = n - 1 - fade_from_rev
        if fade_to < first:
            out.append({"type": "fondu_noir", "n": fade_to, "end_n": first, "black_n": last + 1 - first})
        if fade_from_end > last:
            out.append({"type": "fondu_depuis_noir", "n": last + 1, "end_n": fade_from_end + 1})
        if fade_to >= first and fade_from_end <= last:
            out.append({"type": "noir", "n": a, "end_n": b})
    # B : noir et blanc (si la vidéo est en couleurs)
    sat = np.asarray(series["sat"], np.float32)
    if n and float(np.median(sat)) > BW_VIDEO_SAT:
        for a, b in _runs((sat < BW_SAT) & (luma > BLACK_LUMA)):
            if b - a >= BW_MIN_S * FPS:
                out.append({"type": "noir_et_blanc", "n": a, "end_n": b})
    # B : bandes cinéma
    bars = (np.asarray(series["bar_top"]) < BARS_LUMA) & (np.asarray(series["bar_bot"]) < BARS_LUMA) & (
        np.asarray(series["center"]) > BARS_CENTER
    )
    for a, b in _runs(bars):
        if b - a >= BARS_MIN_S * FPS:
            out.append({"type": "bandes_cinema", "n": a, "end_n": b})
    return sorted(out, key=lambda e: e["n"])


# ======================================================================= plans
def build_plans(cuts: list[dict], duration: float) -> list[dict]:
    edges = [0.0] + [c["t"] for c in cuts if 0 < c["t"] < duration] + [duration]
    plans = []
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        plans.append({"id": f"P{i + 1:03d}", "start": round(a, 3), "end": round(b, 3),
                      "cut_in": "debut" if i == 0 else cuts[i - 1]["kind"]})
    return plans


def plan_at(plans: list[dict], t: float) -> str:
    for p in plans:
        if p["start"] <= t < p["end"]:
            return p["id"]
    return plans[-1]["id"] if plans else ""


def _pair_zooms(zooms: list[dict], plans: list[dict], duration: float) -> list[dict]:
    """Un zoom avant est apparié au premier zoom arrière d'échelle inverse du même plan (≤ 10 s)."""
    used: set[int] = set()
    out = []
    for i, z in enumerate(zooms):
        if i in used:
            continue
        plan = plan_at(plans, z["t"])
        plan_end = next((p["end"] for p in plans if p["id"] == plan), duration)
        end, paired = plan_end, False
        if z["dir"] == "avant":
            for j in range(i + 1, len(zooms)):
                r = zooms[j]
                if r["t"] - z["t"] > PAIR_MAX_S or plan_at(plans, r["t"]) != plan:
                    break
                if r["dir"] == "arriere" and j not in used and abs(r["scale"] / z["scale"] - 1) <= PAIR_SCALE_TOL:
                    used.add(j)
                    end, paired = r["t"], True
                    break
        out.append({**z, "end": round(end, 3), "hold": round(end - z["t"], 3), "returned": paired, "plan": plan})
    return out


def build_events(cuts: list[dict], in_plan: list[dict], static: list[dict], duration: float) -> list[dict]:
    """Événements de image_evenements.json, avec ids chronologiques par lettre et plan de rattachement."""
    plans = build_plans(cuts, duration)
    zooms = _pair_zooms([e for e in in_plan if e["type"] == "zoom"], plans, duration)
    transients = [e for e in in_plan if e["type"] != "zoom"]
    events: list[dict] = []
    for z in zooms:
        events.append({"letter": "Z", "type": "zoom", "t": z["t"], "end": z["end"], "dir": z["dir"],
                       "scale": z["scale"], "cx": z["cx"], "cy": z["cy"], "zone": z["zone"],
                       "whole_frame": z["whole_frame"], "ncc": z["ncc"], "gain": z["gain"],
                       "hold": z["hold"], "returned": z["returned"], "plan": z["plan"]})
    for e in transients:
        events.append({"letter": "F", "type": e["type"], "t": e["t"], "dur": e["dur"], "plan": plan_at(plans, e["t"])})
    covered = [(e["n"], e["n"] + round(e["dur"] * FPS)) for e in transients]
    letters = {"fige": "G", "noir": "N", "fondu_noir": "N", "fondu_depuis_noir": "N",
               "noir_et_blanc": "B", "bandes_cinema": "B"}
    for e in static:
        if e["type"] == "noir" and any(a <= e["n"] < b for a, b in covered):
            continue  # noir bref déjà compté comme transitoire
        t = e["n"] / FPS
        item = {"letter": letters[e["type"]], "type": e["type"], "t": round(t, 3),
                "dur": round((e["end_n"] - e["n"]) / FPS, 3), "plan": plan_at(plans, t)}
        if e.get("black_n"):
            item["black"] = round(e["black_n"] / FPS, 3)
        events.append(item)
    events.sort(key=lambda e: (e["t"], e["letter"]))
    counters: dict[str, int] = {}
    final = []
    for e in events:
        letter = e.pop("letter")
        counters[letter] = counters.get(letter, 0) + 1
        final.append({"id": f"{letter}{counters[letter]:02d}", **e})
    return final


# ===================================================================== métriques
def _pct(part: float, total: float) -> float:
    return round(100.0 * part / total, 1) if total else 0.0


def image_metrics(plans: list[dict], cuts: list[dict], events: list[dict], series: dict, duration: float) -> dict:
    minutes = max(duration / 60, 0.01)
    shots = [p["end"] - p["start"] for p in plans if p["end"] - p["start"] > 0.04]
    q = statistics.quantiles(shots, n=4) if len(shots) >= 4 else [0, 0, 0]
    p90 = float(np.percentile(shots, 90)) if shots else 0.0
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)
    zooms = by_type.get("zoom", [])
    ins = [z for z in zooms if z["dir"] == "avant"]
    holds = [z["hold"] for z in ins if z.get("returned")]
    flashes = len(by_type.get("flash_blanc", []))
    inserts = len(by_type.get("image_inseree", [])) + len(by_type.get("noir_bref", []))
    fades = sum(len(by_type.get(k, [])) for k in ("fondu_noir", "fondu_depuis_noir", "noir"))
    bars_s = sum(e["dur"] for e in by_type.get("bandes_cinema", []))
    dpix = np.asarray(series.get("dpix", []), np.float32)
    return {
        "cuts": len(cuts),
        "cuts_per_min": round(len(cuts) / minutes, 1),
        "median_shot": round(statistics.median(shots), 2) if shots else round(duration, 2),
        "shot_p25": round(q[0], 2),
        "shot_p75": round(q[2], 2),
        "shot_p90": round(p90, 2),
        "shots_under_1s_pct": _pct(sum(1 for s in shots if s < 1.0), len(shots)),
        "jump_cut_pct": _pct(sum(1 for c in cuts if c["kind"] == "meme_decor"), len(cuts)),
        "punch_ins": len(ins),
        "punch_ins_per_min": round(len(ins) / minutes, 2),
        "zoom_scale_median": round(statistics.median(z["scale"] for z in ins), 2) if ins else 0.0,
        "zoom_hold_median_s": round(statistics.median(holds), 2) if holds else 0.0,
        "zoom_layer_only_pct": _pct(sum(1 for z in zooms if not z["whole_frame"]), len(zooms)),
        "flashes_per_min": round(flashes / minutes, 2),
        "inserts_per_min": round(inserts / minutes, 2),
        "freezes_per_min": round(len(by_type.get("fige", [])) / minutes, 2),
        "fades_per_min": round(fades / minutes, 2),
        "bw_per_10min": round(10 * len(by_type.get("noir_et_blanc", [])) / minutes, 2),
        "letterbox_pct": _pct(bars_s, duration),
        "visual_changes_per_min": round((len(cuts) + len(zooms) + flashes) / minutes, 1),
        "motion_mean": round(float(dpix.mean()), 4) if len(dpix) else 0.0,
        "image_version": IMAGE_VERSION,
    }


# ====================================================================== décodage
def use_hwaccel(info: MediaInfo) -> bool:
    return sys.platform == "darwin" and info.video_codec in HW_CODECS


def decode_args(src: Path, thumbs: Path, hwaccel: bool) -> list[str]:
    graph = (
        f"[0:v]setpts=PTS-STARTPTS,split=2[a][b];"
        f"[a]fps={FPS},scale={W}:{H}:flags=area:force_original_aspect_ratio=decrease,format=rgb24,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2[m];"
        f"[b]fps={THUMB_FPS},scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease,"
        f"pad={THUMB_W}:{THUMB_H}:(ow-iw)/2:(oh-ih)/2,setsar=1[t]"
    )
    args = ["-hwaccel", HWACCEL] if hwaccel else []
    args += ["-i", str(src), "-an", "-sn", "-dn", "-filter_complex", graph,
             "-map", "[m]", "-f", "rawvideo", "pipe:1",
             "-map", "[t]", "-q:v", str(THUMB_QUALITY), "-start_number", "0", str(thumbs / THUMB_PATTERN)]
    return args


def _decode(src: Path, out_dir: Path, info: MediaInfo, box, hwaccel: bool, progress: Progress) -> tuple[dict, int]:
    """Décodage unique : séries par image (mémoire) et luminance 128×72 dans luma128.u8 (disque)."""
    thumbs = out_dir / THUMB_DIR
    if thumbs.exists():
        for f in thumbs.glob("*.jpg"):
            f.unlink()
    thumbs.mkdir(parents=True, exist_ok=True)
    expected = max(1, int(info.duration * FPS))
    parts: dict[str, list[np.ndarray]] = {k: [] for k in SERIES_KEYS}
    prev = None
    done = 0
    with open(out_dir / "luma128.u8", "wb") as raw, contextlib.closing(
        stream_raw_frames(decode_args(src, thumbs, hwaccel), (H, W, 3), block=BLOCK)
    ) as frames:
        for block in frames:
            d = descriptors(block, prev, box)
            raw.write(d.pop("y").tobytes())
            for k in SERIES_KEYS:
                parts[k].append(d[k])
            prev = block[-1].copy()
            done += len(block)
            progress(DECODE_SHARE * min(1.0, done / expected), "Analyse de l'image")
    series = {k: (np.concatenate(v) if v else np.zeros(0, np.float32)) for k, v in parts.items()}
    return series, done


def analyze_image(src: Path, out_dir: Path, info: MediaInfo, *, progress: Progress, hwaccel: bool | None = None) -> dict:
    """Mesure l'image (§3) et écrit image_trames.npz, plans.json, image_evenements.json, images4/, vignette.jpg."""
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    box = content_box(info.width, info.height)
    hw = use_hwaccel(info) if hwaccel is None else hwaccel
    decode = HWACCEL if hw else "logiciel"
    luma_path = out_dir / "luma128.u8"
    try:
        try:
            series, count = _decode(src, out_dir, info, box, hw, progress)
        except FFmpegUnavailable:
            raise
        except FFmpegError:
            if not hw:
                raise
            decode = "logiciel"  # décodage matériel refusé (codec, profil, machine) : on repasse en logiciel
            series, count = _decode(src, out_dir, info, box, False, progress)
        duration = count / FPS if count else float(info.duration)
        progress(DECODE_SHARE, "Plans, zooms et effets")
        x0, y0, x1, y1 = _even(box)
        if count:
            frames = np.memmap(luma_path, dtype=np.uint8, mode="r", shape=(count, H, W))
            cuts, in_plan = detect_cuts(series, frames[:, y0:y1, x0:x1])
            del frames
        else:
            cuts, in_plan = [], []
    finally:
        luma_path.unlink(missing_ok=True)
    static = detect_static_events(series)
    plans = build_plans(cuts, duration)
    events = build_events(cuts, in_plan, static, duration)
    np.savez_compressed(out_dir / "image_trames.npz", **{k: v.astype(np.float16) for k, v in series.items()})
    _write_json(out_dir / "plans.json", {
        "version": IMAGE_VERSION, "fps": FPS, "duration": round(duration, 3), "content_box": list(box),
        "plans": plans,
        "cuts": [{k: c[k] for k in ("t", "kind", "pc", "dhist", "dpix")} for c in cuts],
    })
    _write_json(out_dir / "image_evenements.json", {"version": IMAGE_VERSION, "events": events})
    _thumbnail(out_dir, duration)
    metrics = image_metrics(plans, cuts, events, series, duration)
    metrics["decode"] = decode
    progress(1.0, "")
    return metrics


def thumb_files(out_dir: Path) -> list[Path]:
    return sorted((Path(out_dir) / THUMB_DIR).glob("f_*.jpg"))


def _thumbnail(out_dir: Path, duration: float) -> None:
    """vignette.jpg : 320 px de large, à 10 % de la durée."""
    files = thumb_files(out_dir)
    if not files:
        return
    k = min(len(files) - 1, int(round(0.1 * duration * THUMB_FPS)))
    with contextlib.suppress(FFmpegError):
        run_ffmpeg(["-i", str(files[k]), "-vf", "scale=320:-2", "-q:v", "4", str(out_dir / "vignette.jpg")])


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)
