"""Fabrique de faux rush : deux POV synchronisés à un décalage connu, avec des « répliques »."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

SR = 48000
B_DELAY = 3.5  # le POV B a commencé à filmer 3,5 s après A
CORPUS = [
    "non mais attends regarde ça", "t'es sérieux là", "mdr mais non", "c'est la bonne cette fois",
    "j'y crois pas !", "ah ah ah", "vas-y saute", "oh non non non", "trop fort", "on recommence",
    "il est où le boss", "attention derrière toi !", "j'ai plus de vie", "c'est n'importe quoi",
]


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    stereo = np.stack([x, x], axis=1)
    data = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def make_script(duration: float, seed: int = 7):
    """Répliques alternées entre A et B, avec de temps en temps un fou rire (son fort sans mots)."""
    rng = np.random.default_rng(seed)
    words, events = [], []
    t = 2.0
    speaker = "A"
    while t < duration - 6:
        sentence = CORPUS[int(rng.integers(len(CORPUS)))].split()
        loud = rng.random() < 0.2
        for w in sentence:
            d = float(rng.uniform(0.18, 0.4))
            words.append({"w": w, "s": round(t, 3), "e": round(t + d, 3), "p": 0.9, "spk": speaker, "loud": loud})
            t += d + float(rng.uniform(0.04, 0.12))
        if loud and rng.random() < 0.6:
            events.append((t + 0.2, t + 1.4, speaker))
            t += 1.6
        # parfois un long blanc (à couper au montage)
        t += float(rng.uniform(2.5, 5.0)) if rng.random() < 0.3 else float(rng.uniform(0.3, 0.8))
        speaker = "B" if speaker == "A" else "A"
    return words, events


def synth_tracks(duration: float, words, events, seed: int = 3):
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    voice = {"A": np.zeros(n, np.float32), "B": np.zeros(n, np.float32)}
    for w in words:
        i0, i1 = int(w["s"] * SR), int(w["e"] * SR)
        amp = 0.5 if w["loud"] else 0.15
        voice[w["spk"]][i0:i1] += (rng.standard_normal(i1 - i0) * amp).astype(np.float32)
    for s, e, spk in events:
        i0, i1 = int(s * SR), int(e * SR)
        voice[spk][i0:i1] += (rng.standard_normal(i1 - i0) * 0.6).astype(np.float32)
    noise = lambda: (rng.standard_normal(n) * 0.003).astype(np.float32)  # noqa: E731
    track_a = voice["A"] + 0.25 * voice["B"] + noise()
    track_b = voice["B"] + 0.25 * voice["A"] + noise()
    return track_a, track_b


@pytest.fixture(scope="session")
def rushes(tmp_path_factory):
    root = tmp_path_factory.mktemp("rush")
    duration = 150.0
    words, events = make_script(duration)
    track_a, track_b = synth_tracks(duration, words, events)
    track_b = track_b[int(B_DELAY * SR) :]
    _write_wav(root / "a.wav", track_a)
    _write_wav(root / "b.wav", track_b)
    for key, src in (("A", "testsrc2=s=640x360:r=30"), ("B", "smptehdbars=s=640x360:r=30")):
        dur = duration if key == "A" else duration - B_DELAY
        _ffmpeg(
            "-f", "lavfi", "-i", f"{src}:d={dur}", "-i", str(root / f"{key.lower()}.wav"),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(root / f"pov_{key}.mp4"),
        )
    # Les mots sont donnés en temps du POV A (= temps maître, A ayant démarré en premier)
    clean_words = [{k: w[k] for k in ("w", "s", "e", "p")} for w in words]
    return {"root": root, "a": root / "pov_A.mp4", "b": root / "pov_B.mp4", "words": clean_words, "events": events, "duration": duration}


@pytest.fixture(scope="session")
def library_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("bibliotheque")
    for sub in ("sfx", "musiques", "personnages/Krok", "personnages/Mil", "memes"):
        (root / sub).mkdir(parents=True)
    t = np.linspace(0, 0.5, int(SR * 0.5), endpoint=False)
    _write_wav(root / "sfx" / "boing_cartoon.wav", (0.5 * np.sin(2 * np.pi * (300 + 600 * t) * t)).astype(np.float32))
    _write_wav(root / "sfx" / "whoosh_transition.wav", (0.3 * np.random.default_rng(1).standard_normal(len(t))).astype(np.float32))
    _write_wav(root / "sfx" / "rire_public.wav", (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32))
    tm = np.linspace(0, 60, SR * 60, endpoint=False)
    _write_wav(root / "musiques" / "chill_lofi.wav", (0.2 * np.sin(2 * np.pi * 330 * tm)).astype(np.float32))
    _ffmpeg(
        "-f", "lavfi", "-i", "color=c=black:s=200x300:r=30:d=2,format=rgba,"
        "geq=r=255:g=0:b=0:a='if(between(X,50,150)*between(Y,40,260),255,0)'",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", str(root / "personnages" / "Krok" / "krok_rire.webm"),
    )
    _ffmpeg(
        "-f", "lavfi", "-i", "color=c=black:s=200x300,format=rgba,"
        "geq=r=255:g=230:b=0:a='if(between(X,40,160)*between(Y,40,260),255,0)'",
        "-frames:v", "1", str(root / "personnages" / "Mil" / "mil_choque.png"),
    )
    _ffmpeg(
        "-f", "lavfi", "-i", "color=c=0x00FF00:s=320x180:r=30:d=1.5,drawbox=x=120:y=50:w=80:h=80:color=white:t=fill",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "memes" / "choc_fond_vert.mp4"),
    )
    return root


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("KROKCUT_HOME", str(tmp_path / "ws"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    return tmp_path / "ws"
