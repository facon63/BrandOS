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
    # 16–24 : testsrc2 retourné, saut de 7 s dans la source à 20,0 (jump cut), puis 1 s figée
    bw, bh = w // 4, h // 3  # un « personnage » qui traverse le décor : le saut de 7 s le déplace d'un coup
    g.append(f"testsrc2={src}:d=15,hflip[c00];smptebars=s={bw}x{bh}:r={fps}[cbox];"
             f"[c00][cbox]overlay=x='mod(t*{(w - bw) / 15:.2f},{w - bw})':y={h // 3}:shortest=1,split[c0][c1]")
    g.append("[c0]trim=0:4,setpts=PTS-STARTPTS[c0t];[c1]trim=11:15,setpts=PTS-STARTPTS[c1t]")
    g.append("[c0t][c1t]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop_duration=1[C]")
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
    if audio:
        voice, words = voice16(50.0, seed=3)
        wav = tmp / (stem + ".wav")
        write_wav(wav, voice)
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
        "insert": 37.0,
        "freeze": (24.0, 25.0),
        "fade": (28.0, 29.0),
        "black": (29.0, 29.5),
        "bw": (31.0, 33.0),
        "bars": (34.0, 35.0),
        "no_cut_zones": [(8.1, 15.9), (43.1, 46.4), (46.6, 49.9)],
        "words": words,
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
    [(730, 90), (1090, 110), (2440, 160)],
    [(300, 60), (2250, 150), (3000, 200)],
    [(500, 80), (850, 100), (2400, 160)],
    [(450, 70), (1900, 130), (2600, 170)],
    [(320, 60), (800, 90), (2250, 150)],
]


def _syllable(rng: np.random.Generator, dur: float, f0: float, f0_end: float, sr: int = SR) -> np.ndarray:
    """Voyelle à formants sur une f0 qui glisse et tremble, précédée d'une consonne bruitée."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = np.linspace(f0, f0_end, n) * (1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4, 7) * t))
    ph = 2 * np.pi * np.cumsum(f) / sr
    formants = VOWELS[int(rng.integers(len(VOWELS)))]
    x = np.zeros(n)
    fmean = 0.5 * (f0 + f0_end)
    for k in range(1, int(7000 / fmean)):
        fk = k * fmean
        gain = sum(np.exp(-0.5 * ((fk - F) / bw) ** 2) for F, bw in formants) + 0.03
        x += gain * np.sin(k * ph + rng.uniform(0, 2 * np.pi)) / np.sqrt(k)
    env = np.sin(np.pi * np.arange(n) / n) ** 0.6
    x *= env
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
    """Bruit en cloche passe-haut."""
    rng = np.random.default_rng(seed)
    n = int(d * SR)
    x = rng.standard_normal(n)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec *= np.clip((f - 1500) / 1500, 0, 1)  # passe-haut doux
    x = np.fft.irfft(spec, n)
    env = np.sin(np.pi * np.arange(n) / n) ** 2
    return (level * env * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def ding(level: float = 0.3) -> np.ndarray:
    """Notification : 1 568 + 3 136 Hz, décroissant."""
    t = _t(0.7)
    return (level * (np.sin(2 * np.pi * 1568 * t) + 0.5 * np.sin(2 * np.pi * 3136 * t)) * np.exp(-t * 5)
            * np.minimum(1, t / 0.002)).astype(np.float32)


def clic(level: float = 0.8, seed: int = 11) -> np.ndarray:
    """Coup bref de 5 ms."""
    rng = np.random.default_rng(seed)
    n = int(0.005 * SR)
    return (level * np.linspace(1, 0, n) * rng.standard_normal(n)).clip(-1, 1).astype(np.float32)


def sature(d: float = 0.6) -> np.ndarray:
    """Cri saturé : 400 Hz modulé, écrêté."""
    t = _t(d)
    return (np.clip(3 * np.sin(2 * np.pi * 400 * t) * np.sign(np.sin(2 * np.pi * 7 * t) + 0.3), -1, 1) * 0.99).astype(np.float32)


def montee(d: float = 2.0, level: float = 0.4, seed: int = 13) -> np.ndarray:
    """Riser : bruit + sinus qui montent en volume et en hauteur, coupés net."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    f = 200 + 1200 * (t / d) ** 2
    x = 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * rng.standard_normal(len(t)) * 0.4
    env = (t / d) ** 2
    return (level * env * x).astype(np.float32)


def glissando(d: float = 0.5, f0: float = 300.0, f1: float = 900.0, level: float = 0.3) -> np.ndarray:
    """Son cartoon : chirp 300 → 900 Hz."""
    t = _t(d)
    f = f0 * (f1 / f0) ** (t / d)
    env = np.minimum(1, np.minimum(t / 0.01, (t[-1] - t + 1e-4) / 0.01))
    return (level * np.sin(2 * np.pi * np.cumsum(f) / SR) * env).astype(np.float32)


def place(x: np.ndarray, at: float, sig: np.ndarray, gain: float = 1.0) -> None:
    i = int(round(at * SR))
    m = min(len(sig), len(x) - i)
    x[i:i + m] += gain * sig[:m]
