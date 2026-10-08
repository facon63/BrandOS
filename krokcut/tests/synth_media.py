"""Médias synthétiques à vérité connue pour tester les mesures de l'onglet « Comparer ».

Vidéo : un faux montage de 50 s fait de sources lavfi (testsrc2, mandelbrot, mires…) avec des
coupes, un jump cut, des zooms secs, un flash, une image insérée, un figé, un fondu au noir, un
passage en noir et blanc, des bandes cinéma et des pièges (zoom continu, défilement rapide, jeu de la
vie). Son : voix synthétique (syllabes à formants), moteur, musique rythmée, nappe, bruitages.
Tout est généré localement par ffmpeg et numpy, sans aucun téléchargement.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args], check=True)


def _codec_args(codec: str) -> list[str]:
    if codec == "libvpx-vp9":
        return ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-deadline", "realtime", "-cpu-used", "8",
                "-row-mt", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", codec, "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p"]


# ------------------------------------------------------------------------- vidéo
def _between(a: float, b: float, fps: float) -> str:
    """Images dont l'instant est dans [a, b[ (décalage d'une demi-image : pas d'erreur d'arrondi)."""
    h = 0.5 / fps
    return f"between(t,{a - h:.6f},{b - h:.6f})"


def _punch(label_in: str, label_out: str, w: int, h: int, fps: float, t0: float, t1: float,
           scale: float, cx: float = 0.5, cy: float = 0.5) -> str:
    """Zoom sec : de t0 à t1, l'image est recadrée ×scale autour de (cx, cy) (temps continu)."""
    return (
        f"[{label_in}]split[{label_out}_a][{label_out}_b];"
        f"[{label_out}_b]crop=iw/{scale}:ih/{scale}:x=iw*{cx}-ow/2:y=ih*{cy}-oh/2,scale={w}:{h},setsar=1[{label_out}_z];"
        f"[{label_out}_a][{label_out}_z]overlay=enable='{_between(t0, t1, fps)}'[{label_out}]"
    )


def _moving_box(label_in: str, label_out: str, w: int, h: int, fps: float, color: str = "white") -> str:
    """Boîte qui traverse l'image : une mire fixe devient une image qui bouge (sinon ce serait un figé)."""
    bw, bh = w // 8, h // 4
    return (
        f"color=c={color}:s={bw}x{bh}:r={fps}[{label_out}_box];"
        f"[{label_in}][{label_out}_box]overlay=x='mod(t*{w * 0.6:.1f},{w - bw})':y={h // 3}:shortest=1[{label_out}]"
    )


def edit_video(tmp: Path, size: tuple[int, int] = (640, 360), fps: int = 30, codec: str = "libx264",
               *, audio: bool = True, name: str | None = None) -> tuple[Path, dict]:
    """Faux montage de 50 s et sa vérité terrain (instants dans le temps de la vidéo)."""
    w, h = size
    src = f"s={w}x{h}:r={fps}"
    msrc = f"s={w // 2}x{h // 2}:r={fps}"  # mandelbrot est lent : calculé en demi-taille puis agrandi
    up = f"scale={w}:{h}"
    fr = 1.0 / 30  # durées des transitoires exprimées en images de l'instrument (30 i/s)
    g = []
    # 0–8 : testsrc2, zoom sec ×1,25 au centre de 4,0 à 5,0
    g.append(f"testsrc2={src}:d=8[a0]")
    g.append(_punch("a0", "A", w, h, fps, 4.0, 5.0, 1.25))
    # 8–16 : mandelbrot (zoom continu : piège), flash blanc de 2 images à 12,0
    g.append(f"mandelbrot={msrc}:end_pts=800,{up},trim=duration=8,setpts=PTS-STARTPTS[b0]")
    g.append(f"color=c=white:{src}:d=8[bw]")
    g.append(f"[b0][bw]overlay=enable='{_between(4.0, 4.0 + 2 * fr, fps)}'[B]")
    # 16–24 : testsrc2 retourné, 2 images noires à 18,0, saut de 7 s dans la source à 20,0 (jump cut), puis 1 s figée
    bw, bh = w // 4, h // 3  # un « personnage » qui traverse le décor : le saut de 7 s le déplace d'un coup
    g.append(f"testsrc2={src}:d=15,hflip[c00];smptebars=s={bw}x{bh}:r={fps}[cbox];"
             f"[c00][cbox]overlay=x='mod(t*{(w - bw) / 15:.2f},{w - bw})':y={h // 3}:shortest=1,split[c0][c1]")
    g.append("[c0]trim=0:4,setpts=PTS-STARTPTS[c0t];[c1]trim=11:15,setpts=PTS-STARTPTS[c1t]")
    g.append("[c0t][c1t]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop_duration=1,"
             f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{_between(2.0, 2.0 + 2 * fr, fps)}'[C]")  # 2 images noires à 18,0
    # 25–29,5 : barres SMPTE HD + boîte qui bouge, fondu au noir de 28 à 29, puis 0,5 s de noir
    g.append(f"smptehdbars={src}:d=4[d0]")
    g.append(_moving_box("d0", "d1", w, h, fps))
    g.append("[d1]fade=t=out:st=3:d=1[D]")
    g.append(f"color=c=black:{src}:d=0.5[Dk]")
    # 29,5–33 : testsrc2 retourné verticalement, noir et blanc de 31 à 33
    g.append(f"testsrc2={src}:d=24,trim=20:23.5,setpts=PTS-STARTPTS,vflip,"
             f"hue=s=0:enable='{_between(1.5, 3.5, fps)}'[E]")
    # 33–36 : mire RGB + boîte qui bouge, bandes cinéma (haut et bas) de 34 à 35
    g.append(f"rgbtestsrc={src}:d=3[f0]")
    g.append(_moving_box("f0", "f1", w, h, fps, "yellow"))
    bar = int(round(h * 0.125))
    g.append(f"[f1]drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill:enable='{_between(1.0, 2.0, fps)}',"
             f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill:enable='{_between(1.0, 2.0, fps)}'[F]")
    # 36–40 : testsrc2 en négatif, 4 images de mandelbrot insérées à 37,0, zoom ×1,5 décentré de 38,4 à 39,2
    g.append(f"testsrc2={src}:d=4,negate[g0]")
    g.append(f"mandelbrot={msrc}:start_scale=1.2,{up},trim=duration=4,setpts=PTS-STARTPTS[gm]")
    g.append(f"[g0][gm]overlay=enable='{_between(1.0, 1.0 + 4 * fr, fps)}'[g1]")
    g.append(_punch("g1", "G", w, h, fps, 2.4, 3.2, 1.5, cx=0.6, cy=0.4))
    # 40–43 : six plans de 0,5 s
    g.append(f"life=s=64x36:r={fps}:mold=5:ratio=0.5:seed=3:life_color=#ffcc00:death_color=#203080,"
             f"scale={w}:{h}:flags=neighbor,trim=duration=0.5,setpts=PTS-STARTPTS[h1]")
    g.append(f"smptebars={src}:d=0.5[h2a]")
    g.append(_moving_box("h2a", "h2", w, h, fps))
    g.append(f"testsrc2={src}:d=0.5,hue=h=120[h3]")
    g.append(f"mandelbrot={msrc}:start_scale=0.8:start_x=-0.75:start_y=0.1,{up},trim=duration=0.5,setpts=PTS-STARTPTS[h4]")
    g.append(f"rgbtestsrc={src}:d=0.5,hue=h=90[h5a]")
    g.append(_moving_box("h5a", "h5", w, h, fps, "red"))
    g.append(f"yuvtestsrc={src}:d=0.5[h6a]")
    g.append(_moving_box("h6a", "h6", w, h, fps, "black"))
    # 43–50 : pièges sans coupe ni zoom : testsrc2 qui défile vite, puis le jeu de la vie
    g.append(f"testsrc2={src}:d=3.5,scroll=horizontal=0.03[I]")
    # cellules de 1/64 de la largeur : l'image de mesure (128×72) garde leurs couleurs
    g.append(f"life=s=64x36:r={fps}:mold=10:ratio=0.3:seed=7:life_color=#40e0d0:death_color=#802020,"
             f"scale={w}:{h}:flags=neighbor,trim=duration=3.5,setpts=PTS-STARTPTS[J]")
    parts = ["A", "B", "C", "D", "Dk", "E", "F", "G", "h1", "h2", "h3", "h4", "h5", "h6", "I", "J"]
    # pas de filtre fps ici : après un overlay, il perdrait la dernière image de chaque partie
    norm = [f"[{p}]format=yuv420p,setsar=1[n{p}]" for p in parts]
    g += norm
    g.append("".join(f"[n{p}]" for p in parts) + f"concat=n={len(parts)}:v=1:a=0[v]")

    tmp.mkdir(parents=True, exist_ok=True)
    stem = name or f"montage_{w}x{h}_{fps}_{codec}"
    ext = ".webm" if codec == "libvpx-vp9" else ".mp4"
    dst = tmp / (stem + ext)
    script = tmp / (stem + "_graphe.txt")
    script.write_text(";\n".join(g), "utf-8")
    cmd = ["-filter_complex_script", str(script)]
    words: list[tuple[float, float]] = []
    sound: dict = {}
    if audio:
        track, sound = edit_soundtrack()
        words = sound["words"]
        wav = tmp / (stem + ".wav")
        write_wav(wav, track)
        cmd += ["-i", str(wav), "-map", "[v]", "-map", "0:a"]
        cmd += ["-c:a", "libopus" if codec == "libvpx-vp9" else "aac", "-b:a", "96k"]
    else:
        cmd += ["-map", "[v]"]
    _ffmpeg(*cmd, *_codec_args(codec), "-t", "50", str(dst))
    script.unlink(missing_ok=True)
    truth = {
        "duration": 50.0,
        "cuts": [8.0, 16.0, 20.0, 25.0, 29.5, 33.0, 36.0, 40.0, 40.5, 41.0, 41.5, 42.0, 42.5, 43.0, 46.5],
        "meme_decor": [20.0],
        "zooms": [
            {"t": 4.0, "end": 5.0, "scale": 1.25, "cx": 0.5, "cy": 0.5},
            {"t": 38.4, "end": 39.2, "scale": 1.5, "cx": 0.6, "cy": 0.4},
        ],
        "flash": 12.0,
        "black_frame": 18.0,
        "insert": 37.0,
        "freeze": (24.0, 25.0),
        "fade": (28.0, 29.0),
        "black": (29.0, 29.5),
        "bw": (31.0, 33.0),
        "bars": (34.0, 35.0),
        "no_cut_zones": [(8.1, 15.9), (43.1, 46.4), (46.6, 49.9)],
        "words": words,
        "sound": sound,
    }
    return dst, truth


def zoom_clip(tmp: Path, *, scale: float = 1.25, cx: float = 0.5, cy: float = 0.5, layer: bool = False,
              size: tuple[int, int] = (640, 360), fps: int = 30, name: str = "zoom") -> Path:
    """6 s de testsrc2 avec un zoom sec de 2,0 à 3,0 ; `layer` : sous un cadre fixe texturé en coin (facecam)."""
    w, h = size
    src = f"s={w}x{h}:r={fps}"
    g = [f"testsrc2={src}:d=6[s0]", _punch("s0", "z", w, h, fps, 2.0, 3.0, scale, cx, cy)]
    out = "z"
    if layer:  # cadre de 25 % de la largeur, texturé et immobile, posé par-dessus le zoom
        fw, fh = w // 4, h // 4
        g.append(f"smptebars=s={fw}x{fh}:r={fps}[cam0];[cam0]drawgrid=w=8:h=8:t=1:c=white[cam]")
        g.append(f"[z][cam]overlay=x={w - fw - 8}:y=8:shortest=1[zl]")
        out = "zl"
    tmp.mkdir(parents=True, exist_ok=True)
    dst = tmp / f"{name}.mp4"
    _ffmpeg("-filter_complex", ";".join(g), "-map", f"[{out}]", *_codec_args("libx264"), "-t", "6", str(dst))
    return dst


def zoompan_clip(tmp: Path, seconds: float = 5.0, size: tuple[int, int] = (640, 360), fps: int = 30) -> Path:
    """Zoom lent et continu (×1 → ×1,4 en 5 s) : ce n'est pas un zoom sec."""
    w, h = size
    frames = int(seconds * fps)
    step = 0.4 / frames
    dst = tmp / "zoompan.mp4"
    tmp.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r={fps}:d={seconds}",
            "-vf", f"zoompan=z='1+{step:.6f}*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={fps}",
            *_codec_args("libx264"), str(dst))
    return dst


def rate_clip(tmp: Path, src_fps: float, out_fps: float, seconds: float = 6.0, size: tuple[int, int] = (640, 360)) -> Path:
    """testsrc2 filmé à `src_fps` puis converti à `out_fps` (images dupliquées) : aucun figé ne doit sortir."""
    w, h = size
    dst = tmp / f"cadence_{src_fps:g}_{out_fps:g}.mp4"
    tmp.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r={src_fps}:d={seconds}", "-vf", f"fps={out_fps}",
            *_codec_args("libx264"), str(dst))
    return dst


# --------------------------------------------------------------------------- son
def write_wav(path: Path, x: np.ndarray, sr: int = SR, stereo: bool = False) -> None:
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    if stereo:
        data = np.stack([data, data], axis=1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2 if stereo else 1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def write_pcm(path: Path, x: np.ndarray) -> Path:
    """PCM 16 kHz mono s16le, comme extract_pcm."""
    (np.clip(x, -1, 1) * 32767).astype("<i2").tofile(path)
    return path


VOWELS = [  # formants (Hz) et largeurs de bande : a, i, o, é, u
    [(730, 90), (1090, 110), (2440, 170)],
    [(300, 60), (2250, 100), (3000, 170)],
    [(500, 80), (850, 100), (2400, 160)],
    [(450, 70), (1900, 110), (2600, 160)],
    [(320, 60), (800, 90), (2250, 150)],
]


def _formant_gain(f: np.ndarray, formants) -> np.ndarray:
    """Cascade de résonateurs du 2e ordre (gain 1 à 0 Hz) : l'enveloppe spectrale d'une voyelle."""
    g = np.ones_like(f, dtype=np.float64)
    for F, B in formants:
        g *= F**2 / np.sqrt((F**2 - f**2) ** 2 + (f * B) ** 2)
    return g


def _syllable(rng: np.random.Generator, dur: float, f0: float, f0_end: float, sr: int = SR) -> np.ndarray:
    """Voyelle (source harmonique en 1/k filtrée par les formants) sur une f0 qui glisse et tremble,
    précédée d'une consonne bruitée."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = np.linspace(f0, f0_end, n) * (1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4, 7) * t))
    ph = 2 * np.pi * np.cumsum(f) / sr
    formants = VOWELS[int(rng.integers(len(VOWELS)))]
    fmean = 0.5 * (f0 + f0_end)
    k = np.arange(1, int(7000 / fmean))
    gains = _formant_gain(k * fmean, formants) / k
    x = np.zeros(n)
    for kk, gain in zip(k, gains):
        x += gain * np.sin(kk * ph + rng.uniform(0, 2 * np.pi))
    env = np.sin(np.pi * np.arange(n) / n) ** 0.6
    x *= env / (np.abs(x).max() + 1e-9)
    cons = int(rng.uniform(0.02, 0.06) * sr)  # consonne : bruit bref à l'attaque
    x[:cons] += 0.3 * rng.standard_normal(cons) * np.linspace(1, 0.2, cons)
    return x / (np.abs(x).max() + 1e-9)


def voice16(seconds: float, seed: int = 1, f0: tuple[float, float] = (120, 220), level: float = 0.25,
            start: float = 0.5) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Parole synthétique : mots de 1 à 3 syllabes, 4 à 6 syllabes/s, pauses connues. Renvoie (signal, mots)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    x = np.zeros(n)
    words: list[tuple[float, float]] = []
    t = start
    while t < seconds - 1.0:
        phrase_words = int(rng.integers(3, 9))
        for _ in range(phrase_words):
            s = t
            for _ in range(int(rng.integers(1, 4))):
                d = float(rng.uniform(0.14, 0.22))
                a = float(rng.uniform(*f0))
                syl = _syllable(rng, d, a, a * rng.uniform(0.85, 1.15))
                i = int(t * SR)
                if i + len(syl) >= n:
                    break
                x[i:i + len(syl)] += level * rng.uniform(0.6, 1.0) * syl
                t += d + float(rng.uniform(0.0, 0.03))
            words.append((round(s, 3), round(t, 3)))
            t += float(rng.uniform(0.04, 0.15))
            if t >= seconds - 1.0:
                break
        t += float(rng.uniform(0.3, 1.2))  # pause entre deux phrases
    return x.astype(np.float32), words


def deep_voice16(seconds: float, seed: int = 2) -> tuple[np.ndarray, list[tuple[float, float]]]:
    return voice16(seconds, seed, f0=(90, 110))


def drone16(seconds: float, f0: float = 120.0, level: float = 0.05) -> np.ndarray:
    """Ronronnement de moteur figé : 120 Hz et ses harmoniques (piège tonal sans changement d'accord)."""
    t = np.arange(int(seconds * SR)) / SR
    x = sum((0.7 ** k) * np.sin(2 * np.pi * f0 * k * t + k) for k in range(1, 9))
    return (level * x / np.abs(x).max()).astype(np.float32)


CHORDS = [(220.0, 277.2, 329.6), (196.0, 246.9, 293.7), (174.6, 220.0, 261.6), (164.8, 207.7, 246.9)]


def _kick(sr: int = SR) -> np.ndarray:
    t = np.arange(int(0.25 * sr)) / sr
    return np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 35)) * t) * np.exp(-t * 14)


def music16(seconds: float, bpm: float = 110.0, chords=CHORDS, seed: int = 4, level: float = 0.25,
            fade_out: float = 0.0) -> np.ndarray:
    """Musique rythmée : grosse caisse sur chaque temps, charleston, accords qui changent toutes les 4 mesures."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros(n)
    beat = 60.0 / bpm
    kick = _kick()
    k = 0
    while k * beat < seconds:
        i = int(k * beat * SR)
        j = min(n, i + int(beat * SR))
        tt = np.arange(j - i) / SR
        out[i:min(n, i + len(kick))] += 0.9 * kick[: min(n, i + len(kick)) - i]
        hi = int((k + 0.5) * beat * SR)
        if hi < n:
            m = min(n - hi, int(0.04 * SR))
            out[hi:hi + m] += 0.12 * rng.standard_normal(m) * np.exp(-np.arange(m) / (0.008 * SR))
        chord = chords[(k // 8) % len(chords)]
        out[i:j] += 0.12 * sum(np.sin(2 * np.pi * f * tt) for f in chord)
        out[i:j] += 0.08 * np.sin(2 * np.pi * chord[k % 3] * 2 * tt) * np.exp(-tt * 5)
        k += 1
    out = level * out / (np.abs(out).max() + 1e-9)
    if fade_out:
        m = int(fade_out * SR)
        out[-m:] *= np.linspace(1, 0, m)
    return out.astype(np.float32)


def pad16(seconds: float, level: float = 0.15, change_s: float = 2.0) -> np.ndarray:
    """Nappe : accords tenus sans percussion qui changent toutes les 2 s."""
    n = int(seconds * SR)
    out = np.zeros(n)
    step = int(change_s * SR)
    for k, i in enumerate(range(0, n, step)):
        j = min(n, i + step)
        tt = np.arange(j - i) / SR
        env = np.minimum(1, np.minimum(tt / 0.05, (tt[-1] - tt + 1e-3) / 0.05))
        out[i:j] += env * sum(np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt) for f in CHORDS[k % 4])
    return (level * out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def _t(d: float) -> np.ndarray:
    return np.arange(int(d * SR)) / SR


def bip(d: float = 0.6, level: float = 0.3) -> np.ndarray:
    """Bip de censure 1 kHz."""
    t = _t(d)
    env = np.minimum(1, np.minimum(t / 0.003, (t[-1] - t + 1e-4) / 0.003))
    return (level * np.sin(2 * np.pi * 1000 * t) * env).astype(np.float32)


def boum(level: float = 0.7) -> np.ndarray:
    """« Vine boom » : 55 Hz qui décroît."""
    t = _t(0.8)
    return (level * np.sin(2 * np.pi * (55 + 30 * np.exp(-t * 8)) * t) * np.exp(-t * 4.5)
            * np.minimum(1, t / 0.004)).astype(np.float32)


def whoosh(d: float = 0.5, level: float = 0.35, seed: int = 9) -> np.ndarray:
    """Bruit en cloche, penché vers les aigus (passe-haut doux du 1er ordre)."""
    rng = np.random.default_rng(seed)
    n = int(d * SR)
    noise = rng.standard_normal(n + 1)
    x = noise[1:] + 1.5 * np.diff(noise)
    env = np.sin(np.pi * np.arange(n) / n)
    return (level * env * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def ding(level: float = 0.3) -> np.ndarray:
    """Notification : 1 568 + 3 136 Hz, décroissant."""
    t = _t(0.7)
    return (level * (np.sin(2 * np.pi * 1568 * t) + 0.5 * np.sin(2 * np.pi * 3136 * t)) * np.exp(-t * 5)
            * np.minimum(1, t / 0.002)).astype(np.float32)


def clic(level: float = 0.8) -> np.ndarray:
    """Coup bref de 5 ms (sinus amorti à 3 kHz, sans écrêtage)."""
    t = _t(0.005)
    return (level * np.exp(-t / 0.002) * np.sin(2 * np.pi * 3000 * t)).astype(np.float32)


def sature(d: float = 0.6) -> np.ndarray:
    """Cri saturé : 400 Hz modulé, écrêté."""
    t = _t(d)
    return (np.clip(3 * np.sin(2 * np.pi * 400 * t) * np.sign(np.sin(2 * np.pi * 7 * t) + 0.3), -1, 1) * 0.99).astype(np.float32)


def montee(d: float = 2.0, level: float = 0.5, seed: int = 13) -> np.ndarray:
    """Riser : bruit + sinus qui montent (en hauteur, et de 30 dB en volume, régulièrement), coupés net."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    f = 200 + 1200 * (t / d) ** 2
    x = 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.2 * rng.standard_normal(len(t))
    env = 10 ** ((-30 + 30 * t / d) / 20)
    return (level * env * x).astype(np.float32)


def glissando(d: float = 0.5, f0: float = 300.0, f1: float = 900.0, level: float = 0.4) -> np.ndarray:
    """Son cartoon : chirp 300 → 900 Hz."""
    t = _t(d)
    f = f0 * (f1 / f0) ** (t / d)
    env = np.minimum(1, np.minimum(t / 0.01, (t[-1] - t + 1e-4) / 0.01))
    return (level * np.sin(2 * np.pi * np.cumsum(f) / SR) * env).astype(np.float32)


def place(x: np.ndarray, at: float, sig: np.ndarray, gain: float = 1.0) -> None:
    i = int(round(at * SR))
    m = min(len(sig), len(x) - i)
    x[i:i + m] += gain * sig[:m]


def rms_db(x: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(np.asarray(x, np.float64) ** 2) + 1e-12))


def voice_rms_db(x: np.ndarray, words: list[tuple[float, float]]) -> float:
    """Niveau RMS de la parole (sur les mots seulement)."""
    return rms_db(np.concatenate([x[int(s * SR):int(e * SR)] for s, e in words]))


def place_at(x: np.ndarray, at: float, sig: np.ndarray, rel_db: float | None, voice_db: float, *,
             ref: str = "actif") -> None:
    """Pose `sig` à `at`, à `rel_db` au-dessus de la voix (None : tel quel) ; référence de niveau : la partie
    active du son, ou sa fin (« fin » : une montée est jugée sur ses 100 dernières ms)."""
    gain = 1.0
    if rel_db is not None:
        part = sig[-SR // 10:] if ref == "fin" else sig[np.abs(sig) > 0.05 * np.abs(sig).max()]
        gain = min(10 ** ((voice_db + rel_db - rms_db(part)) / 20), 0.98 / np.abs(sig).max())
    place(x, at, sig, gain)


# catégorie, son, où (« mot » : sur une syllabe, « trou » : entre deux phrases), niveau par rapport à la voix
EVENT_SPECS = [
    ("bip", bip, "mot", 15), ("tonal", ding, "mot", 15), ("boum", boum, "trou", 6),
    ("whoosh", whoosh, "trou", 10), ("clic", clic, "trou", 10), ("sature", sature, "trou", None),
    ("glissando", glissando, "trou", 6), ("montee", montee, "trou", 15),
]


def sound_mix(seed: int = 1, deep: bool = False, seconds: float = 80.0) -> tuple[np.ndarray, list, list]:
    """Voix synthétique + les 8 sortes de sons marquants, placés au hasard (graine) : bip et ding sur une
    syllabe, les autres dans un trou de parole. Renvoie (signal, mots, [(instant, catégorie, durée)])."""
    v, words = (deep_voice16 if deep else voice16)(seconds, seed=seed)
    x = v + (0.002 * np.random.default_rng(seed).standard_normal(len(v))).astype(np.float32)
    vr = voice_rms_db(v, words)
    ws = sorted(words)
    gaps = [(a[1], b[0]) for a, b in zip(ws, ws[1:]) if b[0] - a[1] >= 0.7]
    inside = [(s, e) for s, e in ws if e - s >= 0.3]
    rng = np.random.default_rng(100 + seed)
    used: list[float] = []

    def free(t: float) -> bool:
        return all(abs(t - u) > 2.5 for u in used) and 3 < t < seconds - 4

    plan = []
    for cat, make, where, rel in EVENT_SPECS:
        spots = [a + 0.3 for a, _ in gaps] if where == "trou" else [s + 0.4 * (e - s) for s, e in inside]
        t = next((float(t) for t in rng.permutation(spots) if free(float(t))), None)
        if t is None:
            continue
        used.append(t)
        sig = make()
        place_at(x, t, sig, rel, vr, ref="fin" if cat == "montee" else "actif")
        plan.append((round(t, 3), cat, len(sig) / SR))
    return np.clip(x, -1, 1).astype(np.float32), words, sorted(plan)


def music_at(sig: np.ndarray, voice_db_median: float, rel_db: float) -> np.ndarray:
    """Règle une musique pour que son niveau de fond (20e centile de E, trames de 10 ms) soit `rel_db` sous
    le niveau médian de la voix (même mesure que level_vs_voice_db)."""
    frames = sig[: len(sig) // 160 * 160].astype(np.float64).reshape(-1, 160)
    p20 = float(np.percentile(10 * np.log10(np.mean(frames**2, axis=1) + 1e-10), 20))
    return (sig * 10 ** ((voice_db_median + rel_db - p20) / 20)).astype(np.float32)


def voice_median_db(x: np.ndarray, words: list[tuple[float, float]]) -> float:
    """Médiane du niveau par trame de 10 ms sur les mots (mesure de soundscan pour la voix)."""
    frames = x[: len(x) // 160 * 160].astype(np.float64).reshape(-1, 160)
    e = 10 * np.log10(np.mean(frames**2, axis=1) + 1e-10)
    mask = np.zeros(len(e), bool)
    for s, t in words:
        mask[max(0, int((s - 0.05) * 100)):int(np.ceil((t + 0.05) * 100))] = True
    return float(np.median(e[mask]))


def edit_soundtrack(seconds: float = 50.0, seed: int = 3) -> tuple[np.ndarray, dict]:
    """Bande-son du faux montage : voix, musique rythmée sous la voix (coupée net sur une coupe), bruitages
    calés sur l'image (clic sur le zoom, boum sur la coupe…), et un silence complet coupé net.

    Autour d'un bruitage posé « dans un trou », la voix est coupée (fondus de 20 ms) : la vérité ne dépend pas
    du hasard des pauses. Renvoie (signal, vérité).
    """
    v, words = voice16(seconds, seed=seed)
    rng = np.random.default_rng(seed)
    music = (9.0, 29.5, 110.0)
    events = [  # (instant, catégorie, son, où, niveau / voix)
        (4.0, "clic", clic(), "trou", 10), (8.0, "boum", boum(), "trou", 6), (15.9, "whoosh", whoosh(), "trou", 10),
        (21.0, "bip", bip(), "mot", 15), (26.5, "tonal", ding(), "mot", 15), (31.5, "sature", sature(), "trou", None),
        (34.5, "glissando", glissando(), "trou", 6), (44.5, "montee", montee(), "trou", 15),
    ]
    keep = np.ones(len(v))
    holes = [(t - 0.3, t + len(sig) / SR + 0.3) for t, _, sig, where, _ in events if where == "trou"]
    # les mots touchés par un trou disparaissent en entier : la voix reprend sur un début de mot
    gone = [(s, e) for s, e in words if any(a - 0.05 < e and s < b + 0.05 for a, b in holes)]
    for s, e in gone:
        keep[int((s - 0.01) * SR):int((e + 0.03) * SR)] = 0
    for a, b in holes:
        keep[int(a * SR):int(b * SR)] = 0
    v = (v * keep).astype(np.float32)
    words = [w for w in words if w not in gone]
    # silence complet coupé net au milieu d'un mot : le son tombe d'un coup (la parole s'arrête au milieu)
    long_word = next((s, e) for s, e in words if s > 40.5 and e - s >= 0.3 and all(abs(s - t) > 1.5 for t, *_ in events))
    silence = (round(long_word[0] + 0.15, 2), 0.6)
    vr = voice_rms_db(v, words)
    vmed = voice_median_db(v, words)
    x = v + (0.002 * rng.standard_normal(len(v))).astype(np.float32)
    place(x, music[0], music_at(music16(music[1] - music[0], music[2]), vmed, -12))
    plan = []
    for t, cat, sig, _, rel in events:
        place_at(x, t, sig, rel, vr, ref="fin" if cat == "montee" else "actif")
        plan.append({"t": t, "cat": cat, "dur": round(len(sig) / SR, 3)})
    i = int(silence[0] * SR)
    x[i:i + int(silence[1] * SR)] = 0.0  # silence complet, coupé net (le son ne s'éteint pas avant)
    truth = {"words": words, "events": plan, "music": {"start": music[0], "end": music[1], "bpm": music[2]},
             "silence": {"t": silence[0], "dur": silence[1]}}
    return np.clip(x, -1, 1).astype(np.float32), truth


# ------------------------------------------------------------- cache des tests
_CACHE: dict = {}


def cached(key, build):
    """Un même média synthétique (ou une même analyse) sert à plusieurs fichiers de tests."""
    if key not in _CACHE:
        _CACHE[key] = build()
    return _CACHE[key]
