"""Retrouve les bruitages (et musiques) de la bibliothèque dans une vidéo déjà montée.

Principe : corrélation croisée normalisée entre la bande-son de la vidéo et chaque son de la
bibliothèque, après un filtre qui aplatit le spectre de la bande-son (la voix ressemble alors
beaucoup moins à un bruitage). Un pic net indique que ce son a été posé à cet endroit, y compris
mixé sous les voix (jusqu'à une douzaine de dB en dessous) ou à un autre volume. Un son modifié
(pitch, effet, filtre) n'est pas retrouvé : les chiffres obtenus sont donc des minimums.

Garde-fous contre les faux positifs (validés sur de la vraie parole et de vrais bruitages) :
- seuil tiré de la queue de distribution des maxima par bloc (statistique des valeurs extrêmes),
  plus strict pour les sons très brefs (clic, pop), qui ressemblent à des syllabes ;
- le son doit être présent sur toute sa durée (pas seulement sur son attaque) ;
- les échos d'un son déjà trouvé et les ressemblances avec la fin d'un autre son sont écartés,
  deux sons réellement superposés sont gardés tous les deux ;
- un son qui « colle » partout est écarté ;
- une musique n'est retenue que si 24 s d'affilée se retrouvent dans la vidéo, ou si un
  extrait ressort très nettement (intro, générique).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .ffmpeg_utils import FFmpegError, run_ffmpeg

DETECT_SR = 8000
MIN_SOUND_S = 0.08  # après découpe des silences
HEAD_EXCERPT_S = 3.0  # sons longs : on cherche leur début (retrouve aussi un son coupé au montage)
MUSIC_EXCERPT_S = 8.0
MUSIC_RUN = 3  # extraits consécutifs alignés (24 s d'affilée) : fiable même 20 dB sous les voix
MUSIC_FLOOR = 0.05  # score minimal sur chacun de ces extraits
MUSIC_LOUD = 0.5  # un seul extrait suffit quand la musique est bien audible (intro, générique)
MAX_MUSIC_EXCERPTS = 30  # 4 premières minutes du morceau
SCORE_FLOOR = 0.15
IMPULSIVE_FLOOR = 0.35
IMPULSIVE_SPAN_S = 0.08
BLOCK_K = 12.0
TAIL_K = 10.0
THRESHOLD_CAP = 0.9
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
    weight: float = field(default=0.0)  # « quantité de son » : départage deux variantes


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
        weight=float(np.sqrt(np.sum(x.astype(np.float64) ** 2))),
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

    def consistent(self, t: np.ndarray, idx: int) -> bool:
        """Le son est-il vraiment là, sur toute sa durée ?

        Si on a vraiment posé ce son, chaque morceau de l'extrait contient au moins sa part
        d'énergie (la voix ou la musique ne font qu'en ajouter). Une ressemblance due au hasard
        (fin d'un autre son, attaque d'un mot) laisse des morceaux presque vides.
        """
        L = len(t)
        w = self.signal[idx : idx + L].astype(np.float64)
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
        threshold = self.threshold(ncc, L, floor)
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
        return t, threshold, sorted((j, float(ncc[j])) for j in taken)

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


def _ncc_at(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) != len(b) or len(a) < 10:
        return 0.0
    a = a.astype(np.float64) - a.mean()
    b = b.astype(np.float64) - b.mean()
    den = np.sqrt(np.sum(a * a) * np.sum(b * b))
    return float(np.sum(a * b) / den) if den > 1e-12 else 0.0


def _variants(a: dict, b: dict, sr: int = DETECT_SR) -> bool:
    """Deux sons trouvés au même endroit sont-ils deux versions du même son (à fusionner) ?"""
    lag = b["idx"] - a["idx"]
    ta, tb = a["template"].x, b["template"].x
    if lag < 0:
        ta, tb, lag = tb, ta, -lag
    m = min(len(ta) - lag, len(tb))
    if m < 0.05 * sr:
        return False
    return _ncc_at(ta[lag : lag + m], tb[:m]) >= 0.5


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
    empty = {"hits": [], "music": [], "skipped": 0, "unreliable": [], "too_short": [], "tested": 0}
    if len(signal) < sr:
        return empty

    music_assets = [a for a in library.of_kind("music") if (a.get("duration") or 0) >= MUSIC_EXCERPT_S * 2]
    jingles = [a for a in library.of_kind("music") if a not in music_assets]  # musiques courtes : cherchées comme un bruitage
    jingle_ids = {a["id"] for a in jingles}
    sfx_assets = library.of_kind("sfx") + jingles
    # Budget de calcul (une FFT par son, une par extrait de musique) : les bruitages d'abord
    budget = max_templates
    skipped = max(0, len(sfx_assets) - budget)
    sfx_assets = sfx_assets[:budget]
    budget -= len(sfx_assets)
    kept_music = []
    for asset in music_assets:
        cost = min(MAX_MUSIC_EXCERPTS, int((asset.get("duration") or 0) // MUSIC_EXCERPT_S))
        if cost <= budget:
            kept_music.append(asset)
            budget -= cost
        else:
            skipped += 1
    music_assets = kept_music
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
            if h["score"] * h["template"].weight > rival["score"] * rival["template"].weight:
                h["gain"] = rival["gain"]
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
        best = 0.0
        run: list[np.ndarray] = []
        for k in range(min(MAX_MUSIC_EXCERPTS, len(track) // L)):
            prepared = detector.prepare(track[k * L : (k + 1) * L])
            if prepared is None:  # passage muet du morceau
                run = []
                continue
            curve = detector.ncc(prepared, prepared)
            i = int(np.argmax(curve))
            if curve[i] >= MUSIC_LOUD and detector.consistent(prepared, i):
                best = max(best, float(curve[i]))
            run = (run + [curve])[-MUSIC_RUN:]
            if len(run) == MUSIC_RUN:
                n = len(run[0]) - (MUSIC_RUN - 1) * L
                if n > 0:
                    aligned = run[0][:n].copy()
                    for r in range(1, MUSIC_RUN):
                        np.minimum(aligned, run[r][r * L : r * L + n], out=aligned)
                    i = int(np.argmax(aligned))
                    if aligned[i] >= MUSIC_FLOOR:
                        best = max(best, float(aligned[i]))
        if best:
            music_best[asset["id"]] = max(music_best.get(asset["id"], 0.0), best)
    music_found = [{"asset": a, "score": round(v, 3)} for a, v in music_best.items()]

    return {
        "hits": hits,
        "music": sorted(music_found, key=lambda m: -m["score"]),
        "skipped": skipped,
        "unreliable": unreliable,
        "too_short": too_short,
        "tested": len(templates) + len(music_assets),
    }
