"""Analyse audio : synchronisation des deux POV, niveaux, mixage pour la transcription."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 16000  # fréquence d'analyse
HOP = 0.1  # pas des courbes de niveau (secondes)
ENV_HOP = 0.01  # pas de l'enveloppe utilisée pour la synchro


# ---------------------------------------------------------------------------- PCM
def pcm_duration(path: str | Path, sr: int = SR) -> float:
    return Path(path).stat().st_size / 2 / sr


def read_pcm(path: str | Path, start: float, duration: float, sr: int = SR) -> np.ndarray:
    """Lit `duration` secondes à partir de `start` (complète par du silence hors fichier)."""
    n = max(0, int(round(duration * sr)))
    out = np.zeros(n, dtype=np.float32)
    if n == 0:
        return out
    data = np.memmap(path, dtype="<i2", mode="r")
    i0 = int(round(start * sr))
    src0, src1 = max(0, i0), min(len(data), i0 + n)
    if src1 > src0:
        out[src0 - i0 : src1 - i0] = data[src0:src1].astype(np.float32) / 32768.0
    del data
    return out


# --------------------------------------------------------------------------- synchro
@dataclass
class SyncResult:
    lag: float  # t_B = t_A + lag (au début des fichiers)
    drift: float = 0.0  # variation du lag par seconde de A
    confidence: float = 0.0
    double_peak: bool = False
    measurements: list[dict] = field(default_factory=list)
    warning: str = ""


def onset_envelope(x: np.ndarray, sr: int = SR, hop: float = ENV_HOP) -> np.ndarray:
    """Enveloppe d'attaques : robuste aux différences de micro, de codec (Discord) et de volume."""
    size = int(sr * hop)
    n = len(x) // size
    if n < 2:
        return np.zeros(0, dtype=np.float32)
    frames = x[: n * size].reshape(n, size)
    energy = np.log10(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-9)
    onset = np.diff(energy, prepend=energy[0])
    onset = np.maximum(onset, 0.0)
    std = onset.std()
    if std < 1e-9:
        return np.zeros(n, dtype=np.float32)
    return ((onset - onset.mean()) / std).astype(np.float32)


def _xcorr(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """c[k] = somme a[n]·b[n+k] pour tous les décalages k (en échantillons d'enveloppe)."""
    size = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    fa = np.fft.rfft(a, size)
    fb = np.fft.rfft(b, size)
    full = np.fft.irfft(np.conj(fa) * fb, size)
    # décalages positifs puis négatifs
    corr = np.concatenate([full[-(len(a) - 1) :], full[: len(b)]])
    lags = np.arange(-(len(a) - 1), len(b))
    return lags, corr


def _pick_peak(lags, corr, min_overlap, len_a, len_b, hop):
    overlap = np.minimum(len_a, len_b - lags) - np.maximum(0, -lags)
    valid = overlap >= min_overlap
    if not valid.any():
        return None
    score = np.where(valid, corr / np.maximum(overlap, 1), -np.inf)
    k = int(np.argmax(score))
    best = score[k]
    finite = score[np.isfinite(score)]
    z = float((best - finite.mean()) / (finite.std() + 1e-12))

    # Sous-échantillonnage par interpolation parabolique
    frac = 0.0
    if 0 < k < len(score) - 1 and np.isfinite(score[k - 1]) and np.isfinite(score[k + 1]):
        y0, y1, y2 = score[k - 1], score[k], score[k + 1]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            frac = float(np.clip(0.5 * (y0 - y2) / denom, -0.5, 0.5))

    # Double pic typique d'un appel Discord : chaque voix revient avec la latence réseau
    window = int(0.6 / hop)
    lo, hi = max(0, k - window), min(len(score), k + window + 1)
    local = score[lo:hi].copy()
    local[max(0, k - lo - 4) : k - lo + 5] = -np.inf
    double = False
    second_lag = None
    if np.isfinite(local).any():
        j = int(np.argmax(local))
        if local[j] >= 0.6 * best and best > 0:
            double = True
            second_lag = lags[lo + j]
    lag_frames = lags[k] + frac
    if double and second_lag is not None:
        lag_frames = (lag_frames + second_lag) / 2.0
    return lag_frames * hop, z, double


def estimate_lag(
    a: np.ndarray, b: np.ndarray, *, sr: int = SR, min_overlap_s: float = 60.0
) -> tuple[float, float, bool] | None:
    """Décalage (s) tel qu'un son à l'instant t dans `a` soit à t + lag dans `b`."""
    ea, eb = onset_envelope(a, sr), onset_envelope(b, sr)
    if len(ea) < 10 or len(eb) < 10:
        return None
    lags, corr = _xcorr(ea, eb)
    min_overlap = int(min(min_overlap_s / ENV_HOP, 0.5 * min(len(ea), len(eb))))
    return _pick_peak(lags, corr, min_overlap, len(ea), len(eb), ENV_HOP)


def synchronize(pcm_a: str | Path, pcm_b: str | Path, *, search_minutes: float = 30.0) -> SyncResult:
    dur_a, dur_b = pcm_duration(pcm_a), pcm_duration(pcm_b)
    window = min(search_minutes * 60, dur_a, dur_b)
    a = read_pcm(pcm_a, 0, window)
    b = read_pcm(pcm_b, 0, window)
    first = estimate_lag(a, b, min_overlap_s=min(120.0, window / 3))
    if first is None:
        return SyncResult(lag=0.0, warning="Audio trop court pour synchroniser.")
    lag0, z0, double = first
    measures = [{"t_a": 0.0, "lag": lag0, "z": z0}]

    # Vérifie la dérive plus loin dans l'enregistrement
    overlap_start = max(0.0, -lag0)
    overlap_end = min(dur_a, dur_b - lag0)
    for frac in (0.5, 0.9):
        t_a = overlap_start + frac * (overlap_end - overlap_start) - 150
        if t_a <= overlap_start + 300 or t_a + 300 > overlap_end:
            continue
        seg_a = read_pcm(pcm_a, t_a, 300)
        margin = 3.0
        seg_b = read_pcm(pcm_b, t_a + lag0 - margin, 300 + 2 * margin)
        res = estimate_lag(seg_a, seg_b, min_overlap_s=200)
        if res is None:
            continue
        local_lag, z, _ = res
        measured = lag0 - margin + local_lag
        if z > 6 and abs(measured - lag0) < margin * 0.9:
            measures.append({"t_a": t_a + 150, "lag": measured, "z": z})

    drift = 0.0
    if len(measures) >= 2:
        t = np.array([m["t_a"] for m in measures])
        lags = np.array([m["lag"] for m in measures])
        drift, intercept = np.polyfit(t, lags, 1)
        lag0 = float(intercept)
        if abs(drift) < 2e-6:  # < 30 ms sur 4 h : on néglige
            drift = 0.0
            lag0 = float(np.mean(lags))

    warning = ""
    if z0 < 8:
        warning = (
            "Synchro peu fiable (signal commun faible). Vérifie le résultat ou saisis "
            "le décalage à la main dans le projet."
        )
    return SyncResult(
        lag=float(lag0),
        drift=float(drift),
        confidence=float(z0),
        double_peak=bool(double),
        measurements=measures,
        warning=warning,
    )


def sources_offsets(lag: float, drift: float = 0.0) -> dict[str, tuple[float, float]]:
    """Convertit le lag en (offset, rate) pour chaque source sur la timeline maître.

    t_B = lag + (1 + drift)·t_A  et  t_src = (t_master - offset)·rate.
    """
    rate_b = 1.0 + drift
    off_a = 0.0
    off_b = off_a - lag / rate_b
    shift = min(off_a, off_b)
    return {"A": (off_a - shift, 1.0), "B": (off_b - shift, rate_b)}


# ---------------------------------------------------------------------- niveaux
def level_curve(pcm: str | Path, hop: float = HOP, sr: int = SR, block_s: float = 600.0) -> np.ndarray:
    """Niveau RMS (dBFS) par fenêtre de `hop` secondes sur tout le fichier."""
    total = pcm_duration(pcm, sr)
    size = int(sr * hop)
    out = []
    t = 0.0
    while t < total:
        x = read_pcm(pcm, t, min(block_s, total - t), sr)
        n = len(x) // size
        if n:
            frames = x[: n * size].reshape(n, size)
            out.append(10 * np.log10(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-10))
        t += block_s
    return np.concatenate(out).astype(np.float32) if out else np.zeros(0, np.float32)


def to_master_curve(curve: np.ndarray, offset: float, rate: float, master_frames: int, hop: float = HOP) -> np.ndarray:
    t_master = np.arange(master_frames) * hop
    idx = np.round((t_master - offset) * rate / hop).astype(np.int64)
    out = np.full(master_frames, -100.0, dtype=np.float32)
    ok = (idx >= 0) & (idx < len(curve))
    out[ok] = curve[idx[ok]]
    return out


@dataclass
class Levels:
    """Courbes de niveau des deux POV sur la timeline maître."""

    a: np.ndarray
    b: np.ndarray
    hop: float = HOP
    floor_a: float = -60.0
    floor_b: float = -60.0
    loud_a: float = -20.0
    loud_b: float = -20.0

    @classmethod
    def compute_thresholds(cls, a: np.ndarray, b: np.ndarray, hop: float = HOP) -> "Levels":
        def stats(x):
            valid = x[x > -99]
            if len(valid) < 10:
                return -60.0, -20.0
            return float(np.percentile(valid, 15)), float(np.percentile(valid, 97))

        fa, la = stats(a)
        fb, lb = stats(b)
        return cls(a=a, b=b, hop=hop, floor_a=fa, floor_b=fb, loud_a=la, loud_b=lb)

    def save(self, path: Path) -> None:
        np.savez_compressed(
            path,
            a=self.a,
            b=self.b,
            meta=np.array([self.hop, self.floor_a, self.floor_b, self.loud_a, self.loud_b]),
        )

    @classmethod
    def load(cls, path: Path) -> "Levels":
        data = np.load(path)
        hop, fa, fb, la, lb = data["meta"].tolist()
        return cls(a=data["a"], b=data["b"], hop=hop, floor_a=fa, floor_b=fb, loud_a=la, loud_b=lb)

    def _slice(self, t0: float, t1: float) -> slice:
        i0 = max(0, int(t0 / self.hop))
        i1 = max(i0 + 1, int(np.ceil(t1 / self.hop)))
        return slice(i0, min(i1, len(self.a)))

    def mean_db(self, key: str, t0: float, t1: float) -> float:
        curve = self.a if key == "A" else self.b
        part = curve[self._slice(t0, t1)]
        if not len(part):
            return -100.0
        # moyenne en énergie, pas en dB
        return float(10 * np.log10(np.mean(10 ** (part.astype(np.float64) / 10)) + 1e-10))

    def is_quiet(self, t0: float, t1: float, margin_db: float = 8.0) -> bool:
        """Vrai si aucun des deux micros ne capte d'activité nette entre t0 et t1."""
        s = self._slice(t0, t1)
        a, b = self.a[s], self.b[s]
        if not len(a):
            return True
        return bool(
            (a.max() < self.floor_a + margin_db + 6) and (b.max() < self.floor_b + margin_db + 6)
        )

    def loud_mask(self) -> np.ndarray:
        return (self.a >= self.loud_a) | (self.b >= self.loud_b)

    def active_mask(self, margin_db: float = 12.0) -> np.ndarray:
        return (self.a >= self.floor_a + margin_db) | (self.b >= self.floor_b + margin_db)


# ------------------------------------------------------------------------ mixage
def write_master_mix(
    pcm_a: Path,
    pcm_b: Path,
    offsets: dict[str, tuple[float, float]],
    master_duration: float,
    dst: Path,
    *,
    block_s: float = 60.0,
    on_progress=None,
) -> None:
    """Mixe les deux POV, recalés, en un seul PCM sur la timeline maître."""
    tmp = Path(str(dst) + ".part")
    with open(tmp, "wb") as fh:
        t = 0.0
        while t < master_duration:
            dur = min(block_s, master_duration - t)
            mix = np.zeros(int(round(dur * SR)), dtype=np.float32)
            for pcm, key in ((pcm_a, "A"), (pcm_b, "B")):
                offset, rate = offsets[key]
                start = (t - offset) * rate
                x = read_pcm(pcm, start, dur * rate + 0.01)
                if abs(rate - 1.0) > 1e-7 and len(x) > 1:
                    pos = np.linspace(0, len(x) - 1, len(mix))
                    x = np.interp(pos, np.arange(len(x)), x).astype(np.float32)
                mix += x[: len(mix)] if len(x) >= len(mix) else np.pad(x, (0, len(mix) - len(x)))
            np.clip(mix, -1.0, 1.0, out=mix)
            fh.write((mix * 32767).astype("<i2").tobytes())
            t += block_s
            if on_progress:
                on_progress(min(1.0, t / master_duration))
    tmp.replace(dst)
