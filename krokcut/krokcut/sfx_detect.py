"""Retrouve les bruitages (et musiques) de la bibliothèque dans une vidéo déjà montée.

Principe : corrélation croisée normalisée entre la bande-son de la vidéo et chaque son de la
bibliothèque, après un filtre qui aplatit le spectre de la bande-son (la voix ressemble alors
beaucoup moins à un bruitage). Un pic net indique que ce son a été posé à cet endroit, y compris
mixé sous les voix (jusqu'à une douzaine de dB en dessous) ou à un autre volume. Un son modifié
(pitch, effet, filtre) n'est pas retrouvé : les chiffres obtenus sont donc des minimums.

Garde-fous contre les faux positifs (validés sur de la vraie parole et de vrais bruitages) :
- seuil tiré de la queue de distribution des maxima par bloc (statistique des valeurs extrêmes),
  mesurée sans les endroits où le son est vraiment là (un son posé 30 fois ne relève pas son
  propre seuil), plus strict pour les sons très brefs (clic, pop) qui ressemblent à des syllabes ;
- le son doit être présent sur toute sa durée (pas seulement sur son attaque) ;
- les échos d'un son déjà trouvé et les ressemblances avec la fin d'un autre son sont écartés,
  deux sons réellement superposés sont gardés tous les deux, un son tenu répété aussitôt
  (« ding ding ») compte deux fois ;
- un son qui « colle » partout est écarté ;
- une musique n'est retenue que si 24 s d'affilée se retrouvent dans la vidéo (48 s quand le
  calage est faible : un autre morceau au même tempo peut faire illusion), ou si un extrait
  ressort très nettement (intro, générique) ; deux morceaux calés au même endroit passent par la
  même vérification que les bruitages superposés.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .ffmpeg_utils import FFmpegError, run_ffmpeg

DETECT_SR = 8000
SFX_DETECTOR_VERSION = 2  # change quand la détection change : les anciennes mesures sont refaites
MIN_SOUND_S = 0.08  # après découpe des silences
HEAD_EXCERPT_S = 3.0  # sons longs : on cherche leur début (retrouve aussi un son coupé au montage)
MUSIC_EXCERPT_S = 8.0
MUSIC_RUN = 3  # extraits consécutifs alignés (24 s d'affilée) : fiable même 20 dB sous les voix
MUSIC_FLOOR = 0.05  # score minimal sur chacun de ces extraits
MUSIC_LOUD = 0.5  # un seul extrait suffit quand la musique est bien audible (intro, générique)
MAX_MUSIC_EXCERPTS = 30  # 4 premières minutes du morceau
MUSIC_MIN_EXCERPTS = 6  # gardés à chaque musique même avec une énorme bibliothèque de bruitages
MUSIC_SHARPNESS = 1.5  # le bon calage doit dépasser nettement les calages voisins (20 à 250 ms)
MUSIC_SURE = 0.09  # en dessous, un autre morceau au même tempo peut faire illusion...
MUSIC_LONG_RUN = 6  # ... il faut alors 6 extraits alignés d'affilée (48 s), pas seulement 3
REPEAT_MIN_SCORE = 0.5
REPEAT_RATIO = 0.7  # le 2e départ doit être presque aussi net que le 1er
REPEAT_GAP_S = 0.1  # un son tenu répété aussitôt : 2e départ cherché au-delà de cet écart
SCORE_FLOOR = 0.15
IMPULSIVE_FLOOR = 0.35
IMPULSIVE_SPAN_S = 0.08
BLOCK_K = 12.0
TAIL_K = 10.0
THRESHOLD_CAP = 0.9
LOCAL_CONTRAST = 2.0  # pic au moins 2 fois au-dessus de ce qui l'entoure
WHITEN_POWER = 0.5
SIDE_LOBE_RATIO = 0.5
REJECT_RADIUS = 40  # 5 ms
LENGTH_GRID = 200  # 25 ms : les sons de longueur voisine partagent les calculs de normalisation


def load_detect_signal(pcm16k: Path, out: Path) -> np.ndarray:
    """Bande-son de la vidéo à 8 kHz, passée par le même rééchantillonneur (ffmpeg) que les sons."""
    if not out.exists():
        tmp = Path(str(out) + ".part")
        run_ffmpeg(
            ["-f", "s16le", "-ar", "16000", "-ac", "1", "-i", str(pcm16k),
             "-ar", str(DETECT_SR), "-f", "s16le", "-acodec", "pcm_s16le", str(tmp)]
        )
        tmp.replace(out)
    return np.fromfile(out, dtype="<i2").astype(np.float32) / 32768.0


def load_asset_audio(path: Path, cache_dir: Path) -> np.ndarray:
    """Décode un son de la bibliothèque en PCM 8 kHz mono (mis en cache)."""
    stat = path.stat()
    key = hashlib.sha1(f"{path}|{stat.st_size}|{stat.st_mtime}".encode()).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{key}.pcm"
    if not out.exists():
        tmp = Path(str(out) + ".part")
        run_ffmpeg(["-i", str(path), "-vn", "-ac", "1", "-ar", str(DETECT_SR), "-f", "s16le", "-acodec", "pcm_s16le", str(tmp)])
        tmp.replace(out)
    return np.fromfile(out, dtype="<i2").astype(np.float32) / 32768.0


# ----------------------------------------------------------------- sons
@dataclass
class Template:
    asset_id: str
    x: np.ndarray  # extrait cherché (8 kHz)
    head: float  # décalage (s) du début de l'extrait dans le fichier d'origine
    impulsive: bool
    radius: int  # rayon de suppression des non-maxima (échantillons)
    weight: float = field(default=0.0)  # durée utile du son (s) : entre deux variantes, la plus complète


def trim_silence(raw: np.ndarray, sr: int = DETECT_SR, rel_db: float = -55.0, margin_s: float = 0.02) -> tuple[np.ndarray, float] | None:
    """Retire les silences en début et fin de fichier (fréquents à l'export d'un bruitage)."""
    if not len(raw):
        return None
    a = np.abs(raw)
    peak = float(a.max())
    if peak < 1e-4:
        return None
    idx = np.flatnonzero(a > peak * 10 ** (rel_db / 20))
    start = max(0, int(idx[0]) - int(margin_s * sr))
    end = min(len(raw), int(idx[-1]) + int(margin_s * sr) + 1)
    return raw[start:end], start / sr


def energy_span(x: np.ndarray, sr: int = DETECT_SR) -> float:
    """Durée qui contient 90 % de l'énergie du son."""
    e = np.cumsum(x.astype(np.float64) ** 2)
    if e[-1] <= 0:
        return 0.0
    lo, hi = np.searchsorted(e, [0.05 * e[-1], 0.95 * e[-1]])
    return (hi - lo) / sr


def suppression_radius(x: np.ndarray, sr: int = DETECT_SR) -> int:
    """Deux occurrences rapprochées (« boing boing ») restent distinctes si le son n'est pas périodique."""
    L = len(x)
    t = x.astype(np.float64) - x.mean()
    size = 1 << int(np.ceil(np.log2(2 * L)))
    spec = np.fft.rfft(t, size)
    ac = np.fft.irfft(spec * np.conj(spec), size)[:L]
    if ac[0] <= 0:
        return L
    ac = np.abs(ac / ac[0])
    below = np.flatnonzero(ac < 0.5)
    if not len(below):
        return L
    main = int(below[0])
    if float(ac[main:].max(initial=0.0)) >= 0.5:  # son périodique (note tenue) : pics secondaires
        return L
    return int(min(L, max(main, 0.05 * sr)))


def make_template(asset_id: str, raw: np.ndarray, sr: int = DETECT_SR) -> Template | None:
    trimmed = trim_silence(raw, sr)
    if trimmed is None:
        return None
    x, head = trimmed
    x = x[: int(HEAD_EXCERPT_S * sr)]
    if len(x) < MIN_SOUND_S * sr:
        return None
    # Longueur arrondie à la grille (en reprenant la suite du fichier : pas de zéros ajoutés)
    want = int(np.ceil(len(x) / LENGTH_GRID) * LENGTH_GRID)
    start = int(round(head * sr))
    x = raw[start : start + want]
    if len(x) < want:
        x = np.pad(x, (0, want - len(x)))
    return Template(
        asset_id=asset_id,
        x=x.astype(np.float32),
        head=head,
        impulsive=energy_span(x, sr) < IMPULSIVE_SPAN_S,
        radius=suppression_radius(x, sr),
        weight=energy_span(trimmed[0], sr),
    )


# ------------------------------------------------------------ corrélation
WHITEN_TAPS = 129
WHITEN_RANGE_DB = 30.0


def whitening_filter(signal: np.ndarray, sr: int = DETECT_SR, taps: int = WHITEN_TAPS) -> np.ndarray | None:
    """Filtre qui aplatit le spectre moyen de la bande-son (surtout la voix).

    Appliqué à la fois à la bande-son et aux sons cherchés, il ne change rien à un son posé tel
    quel, mais la voix ressemble beaucoup moins à un bruitage : moins de fausses alertes, et des
    bruitages retrouvés plus bas sous les voix.
    """
    nper = 256
    nf = len(signal) // nper
    if nf < 32:
        return None
    frames = signal[: nf * nper].reshape(nf, nper).astype(np.float64)
    frames = frames - frames.mean(axis=1, keepdims=True)
    psd = (np.abs(np.fft.rfft(frames * np.hanning(nper), axis=1)) ** 2).mean(axis=0)
    if psd.max() <= 0:
        return None
    psd = np.convolve(psd, np.ones(5) / 5, mode="same")
    psd = np.maximum(psd, psd.max() * 10 ** (-WHITEN_RANGE_DB / 10))
    gain = psd ** -WHITEN_POWER
    gain[0] = 0.0  # pas de continu
    h = np.fft.irfft(gain, nper)
    h = np.roll(h, nper // 2)[nper // 2 - taps // 2 : nper // 2 + taps // 2 + 1] * np.hanning(taps)
    return (h / np.sqrt(np.sum(h * h))).astype(np.float32)


def apply_filter(x: np.ndarray, h: np.ndarray | None) -> np.ndarray:
    if h is None or len(x) < len(h):
        return x.astype(np.float32)
    if len(x) < 1 << 16:
        return np.convolve(x, h, mode="same").astype(np.float32)
    size = 1 << int(np.ceil(np.log2(len(x) + len(h))))
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(h, size), size)
    return y[len(h) // 2 : len(h) // 2 + len(x)].astype(np.float32)


class Detector:
    """Prépare la bande-son une fois, puis compare chaque son en une FFT."""

    def __init__(
        self,
        signal: np.ndarray,
        sr: int = DETECT_SR,
        max_template_s: float = max(HEAD_EXCERPT_S, MUSIC_EXCERPT_S) + 0.1,
        whiten: bool | np.ndarray | None = True,
    ):
        self.sr = sr
        if whiten is True:
            self.fir = whitening_filter(signal, sr)
        elif whiten is False or whiten is None:
            self.fir = None
        else:
            self.fir = whiten
        raw = signal.astype(np.float32)
        self.signal = apply_filter(raw, self.fir)
        raw_rms = float(np.sqrt(np.mean(raw.astype(np.float64) ** 2))) if len(raw) else 0.0
        white_rms = float(np.sqrt(np.mean(self.signal.astype(np.float64) ** 2))) if len(raw) else 0.0
        level = white_rms / raw_rms if raw_rms > 0 else 1.0
        self.n = len(signal)
        self.nfft = 1 << int(np.ceil(np.log2(self.n + int(max_template_s * sr) + 1)))
        self.spectrum = np.fft.rfft(self.signal, self.nfft)  # simple précision : 2 à 3 fois plus rapide
        x64 = self.signal.astype(np.float64)
        self.cumsum = np.concatenate([[0.0], np.cumsum(x64)])
        self.cumsum2 = np.concatenate([[0.0], np.cumsum(x64 * x64)])
        self.floor = 1e-4 * level  # en dessous (quasi-silence), aucune comparaison n'a de sens
        self._denom: tuple[int, np.ndarray] | None = None

    def _denominator(self, L: int) -> np.ndarray:
        if self._denom and self._denom[0] == L:
            return self._denom[1]
        win_sum = self.cumsum[L:] - self.cumsum[:-L]
        var = (self.cumsum2[L:] - self.cumsum2[:-L]) - win_sum * win_sum / L  # en double précision
        np.maximum(var, 0.0, out=var)
        denom = np.sqrt(var).astype(np.float32)
        denom[var < (self.floor**2) * L] = np.inf  # silence : score nul
        self._denom = (L, denom)
        return denom

    def prepare(self, template: np.ndarray) -> np.ndarray | None:
        """Son passé par le même filtre que la bande-son, centré."""
        L = len(template)
        if L < MIN_SOUND_S * self.sr or L >= self.n:
            return None
        t = apply_filter(template, self.fir).astype(np.float64)
        t -= t.mean()
        if float(np.sqrt(np.sum(t * t))) < 1e-6:
            return None
        return t.astype(np.float32)

    def ncc(self, template: np.ndarray, prepared: np.ndarray | None = None) -> np.ndarray | None:
        t = prepared if prepared is not None else self.prepare(template)
        if t is None:
            return None
        L = len(t)
        t_norm = float(np.sqrt(np.sum(t.astype(np.float64) ** 2)))
        corr = np.fft.irfft(self.spectrum * np.conj(np.fft.rfft(t, self.nfft)), self.nfft)[: self.n - L + 1]
        return corr / (np.float32(t_norm) * self._denominator(L))

    @staticmethod
    def threshold(ncc: np.ndarray, L: int, floor: float, k: float = TAIL_K) -> float:
        """Seuil tiré de la queue de distribution des maxima par bloc (valeurs extrêmes).

        Au-delà du 90e centile, les maxima décroissent à peu près exponentiellement : on mesure
        cette pente sur la vidéo elle-même et on se place assez loin pour qu'une coïncidence
        (voix qui ressemble au son) soit très improbable, même sur 400 sons et une heure de vidéo.
        """
        block = max(1, min(L, len(ncc) // 16))
        nb = len(ncc) // block
        bm = np.sort(ncc[: nb * block].reshape(nb, block).max(axis=1))
        med = float(np.median(bm))
        mad = float(np.median(np.abs(bm - med))) * 1.4826
        q90 = float(bm[int(0.9 * (nb - 1))])
        excess = bm[bm > q90] - q90
        if len(excess) < 8:  # trop peu de blocs pour mesurer la queue
            thr = max(med + BLOCK_K * mad, q90 + k * mad)
        else:
            thr = q90 + k * float(np.median(excess)) / np.log(2)
        # Plafond : une vidéo très chargée en sons (ou presque silencieuse) gonfle la queue ;
        # au-delà de ce score, la vérification sur toute la durée suffit à écarter le hasard.
        return max(floor, min(thr, THRESHOLD_CAP))

    @staticmethod
    def mad_threshold(ncc: np.ndarray, L: int, floor: float, k: float = BLOCK_K) -> float:
        """Seuil = médiane + k × MAD des maxima par bloc (musiques : queue peu fournie)."""
        block = max(1, min(L, len(ncc) // 16))
        nb = len(ncc) // block
        bm = ncc[: nb * block].reshape(nb, block).max(axis=1)
        med = float(np.median(bm))
        mad = float(np.median(np.abs(bm - med))) * 1.4826
        return max(floor, med + k * mad)

    @staticmethod
    def peaks(ncc: np.ndarray, threshold: float, radius: int, max_hits: int) -> list[tuple[int, float]]:
        """Maxima au-dessus du seuil, espacés d'au moins `radius` (sans autre vérification)."""
        candidates = np.flatnonzero(ncc >= threshold)
        if not len(candidates):
            return []
        order = candidates[np.argsort(-ncc[candidates], kind="stable")]
        taken: list[int] = []
        for idx in order:
            if all(abs(int(idx) - j) >= radius for j in taken):
                taken.append(int(idx))
                if len(taken) >= max_hits:
                    break
        return sorted((j, float(ncc[j])) for j in taken)

    def noise_threshold(self, ncc: np.ndarray, t: np.ndarray, floor: float, max_hits: int) -> float:
        """Seuil mesuré sur la bande-son sans les endroits où le son est vraiment là.

        Un son utilisé 30 fois remplirait sinon lui-même la queue de distribution, et son seuil
        monterait au-dessus de ses propres occurrences.
        """
        L = len(t)
        masked = None
        for idx, score in Detector.peaks(ncc, floor, L, max_hits):
            # Une vraie occurrence est un pic isolé ; un son qui ressemble au fond (bourdonnement)
            # donne un plateau : on ne le retire pas, sinon il fausserait lui-même son seuil.
            around = np.concatenate([ncc[max(0, idx - 4 * L) : max(0, idx - L)], ncc[idx + L : idx + 5 * L]])
            if len(around) and score < LOCAL_CONTRAST * float(np.percentile(np.abs(around), 90)):
                continue
            if self.consistent(t, idx):
                if masked is None:
                    masked = ncc.copy()
                    fill = float(np.median(ncc[:: max(1, len(ncc) // 100000)]))
                masked[max(0, idx - L) : idx + L] = fill
        return self.threshold(ncc if masked is None else masked, L, floor)

    def consistent(self, t: np.ndarray, idx: int) -> bool:
        """Le son est-il vraiment là, sur toute sa durée ?

        Si on a vraiment posé ce son, chaque morceau de l'extrait contient au moins sa part
        d'énergie (la voix ou la musique ne font qu'en ajouter). Une ressemblance due au hasard
        (fin d'un autre son, attaque d'un mot) laisse des morceaux presque vides.
        """
        return self.consistent_window(t, self.signal[idx : idx + len(t)])

    @staticmethod
    def consistent_window(t: np.ndarray, window: np.ndarray) -> bool:
        L = len(t)
        w = np.asarray(window, dtype=np.float64).copy()
        if len(w) < L:
            return False
        w -= w.mean()
        t = t.astype(np.float64)
        tt = float(np.dot(t, t))
        g = float(np.dot(w, t)) / tt if tt > 0 else 0.0
        if g <= 0:
            return False
        ns = int(np.clip(L // 400, 4, 60))
        seg = L // ns
        et = (t[: ns * seg].reshape(ns, seg) ** 2).sum(axis=1)
        ew = (w[: ns * seg].reshape(ns, seg) ** 2).sum(axis=1)
        missing = ew < 0.1 * g * g * et
        return float(et[missing].sum()) <= 0.25 * float(et.sum())

    def search(
        self, template: np.ndarray, floor: float = SCORE_FLOOR, radius: int | None = None, max_hits: int = 200
    ) -> tuple[np.ndarray | None, float, list[tuple[int, float]]]:
        """Son préparé, seuil, et positions (échantillons) + scores où il apparaît, garde-fous compris."""
        t = self.prepare(template)
        if t is None:
            return None, 1.0, []
        ncc = self.ncc(template, t)
        L = len(t)
        threshold = self.noise_threshold(ncc, t, floor, max_hits)
        candidates = np.flatnonzero(ncc >= threshold)
        if not len(candidates):
            return t, threshold, []
        radius = radius or L
        order = candidates[np.argsort(-ncc[candidates], kind="stable")]
        taken: list[int] = []
        rejected: list[int] = []
        checks = 0
        for idx in order:
            idx = int(idx)
            score = float(ncc[idx])
            if any(abs(idx - j) < radius for j in taken):
                continue
            if any(abs(idx - j) < L and score < SIDE_LOBE_RATIO * float(ncc[j]) for j in taken):
                continue  # écho d'un son déjà trouvé (pic secondaire de corrélation)
            if any(abs(idx - j) < REJECT_RADIUS for j in rejected):
                continue
            checks += 1
            if checks > 4 * max_hits + 50:
                break
            if not self.consistent(t, idx):
                rejected.append(idx)
                continue
            taken.append(idx)
            if len(taken) > max_hits:
                break
        hits = [(j, float(ncc[j])) for j in taken]
        if radius > REPEAT_GAP_S * self.sr and hits and len(hits) <= max_hits:  # son tenu : « ding ding »
            hits += self.repeats(t, hits, threshold, radius)
        return t, threshold, sorted(hits)

    def _local_ncc(self, segment: np.ndarray, t: np.ndarray) -> np.ndarray:
        L, n = len(t), len(segment)
        if n < L:
            return np.zeros(0)
        size = 1 << int(np.ceil(np.log2(n + L)))
        corr = np.fft.irfft(np.fft.rfft(segment, size) * np.conj(np.fft.rfft(t, size)), size)[: n - L + 1]
        c1 = np.concatenate([[0.0], np.cumsum(segment)])
        c2 = np.concatenate([[0.0], np.cumsum(segment * segment)])
        win = c1[L:] - c1[:-L]
        var = np.maximum((c2[L:] - c2[:-L]) - win * win / L, 0.0)
        den = np.sqrt(var * float(np.dot(t, t)))
        return np.where(var > (self.floor**2) * L, corr / np.maximum(den, 1e-12), 0.0)

    def repeats(self, t: np.ndarray, hits: list[tuple[int, float]], threshold: float, radius: int) -> list[tuple[int, float]]:
        """Un son tenu (note, gong) répété aussitôt : une fois le premier retiré, le second ressort."""
        L = len(t)
        t64 = t.astype(np.float64)
        tt = float(np.dot(t64, t64))
        gap = int(REPEAT_GAP_S * self.sr)
        found: list[tuple[int, float]] = []
        for idx, score in hits:
            if score < REPEAT_MIN_SCORE:  # sous les voix, un son faible ne laisse pas voir un 2e départ fiable
                continue
            a, b = max(0, idx - radius), min(self.n, idx + radius + L)
            seg = self.signal[a:b].astype(np.float64)
            w = seg[idx - a : idx - a + L]
            seg[idx - a : idx - a + L] -= (float(np.dot(w - w.mean(), t64)) / tt) * t64
            local = self._local_ncc(seg, t64)
            if not len(local):
                continue
            pos = np.arange(len(local)) + a
            local[np.abs(pos - idx) < gap] = 0.0
            local[np.abs(pos - idx) >= radius] = 0.0
            for k, _ in hits:  # pas sur une autre occurrence déjà trouvée
                if k != idx and abs(k - idx) < 2 * radius + L:
                    local[max(0, k - radius - a) : max(0, k + radius - a)] = 0.0
            j = int(np.argmax(local))
            if local[j] >= max(threshold, REPEAT_RATIO * score) and self.consistent_window(t, seg[j : j + L]):
                if all(abs(a + j - k) >= gap for k, _ in found):
                    found.append((a + j, float(local[j])))
        return found

    def residual_score(self, t: np.ndarray, idx: int, others: list[tuple[int, np.ndarray, float]]) -> tuple[float, float]:
        """Score et gain du son à `idx` une fois retirés les sons déjà trouvés qui le chevauchent."""
        L = len(t)
        w = self.signal[idx : idx + L].astype(np.float64)
        for k_idx, k_t, k_gain in others:
            off = k_idx - idx
            a0, a1 = max(0, off), min(L, off + len(k_t))
            if a1 > a0:
                w[a0:a1] -= k_gain * k_t[a0 - off : a1 - off]
        w -= w.mean()
        t = t.astype(np.float64)
        tt, ww = float(np.dot(t, t)), float(np.dot(w, w))
        if tt <= 0 or ww <= 0:
            return 0.0, 0.0
        dot = float(np.dot(w, t))
        return dot / np.sqrt(tt * ww), dot / tt

    def find(self, template: np.ndarray, floor: float = SCORE_FLOOR, radius: int | None = None, max_hits: int = 200) -> list[tuple[float, float]]:
        """Liste (instant en s, score 0..1) des endroits où le son apparaît."""
        return [(i / self.sr, s) for i, s in self.search(template, floor, radius, max_hits)[2]]


def sharp_peak(curve: np.ndarray, i: int, sr: int = DETECT_SR) -> bool:
    """Le bon calage d'une musique ressort des calages voisins (20 à 250 ms autour).

    Une musique seulement ressemblante (nappes, accords tenus) donne plutôt un plateau.
    """
    near, far = int(0.02 * sr), int(0.25 * sr)
    sides = np.concatenate([curve[max(0, i - far) : max(0, i - near)], curve[i + near : i + far]])
    return not len(sides) or float(curve[i]) >= MUSIC_SHARPNESS * float(sides.max())


def _aligned_run(detector: "Detector", track: np.ndarray, first: int, idx: int, L: int, limit: int = MUSIC_LONG_RUN) -> int:
    """Nombre d'extraits qui se suivent dans le morceau ET dans la vidéo, au même calage."""
    count = MUSIC_RUN
    for step in (1, -1):
        r = MUSIC_RUN if step == 1 else 1
        while count < limit:
            k, pos = (first + r, idx + r * L) if step == 1 else (first - r, idx - r * L)
            if k < 0 or (k + 1) * L > len(track) or pos < 0 or pos + L > detector.n:
                break
            prepared = detector.prepare(track[k * L : (k + 1) * L])
            if prepared is None or detector.residual_score(prepared, pos, [])[0] < MUSIC_FLOOR:
                break
            count += 1
            r += 1
    return count


def _ncc_at(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) != len(b) or len(a) < 10:
        return 0.0
    a = a.astype(np.float64) - a.mean()
    b = b.astype(np.float64) - b.mean()
    den = np.sqrt(np.sum(a * a) * np.sum(b * b))
    return float(np.sum(a * b) / den) if den > 1e-12 else 0.0


def _variants(a: dict, b: dict, sr: int = DETECT_SR) -> bool:
    """Deux sons trouvés au même endroit sont-ils deux versions du même fichier (à fusionner) ?

    Oui seulement s'ils se superposent sur presque toute leur énergie (même son, avec un peu plus ou
    moins de silence ou de queue) : un son bref qui ressemble au début d'un son long n'en est pas un.
    """
    lag = b["idx"] - a["idx"]
    ta, tb = a["template"].x, b["template"].x
    if lag < 0:
        ta, tb, lag = tb, ta, -lag
    m = min(len(ta) - lag, len(tb))
    if m < 0.05 * sr:
        return False
    ea, eb = ta.astype(np.float64) ** 2, tb.astype(np.float64) ** 2
    covered_a = float(ea[lag : lag + m].sum()) / max(float(ea.sum()), 1e-12)
    covered_b = float(eb[:m].sum()) / max(float(eb.sum()), 1e-12)
    return covered_a >= 0.95 and covered_b >= 0.95 and _ncc_at(ta[lag : lag + m], tb[:m]) >= 0.9


def _better_variant(h: dict, rival: dict) -> bool:
    """Entre deux variantes : la plus complète (durée utile), à égalité la mieux reconnue."""
    wh, wr = h["template"].weight, rival["template"].weight
    if abs(wh - wr) > 0.1 * max(wh, wr):
        return wh > wr
    return h["score"] > rival["score"]


def detect_library_sounds(
    signal: np.ndarray,
    library,
    cache_dir: Path,
    on_progress=None,
    max_templates: int = 400,
) -> dict:
    """Cherche tous les bruitages et musiques de la bibliothèque dans une bande-son à 8 kHz."""
    sr = DETECT_SR
    duration_min = max(len(signal) / sr / 60, 0.01)
    empty = {"hits": [], "music": [], "skipped": 0, "skipped_music": [], "unreliable": [], "too_short": [], "tested": 0}
    if len(signal) < sr:
        return empty

    long_enough = MUSIC_EXCERPT_S * MUSIC_RUN  # 24 s : de quoi retrouver 3 extraits d'affilée
    music_assets = [a for a in library.of_kind("music") if (a.get("duration") or 0) >= long_enough]
    jingles = [a for a in library.of_kind("music") if a not in music_assets]  # musiques courtes : cherchées comme un bruitage
    jingle_ids = {a["id"] for a in jingles}
    sfx_assets = library.of_kind("sfx") + jingles
    # Budget de calcul (une FFT par son, une par extrait de musique) : chaque musique garde ses
    # premiers extraits, les bruitages prennent le reste, et ce qui reste prolonge les musiques.
    full = {a["id"]: min(MAX_MUSIC_EXCERPTS, int((a.get("duration") or 0) // MUSIC_EXCERPT_S)) for a in music_assets}
    allot: dict[str, int] = {}
    reserve = max_templates // 4
    for a in music_assets:
        need = min(full[a["id"]], MUSIC_MIN_EXCERPTS)
        if need <= reserve:
            allot[a["id"]] = need
            reserve -= need
    skipped_music = [a["name"] for a in music_assets if a["id"] not in allot]
    budget = max_templates - sum(allot.values())
    skipped = max(0, len(sfx_assets) - budget)
    sfx_assets = sfx_assets[:budget]
    budget -= len(sfx_assets)
    for a in music_assets:
        if a["id"] in allot:
            more = min(full[a["id"]] - allot[a["id"]], budget)
            allot[a["id"]] += more
            budget -= more
    music_assets = [a for a in music_assets if a["id"] in allot]
    total = len(sfx_assets) + len(music_assets)

    # Bruitages : les sons de longueur voisine partagent le calcul de normalisation
    templates: list[Template] = []
    too_short: list[str] = []
    for asset in sfx_assets:
        try:
            raw = load_asset_audio(library.path_of(asset), cache_dir)
        except (FFmpegError, OSError):
            continue
        tpl = make_template(asset["id"], raw, sr)
        if tpl is None:
            too_short.append(asset["id"])
        else:
            templates.append(tpl)
    templates.sort(key=lambda t: len(t.x))

    detector = Detector(signal, sr)
    limit = int(8 * duration_min + 3)  # au-delà, le son « colle » partout : pas fiable
    raw_hits: list[dict] = []
    unreliable: list[str] = []
    for i, tpl in enumerate(templates):
        if on_progress:
            on_progress(i / max(1, total), tpl.asset_id)
        floor = IMPULSIVE_FLOOR if tpl.impulsive else SCORE_FLOOR
        prepared, thr, found = detector.search(tpl.x, floor, tpl.radius, limit + 1)
        if len(found) > limit:
            unreliable.append(tpl.asset_id)
            continue
        raw_hits += [{"idx": idx, "score": score, "template": tpl, "t": prepared, "thr": thr} for idx, score in found]

    # Sons qui se chevauchent, du plus net au moins net :
    # - deux variantes du même son (deux fichiers presque identiques) -> une seule ;
    # - sinon, on retire le son le plus net et on regarde si l'autre est encore là
    #   (deux sons superposés -> les deux ; simple ressemblance avec la fin d'un autre son -> écarté).
    raw_hits.sort(key=lambda h: -h["score"])
    kept: list[dict] = []
    for h in raw_hits:
        end = h["idx"] + len(h["t"])
        overlapping = [k for k in kept if k["idx"] < end and h["idx"] < k["idx"] + len(k["t"])]
        rival = next((k for k in overlapping if k["template"].asset_id != h["template"].asset_id and _variants(k, h, sr)), None)
        if rival is not None:
            if _better_variant(h, rival):
                others = [(k["idx"], k["t"], k["gain"]) for k in overlapping if k is not rival]
                h["gain"] = detector.residual_score(h["t"], h["idx"], others)[1]  # son propre gain, pas celui du rival
                kept[kept.index(rival)] = h
            continue
        score, gain = detector.residual_score(h["t"], h["idx"], [(k["idx"], k["t"], k["gain"]) for k in overlapping])
        if overlapping and score < h["thr"]:
            continue
        h["gain"] = gain
        kept.append(h)
    hits = [
        {
            "t": round(h["idx"] / sr, 2),  # début audible du son dans la vidéo
            "start": round(h["idx"] / sr - h["template"].head, 2),  # début du fichier son
            "asset": h["template"].asset_id,
            "score": round(h["score"], 3),
        }
        for h in sorted(kept, key=lambda h: (h["idx"], h["template"].asset_id))
        if h["template"].asset_id not in jingle_ids
    ]
    music_best: dict[str, float] = {}
    for h in kept:
        if h["template"].asset_id in jingle_ids:
            music_best[h["template"].asset_id] = max(music_best.get(h["template"].asset_id, 0.0), h["score"])

    # Musiques : le morceau est découpé en extraits de 8 s. Il est reconnu si 3 extraits qui se
    # suivent se retrouvent à la suite dans la vidéo (même sous les voix), ou si un extrait
    # ressort très nettement (musique seule : intro, générique).
    L = int(MUSIC_EXCERPT_S * sr)
    candidates: list[dict] = []  # meilleur calage de chaque morceau : score, extraits et positions
    for j, asset in enumerate(music_assets):
        if on_progress:
            on_progress((len(templates) + j) / max(1, total), asset["name"])
        try:
            trimmed = trim_silence(load_asset_audio(library.path_of(asset), cache_dir), sr)
        except (FFmpegError, OSError):
            continue
        if trimmed is None:
            continue
        track = trimmed[0]
        best: dict | None = None
        run: list[tuple[np.ndarray, np.ndarray]] = []
        for k in range(min(allot[asset["id"]], len(track) // L)):
            prepared = detector.prepare(track[k * L : (k + 1) * L])
            if prepared is None:  # passage muet du morceau
                run = []
                continue
            curve = detector.ncc(prepared, prepared)
            i = int(np.argmax(curve))
            if curve[i] >= MUSIC_LOUD and detector.consistent(prepared, i) and (not best or curve[i] > best["score"]):
                best = {"asset": asset["id"], "score": float(curve[i]), "floor": MUSIC_LOUD, "parts": [(i, prepared)]}
            run = (run + [(curve, prepared)])[-MUSIC_RUN:]
            if len(run) == MUSIC_RUN:
                n = len(run[0][0]) - (MUSIC_RUN - 1) * L
                if n > 0:
                    aligned = run[0][0][:n].copy()
                    for r in range(1, MUSIC_RUN):
                        np.minimum(aligned, run[r][0][r * L : r * L + n], out=aligned)
                    for i, score in Detector.peaks(aligned, MUSIC_FLOOR, int(0.25 * sr), 5):
                        if (best and score <= best["score"]) or not sharp_peak(aligned, i, sr):
                            continue
                        first = k - MUSIC_RUN + 1  # extrait du morceau calé en i
                        if score < MUSIC_SURE and _aligned_run(detector, track, first, i, L) < MUSIC_LONG_RUN:
                            continue  # calage faible et court : peut-être un autre morceau au même tempo
                        parts = [(i + r * L, run[r][1]) for r in range(MUSIC_RUN)]
                        best = {"asset": asset["id"], "score": float(score), "floor": MUSIC_FLOOR, "parts": parts}
        if best:
            candidates.append(best)
    # Deux morceaux trouvés au même endroit (même boucle de batterie, intro d'un autre morceau…) :
    # on retire le plus net et on regarde si l'autre est encore là, comme pour les bruitages.
    accepted: list[tuple[int, np.ndarray, float]] = []
    for cand in sorted(candidates, key=lambda c: -c["score"]):
        scores, gains = [], []
        for idx, prepared in cand["parts"]:
            others = [(k, t, g) for k, t, g in accepted if k < idx + L and idx < k + len(t)]
            score, gain = detector.residual_score(prepared, idx, others)
            scores.append(score)
            gains.append(gain)
        if min(scores) >= cand["floor"] or not any(k < idx + L and idx < k + len(t) for idx, _ in cand["parts"] for k, t, _ in accepted):
            accepted += [(idx, prepared, g) for (idx, prepared), g in zip(cand["parts"], gains)]
            music_best[cand["asset"]] = max(music_best.get(cand["asset"], 0.0), cand["score"])
    music_found = [{"asset": a, "score": round(v, 3)} for a, v in music_best.items()]

    return {
        "hits": hits,
        "music": sorted(music_found, key=lambda m: -m["score"]),
        "skipped": skipped,
        "skipped_music": skipped_music,
        "unreliable": unreliable,
        "too_short": too_short,
        "tested": len(templates) + len(music_assets),
        "detector": SFX_DETECTOR_VERSION,
    }
