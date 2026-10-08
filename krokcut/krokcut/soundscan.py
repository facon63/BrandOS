"""Mesures locales du son d'une vidéo montée : bruitages, musique de fond, silences, pauses, volume.

numpy seul, sur le PCM 16 kHz mono de la vidéo (audio.pcm), lu par blocs de 60 s avec 1 s de
recouvrement : la mémoire reste faible même pour une heure. Toutes les trames sont au pas de 10 ms.

Claude n'entend pas le son : ces mesures sont tout ce qu'il en saura. Le détecteur ne distingue pas
un bruitage ajouté au montage d'un son du jeu ou d'un cri ; Claude tranche ensuite avec l'image et la
parole (verdict par id S, M). Le même instrument mesure toutes les chaînes : on compare des rapports.

Ids : S### sons marquants, M# musiques, C## silences complets.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import pcm_duration, read_pcm
from .ffmpeg_utils import run_ffmpeg

SOUND_VERSION = 1  # change quand les mesures changent : les vidéos déjà mesurées sont refaites

# --------------------------------------------------------------- représentations (§4.1)
SR = 16000
HOP = 160  # 10 ms
FPS = SR // HOP  # trames par seconde
BLOCK_S = 60.0
OVERLAP_S = 1.0
NFFT_A = 512  # STFT-A : bandes, mel, platitude, SuperFlux
NFFT_B = 1024  # STFT-B (15,6 Hz par raie) : raies tonales, peigne, chroma, part < 90 Hz
N_MELS = 64
MEL_RANGE = (30.0, 8000.0)
BANDS = {"sub": (30, 150), "low": (150, 400), "mid": (400, 3400), "high": (3400, 8000)}
BAND_KEYS = tuple(BANDS)
FLAT_RANGE = (300, 7000)
KICK_HZ = 110  # SuperFlux grave : grosse caisse
LOW90_HZ = (30, 90)
LINE_RANGE = (100, 6000)  # raies cherchées (les événements n'en gardent que 150–6 000 Hz)
LINE_SAL_DB = 15.0
LINE_MED_BINS = 12  # saillance = dB − médiane des ±12 raies
FLOOR_DB = -100.0
CHROMA_RANGE = (100, 4000)
SPEECH_PAD = 0.05
VAD_BLOCK_S = 600.0
VAD_OPTIONS = {"threshold": 0.5, "min_speech_duration_ms": 120, "min_silence_duration_ms": 80, "speech_pad_ms": 0}

# ------------------------------------------------------- événements non vocaux (§4.2)
ONSET_WIN = 150  # ±1,5 s
ONSET_K = 4.0
ONSET_OFFSET = 0.5
ONSET_LOCAL = 3  # maximum local sur ±3 trames
ONSET_GAP = 5  # 50 ms entre deux attaques
ONSET_BACK = 6  # l'instant est affiné sur la montée de E (mi-hauteur), 60 ms au plus avant l'attaque
NARROW_BANDS = 4  # flux des 4 bandes qui montent le plus : un bip ou un ding pur bouge peu la moyenne des 64 bandes
COARSE_STEP = 10  # médianes glissantes calculées toutes les 100 ms
PRE = (25, 3)  # [c − 250 ms, c − 30 ms]
POST = 12  # [c, c + 120 ms]
ACCEPT_RISE = 10.0
ACCEPT_CONTEXT = 6.0
OVERLAP_RISE = 10.0  # une attaque dans un son en cours doit encore monter de 10 dB
END_DROP = 15.0
END_ABOVE_PRE = 3.0
END_FRAMES = 3
MAX_EVENT_S = 4.0
DOMINANT_MIN_FRAMES = 12  # raie stable ≥ 120 ms
DOMINANT_FMIN = 400
NEW_PEAK_SAL = 12.0
NEW_PEAK_RISE = 10.0
COMB_F0 = (80.0, 400.0, 2.0)
COMB_KMAX = 12
COMB_DOMINANT_K = (1, 12)  # rang de la référence dans la série (voir _comb_count)
COMB_TOL = (8.0, 0.01)
COMB_REL_DB = 25.0  # seuls comptent les pics à moins de 25 dB de la référence
CLIP_LEVEL = 0.98
FINAL_DROP_FRAMES = 10
IN_SPEECH = 0.5
# montée (riser) : son qui enfle pendant 1 à 4 s puis s'arrête net
RISER_MIN_S, RISER_MAX_S = 1.0, 4.0
RISER_SMOOTH = 5
RISER_ENVELOPE = 20  # enveloppe (maximum sur 200 ms) : passe par-dessus les syllables
RISER_POINTS = 5  # niveaux à 0, 25, 50, 75 et 100 % de la montée
RISER_PEAK_TAIL = 0.15  # le plus fort est atteint à la fin (derniers 15 %)
RISER_MAX_DIP = 6.0  # sur la 2e moitié, le niveau ne retombe jamais de plus de 6 dB (une voix : creux entre syllabes)
RISER_SPEARMAN = 0.8
RISER_MIN_RISE = 12.0
RISER_DROP = 10.0
RISER_STEADY = 0.1  # chaque quart de la montée apporte au moins 10 % de la hausse (une phrase qui démarre : tout au début)
RISER_LAST_HALF_DB = 6.0  # et ça monte encore d'au moins 6 dB sur la 2e moitié (une voix qui s'anime, non)

# catégories (§4.3), dans l'ordre d'essai
CATEGORIES = {
    "sature": "son saturé",
    "boum": "boum / impact grave",
    "bip": "bip (censure ?)",
    "tonal": "ding / jingle / notification",
    "glissando": "son cartoon (glissando, boing)",
    "whoosh": "whoosh / transition",
    "montee": "montée (riser)",
    "clic": "coup bref / clic",
    "autre": "autre son marquant",
}
EDITORIAL = tuple(c for c in CATEGORIES if c != "autre")
IN_SPEECH_OK = ("sature", "boum", "bip", "tonal", "glissando", "whoosh", "montee")
CLIP_RATIO = 0.005
BOUM_RISE, BOUM_LOW90, BOUM_SUB, BOUM_ATTACK_MS, BOUM_MIN_S = 12.0, 0.40, 0.70, 40, 0.15
TONE_SAL, TONE_SHARE, COMB_MAX = 20.0, 0.35, 4
TONE_COVER = 0.5  # la raie tient au moins la moitié du son (une harmonique de voix croisée par un glissando, non)
TONE_DEV_ST = 1.0  # un son tonal tient sa hauteur à un demi-ton près (une voyelle chantée glisse)
TONE_PURE_SHARE = 0.9  # une raie fixe qui porte 90 % de l'énergie est un son pur, même alignée sur une voix grave
BIP_F, BIP_DEV_ST, BIP_DUR = (700, 1300), 0.3, (0.12, 2.5)
GLIDE_SAL, GLIDE_FRAC, GLIDE_RATE, GLIDE_RANGE, GLIDE_DUR = 15.0, 0.6, 10.0, 4.0, (0.15, 2.0)
GLIDE_STEP_ST = 1.0  # la hauteur suivie ne saute pas de plus d'un demi-ton par trame (sinon : autre harmonique)
WHOOSH_FLAT, WHOOSH_HIGH, WHOOSH_MIDHIGH, WHOOSH_ATTACK_MS, WHOOSH_DUR = 0.25, 0.45, 0.8, 30, (0.15, 1.5)
CLIC_RISE, CLIC_ATTACK_MS, CLIC_MAX_S = 15.0, 10, 0.12
AUTRE_RISE = 12.0
VISUAL_WINDOW = 0.15

# ------------------------------------------------------------------ musique (§4.4)
MUSIC_WIN = 600  # 6 s
MUSIC_STEP = 100  # 1 s
BEAT_LAGS = (30, 100)  # 60 à 200 BPM
BEAT_MIN = 0.30
LAG_TOL = 2
LAG_HISTORY = 4
TONAL_MIN_FREE = 150  # 1,5 s hors parole dans la fenêtre
TONAL_LINES = 2
TONAL_LINE_FRAMES = 25  # raie stable ≥ 250 ms
TONAL_FRAC = 0.30
CHROMA_BLOCK = 150  # 1,5 s
CHROMA_VAR = 0.15
TONAL_ABOVE_FLOOR = 10.0
FLOOR_PCT = 15
ENTER_WINDOWS = 3
EXIT_WINDOWS = 3
MUSIC_MIN_S = 6.0
MUSIC_MERGE_S = 2.0
SEED_SHIFT_W = 5  # fenêtre de référence : 5 fenêtres à l'intérieur des bornes grossières
UNKNOWN_MAX_W = 15  # fenêtres « on ne sait pas » (parole continue) qui ne coupent pas une musique...
UNKNOWN_PROBE = (200, 400)  # ... sauf si le centre de l'une d'elles prouve qu'elle est partie
BEAT_TOL = 3  # un temps tombe à ±30 ms de la grille du tempo
BEAT_PEAK_K = 2.0  # attaque de grosse caisse : Dk au-dessus de médiane + 2·MAD de la fenêtre
BEAT_MISSES = 2  # deux temps manqués de suite : la grosse caisse s'est arrêtée
KICK_GATE_DB = 8.0  # un temps est au plus 8 dB sous les autres en grave (une consonne qui démarre, non)
KICK_RISE_DB = 6.0  # ... et le grave y monte d'au moins 6 dB par rapport aux 40 ms d'avant
KICK_RISE_FRAMES = 4
KICK_REF_PCT = 90  # niveau de référence d'un temps : 90e centile des attaques graves de la fenêtre
FADE_KICK_DB = 4.0  # derniers temps suivis 4 dB sous ceux de la fenêtre : la musique s'éteint (fondu)
BEAT_SEARCH_S = 3.0  # on suit les temps jusqu'à 3 s au-delà des fenêtres positives
BOUND_SEARCH_S = 3.0  # bornes cherchées jusqu'à 3 s au-delà des dernières preuves de musique
PRESENT_DB = 6.0  # trame sans parole à moins de 6 dB du niveau de la musique : elle est encore là
ABSENT_MIN = 5  # 50 ms de trames à 12 dB sous ce niveau (même entre deux mots) : elle est partie
ABSENT_HOLD_S = 2.0  # ... sans qu'elle revienne dans les 2 s
LEVEL_MIN_FRAMES = 10  # trames sans parole nécessaires pour mesurer un niveau (sinon 20e centile de tout)
CUT_DROP = 12.0  # coupure nette : chute ≥ 12 dB...
CUT_SPAN = 20  # ... en ≤ 0,2 s
FADE_DROP = 6.0  # fondu : le niveau hors parole a baissé de ≥ 6 dB entre [fin − 8 s, fin − 3 s]...
FADE_FAR = (8.0, 3.0)
FADE_NEAR_FRAMES = 20  # ... et les 20 trames sans parole les plus proches de la fin (à 2,5 s au plus)
FADE_NEAR_MAX_S = 2.5
CHANGE_TEMPO = 0.06
CHANGE_CHROMA = 0.35
CHANGE_LEVEL = 6.0
CHANGE_HOLD_S = 4.0
CHANGE_SIDE_S = 6.0
CHANGE_WITHIN = 2.0  # l'harmonie change vraiment : 2 fois plus qu'à l'intérieur de chaque côté (suite d'accords)

# ------------------------------------------------------------- silences (§4.5)
SILENCE_DB = -60.0
SILENCE_MIN = 15  # 150 ms
SILENCE_MARGIN_S = 1.0
ABRUPT_FROM_DB = -35.0
ABRUPT_DROP = 25.0
ABRUPT_FRAMES = 3  # 30 ms
DEAD_AIR_ABOVE_FLOOR = 6.0
DEAD_AIR_MIN = 50  # 0,5 s
PAUSE_MAX_S = 3.0
TAIL_MAX_S = 2.0
WORD_CUT_WINDOW = 0.5
WORD_CUT_MARGIN = 0.05

# ------------------------------------------------------------ volume et rythme (§4.6, 4.7)
R128_HOP = 0.1
SPIKE_LU = 9.0
SPIKE_MIN_S = 0.3
SHORTTERM_FLOOR = -70.0
RHYTHM_WIN_S = 30.0

Progress = Callable[[float, str], None]
SpeechProvider = Callable[[Path], list[tuple[float, float]]]
DEFAULT_VAD = object()  # sentinelle : VAD Silero livrée avec faster-whisper


# ======================================================================= outils
def _db(power):
    return 10 * np.log10(np.asarray(power, dtype=np.float64) + 1e-10)


def _hz_bins(nfft: int) -> np.ndarray:
    return np.fft.rfftfreq(nfft, 1 / SR)


def _mel_bank() -> tuple[np.ndarray, np.ndarray]:
    """Banc mel triangulaire (N_MELS × raies de NFFT_A) ; chaque bande garde au moins une raie."""
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)  # noqa: E731
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)  # noqa: E731
    pts = mel2hz(np.linspace(hz2mel(MEL_RANGE[0]), hz2mel(MEL_RANGE[1]), N_MELS + 2))
    freqs = _hz_bins(NFFT_A)
    bank = np.zeros((N_MELS, len(freqs)), np.float32)
    for i in range(N_MELS):
        lo, c, hi = pts[i : i + 3]
        tri = np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c))
        bank[i] = np.clip(tri, 0, None)
        if not bank[i].any():  # bande plus étroite qu'une raie (graves) : la raie la plus proche
            bank[i, int(np.argmin(np.abs(freqs - c)))] = 1.0
    return bank, pts[1:-1]


_MEL, _MEL_CENTERS = _mel_bank()


def _chroma_matrix() -> np.ndarray:
    freqs = _hz_bins(NFFT_B)
    mat = np.zeros((len(freqs), 12), np.float32)
    sel = (freqs >= CHROMA_RANGE[0]) & (freqs <= CHROMA_RANGE[1])
    pcs = np.round(12 * np.log2(freqs[sel] / 440.0)).astype(int) % 12
    mat[np.flatnonzero(sel), pcs] = 1.0
    return mat


_CHROMA = _chroma_matrix()


def _frames(x: np.ndarray, win: int, n_frames: int) -> np.ndarray:
    """Trames de `win` échantillons centrées sur le milieu de chaque pas de 10 ms (zéros hors signal)."""
    pad = win // 2
    xp = np.pad(x.astype(np.float32), (pad, pad + win))
    view = np.lib.stride_tricks.sliding_window_view(xp, win)
    return view[np.arange(n_frames) * HOP + HOP // 2]


def _power(x: np.ndarray, win: int, n_frames: int) -> np.ndarray:
    frames = _frames(x, win, n_frames) * np.hanning(win).astype(np.float32)
    spec = np.fft.rfft(frames, axis=1)
    return (spec.real**2 + spec.imag**2).astype(np.float32)


def _run_lengths(mask: np.ndarray) -> np.ndarray:
    """Longueur (en trames) de la séquence de vrais qui contient chaque case, colonne par colonne."""
    t, f = mask.shape
    m = np.zeros((f, t + 2), np.int8)
    m[:, 1:-1] = mask.T
    d = np.diff(m, axis=1).ravel()  # (f, t+1) aplati : débuts (+1) et fins (−1) d'une même colonne
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    acc = np.zeros(len(d) + 1, np.int64)
    np.add.at(acc, starts, ends - starts)
    np.add.at(acc, ends, -(ends - starts))
    lengths = np.cumsum(acc)[:-1].reshape(f, t + 1)[:, :t]
    return lengths.T.astype(np.int32)


def _peaks(db: np.ndarray, lo_hz: float, hi_hz: float, min_sal: float) -> tuple[np.ndarray, np.ndarray]:
    """Pics locaux saillants d'un spectrogramme dB (T × raies) : masque et saillance (0 ailleurs)."""
    freqs = _hz_bins(2 * (db.shape[1] - 1))
    k0 = max(1, int(np.searchsorted(freqs, lo_hz)))
    k1 = min(db.shape[1] - 2, int(np.searchsorted(freqs, hi_hz, side="right")) - 1)
    mask = np.zeros(db.shape, bool)
    sal = np.zeros(db.shape, np.float32)
    if k1 <= k0:
        return mask, sal
    core = db[:, k0 : k1 + 1]
    local = (core > db[:, k0 - 1 : k1]) & (core >= db[:, k0 + 1 : k1 + 2])
    tt, kk = np.nonzero(local)
    if not len(tt):
        return mask, sal
    kk = kk + k0
    padded = np.pad(db, ((0, 0), (LINE_MED_BINS, LINE_MED_BINS)), mode="edge")
    offs = np.arange(2 * LINE_MED_BINS + 1)
    windows = padded[tt[:, None], kk[:, None] + offs[None, :]]
    s = db[tt, kk] - np.median(windows, axis=1)
    keep = s >= min_sal
    mask[tt[keep], kk[keep]] = True
    sal[tt[keep], kk[keep]] = s[keep]
    return mask, sal


def _stable(mask: np.ndarray) -> np.ndarray:
    """Pour chaque pic, depuis combien de trames une raie reste à la même raie ±1 (longueur totale)."""
    dil = mask.copy()
    dil[:, 1:] |= mask[:, :-1]
    dil[:, :-1] |= mask[:, 1:]
    return np.where(mask, _run_lengths(dil), 0)


def _sliding_median(x: np.ndarray, half: int, step: int = COARSE_STEP, mad: bool = False):
    """Médiane (et MAD) glissante sur ±half, calculée tous les `step` puis répétée (rapide sur 1 h)."""
    n = len(x)
    if n == 0:
        return (np.zeros(0), np.zeros(0)) if mad else np.zeros(0)
    centers = np.arange(0, n, step)
    padded = np.pad(x.astype(np.float32), half, mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(padded, 2 * half + 1)[centers]
    med = np.median(view, axis=1)
    idx = np.minimum(np.arange(n) // step, len(centers) - 1)
    if not mad:
        return med[idx]
    dev = np.median(np.abs(view - med[:, None]), axis=1)
    return med[idx], dev[idx]


def _interval_mask(spans, n: int, pad: float = 0.0) -> np.ndarray:
    mask = np.zeros(n, bool)
    for s, e in spans:
        a = max(0, int(np.floor((s - pad) * FPS)))
        b = min(n, int(np.ceil((e + pad) * FPS)))
        if b > a:
            mask[a:b] = True
    return mask


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    if not len(mask):
        return []
    m = np.concatenate([[False], mask.astype(bool), [False]])
    edges = np.flatnonzero(np.diff(m.astype(np.int8)))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]


def _energy_mean(e_db: np.ndarray) -> float:
    if not len(e_db):
        return FLOOR_DB
    return float(_db(np.mean(10 ** (np.asarray(e_db, np.float64) / 10))))


def _spearman(y: np.ndarray) -> float:
    n = len(y)
    if n < 3:
        return 0.0
    r = np.argsort(np.argsort(y, kind="stable"), kind="stable").astype(np.float64)
    t = np.arange(n, dtype=np.float64)
    r -= r.mean()
    t -= t.mean()
    den = np.sqrt((r * r).sum() * (t * t).sum())
    return float((r * t).sum() / den) if den else 0.0


def _parabolic(row: np.ndarray, k: int) -> float:
    if 0 < k < len(row) - 1:
        a, b, c = row[k - 1], row[k], row[k + 1]
        den = a - 2 * b + c
        if abs(den) > 1e-9:
            return float(k + np.clip(0.5 * (a - c) / den, -0.5, 0.5))
    return float(k)


# ===================================================================== représentations
@dataclass
class Features:
    """Séries par trame de 10 ms (trame i : de i·10 ms à (i+1)·10 ms) et accès au signal brut."""

    E: np.ndarray  # niveau RMS (dBFS)
    D: np.ndarray  # SuperFlux
    Dk: np.ndarray  # SuperFlux des bandes graves (grosse caisse)
    Dn: np.ndarray  # flux des bandes qui montent le plus (sons à bande étroite)
    Ek: np.ndarray  # niveau (dB) sous 110 Hz : sépare une grosse caisse d'une consonne qui démarre
    bands: np.ndarray  # (T, 4) énergies sub / low / mid / high (STFT-A)
    flatness: np.ndarray
    chroma: np.ndarray  # (T, 12)
    lines: np.ndarray  # raies stables ≥ 250 ms entre 100 et 4 000 Hz, par trame
    read: Callable[[float, float], np.ndarray] = field(repr=False)  # (début s, durée s) → signal

    @property
    def n(self) -> int:
        return len(self.E)

    @property
    def duration(self) -> float:
        return self.n / FPS


def _block_features(x: np.ndarray, n_frames: int) -> dict:
    """Descripteurs d'un extrait (avec son recouvrement) : une valeur par trame de 10 ms."""
    rms = x[: n_frames * HOP].astype(np.float64).reshape(n_frames, HOP)
    e = _db(np.mean(rms**2, axis=1)).astype(np.float32)
    pa = _power(x, NFFT_A, n_frames)
    fa = _hz_bins(NFFT_A)
    bands = np.stack([pa[:, (fa >= lo) & (fa < hi)].sum(axis=1) for lo, hi in BANDS.values()], axis=1)
    sel = (fa >= FLAT_RANGE[0]) & (fa < FLAT_RANGE[1])
    ps = pa[:, sel].astype(np.float64) + 1e-12
    flat = (np.exp(np.log(ps).mean(axis=1)) / ps.mean(axis=1)).astype(np.float32)
    mel = _db(pa @ _MEL.T).astype(np.float32)
    lmax = mel.copy()
    lmax[:, 1:] = np.maximum(lmax[:, 1:], mel[:, :-1])
    lmax[:, :-1] = np.maximum(lmax[:, :-1], mel[:, 1:])
    flux = np.zeros_like(mel)
    flux[2:] = np.maximum(0, mel[2:] - lmax[:-2])
    d = flux.mean(axis=1)
    dn = np.sort(flux, axis=1)[:, -NARROW_BANDS:].mean(axis=1)
    kick = _MEL_CENTERS < KICK_HZ
    dk = flux[:, kick].mean(axis=1) if kick.any() else np.zeros(n_frames, np.float32)
    ek = _db(pa[:, (fa >= LOW90_HZ[0]) & (fa < KICK_HZ)].sum(axis=1)).astype(np.float32)
    pb = _power(x, NFFT_B, n_frames)
    chroma = pb @ _CHROMA
    chroma /= chroma.sum(axis=1, keepdims=True) + 1e-12
    mask, _ = _peaks(_db(pb).astype(np.float32), *LINE_RANGE, LINE_SAL_DB)
    stable = _stable(mask)
    fb = _hz_bins(NFFT_B)
    music_band = (fb >= CHROMA_RANGE[0]) & (fb <= CHROMA_RANGE[1])
    lines = (stable[:, music_band] >= TONAL_LINE_FRAMES).sum(axis=1)
    return {"E": e, "D": d.astype(np.float32), "Dk": dk.astype(np.float32), "Dn": dn.astype(np.float32), "Ek": ek,
            "bands": bands.astype(np.float32),
            "flatness": flat, "chroma": chroma.astype(np.float32), "lines": lines.astype(np.int16)}


def stft_features(x: np.ndarray) -> Features:
    """Représentations du §4.1 d'un signal en mémoire (16 kHz mono, float), en blocs de 60 s."""
    x = np.asarray(x, np.float32)

    def read(t0: float, dur: float) -> np.ndarray:
        n = max(0, int(round(dur * SR)))
        out = np.zeros(n, np.float32)
        i0 = int(round(t0 * SR))
        a, b = max(0, i0), min(len(x), i0 + n)
        if b > a:
            out[a - i0 : b - i0] = x[a:b]
        return out

    return _features_from(read, len(x) / SR)


def _features_from(read: Callable[[float, float], np.ndarray], duration: float,
                   on_block: Callable[[float], None] | None = None) -> Features:
    total = int(duration * FPS)
    parts: dict[str, list[np.ndarray]] = {}
    t0 = 0.0
    while t0 * FPS < total:
        keep = min(int(BLOCK_S * FPS), total - int(t0 * FPS))
        x = read(t0 - OVERLAP_S, BLOCK_S + 2 * OVERLAP_S)
        n_all = int(len(x) // HOP)
        feats = _block_features(x, n_all)
        a = int(OVERLAP_S * FPS)
        for k, v in feats.items():
            parts.setdefault(k, []).append(v[a : a + keep])
        t0 += BLOCK_S
        if on_block:
            on_block(min(1.0, t0 / max(duration, 1e-6)))
    if not parts:
        empty = np.zeros(0, np.float32)
        return Features(empty, empty, empty, empty, empty, np.zeros((0, 4), np.float32), empty,
                        np.zeros((0, 12), np.float32), np.zeros(0, np.int16), read)
    cat = {k: np.concatenate(v) for k, v in parts.items()}
    return Features(cat["E"], cat["D"], cat["Dk"], cat["Dn"], cat["Ek"], cat["bands"], cat["flatness"], cat["chroma"],
                    cat["lines"], read)


# ========================================================================== parole
def vad_available() -> bool:
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps  # noqa: F401
    except Exception:  # paquet absent ou cassé : mots Whisper seuls
        return False
    return True


def default_vad(pcm: Path) -> list[tuple[float, float]]:
    """Segments de parole de la VAD Silero livrée avec faster-whisper (hors ligne), par blocs de 10 min."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except Exception:
        return []
    total = pcm_duration(pcm)
    out: list[tuple[float, float]] = []
    t0 = 0.0
    while t0 < total:
        x = read_pcm(pcm, t0, min(VAD_BLOCK_S, total - t0))
        for seg in get_speech_timestamps(x, VadOptions(**VAD_OPTIONS)):
            out.append((t0 + seg["start"] / SR, t0 + seg["end"] / SR))
        t0 += VAD_BLOCK_S
    return out


def speech_mask(n: int, words: list[tuple[float, float]], vad: list[tuple[float, float]] | None = None) -> np.ndarray:
    """Masque de parole : mots Whisper élargis de 50 ms, plus les segments de la VAD."""
    mask = _interval_mask(words, n, SPEECH_PAD)
    if vad:
        mask |= _interval_mask(vad, n)
    return mask


# ===================================================================== événements
def _peaks_over_threshold(d: np.ndarray) -> np.ndarray:
    """Maxima locaux (±3 trames) au-dessus de médiane + 4·MAD + 0,5 sur ±1,5 s."""
    med, mad = _sliding_median(d, ONSET_WIN, mad=True)
    thr = med + ONSET_K * mad + ONSET_OFFSET
    padded = np.pad(d, ONSET_LOCAL, mode="edge")
    local = d >= np.lib.stride_tricks.sliding_window_view(padded, 2 * ONSET_LOCAL + 1).max(axis=1)
    return local & (d > thr)


def _onsets(feats: Features) -> np.ndarray:
    """Attaques : pic du SuperFlux (§4.2), ou pic du flux des bandes qui montent le plus (bip, ding)."""
    d = feats.D
    if len(d) < 3:
        return np.zeros(0, np.int64)
    strength = d / (np.median(d) + 1e-6) + feats.Dn / (np.median(feats.Dn) + 1e-6)
    cand = np.flatnonzero(_peaks_over_threshold(d) | _peaks_over_threshold(feats.Dn))
    out: list[int] = []
    for c in cand:
        if out and c - out[-1] < ONSET_GAP:
            if strength[c] > strength[out[-1]]:
                out[-1] = int(c)
            continue
        out.append(int(c))
    return np.array(out, np.int64)


def _extent(e: np.ndarray, c: int, peak_i: int, pre: float) -> int:
    """Fin de l'événement : E reste 3 trames sous max(pic − 15, pré + 3), 4 s au plus."""
    level = max(float(e[peak_i]) - END_DROP, pre + END_ABOVE_PRE)
    limit = min(len(e), c + int(MAX_EVENT_S * FPS))
    below = 0
    for i in range(peak_i + 1, limit):
        below = below + 1 if e[i] < level else 0
        if below >= END_FRAMES:
            return i - END_FRAMES + 1
    return limit


@dataclass
class _Local:
    """Analyse fine (STFT-B) autour d'un événement, sur le signal relu."""

    db: np.ndarray  # (trames, raies) dB
    power: np.ndarray
    sal: np.ndarray
    peaks: np.ndarray
    stable: np.ndarray
    first: int  # indice global de la première trame
    x: np.ndarray  # signal de l'événement (pour l'écrêtage)


def _local_analysis(feats: Features, c: int, end: int) -> _Local:
    first = max(0, c - PRE[0] - 5)
    last = min(feats.n, end + 5)
    t0 = first / FPS - 0.1  # 100 ms de contexte pour les fenêtres de 64 ms
    x = feats.read(t0, (last - first) / FPS + 0.2)
    n_all = len(x) // HOP
    pb = _power(x, NFFT_B, n_all)
    skip = 10
    pb = pb[skip : skip + (last - first)]
    db = _db(pb).astype(np.float32)
    peaks, sal = _peaks(db, *LINE_RANGE, LINE_SAL_DB)
    xs = feats.read(c / FPS, max(1, end - c) / FPS)
    return _Local(db, pb, sal, peaks, _stable(peaks), first, xs)


def _new_peaks(loc: _Local, frame: int, pre: slice) -> tuple[np.ndarray, np.ndarray]:
    """Pics saillants (≥ 12 dB) de la trame qui ont monté de ≥ 10 dB depuis avant l'attaque : (Hz, dB)."""
    fb = _hz_bins(NFFT_B)
    row = loc.db[frame]
    before = loc.db[pre].mean(axis=0) if pre.stop > pre.start else np.full_like(row, FLOOR_DB)
    mask, _ = _peaks(row[None, :], 80, 6000, NEW_PEAK_SAL)
    new = np.flatnonzero(mask[0] & (row - before >= NEW_PEAK_RISE))
    hz = np.array([_parabolic(row, int(k)) * SR / NFFT_B for k in new])
    return (hz if len(new) else fb[new]), row[new]


def _comb_count(freqs: np.ndarray, ref_hz: float, levels: np.ndarray | None = None, ref_db: float | None = None) -> int:
    """Nombre de pics à k·f0 (k ≤ 12), pour la f0 (80–400 Hz) dont la référence est une harmonique (rang ≤ 12).

    Le rang de la référence n'est pas limité à 2–8 : la raie la plus forte d'une voix est parfois une
    harmonique haute (formants). Seuls les pics nouveaux et proches en niveau comptent, ce qui protège
    un ding posé sur une syllabe (ses harmoniques de voix existaient déjà).

    Avec `levels` et `ref_db`, seuls comptent les pics à moins de COMB_REL_DB de la référence.
    """
    if levels is not None and ref_db is not None and len(freqs):
        freqs = freqs[levels >= ref_db - COMB_REL_DB]
    if ref_hz <= 0 or len(freqs) < 2:
        return int(len(freqs) > 0)
    best = 0
    for f0 in np.arange(*COMB_F0):
        kd = round(ref_hz / f0)
        if not (COMB_DOMINANT_K[0] <= kd <= COMB_DOMINANT_K[1]) or abs(ref_hz - kd * f0) > max(COMB_TOL[0], COMB_TOL[1] * ref_hz):
            continue
        k = np.round(freqs / f0)
        ok = (k >= 1) & (k <= COMB_KMAX) & (np.abs(freqs - k * f0) <= np.maximum(COMB_TOL[0], COMB_TOL[1] * freqs))
        best = max(best, int(ok.sum()))
    return best


def _comb(loc: _Local, frame: int, pre: slice, ref_hz: float) -> int:
    """Peigne harmonique sur les pics nouveaux de la trame du pic. Référence : la raie dominante, ou à
    défaut le pic nouveau le plus fort (une voix y est reconnue : ses harmoniques sont nouvelles)."""
    freqs, levels = _new_peaks(loc, frame, pre)
    if not len(freqs):
        return 0
    if ref_hz > 0:  # hauteur de la raie mesurée sur cette trame (une voix glisse d'une trame à l'autre)
        fb = _hz_bins(NFFT_B)
        k0 = int(np.argmin(np.abs(fb - ref_hz)))
        row = loc.db[frame]
        k = max(1, k0 - 2) + int(np.argmax(row[max(1, k0 - 2) : k0 + 3]))
        ref_hz, ref_db = _parabolic(row, k) * SR / NFFT_B, float(row[k])
    else:
        i = int(np.argmax(levels))
        ref_hz, ref_db = float(freqs[i]), float(levels[i])
    return _comb_count(freqs, ref_hz, levels, ref_db)


def _accept(feats: Features, c: int) -> dict | None:
    """Filtre d'acceptation (§4.2) : montée ≥ 10 dB sur l'avant, ≥ 6 dB au-dessus du contexte de ±1,5 s."""
    e = feats.E
    n = feats.n
    if c - PRE[0] < 0 or c >= n:
        return None
    pre = _energy_mean(e[c - PRE[0] : c - PRE[1]])
    post_slice = e[c : min(n, c + POST)]
    peak_i = c + int(np.argmax(post_slice))
    post = float(post_slice.max())
    ctx = float(np.median(e[max(0, c - ONSET_WIN) : c + ONSET_WIN + 1]))
    if post - pre < ACCEPT_RISE or post - ctx < ACCEPT_CONTEXT:
        return None
    return {"pre": pre, "post": post, "ctx": ctx, "peak_i": peak_i}


def _onset_time(e: np.ndarray, c: int, acc: dict) -> int:
    """Première trame de la montée : E passe la mi-hauteur entre l'avant et le pic, juste avant le pic."""
    thr = acc["pre"] + 0.5 * (acc["post"] - acc["pre"])
    f = acc["peak_i"]
    while f - 1 >= max(0, c - ONSET_BACK) and e[f - 1] >= thr:
        f -= 1
    return f


def event_features(feats: Features, c: int, speech: np.ndarray, voice_db: float, end: int | None = None) -> dict | None:
    """Acceptation puis caractéristiques d'une attaque en trame c (§4.2). `end` : fin imposée (son suivant)."""
    acc = _accept(feats, c)
    if acc is None:
        return None
    e = feats.E
    pre, post, ctx, peak_i = acc["pre"], acc["post"], acc["ctx"], acc["peak_i"]
    rise = post - pre
    natural = _extent(e, c, peak_i, pre)
    end = natural if end is None else max(c + 1, min(end, natural))
    if peak_i >= end:  # le son suivant commence avant le pic : cette attaque n'est que son prélude
        return None
    dur = (end - c) / FPS
    top_i = c + int(np.argmax(e[c:end]))  # plus fort de tout le son (l'attaque, elle, est jugée sur 120 ms)
    span = slice(c, end)
    band = feats.bands[span].sum(axis=0)
    total = float(band.sum()) + 1e-12
    shares = {k: float(band[i] / total) for i, k in enumerate(BAND_KEYS)}
    loc = _local_analysis(feats, c, end)
    rel = lambda i: i - loc.first  # noqa: E731
    fb = _hz_bins(NFFT_B)
    ev_rows = slice(rel(c), rel(end))
    pow_ev = loc.power[ev_rows]
    low90 = float(pow_ev[:, (fb >= LOW90_HZ[0]) & (fb < LOW90_HZ[1])].sum() / (pow_ev[:, fb >= LOW90_HZ[0]].sum() + 1e-12))
    # raie dominante : stable ≥ 120 ms, ≥ 400 Hz, saillante (≥ 15 dB), la plus forte
    ok_line = (loc.stable[ev_rows] >= DOMINANT_MIN_FRAMES) & (fb >= DOMINANT_FMIN)[None, :] & (loc.sal[ev_rows] >= LINE_SAL_DB)
    # la raie doit naître avec l'attaque (dans ses 120 ms) : une raie qui arrive plus tard est un autre son
    head = ok_line[:POST].any(axis=0)
    head = head | np.roll(head, 1) | np.roll(head, -1)
    ok_line &= head[None, :]
    sal_ev = np.where(ok_line, loc.sal[ev_rows], 0)
    power_ev = np.where(ok_line, loc.db[ev_rows], -np.inf)
    line_hz, line_sal, line_share, dev_st, cover = 0.0, 0.0, 0.0, 0.0, 0.0
    pre_rows = slice(max(0, rel(c - PRE[0])), max(0, rel(c - PRE[1])))
    ref_frame = rel(peak_i)
    if ok_line.any():
        r, k = np.unravel_index(int(np.argmax(power_ev)), power_ev.shape)
        line_sal = float(sal_ev[r, k])
        line_hz = _parabolic(loc.db[rel(c) + r], int(k)) * SR / NFFT_B
        frame = ref_frame if loc.peaks[ref_frame, max(0, k - 1) : k + 2].any() else rel(c) + int(r)
        row = loc.power[frame]
        line_share = float(row[max(0, k - 2) : k + 3].sum() / (row[fb >= 80].sum() + 1e-12))
        track = []  # hauteur de la raie le long de l'événement (écart en demi-tons)
        for i in range(rel(c), rel(end)):
            seg = loc.db[i, max(1, k - 2) : k + 3]
            kk = max(1, k - 2) + int(np.argmax(seg))
            if loc.peaks[i, kk]:
                track.append(_parabolic(loc.db[i], kk) * SR / NFFT_B)
        if len(track) >= 2:
            st = 12 * np.log2(np.asarray(track) / np.median(track))
            dev_st = float(np.max(np.abs(st)))
        cover = len(track) / max(1, end - c)
        comb = _comb(loc, frame, pre_rows, line_hz)
    else:  # sans raie : le peigne est cherché au pic et aux tiers du son (une phrase reste une voix)
        frames = sorted({ref_frame, rel(c) + (end - c) // 3, rel(c) + 2 * (end - c) // 3})
        comb = max(_comb(loc, min(fr, len(loc.db) - 1), pre_rows, 0.0) for fr in frames)
    # glissement : fréquence dominante trame par trame (saillance ≥ 15 dB), suivie sans saut d'harmonique
    band_ok = (fb >= 150) & (fb <= 6000)
    rows = loc.db[ev_rows]
    glide_rate, glide_range, glide_frac = 0.0, 0.0, 0.0
    if len(rows):
        k_dom = np.argmax(np.where(band_ok[None, :], rows, -1e9), axis=1)
        sal_dom = loc.sal[ev_rows][np.arange(len(k_dom)), k_dom]
        hz = np.array([_parabolic(rows[i], int(k_dom[i])) * SR / NFFT_B for i in range(len(k_dom))])
        st = 12 * np.log2(np.maximum(hz, 1.0) / 440.0)
        ok = sal_dom >= GLIDE_SAL
        best = (0, 0)
        start = None
        for i in range(len(st) + 1):
            cont = i < len(st) and ok[i] and (start is None or abs(st[i] - st[i - 1]) <= GLIDE_STEP_ST)
            if cont and start is None:
                start = i
            elif not cont and start is not None:
                if i - start > best[1] - best[0]:
                    best = (start, i)
                start = i if i < len(st) and ok[i] else None
        a, b = best
        glide_frac = (b - a) / len(st)
        if b - a >= 3:
            track = st[a:b]
            glide_rate = float(abs(np.polyfit(np.arange(b - a) / FPS, track, 1)[0]))
            glide_range = float(np.percentile(track, 90) - np.percentile(track, 10))
    x = loc.x
    clip = float(np.mean(np.abs(x) >= CLIP_LEVEL)) if len(x) else 0.0
    trend = _spearman(e[span])
    tail = e[max(c, end - FINAL_DROP_FRAMES) : end]
    after = e[end + 1 : end + 4]
    final_drop = float(tail.max() - after.max()) if len(tail) and len(after) else 0.0
    peak_db = float(e[top_i])
    return {
        "c": c, "t": round(_onset_time(e, c, acc) / FPS, 3), "end": end, "dur": round(dur, 3), "rise_db": round(rise, 1),
        "context_db": round(post - ctx, 1), "peak_db": round(peak_db, 1),
        "peak_vs_voice_db": round(peak_db - voice_db, 1), "attack_ms": int((top_i - c) * 1000 / FPS),
        **{k: round(v, 3) for k, v in shares.items()}, "low90": round(low90, 3),
        "flatness": round(float(np.median(feats.flatness[span])), 3),
        "f_line": round(line_hz, 1), "line_sal": round(line_sal, 1), "line_share": round(line_share, 3),
        "line_dev_st": round(dev_st, 2), "line_cover": round(cover, 2), "comb": comb,
        "glide_frac": round(glide_frac, 2),
        "glide_st_s": round(glide_rate, 1), "glide_range_st": round(glide_range, 1),
        "clip_ratio": round(clip, 4), "trend": round(trend, 2), "final_drop_db": round(final_drop, 1),
        "in_speech": round(float(speech[span].mean()) if end > c else 0.0, 2),
    }


def _margin(*terms: tuple[float, float, float]) -> float:
    """Confiance : la plus petite marge (valeur − seuil) / échelle, bornée entre 0 et 1."""
    return round(float(np.clip(min((v - thr) / scale for v, thr, scale in terms), 0.0, 1.0)), 2)


def classify(feat: dict) -> str:
    """Catégorie du §4.3 (première règle satisfaite), ou "" si l'attaque est jetée (syllabe, note, son faible)."""
    return _classify(feat)[0]


def _classify(f: dict) -> tuple[str, float]:
    dur = f["dur"]
    in_speech = f["in_speech"] >= IN_SPEECH
    tone = (f["line_sal"] >= TONE_SAL and f["line_share"] >= TONE_SHARE
            and (f["comb"] < COMB_MAX or (f["line_share"] >= TONE_PURE_SHARE and f["line_dev_st"] <= BIP_DEV_ST))
            and f.get("line_cover", 1.0) >= TONE_COVER and f["line_dev_st"] <= TONE_DEV_ST)
    rules: list[tuple[str, bool, Callable[[], float]]] = [
        ("sature", f["clip_ratio"] > CLIP_RATIO, lambda: _margin((f["clip_ratio"], CLIP_RATIO, 0.05))),
        ("boum", f["rise_db"] >= BOUM_RISE and (f["low90"] >= BOUM_LOW90 or f["sub"] >= BOUM_SUB)
         and f["attack_ms"] <= BOUM_ATTACK_MS and dur >= BOUM_MIN_S,
         lambda: _margin((f["rise_db"], BOUM_RISE, 12), (max(f["low90"] / BOUM_LOW90, f["sub"] / BOUM_SUB), 1, 1),
                         (BOUM_ATTACK_MS - f["attack_ms"], 0, BOUM_ATTACK_MS))),
        ("bip", tone and BIP_F[0] <= f["f_line"] <= BIP_F[1] and f["line_dev_st"] <= BIP_DEV_ST
         and BIP_DUR[0] <= dur <= BIP_DUR[1],
         lambda: _margin((f["line_sal"], TONE_SAL, 20), (f["line_share"], TONE_SHARE, 0.65), (BIP_DEV_ST - f["line_dev_st"], 0, BIP_DEV_ST))),
        ("tonal", tone, lambda: _margin((f["line_sal"], TONE_SAL, 20), (f["line_share"], TONE_SHARE, 0.65), (COMB_MAX - f["comb"], 0, COMB_MAX))),
        ("glissando", f["glide_frac"] >= GLIDE_FRAC and f["comb"] < COMB_MAX and f["glide_range_st"] >= GLIDE_RANGE
         and GLIDE_DUR[0] <= dur <= GLIDE_DUR[1],
         lambda: _margin((f["glide_frac"], GLIDE_FRAC, 0.4), (f["glide_range_st"], GLIDE_RANGE, 8))),
        ("whoosh", f["flatness"] >= WHOOSH_FLAT and (f["high"] >= WHOOSH_HIGH or f["mid"] + f["high"] >= WHOOSH_MIDHIGH)
         and f["attack_ms"] >= WHOOSH_ATTACK_MS and WHOOSH_DUR[0] <= dur <= WHOOSH_DUR[1],
         lambda: _margin((f["flatness"], WHOOSH_FLAT, 0.5), (f["attack_ms"], WHOOSH_ATTACK_MS, 100))),
        ("montee", dur >= RISER_MIN_S and f["trend"] >= RISER_SPEARMAN and f["final_drop_db"] >= RISER_DROP,
         lambda: _margin((f["trend"], RISER_SPEARMAN, 0.2), (f["final_drop_db"], RISER_DROP, 20))),
        ("clic", f["rise_db"] >= CLIC_RISE and f["attack_ms"] <= CLIC_ATTACK_MS and dur <= CLIC_MAX_S,
         lambda: _margin((f["rise_db"], CLIC_RISE, 15), (CLIC_MAX_S - dur, 0, CLIC_MAX_S))),
        ("autre", not in_speech and f["rise_db"] >= AUTRE_RISE, lambda: _margin((f["rise_db"], AUTRE_RISE, 12))),
    ]
    for cat, ok, conf in rules:
        if ok and (not in_speech or cat in IN_SPEECH_OK):
            return cat, conf()
    return "", 0.0


def _risers(feats: Features, speech: np.ndarray, voice_db: float) -> list[dict]:
    """Montées : un son qui enfle régulièrement pendant 1 à 4 s puis s'arrête net (≥ 10 dB en ≤ 100 ms)."""
    e = feats.E.astype(np.float64)
    n = len(e)
    if n < RISER_MIN_S * FPS + 20:
        return []
    k = np.ones(RISER_SMOOTH) / RISER_SMOOTH
    env = np.lib.stride_tricks.sliding_window_view(np.pad(e, (RISER_ENVELOPE - 1, 0), mode="edge"), RISER_ENVELOPE).max(axis=1)
    smooth = np.convolve(env, k, mode="same")
    dip = env - e  # creux sous l'enveloppe
    padded = np.pad(e, (FINAL_DROP_FRAMES, 4), mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(padded, FINAL_DROP_FRAMES)
    before = view[:n].max(axis=1)  # max sur [i−10, i)
    after = np.lib.stride_tricks.sliding_window_view(np.pad(e, (0, 4), mode="edge"), 3)[1 : n + 1].max(axis=1)
    drops = np.flatnonzero(before - after >= RISER_DROP)
    out: list[dict] = []
    last_end = -1
    for i in drops:
        if i <= last_end:
            continue
        best = None
        for length in range(int(RISER_MAX_S * FPS), int(RISER_MIN_S * FPS) - 1, -10):
            a = i - length
            if a < 0:
                continue
            seg = smooth[a:i]
            pos = np.linspace(0, len(seg) - RISER_SMOOTH, RISER_POINTS).astype(int)
            levels = np.array([seg[j : j + RISER_SMOOTH].mean() for j in pos])
            total = float(levels[-1] - levels[0])
            if (total >= RISER_MIN_RISE and _spearman(seg) >= RISER_SPEARMAN
                    and float(np.diff(levels).min()) >= RISER_STEADY * total
                    and float(levels[-1] - levels[len(levels) // 2]) >= RISER_LAST_HALF_DB
                    and float(dip[a + len(seg) // 2 : i].max()) <= RISER_MAX_DIP
                    and int(np.argmax(seg)) >= (1 - RISER_PEAK_TAIL) * len(seg)):
                best = a
                break
        if best is None:
            continue
        end = int(i)
        out.append({
            "c": best, "t": round(best / FPS, 3), "end": end, "dur": round((end - best) / FPS, 3),
            "rise_db": round(float(smooth[end - RISER_SMOOTH : end].mean() - smooth[best : best + RISER_SMOOTH].mean()), 1),
            "peak_db": round(float(e[best:end].max()), 1),
            "peak_vs_voice_db": round(float(e[best:end].max()) - voice_db, 1),
            "trend": round(_spearman(smooth[best:end]), 2), "final_drop_db": round(float(before[i] - after[i]), 1),
            "in_speech": round(float(speech[best:end].mean()), 2), "f_line": 0.0,
        })
        last_end = end + FPS
    return out


def detect_events(feats: Features, speech: np.ndarray, voice_db: float | None = None) -> list[dict]:
    """Sons marquants non vocaux (§4.2–4.3), triés par temps, sans ids. Chaque événement porte « cat »."""
    if voice_db is None:
        voice_db = _voice_level(feats.E, speech)
    risers = _risers(feats, speech, voice_db)
    events: list[dict] = []
    for r in risers:
        conf = _margin((r["trend"], RISER_SPEARMAN, 0.2), (r["final_drop_db"], RISER_DROP, 20))
        events.append({**r, "cat": "montee", "confidence": conf})
    # Attaques acceptées, dans l'ordre. Un son s'arrête au plus tard à l'attaque suivante qui monte encore
    # de 10 dB (sons superposés) ; les attaques plus faibles pendant le son en font partie. Une attaque
    # jetée (syllabe, note : pas de catégorie) ne masque jamais les suivantes.
    accepted: list[tuple[int, dict, int]] = []
    for c in _onsets(feats):
        c = int(c)
        if any(r["c"] <= c < r["end"] for r in risers):
            continue  # attaque à l'intérieur d'une montée
        acc = _accept(feats, c)
        if acc is not None:
            accepted.append((c, acc, _extent(feats.E, c, acc["peak_i"], acc["pre"])))
    i = 0
    while i < len(accepted):
        c, acc, natural = accepted[i]
        end, j = natural, i + 1
        while j < len(accepted) and accepted[j][0] < natural:
            cj, accj, _ = accepted[j]
            level = float(np.max(feats.E[c:cj]))  # niveau du son en cours jusque-là
            if cj - c >= ONSET_GAP and accj["post"] - level >= OVERLAP_RISE:
                end = cj
                break
            j += 1
        feat = event_features(feats, c, speech, voice_db, end=end)
        cat, conf = _classify(feat) if feat else ("", 0.0)
        if cat:
            events.append({**feat, "cat": cat, "confidence": conf})
            i = j  # les attaques faibles pendant ce son en faisaient partie
        else:
            i += 1
    events.sort(key=lambda ev: ev["t"])
    return events


def _voice_level(e: np.ndarray, speech: np.ndarray) -> float:
    if speech.any():
        return float(np.median(e[speech[: len(e)]]))
    return float(np.median(e)) if len(e) else FLOOR_DB


# ======================================================================== musique
def _window_beats(dk: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rythme par fenêtre de 6 s (pas de 1 s) : (valeur du pic d'autocorrélation, décalage en trames)."""
    n = len(dk)
    if n < MUSIC_WIN:
        return np.zeros(0), np.zeros(0)
    starts = np.arange(0, n - MUSIC_WIN + 1, MUSIC_STEP)
    view = np.lib.stride_tricks.sliding_window_view(dk.astype(np.float64), MUSIC_WIN)[starts]
    o = view - view.mean(axis=1, keepdims=True)
    size = 1 << int(np.ceil(np.log2(2 * MUSIC_WIN)))
    f = np.fft.rfft(o, size, axis=1)
    ac = np.fft.irfft(f.real**2 + f.imag**2, size, axis=1)[:, : BEAT_LAGS[1] + 2]
    ac = ac / (ac[:, :1] + 1e-12)
    part = ac[:, BEAT_LAGS[0] : BEAT_LAGS[1] + 1]
    k = np.argmax(part, axis=1)
    beat = part[np.arange(len(k)), k]
    lag = np.array([_parabolic(ac[i], int(k[i]) + BEAT_LAGS[0]) for i in range(len(k))])
    return beat, lag


def _level(e: np.ndarray, speech: np.ndarray, a: int, b: int) -> float | None:
    """Niveau du fond entre a et b : médiane de E sur les trames sans parole (20e centile de tout à défaut)."""
    a, b = max(0, a), min(len(e), b)
    if b <= a:
        return None
    free = ~speech[a:b]
    if free.sum() >= LEVEL_MIN_FRAMES:
        return float(np.median(e[a:b][free]))
    return float(np.percentile(e[a:b], 20))


def _free_level(e: np.ndarray, speech: np.ndarray, a: int, b: int) -> float | None:
    """Comme `_level`, mais seulement sur les trames sans parole (None s'il n'y en a pas assez)."""
    a, b = max(0, a), min(len(e), b)
    free = ~speech[a:b] if b > a else np.zeros(0, bool)
    return float(np.median(e[a:b][free])) if free.sum() >= LEVEL_MIN_FRAMES else None


def _last_free_level(e: np.ndarray, speech: np.ndarray, t: int, direction: int) -> float | None:
    """Niveau des 20 trames sans parole les plus proches de t, d'un côté (−1 : avant t, +1 : après), à
    2,5 s au plus : la musique juste avant sa fin (à plein niveau si elle est coupée, déjà basse en fondu)."""
    a, b = (t - int(FADE_NEAR_MAX_S * FPS), t) if direction < 0 else (t, t + int(FADE_NEAR_MAX_S * FPS))
    a, b = max(0, a), min(len(e), b)
    free = np.flatnonzero(~speech[a:b]) + a if b > a else np.zeros(0, np.int64)
    if len(free) < LEVEL_MIN_FRAMES:
        return None
    near = free[-FADE_NEAR_FRAMES:] if direction < 0 else free[:FADE_NEAR_FRAMES]
    return float(np.median(e[near]))


def _window_states(feats: Features, speech: np.ndarray, beat: np.ndarray, lag: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """État de chaque fenêtre de 6 s : 1 musique, 0 pas de musique, −1 on ne sait pas (parole continue).

    Rythmée : pic d'autocorrélation de la grosse caisse ≥ 0,30 et tempo stable sur les 4 fenêtres d'avant.
    Nappe : raies stables, harmonie qui change et niveau au-dessus du plancher, mesurés hors parole.
    """
    e = feats.E
    nw = len(beat)
    floor = float(np.percentile(e, FLOOR_PCT)) if len(e) else FLOOR_DB
    state = np.zeros(nw, np.int8)
    kinds = [""] * nw
    for w in range(nw):
        a = w * MUSIC_STEP
        b = a + MUSIC_WIN
        hist = lag[max(0, w - LAG_HISTORY) : w]
        steady = len(hist) > 0 and abs(lag[w] - float(np.median(hist))) <= LAG_TOL
        if beat[w] >= BEAT_MIN and steady:
            state[w], kinds[w] = 1, "rythmee"
            continue
        free = ~speech[a:b]
        if free.sum() < TONAL_MIN_FREE:
            state[w] = -1  # parole presque continue : une nappe dessous ne se mesure pas
            continue
        lines = feats.lines[a:b][free]
        chroma = feats.chroma[a:b]
        blocks = [chroma[i : i + CHROMA_BLOCK][free[i : i + CHROMA_BLOCK]] for i in range(0, MUSIC_WIN, CHROMA_BLOCK)]
        means = [blk.mean(axis=0) for blk in blocks if len(blk) >= 10]
        var = max((float(np.abs(x - y).sum()) for x, y in zip(means, means[1:])), default=0.0)
        level = float(np.median(e[a:b][free]))
        if np.mean(lines >= TONAL_LINES) >= TONAL_FRAC and var >= CHROMA_VAR and level >= floor + TONAL_ABOVE_FLOOR:
            state[w], kinds[w] = 1, "nappe"
    return state, kinds


def _window_runs(state: np.ndarray) -> list[tuple[int, int]]:
    """Suites de fenêtres musicales : on entre après 3 positives, on sort après 3 négatives. Les fenêtres
    « on ne sait pas » ne comptent ni pour ni contre, sauf plus de 10 de suite. Bornes : positives extrêmes."""
    out: list[tuple[int, int]] = []
    cur: list[int] | None = None
    pos = neg = unk = 0
    first = 0
    for w, st in enumerate(state):
        if st == 1:
            neg = unk = 0
            if cur is not None:
                cur[1] = w
                continue
            first = w if pos == 0 else first
            pos += 1
            if pos >= ENTER_WINDOWS:
                cur = [first, w]
        elif st == 0:
            neg, unk = neg + 1, 0
            if cur is None:
                pos = 0
            elif neg >= EXIT_WINDOWS:
                out.append((cur[0], cur[1]))
                cur, pos = None, 0
        else:
            unk += 1
            if unk > UNKNOWN_MAX_W:
                if cur is not None:
                    out.append((cur[0], cur[1]))
                cur, pos = None, 0
    if cur is not None:
        out.append((cur[0], cur[1]))
    return out


def _split_runs(e: np.ndarray, speech: np.ndarray, state: np.ndarray, runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Coupe une suite là où une fenêtre « on ne sait pas » montre la musique absente entre deux mots
    (trames 12 dB sous le niveau des fenêtres musicales d'avant)."""
    out: list[tuple[int, int]] = []
    for w0, w1 in runs:
        start, last_pos = w0, w0
        bed = _level(e, speech, w0 * MUSIC_STEP, w0 * MUSIC_STEP + MUSIC_WIN)
        broken = False
        for w in range(w0 + 1, w1 + 1):
            if state[w] == 1:
                if broken:
                    out.append((start, last_pos))
                    start, broken = w, False
                last_pos = w
                bed = _level(e, speech, w * MUSIC_STEP, w * MUSIC_STEP + MUSIC_WIN)
            elif state[w] == -1 and bed is not None and not broken:
                c = w * MUSIC_STEP
                broken = _gone(e, c + UNKNOWN_PROBE[0], c + UNKNOWN_PROBE[1], bed)
        out.append((start, last_pos))
    return out


def _walk_beats(feats: Features, w: int, lag: float, direction: int, limit: int) -> tuple[int, float] | None:
    """Dernier (direction +1) ou premier (−1) temps de grosse caisse, en suivant le tempo depuis la fenêtre w
    (au plus jusqu'à la trame `limit`). Renvoie (trame, baisse en dB des deux derniers temps suivis par
    rapport aux temps de la fenêtre : une grosse caisse qui s'éteint peu à peu, c'est un fondu).

    Le train de temps de la fenêtre donne la phase et le niveau grave des temps ; on avance d'un temps à
    la fois (recalé sur l'attaque trouvée à ±30 ms), jusqu'à deux temps manqués de suite. Une consonne
    qui démarre fait aussi monter le flux grave, mais beaucoup moins haut en niveau : elle est écartée.
    """
    dk, ek = feats.Dk, feats.Ek
    n = len(dk)
    a, b = w * MUSIC_STEP, min(n, w * MUSIC_STEP + MUSIC_WIN)
    if lag <= 0 or b - a < 3 * lag:
        return None
    seg = dk[a:b]
    med = float(np.median(seg))
    thr = med + BEAT_PEAK_K * (float(np.median(np.abs(seg - med))) + 1e-6)
    lo, hi = (a, min(n, limit)) if direction > 0 else (max(0, limit), b)
    # attaques graves : le flux grave dépasse le seuil et le niveau sous 110 Hz bondit (≥ 6 dB en 40 ms)
    floor_before = np.lib.stride_tricks.sliding_window_view(np.pad(ek, (KICK_RISE_FRAMES, 0), mode="edge"),
                                                            KICK_RISE_FRAMES)[:n].min(axis=1)
    level = np.maximum(ek, np.concatenate([ek[1:], ek[-1:]]))
    hit = (dk > thr) & (level - floor_before >= KICK_RISE_DB)
    inside = np.flatnonzero(hit[a:b]) + a
    if len(inside) < 3:
        return None
    # niveau d'un temps : les attaques les plus fortes en grave de la fenêtre (les consonnes restent dessous)
    gate = float(np.percentile(level[inside], KICK_REF_PCT)) - KICK_GATE_DB
    ok = hit & (level >= gate)
    inside = inside[level[inside] >= gate]
    best: tuple[int, np.ndarray] | None = None
    for p0 in inside:  # phase qui aligne le plus d'attaques
        k = (inside - p0) / lag
        on = np.abs(k - np.round(k)) * lag <= BEAT_TOL
        if best is None or int(on.sum()) > best[0]:
            best = (int(on.sum()), inside[on])
    train = best[1]
    if len(train) < 3:
        return None
    last = int(train[-1] if direction > 0 else train[0])
    pos, misses = float(last), 0
    ref = float(np.median(level[train]))
    levels = [float(level[t]) for t in (train if direction > 0 else train[::-1])]
    # à chaque temps attendu : la trame la plus forte (flux grave) parmi les attaques au niveau d'un temps
    while misses < BEAT_MISSES:
        pos += direction * lag
        c = int(round(pos))
        if not lo <= c < hi:
            break
        i0, i1 = max(lo, c - BEAT_TOL), min(hi, c + BEAT_TOL + 1)
        cand = np.flatnonzero(ok[i0:i1])
        if len(cand):
            last = i0 + int(cand[int(np.argmax(dk[i0:i1][cand]))])
            pos, misses = float(last), 0
            levels.append(float(level[last]))
        else:
            misses += 1
    return last, ref - float(np.mean(levels[-2:]))


def _bound(e: np.ndarray, speech: np.ndarray, anchor: int, fallback: int, bed: float, direction: int) -> tuple[int, bool]:
    """Borne d'une musique (direction +1 : fin, −1 : début), à partir d'un instant où elle est sûrement là.

    Trames « présentes » : sans parole, à moins de 6 dB du niveau de la musique. Trames « absentes » : à
    12 dB sous ce niveau, parole ou non (la musique ne peut pas jouer sous le bruit de fond : c'est la
    preuve qu'elle est partie, même entre deux mots). La borne suit la dernière présence après laquelle la
    musique reste absente (≥ 50 ms d'absence en 2 s, sans retour). Si la parole cache la transition, on
    garde la position attendue (`fallback`), bornée par ce qu'on a vu. Renvoie (trame, transition nette).
    La fin est la première trame sans musique ; le début, la première trame avec.
    """
    n = len(e)
    stop = anchor + direction * int(BOUND_SEARCH_S * FPS)
    idx = np.arange(anchor, stop, direction)
    idx = idx[(idx >= 0) & (idx < n)]
    free = idx[~speech[idx]]
    present = free[e[free] >= bed - PRESENT_DB]
    absent = idx[e[idx] <= bed - CUT_DROP]
    hold = int(ABSENT_HOLD_S * FPS)
    for p in [anchor, *present.tolist()]:
        later = (absent - p) * direction
        back = (present - p) * direction
        if np.sum((later > 0) & (later <= hold)) >= ABSENT_MIN and not np.any((back > 0) & (back <= hold)):
            last_seen = p
            break
    else:
        if len(present) and (stop < 0 or stop > n):  # la musique va jusqu'au bord du fichier
            return (0 if direction < 0 else n), False
        return int(np.clip(fallback, 0, n)), False
    later = (absent - last_seen) * direction
    gone = int(absent[later > 0][0])
    between = free[((free - last_seen) * direction > 0) & ((gone - free) * direction > 0)]
    edge = gone if direction > 0 else last_seen
    if abs(gone - last_seen) <= CUT_SPAN:  # transition vue : nette
        return edge, True
    if len(between) >= LEVEL_MIN_FRAMES:  # baisse progressive visible (fondu) : la musique s'éteint à `gone`
        return edge, False
    # transition cachée par la parole : position attendue, entre la dernière présence et la première absence
    lo_b, hi_b = sorted((last_seen, gone + (1 if direction < 0 else 0)))
    return int(np.clip(fallback, lo_b, hi_b)), False


def detect_music(feats: Features, speech: np.ndarray) -> dict:
    """Musique de fond (§4.4) : segments M#, tempo, niveau sous les voix, changements, début et fin."""
    e = feats.E
    n = feats.n
    beat, lag = _window_beats(feats.Dk)
    if not len(beat):
        return {"pct": 0.0, "segments": []}
    state, kinds = _window_states(feats, speech, beat, lag)
    positive = state == 1
    voice_db = _voice_level(e, speech)
    segs: list[dict] = []
    for w0, w1 in _split_runs(e, speech, state, _window_runs(state)):
        a0, b1 = w0 * MUSIC_STEP, min(n, w1 * MUSIC_STEP + MUSIC_WIN)
        # Fenêtres de référence entièrement dans la musique : une fenêtre rythmée est positive dès qu'elle
        # contient quelques temps, donc 5 fenêtres après la première positive (et avant la dernière).
        ws = min(w1, w0 + SEED_SHIFT_W)
        we = max(w0, w1 - SEED_SHIFT_W)
        rhythmic = [w for w in range(w0, w1 + 1) if kinds[w] == "rythmee"]
        bed_start = _level(e, speech, ws * MUSIC_STEP, ws * MUSIC_STEP + MUSIC_WIN) or FLOOR_DB
        bed_end = _level(e, speech, we * MUSIC_STEP, we * MUSIC_STEP + MUSIC_WIN) or FLOOR_DB
        # début : premier temps de la grosse caisse, s'il arrive dès les premières fenêtres ; sinon première
        # preuve de musique (nappe, intro sans batterie)
        seed = next((w for w in rhythmic if w >= ws), rhythmic[-1] if rhythmic else None)
        search = int(BEAT_SEARCH_S * FPS)
        walk = _walk_beats(feats, seed, float(lag[seed]), -1, a0 - search) if seed is not None else None
        fade_in = walk is not None and walk[1] >= FADE_KICK_DB
        if walk is not None and walk[0] <= a0 + MUSIC_WIN:
            start, start_cut = _bound(e, speech, walk[0], walk[0], bed_start, -1)
        else:
            start, start_cut = _bound(e, speech, ws * MUSIC_STEP, max(0, a0 + MUSIC_WIN // 2 - 2 * FPS), bed_start, -1)
        # fin : dernier temps (la musique s'arrête avant le temps suivant), ou dernière preuve de musique
        seed = next((w for w in reversed(rhythmic) if w <= we), rhythmic[0] if rhythmic else None)
        walk = _walk_beats(feats, seed, float(lag[seed]), +1, b1 + search) if seed is not None else None
        fade_out = walk is not None and walk[1] >= FADE_KICK_DB
        if walk is not None and walk[0] >= w1 * MUSIC_STEP:
            end, end_cut = _bound(e, speech, walk[0], int(walk[0] + lag[seed] / 2), bed_end, +1)
        else:
            end, end_cut = _bound(e, speech, we * MUSIC_STEP + MUSIC_WIN, min(n, b1 - MUSIC_WIN // 2 + 2 * FPS), bed_end, +1)
        end = max(end, start + 1)
        if segs and start - segs[-1]["_end"] < MUSIC_MERGE_S * FPS:  # deux morceaux presque collés : un seul
            prev = segs[-1]
            prev.update(_end=end, _end_cut=end_cut, _bed_end=bed_end, _fade_out=fade_out)
            prev["_w"][1] = w1
            continue
        segs.append({"_start": start, "_end": end, "_w": [w0, w1], "_start_cut": start_cut, "_end_cut": end_cut,
                     "_bed_start": bed_start, "_bed_end": bed_end, "_fade_in": fade_in, "_fade_out": fade_out})
    out = []
    for seg in segs:
        a, b = seg["_start"], seg["_end"]
        if (b - a) / FPS < MUSIC_MIN_S:
            continue
        w0, w1 = seg["_w"]
        wins = [w for w in range(w0, w1 + 1) if positive[w]]
        rhythmic = [w for w in wins if kinds[w] == "rythmee"]
        kind = "rythmee" if len(rhythmic) >= max(1, len(wins) // 2) else "nappe"
        bpm = round(6000.0 / float(np.median(lag[rhythmic])), 1) if rhythmic else 0.0
        free = ~speech[a:b]
        level = float(np.percentile(e[a:b][free], 20)) if free.sum() >= 10 else float(np.percentile(e[a:b], 20))
        out.append({
            "id": f"M{len(out) + 1}", "start": round(a / FPS, 2), "end": round(b / FPS, 2), "kind": kind, "bpm": bpm,
            "level_vs_voice_db": round(level - voice_db, 1),
            "start_kind": "progressive" if seg["_fade_in"] else _start_kind(e, speech, a, seg["_bed_start"], seg["_start_cut"]),
            "end_kind": "fondu" if seg["_fade_out"] else _end_kind(e, speech, b, seg["_bed_end"], seg["_end_cut"]),
            "changes": _music_changes(feats, speech, lag, np.array([k == "rythmee" for k in kinds]), a, b),
        })
    total = sum(s["end"] - s["start"] for s in out)
    return {"pct": round(100.0 * total / max(feats.duration, 1e-6), 1), "segments": out}


def _gone(e: np.ndarray, a: int, b: int, level: float) -> bool:
    """La musique est absente entre a et b : au moins 50 ms de trames 12 dB sous son niveau (parole ou non)."""
    a, b = max(0, a), min(len(e), b)
    return b > a and int(np.sum(e[a:b] <= level - CUT_DROP)) >= ABSENT_MIN


def _end_kind(e: np.ndarray, speech: np.ndarray, end: int, bed: float, cut: bool) -> str:
    """« fondu » si le niveau hors parole a baissé de ≥ 6 dB entre [fin − 8 s, fin − 3 s] et [fin − 1,5 s, fin] ;
    « coupure_nette » si la musique, restée à son niveau, a disparu juste après (chute vue en ≤ 0,2 s, ou
    cachée par la parole mais prouvée par les trames qui suivent) ; sinon « normale »."""
    far = _free_level(e, speech, end - int(FADE_FAR[0] * FPS), end - int(FADE_FAR[1] * FPS))
    near = _last_free_level(e, speech, end, -1)
    level = bed if far is None else far
    if near is not None and level - near >= FADE_DROP:
        return "fondu"
    if cut or _gone(e, end, end + int(ABSENT_HOLD_S * FPS), level):
        return "coupure_nette"
    return "normale"


def _start_kind(e: np.ndarray, speech: np.ndarray, start: int, bed: float, cut: bool) -> str:
    """« nette » si la musique arrive d'un coup (à son niveau dès la première seconde et demie, rien juste
    avant), sinon « progressive »."""
    first = _last_free_level(e, speech, start, +1)
    if first is not None and bed - first >= FADE_DROP:
        return "progressive"
    if cut or _gone(e, start - int(ABSENT_HOLD_S * FPS), start, bed):
        return "nette"
    return "progressive"


def _music_changes(feats: Features, speech: np.ndarray, lag: np.ndarray, rhythmic: np.ndarray, a: int, b: int) -> list[dict]:
    """Changements de morceau dans un segment : tempo (entre fenêtres rythmées), harmonie ou niveau du fond,
    tenus ≥ 4 s."""
    side = int(CHANGE_SIDE_S)
    hold = int(CHANGE_HOLD_S)
    first_w = int(np.ceil(a / MUSIC_STEP))
    last_w = min(len(lag) - 1, (b - MUSIC_WIN) // MUSIC_STEP)
    free = ~speech[: feats.n]
    flags: list[tuple[int, str]] = []
    for w in range(first_w + side, last_w - side + 1):
        why = ""
        before = [lag[i] for i in range(w - side, w - 2) if rhythmic[i]]
        after = [lag[i] for i in range(w + 2, w + side) if rhythmic[i]]
        if len(before) >= 2 and len(after) >= 2:
            lb, la = float(np.median(before)), float(np.median(after))
            if abs(la - lb) / lb > CHANGE_TEMPO:
                why = "tempo"
        t = w * MUSIC_STEP + MUSIC_WIN // 2
        lo, hi = t - side * FPS, t + side * FPS
        if not why and lo >= a and hi <= b:
            half = side * FPS // 2
            means = [feats.chroma[i : i + half].mean(axis=0) for i in (lo, lo + half, t, t + half)]
            cross = float(np.abs(means[0] + means[1] - means[2] - means[3]).sum() / 2)
            within = max(float(np.abs(means[0] - means[1]).sum()), float(np.abs(means[2] - means[3]).sum()))
            lb_free, la_free = free[lo:t], free[t:hi]
            if cross > CHANGE_CHROMA and cross > CHANGE_WITHIN * within:
                why = "harmonie"
            elif lb_free.sum() >= FPS and la_free.sum() >= FPS:  # niveau du fond : trames sans parole
                level_b = float(np.median(feats.E[lo:t][lb_free]))
                level_a = float(np.median(feats.E[t:hi][la_free]))
                if abs(level_a - level_b) > CHANGE_LEVEL:
                    why = "niveau"
        if why:
            flags.append((t, why))
    changes: list[dict] = []
    group: list[tuple[int, str]] = []
    for item in flags + [(None, "")]:
        if group and (item[0] is None or item[0] - group[-1][0] > MUSIC_STEP):
            if (group[-1][0] - group[0][0]) / FPS + 1 >= hold:  # critère tenu ≥ 4 s
                mid = group[len(group) // 2]
                changes.append({"t": round(mid[0] / FPS, 1), "why": mid[1]})
            group = []
        if item[0] is not None:
            group.append(item)
    return changes


# ======================================================================= silences
def detect_silences(E: np.ndarray, speech: np.ndarray) -> dict:
    """Silences complets C## (coupure nette ou non) et temps morts (§4.5, sans les pauses de mots)."""
    n = len(E)
    margin = int(SILENCE_MARGIN_S * FPS)
    silences = []
    for a, b in _runs(E < SILENCE_DB):
        if b - a < SILENCE_MIN or a < margin or b > n - margin:
            continue
        before = E[max(0, a - ABRUPT_FRAMES) : a]
        abrupt = bool(len(before) and before.max() >= ABRUPT_FROM_DB and before.max() - E[a] >= ABRUPT_DROP)
        silences.append({"id": f"C{len(silences) + 1:02d}", "t": round(a / FPS, 2), "dur": round((b - a) / FPS, 2),
                         "abrupt": abrupt})
    floor = float(np.percentile(E, FLOOR_PCT)) if n else FLOOR_DB
    dead = [{"t": round(a / FPS, 2), "dur": round((b - a) / FPS, 2)}
            for a, b in _runs((~speech[:n]) & (E < floor + DEAD_AIR_ABOVE_FLOOR)) if b - a >= DEAD_AIR_MIN]
    return {"silences": silences, "dead_air": dead}


def pause_stats(words: list[tuple[float, float]]) -> dict:
    """Écarts entre mots consécutifs (0 < écart ≤ 3 s) : ce que `max_silence` de KrokCut règle."""
    ws = sorted(words)
    gaps = [b[0] - a[1] for a, b in zip(ws, ws[1:]) if 0 < b[0] - a[1] <= PAUSE_MAX_S]
    if not gaps:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "over_0_5s_pct": 0.0, "n": 0}
    g = np.asarray(gaps)
    return {"p50": round(float(np.percentile(g, 50)), 3), "p90": round(float(np.percentile(g, 90)), 3),
            "p95": round(float(np.percentile(g, 95)), 3), "over_0_5s_pct": round(100.0 * float(np.mean(g > 0.5)), 1),
            "n": len(gaps)}


def reaction_tail(words: list[tuple[float, float]], cuts: list[float]) -> dict:
    """« Respiration » : temps laissé entre la fin du dernier mot et la coupe qui suit (≤ 2 s)."""
    ws = sorted(words)
    ends = np.array([e for _, e in ws]) if ws else np.zeros(0)
    starts = np.array([s for s, _ in ws]) if ws else np.zeros(0)
    tails = []
    for c in cuts:
        prior = ends[ends <= c]
        if not len(prior):
            continue
        e = float(prior.max())
        if c - e > TAIL_MAX_S or np.any((starts > e) & (starts <= c)):
            continue
        tails.append(c - e)
    return {"median": round(float(np.median(tails)), 3) if tails else 0.0, "n": len(tails)}


def cuts_in_word(words: list[tuple[float, float]], cuts: list[float]) -> float:
    """Part (%) des coupes entourées de parole où un mot est coupé en plein milieu (le son traverse la coupe)."""
    near = inside = 0
    for c in cuts:
        if not any(s < c + WORD_CUT_WINDOW and e > c - WORD_CUT_WINDOW for s, e in words):
            continue
        near += 1
        if any(s < c - WORD_CUT_MARGIN and e > c + WORD_CUT_MARGIN for s, e in words):
            inside += 1
    return round(100.0 * inside / near, 1) if near else 0.0


# ========================================================================= volume
def measure_loudness(src: Path, out_dir: Path, duration: float, on_progress=None) -> dict:
    """Volume EBU R128 (ffmpeg ebur128) : écrit volume.json et renvoie les métriques du §4.6."""
    out_dir = Path(out_dir)
    txt = out_dir / "r128.txt"
    txt.unlink(missing_ok=True)
    run_ffmpeg(
        ["-i", str(Path(src).resolve()), "-vn", "-map", "0:a:0",
         "-af", "ebur128=peak=true:metadata=1,ametadata=mode=print:file=r128.txt", "-f", "null", "-"],
        duration=duration, on_progress=on_progress, cwd=out_dir,
    )
    text = txt.read_text("utf-8", errors="replace") if txt.exists() else ""
    txt.unlink(missing_ok=True)
    data = parse_r128(text)
    _write_json(out_dir / "volume.json", data)
    return loudness_metrics(data, duration)


def parse_r128(text: str) -> dict:
    m_vals, s_vals, peaks = [], [], []
    integrated, lra = None, None
    for line in text.splitlines():
        if not line.startswith("lavfi.r128."):
            continue
        key, _, value = line[len("lavfi.r128."):].partition("=")
        try:
            v = float(value)
        except ValueError:
            continue
        if key == "M":
            m_vals.append(round(v, 2))
        elif key == "S":
            s_vals.append(round(v, 2))
        elif key == "I":
            integrated = v
        elif key == "LRA":
            lra = v
        elif key == "true_peak":
            peaks.append(v)
    peak = max(peaks) if peaks else 0.0
    return {"I": round(integrated if integrated is not None else -70.0, 2), "LRA": round(lra or 0.0, 2),
            "true_peak_db": round(20 * np.log10(peak), 2) if peak > 0 else -120.0,
            "hop": R128_HOP, "M": m_vals, "S": s_vals}


def loudness_metrics(data: dict, duration: float) -> dict:
    m = np.asarray(data.get("M") or [], np.float64)
    s = np.asarray(data.get("S") or [], np.float64)
    i = float(data.get("I", -70.0))
    spikes = sum(1 for a, b in _runs(m >= i + SPIKE_LU) if (b - a) * R128_HOP >= SPIKE_MIN_S - 1e-9)
    valid = s[s > SHORTTERM_FLOOR]
    spread = float(np.percentile(valid, 95) - np.percentile(valid, 10)) if len(valid) else 0.0
    return {"loudness_i": round(i, 1), "loudness_lra": round(float(data.get("LRA", 0.0)), 1),
            "true_peak_db": round(float(data.get("true_peak_db", -120.0)), 1),
            "loudness_spikes_per_min": round(spikes / max(duration / 60, 0.01), 2),
            "shortterm_p95_p10": round(spread, 1)}


# ===================================================================== analyse complète
def analyze_sound(
    pcm: Path,
    out_dir: Path,
    *,
    duration: float,
    words: list[tuple[float, float]],
    cuts: list[float],
    visual_events: list[dict],
    speech_provider: SpeechProvider | None | object = DEFAULT_VAD,
    library_hits: list[float] | None = None,
    progress: Progress = lambda f, m: None,
) -> dict:
    """Mesure le son (§4) ; écrit son_trames.npz, son_evenements.json, musique.json, silences.json, rythme.json."""
    pcm, out_dir = Path(pcm), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = min(float(duration), pcm_duration(pcm)) if duration else pcm_duration(pcm)
    words = [(float(s), float(e)) for s, e in words]
    progress(0.0, "Analyse du son")
    if speech_provider is DEFAULT_VAD:
        source = "whisper+vad" if vad_available() else "whisper"
        vad = default_vad(pcm) if source == "whisper+vad" else []
    elif speech_provider is None:
        source, vad = "whisper", []
    else:
        source, vad = "whisper+vad", list(speech_provider(pcm))
    progress(0.1, "Analyse du son")
    feats = _features_from(lambda t0, d: read_pcm(pcm, t0, d), duration,
                           on_block=lambda f: progress(0.1 + 0.6 * f, "Analyse du son"))
    speech = speech_mask(feats.n, words, vad)
    voice_db = _voice_level(feats.E, speech)
    progress(0.75, "Bruitages")
    raw_events = detect_events(feats, speech, voice_db)
    progress(0.85, "Musique et silences")
    music = detect_music(feats, speech)
    sil = detect_silences(feats.E, speech)
    pauses = pause_stats(words)
    tail = reaction_tail(words, cuts)
    sorted_cuts = sorted(float(c) for c in cuts)
    visual = [(float(c), f"P{i + 2:03d}") for i, c in enumerate(sorted_cuts)]
    visual += [(float(v["t"]), v["id"]) for v in visual_events if v.get("id", "")[:1] in ("Z", "F")]
    events = []
    for ev in raw_events:
        near = [(abs(t - ev["t"]), vid) for t, vid in visual if abs(t - ev["t"]) <= VISUAL_WINDOW + 1e-9]
        events.append({
            "id": f"S{len(events) + 1:03d}", "t": ev["t"], "dur": ev["dur"], "cat": ev["cat"],
            "label": CATEGORIES[ev["cat"]], "rise_db": ev["rise_db"], "peak_vs_voice_db": ev["peak_vs_voice_db"],
            "f_line": ev.get("f_line", 0.0), "in_speech": bool(ev["in_speech"] >= IN_SPEECH),
            "with_visual": min(near)[1] if near else "",
            "salience": round(ev["rise_db"] + ev["peak_vs_voice_db"], 1), "confidence": ev["confidence"],
        })
    editorial = [e for e in events if e["cat"] in EDITORIAL]
    hits = list(library_hits or [])
    recall = None
    if hits:
        recall = round(sum(1 for h in hits if any(abs(e["t"] - h) <= VISUAL_WINDOW for e in events)) / len(hits), 3)
    np.savez_compressed(out_dir / "son_trames.npz", E=feats.E.astype(np.float16), D=feats.D.astype(np.float16),
                        Dk=feats.Dk.astype(np.float16), flatness=feats.flatness.astype(np.float16), speech=speech)
    _write_json(out_dir / "son_evenements.json", {"version": SOUND_VERSION, "events": events})
    _write_json(out_dir / "musique.json", {"version": SOUND_VERSION, **music})
    _write_json(out_dir / "silences.json", {"version": SOUND_VERSION, **sil, "pauses": pauses, "reaction_tail": tail})
    rhythm = rhythm_windows(duration, sorted_cuts, visual_events, editorial, speech, out_dir / "volume.json")
    _write_json(out_dir / "rythme.json", {"version": SOUND_VERSION, "window": RHYTHM_WIN_S, "windows": rhythm})
    minutes = max(duration / 60, 0.01)
    zooms = [v for v in visual_events if v.get("type") == "zoom"]
    by_cat: dict[str, float] = {}
    for e in editorial:
        by_cat[e["cat"]] = by_cat.get(e["cat"], 0) + 1
    segs = music["segments"]
    metrics = {
        "sound_events_per_min": round(len(editorial) / minutes, 2),
        "sound_by_cat": {k: round(v / minutes, 2) for k, v in sorted(by_cat.items())},
        "sound_level_vs_voice_db": round(statistics.median(e["peak_vs_voice_db"] for e in editorial), 1) if editorial else 0.0,
        "events_with_visual_pct": round(100.0 * sum(1 for e in editorial if e["with_visual"]) / len(editorial), 1) if editorial else 0.0,
        "zooms_with_sound_pct": round(100.0 * sum(1 for z in zooms if any(abs(e["t"] - z["t"]) <= VISUAL_WINDOW for e in editorial)) / len(zooms), 1) if zooms else 0.0,
        "music_pct": music["pct"],
        "music_segments": len(segs),
        "music_bpm_median": round(statistics.median(s["bpm"] for s in segs if s["bpm"]), 1) if any(s["bpm"] for s in segs) else 0.0,
        "music_level_vs_voice_db": round(statistics.median(s["level_vs_voice_db"] for s in segs), 1) if segs else 0.0,
        "music_changes_per_10min": round(10 * sum(len(s["changes"]) for s in segs) / minutes, 2),
        "music_cuts_per_10min": round(10 * sum(1 for s in segs if s["end_kind"] == "coupure_nette") / minutes, 2),
        "silences_per_10min": round(10 * len(sil["silences"]) / minutes, 2),
        "sound_cuts_per_10min": round(10 * sum(1 for s in sil["silences"] if s["abrupt"]) / minutes, 2),
        "dead_air_pct": round(100.0 * sum(d["dur"] for d in sil["dead_air"]) / max(duration, 1e-6), 1),
        "pause_p50": pauses["p50"], "pause_p90": pauses["p90"], "pause_p95": pauses["p95"],
        "pauses_over_0_5s_pct": pauses["over_0_5s_pct"],
        "reaction_tail_median": tail["median"],
        "cuts_in_word_pct": cuts_in_word(words, sorted_cuts),
        "speech_source": source,
        "library_recall": recall,
        "library_recall_n": len(hits),
        "sound_version": SOUND_VERSION,
    }
    progress(1.0, "")
    return metrics


def rhythm_windows(duration: float, cuts: list[float], visual_events: list[dict], sounds: list[dict],
                   speech: np.ndarray, volume_json: Path | None = None) -> list[dict]:
    """Fenêtres de 30 s : coupes, zooms et sons par minute, part de parole, volume M moyen."""
    m_vals = []
    if volume_json and Path(volume_json).exists():
        m_vals = json.loads(Path(volume_json).read_text("utf-8")).get("M") or []
    out = []
    t0 = 0.0
    while t0 < duration - 1e-6:
        t1 = min(duration, t0 + RHYTHM_WIN_S)
        minutes = max((t1 - t0) / 60, 1e-6)
        count = lambda ts: sum(1 for t in ts if t0 <= t < t1)  # noqa: E731
        sp = speech[int(t0 * FPS) : int(t1 * FPS)]
        m = [v for v in m_vals[int(t0 / R128_HOP) : int(t1 / R128_HOP)] if v > SHORTTERM_FLOOR]
        out.append({
            "t0": round(t0, 1),
            "cuts_per_min": round(count(cuts) / minutes, 1),
            "zooms_per_min": round(count(v["t"] for v in visual_events if v.get("type") == "zoom") / minutes, 1),
            "sounds_per_min": round(count(s["t"] for s in sounds) / minutes, 1),
            "speech_share": round(float(sp.mean()) if len(sp) else 0.0, 2),
            "loudness_m": round(float(np.mean(m)), 1) if m else None,
        })
        t0 += RHYTHM_WIN_S
    return out


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)
