"""Retrouve les bruitages (et musiques) de la bibliothèque dans une vidéo déjà montée.

Principe : corrélation croisée normalisée entre la bande-son de la vidéo et chaque son
de la bibliothèque. Un pic net indique que ce son a été posé à cet endroit, même s'il est
mixé sous les voix ou à un autre volume. Un son modifié (pitch, effet) ne sera pas retrouvé.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from .ffmpeg_utils import FFmpegError, run_ffmpeg

DETECT_SR = 8000
MIN_TEMPLATE_S = 0.25
MAX_TEMPLATE_S = 8.0
MUSIC_EXCERPT_S = 4.0


def to_detect_rate(x16k: np.ndarray) -> np.ndarray:
    """16 kHz -> 8 kHz (moyenne de deux échantillons : passe-bas grossier suffisant ici)."""
    n = len(x16k) // 2
    return ((x16k[0 : 2 * n : 2] + x16k[1 : 2 * n : 2]) * 0.5).astype(np.float32)


def load_asset_audio(path: Path, cache_dir: Path, start: float = 0.0, duration: float | None = None) -> np.ndarray:
    """Décode un son de la bibliothèque en PCM 8 kHz mono (mis en cache)."""
    stat = path.stat()
    key = hashlib.sha1(f"{path}|{stat.st_size}|{stat.st_mtime}|{start}|{duration}".encode()).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{key}.pcm"
    if not out.exists():
        args = ["-ss", f"{start:.3f}"] if start else []
        args += ["-i", str(path)]
        if duration:
            args += ["-t", f"{duration:.3f}"]
        args += ["-vn", "-ac", "1", "-ar", str(DETECT_SR), "-f", "s16le", "-acodec", "pcm_s16le", str(out) + ".part"]
        run_ffmpeg(args)
        Path(str(out) + ".part").replace(out)
    return np.fromfile(out, dtype="<i2").astype(np.float32) / 32768.0


class Detector:
    """Prépare la bande-son une fois, puis cherche chaque son en une FFT."""

    def __init__(self, signal: np.ndarray, sr: int = DETECT_SR, max_template_s: float = MAX_TEMPLATE_S):
        self.sr = sr
        self.n = len(signal)
        self.nfft = 1 << int(np.ceil(np.log2(self.n + int(max_template_s * sr) + 1)))
        x = signal.astype(np.float32)  # FFT en simple précision : 2 à 3 fois plus rapide, assez précis ici
        self.spectrum = np.fft.rfft(x, self.nfft)
        x64 = x.astype(np.float64)
        self.cumsum = np.concatenate([[0.0], np.cumsum(x64)])
        self.cumsum2 = np.concatenate([[0.0], np.cumsum(x64 * x64)])
        self.floor = 1e-4  # en dessous (quasi-silence), aucune comparaison n'a de sens

    def find(self, template: np.ndarray, min_score: float = 0.3, min_z: float = 10.0, max_hits: int = 200) -> list[tuple[float, float]]:
        """Liste (instant en s, score 0..1) des endroits où le son apparaît."""
        L = len(template)
        if L < MIN_TEMPLATE_S * self.sr or L >= self.n:
            return []
        t = (template.astype(np.float64) - float(np.mean(template))).astype(np.float32)
        t_norm = float(np.sqrt(np.sum(t.astype(np.float64) ** 2)))
        if t_norm < 1e-6:
            return []
        corr = np.fft.irfft(self.spectrum * np.conj(np.fft.rfft(t, self.nfft)), self.nfft)[: self.n - L + 1]
        win_sum = self.cumsum[L:] - self.cumsum[:-L]
        win_sq = self.cumsum2[L:] - self.cumsum2[:-L]
        var = np.maximum(win_sq - win_sum * win_sum / L, 0.0)
        quiet = var < (self.floor**2) * L
        ncc = corr / (t_norm * np.sqrt(var) + 1e-12)
        ncc[quiet] = 0.0

        # Seuil relatif au « bruit de fond » de la corrélation : écarte les sons trop génériques
        sample = ncc[:: max(1, len(ncc) // 200_000)]
        med = float(np.median(sample))
        mad = float(np.median(np.abs(sample - med))) * 1.4826 + 1e-9
        threshold = max(min_score, med + min_z * mad)
        candidates = np.flatnonzero(ncc >= threshold)
        if not len(candidates):
            return []
        order = candidates[np.argsort(-ncc[candidates])]
        taken: list[int] = []
        for idx in order:
            if all(abs(idx - j) >= L for j in taken):
                taken.append(int(idx))
                if len(taken) > max_hits:
                    break
        return sorted((j / self.sr, float(ncc[j])) for j in taken)


def detect_library_sounds(
    signal16k: np.ndarray,
    library,
    cache_dir: Path,
    on_progress=None,
    max_templates: int = 400,
) -> dict:
    """Cherche tous les bruitages et musiques de la bibliothèque dans une bande-son 16 kHz."""
    signal = to_detect_rate(signal16k)
    duration_min = max(len(signal) / DETECT_SR / 60, 0.01)
    sfx = [a for a in library.of_kind("sfx") if MIN_TEMPLATE_S <= (a.get("duration") or 0) <= MAX_TEMPLATE_S]
    music = [a for a in library.of_kind("music") if (a.get("duration") or 0) >= MUSIC_EXCERPT_S * 2]
    skipped = max(0, len(sfx) - max_templates)
    sfx = sfx[:max_templates]
    jobs = [(a, 0.0, None) for a in sfx]
    for a in music:  # trois extraits par musique : on ne sait pas où elle commence dans la vidéo
        for frac in (0.15, 0.45, 0.75):
            jobs.append((a, round(a["duration"] * frac, 2), MUSIC_EXCERPT_S))
    if not jobs or len(signal) < DETECT_SR:
        return {"hits": [], "music": [], "skipped": skipped, "unreliable": []}

    detector = Detector(signal)
    hits: list[dict] = []
    music_found: dict[str, float] = {}
    unreliable: list[str] = []
    for i, (asset, start, length) in enumerate(jobs):
        if on_progress:
            on_progress(i / len(jobs), asset["name"])
        try:
            template = load_asset_audio(library.path_of(asset), cache_dir, start, length)
        except (FFmpegError, OSError):
            continue
        if asset["kind"] == "music":
            found = detector.find(template, min_score=0.08, min_z=12.0, max_hits=50)
            if found:
                music_found[asset["id"]] = max(music_found.get(asset["id"], 0.0), max(s for _, s in found))
            continue
        found = detector.find(template)
        if len(found) > 8 * duration_min + 3:  # un son qui « colle » partout n'est pas fiable
            unreliable.append(asset["id"])
            continue
        hits += [{"t": round(t, 2), "asset": asset["id"], "score": round(s, 3)} for t, s in found]
    hits.sort(key=lambda h: h["t"])
    # Deux sons qui se ressemblent peuvent matcher au même endroit : on garde le meilleur
    merged: list[dict] = []
    for h in hits:
        if merged and abs(h["t"] - merged[-1]["t"]) < 0.15:
            if h["score"] > merged[-1]["score"]:
                merged[-1] = h
            continue
        merged.append(h)
    return {
        "hits": merged,
        "music": sorted(({"asset": k, "score": round(v, 3)} for k, v in music_found.items()), key=lambda m: -m["score"]),
        "skipped": skipped,
        "unreliable": unreliable,
    }
