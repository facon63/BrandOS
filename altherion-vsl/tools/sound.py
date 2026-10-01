"""Altherion VSL — sound design et musique 100 % procéduraux, calés sur l'image.

Entrées : audio/events.json (exporté par l'animation), src/timeline.json, audio/vo.wav
Sorties : out/mix.wav (VO + musique + SFX), out/altherion-vsl_musique-sfx.wav (stem sans voix)

Usage : python3 tools/sound.py
"""
import json
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import maximum_filter1d, uniform_filter1d

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(7)

EV = json.loads((ROOT / "audio" / "events.json").read_text())
TL = json.loads((ROOT / "src" / "timeline.json").read_text())
DUR = EV["duration"]
N = int((DUR + 0.5) * SR)
SEG = TL["segments"]
T = lambda i: SEG[i]["start"]
TE = lambda i: SEG[i]["end"]
EVENTS = EV["events"]


def ev(kind):
    return [e for e in EVENTS if e["type"] == kind]


def ev1(kind):
    return ev(kind)[0]["t"]


# ------------------------------------------------------------------ bus
class Bus:
    def __init__(self):
        self.x = np.zeros((2, N))

    def add(self, sig, t, gain_db=0.0, pan=0.0):
        """Place un signal mono (n,) ou stéréo (2, n) à l'instant t."""
        g = 10 ** (gain_db / 20)
        i0 = int(round(t * SR))
        if sig.ndim == 1:
            a = (pan + 1) * np.pi / 4
            sig = np.stack([sig * np.cos(a), sig * np.sin(a)]) * np.sqrt(2)
        if i0 < 0:
            sig = sig[:, -i0:]
            i0 = 0
        n = min(sig.shape[1], N - i0)
        if n > 0:
            self.x[:, i0:i0 + n] += sig[:, :n] * g


music, sfx, music_verb, sfx_verb = Bus(), Bus(), Bus(), Bus()


def both(bus_dry, bus_wet, sig, t, db, pan=0.0, wet_db=-8.0):
    bus_dry.add(sig, t, db, pan)
    bus_wet.add(sig, t, db + wet_db, pan)


# ------------------------------------------------------------------ outils DSP
def note(name):
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
             "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
    p, o = (name[:2], name[2:]) if name[:2] in names else (name[:1], name[1:])
    midi = 12 * (int(o) + 1) + names[p]
    return 440.0 * 2 ** ((midi - 69) / 12)


def tvec(dur):
    return np.arange(int(dur * SR)) / SR


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    ns = max(0, n - na - nd - nr)
    e = np.concatenate([np.linspace(0, 1, na, endpoint=False) ** 1.5 if na else [],
                        np.linspace(1, s, nd, endpoint=False) if nd else [],
                        np.full(ns, s),
                        np.linspace(s, 0, nr) ** 1.6 if nr else []])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def expdec(n, tau, attack=0.002):
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    na = max(1, int(attack * SR))
    e[:na] *= np.linspace(0, 1, na)
    return e


def sos(kind, f, order=2):
    f = np.clip(f, 20, SR * 0.45)
    return signal.butter(order, f, kind, fs=SR, output="sos")


def filt(x, kind, f, order=2):
    return signal.sosfilt(sos(kind, f, order), x)


def sweep(x, kind, f0, f1, order=2, block=256, curve=None):
    """Filtre dont la fréquence de coupure varie dans le temps (traitement par blocs)."""
    n = len(x)
    out = np.empty_like(x)
    nb = (n + block - 1) // block
    zi = None
    for b in range(nb):
        u = b / max(1, nb - 1)
        if curve is not None:
            u = curve(u)
        f = f0 * (f1 / f0) ** u
        s = sos(kind, [f / 1.6, f * 1.6] if kind == "bandpass" else f, order)
        if zi is None:
            zi = np.zeros((s.shape[0], 2))
        seg = x[b * block:(b + 1) * block]
        out[b * block:(b + 1) * block], zi = signal.sosfilt(s, seg, zi=zi)
    return out


def phase_of(freq, n):
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    return np.cumsum(f / SR), f / SR


def saw(freq, n, ph0=0.0):
    ph, dt = phase_of(freq, n)
    ph = (ph + ph0) % 1.0
    s = 2 * ph - 1
    m1 = ph < dt
    t1 = ph[m1] / dt[m1]
    s[m1] -= t1 + t1 - t1 * t1 - 1
    m2 = ph > 1 - dt
    t2 = (ph[m2] - 1) / dt[m2]
    s[m2] -= t2 * t2 + t2 + t2 + 1
    return s


def sine(freq, n, ph0=0.0):
    ph, _ = phase_of(freq, n)
    return np.sin(2 * np.pi * (ph + ph0))


def tri(freq, n):
    ph, _ = phase_of(freq, n)
    return 2 * np.abs(2 * (ph % 1.0) - 1) - 1


def noise(n, color="white"):
    w = rng.standard_normal(n)
    if color == "pink":
        b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
        w = signal.lfilter(b, a, w) * 4
    return w


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * peak


# ------------------------------------------------------------------ instruments
def pad(notes, dur, cutoff=1800, attack=0.9, release=1.4, detune=8, voices=3, bright=None):
    """Nappe de dents de scie désaccordées, large en stéréo."""
    n = int((dur + release) * SR)
    out = np.zeros((2, n))
    env = adsr(n, attack, 0.3, 0.85, release)
    for f0 in notes:
        f = note(f0) if isinstance(f0, str) else f0
        for v in range(voices):
            c = (v - (voices - 1) / 2) * detune
            vib = 1 + 0.0018 * np.sin(2 * np.pi * (0.17 + 0.05 * v) * np.arange(n) / SR + v)
            s = saw(f * 2 ** (c / 1200) * vib, n, ph0=rng.random())
            pan = (v - (voices - 1) / 2) / max(1, (voices - 1) / 2) * 0.7
            a = (pan + 1) * np.pi / 4
            out[0] += s * np.cos(a)
            out[1] += s * np.sin(a)
    if bright is None:
        out = np.stack([filt(out[0], "low", cutoff, 2), filt(out[1], "low", cutoff, 2)])
    else:
        out = np.stack([sweep(out[0], "low", cutoff, bright), sweep(out[1], "low", cutoff, bright)])
    out = np.stack([filt(out[0], "high", 70), filt(out[1], "high", 70)])
    return out * env / (len(notes) * voices) * 1.6


def choir(notes, dur, attack=0.6, release=1.6):
    """« Aah » : dents de scie filtrées par formants (a)."""
    n = int((dur + release) * SR)
    out = np.zeros((2, n))
    env = adsr(n, attack, 0.4, 0.8, release)
    for f0 in notes:
        f = note(f0)
        for v in range(4):
            vib = 1 + 0.004 * np.sin(2 * np.pi * (4.6 + v * 0.3) * np.arange(n) / SR + v * 1.3)
            s = saw(f * 2 ** ((v - 1.5) * 6 / 1200) * vib, n, ph0=rng.random())
            vf = sum(g * filt(s, "bandpass", [fc * 0.85, fc * 1.15], 2) for fc, g in ((800, 1.0), (1150, 0.6), (2900, 0.25)))
            a = ((v / 3) * 1.4 - 0.7 + 1) * np.pi / 4
            out[0] += vf * np.cos(a)
            out[1] += vf * np.sin(a)
    return out * env / (len(notes) * 4) * 3.0


def bell(f, dur=2.5, tau=0.9, bright=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    partials = [(1, 1.0), (2.0, 0.45), (3.01, 0.25), (4.17, 0.18 * bright), (5.43, 0.1 * bright), (6.8, 0.06 * bright)]
    s = sum(a * np.sin(2 * np.pi * f * r * t + k) * np.exp(-t / (tau / (1 + k * 0.7))) for k, (r, a) in enumerate(partials))
    s *= np.minimum(1, t / 0.003)
    return s / 2


def pluck(f, dur=1.2, tau=0.35, harm=10):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum((1 / k) * np.sin(2 * np.pi * f * k * t) * np.exp(-t / (tau / (1 + 0.45 * (k - 1)))) for k in range(1, harm + 1) if f * k < 16000)
    s *= np.minimum(1, t / 0.002)
    return s * 0.6


def kick(dur=0.6, f0=120, f1=42, tau=0.32):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.045)
    s = sine(f, n) * np.exp(-t / tau)
    click = filt(noise(n), "bandpass", [1500, 5000]) * np.exp(-t / 0.004) * 0.25
    return (s + click) * 0.9


def hat(dur=0.08, tau=0.025):
    n = int(dur * SR)
    return filt(noise(n), "high", 7000) * expdec(n, tau) * 0.35


def impact(dur=3.0, f0=95, f1=34, tau=1.1, noise_amt=0.5, lp=900):
    """Impact cinéma : sub qui chute + souffle filtré."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.25)
    sub = sine(f, n) * np.exp(-t / tau)
    body = filt(noise(n, "pink"), "low", lp) * np.exp(-t / (tau * 0.35)) * noise_amt
    click = filt(noise(n), "bandpass", [800, 4000]) * np.exp(-t / 0.006) * 0.3
    return np.tanh((sub + body + click) * 1.4) * 0.8


def braam(notes, dur=2.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f0 in notes:
        f = note(f0)
        for d in (-9, 0, 9):
            s += saw(f * 2 ** (d / 1200) * (1 + 0.003 * np.sin(2 * np.pi * 5 * t)), n, rng.random())
    s /= len(notes) * 3
    env = adsr(n, 0.02, 0.5, 0.55, 1.6)
    s = sweep(s, "low", 2600, 260, order=2, curve=lambda u: min(1, u * 1.6) ** 0.6)
    s = np.tanh(s * 3) * env
    return s * 0.9


def whoosh(dur=0.8, f0=300, f1=3000, peak=0.6, q=0.5):
    n = int(dur * SR)
    x = noise(n, "pink")
    lo = sweep(x, "low", f1, f0) if f1 < f0 else sweep(x, "high", f0 * 0.5, f1 * 0.5)
    bp = sweep(lo, "low", max(f0, f1) * 1.4, min(f0, f1) * 1.4) if f1 < f0 else sweep(lo, "low", f0 * 2, f1 * 2)
    u = np.linspace(0, 1, n)
    env = np.where(u < peak, (u / peak) ** 2, ((1 - u) / (1 - peak)) ** 1.5)
    return bp * env * 0.9


def riser(dur, f0=200, f1=6000):
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    x = sweep(noise(n, "pink"), "high", f0, f1, curve=lambda v: v ** 1.6) * 0.7
    tone_f = 110 * 2 ** (u ** 1.8 * 3)
    tone = saw(tone_f, n) * 0.25 + saw(tone_f * 1.5, n) * 0.12
    tone = sweep(tone, "low", 400, 5000, curve=lambda v: v ** 1.4)
    return (x + tone) * u ** 2.2


def reverse_swell(dur, f=2000):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = filt(noise(n, "pink"), "bandpass", [f * 0.4, f * 2.5]) * np.exp(-(dur - t) / (dur * 0.28))
    return x * 0.8


def blip(f0, f1, dur=0.09, shape="sine"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    s = sine(f, n) if shape == "sine" else tri(f, n)
    return s * adsr(n, 0.003, dur * 0.3, 0.6, dur * 0.5)


def click(n_ms=7, lo=2000, hi=6500):
    n = int(n_ms / 1000 * SR)
    return filt(noise(n), "bandpass", [lo, hi]) * expdec(n, n_ms / 1000 / 4, 0.0005)


def metal(f, dur=0.7, tau=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rat = [1, 2.32, 4.25, 6.63, 9.38]
    s = sum(np.sin(2 * np.pi * f * r * t + k) * np.exp(-t / (tau / (1 + 0.6 * k))) / (1 + k * 0.6) for k, r in enumerate(rat))
    return s * np.minimum(1, t / 0.001) * 0.35


def chime_chord(notes, dur=3.0, tau=1.2):
    s = sum(bell(note(nn), dur, tau) for nn in notes)
    return s / len(notes) * 1.4


# ------------------------------------------------------------------ MUSIQUE
BPM = 100
BEAT = 60 / BPM


def place_pad(notes, t0, t1, db, cutoff=1600, bright=None, attack=0.9, release=1.4, wet=-6):
    p = pad(notes, t1 - t0, cutoff=cutoff, bright=bright, attack=attack, release=release)
    both(music, music_verb, p, t0, db, wet_db=wet)


def place_bass(pattern, t0, t1, step, db, cutoff=500):
    k = 0
    t = t0
    while t < t1 - 0.01:
        f = note(pattern[k % len(pattern)])
        n = int(step * 0.95 * SR)
        s = saw(f, n) * 0.6 + sine(f / 2, n) * 0.5
        s = filt(s, "low", cutoff) * adsr(n, 0.004, step * 0.4, 0.5, step * 0.35)
        music.add(s, t, db)
        t += step
        k += 1


def place_drums(t0, t1, db, hats=True, kick_every=1):
    k = 0
    t = t0
    while t < t1 - 0.01:
        if k % (2 * kick_every) == 0:
            music.add(kick(), t, db)
        if hats:
            music.add(hat(), t + BEAT / 2, db - 9, pan=0.25)
            music.add(hat(0.05, 0.015), t, db - 15, pan=-0.2)
        t += BEAT / 2
        k += 1


def place_arp(notes, t0, t1, step, db, cutoff0=900, cutoff1=4000, tau=0.25, pan_spread=0.4):
    times = np.arange(t0, t1, step)
    for k, t in enumerate(times):
        u = k / max(1, len(times) - 1)
        s = pluck(note(notes[k % len(notes)]), 0.9, tau)
        s = filt(s, "low", cutoff0 * (cutoff1 / cutoff0) ** u)
        both(music, music_verb, s, t, db, pan=pan_spread * np.sin(k * 1.7), wet_db=-4)


# A · bande-annonce
music.add(filt(sine(note("D1"), int(7.0 * SR)) * adsr(int(7.0 * SR), 1.2, 0.5, 0.9, 1.2), "low", 120), 0.15, -14)
place_pad(["D2", "A2", "D3"], 0.4, 6.4, -12, cutoff=380, attack=2.0, release=1.2)
shim = sine(note("A5"), int(5.6 * SR)) * 0.5 + sine(note("D6"), int(5.6 * SR)) * 0.35
shim *= adsr(len(shim), 1.5, 0.5, 0.8, 1.6) * (0.75 + 0.25 * np.sin(2 * np.pi * 3.1 * np.arange(len(shim)) / SR))
both(music, music_verb, shim, 1.2, -30, wet_db=0)
for e in ev("braam"):
    b = braam(["D2", "A2", "D3", "F3"] if e["n"] == 1 else ["Bb1", "F2", "Bb2", "D3"])
    both(music, music_verb, b, e["t"] - 0.02, -6, wet_db=-3)
    music.add(impact(2.4, 70, 30, 0.9, 0.25), e["t"] - 0.01, -7)
# « Jamais l'ascension » : tout chute d'une octave
tilt = ev1("tilt")
n = int(1.2 * SR)
drop = (sine(note("D3") * 2 ** (-np.linspace(0, 2, n)), n) * 0.6 + saw(note("D2") * 2 ** (-np.linspace(0, 1, n)), n) * 0.2)
drop = filt(drop, "low", 900) * adsr(n, 0.01, 0.2, 0.7, 0.8)
both(music, music_verb, drop, tilt - 0.05, -14, wet_db=-2)

# B · camp de base : le studio se compile
boot = ev1("boot")
compile_e = ev("compile")[0]
c0, c1 = compile_e["t"], compile_e["t"] + compile_e["dur"]
collapse = ev1("collapse")
zero = ev1("zero")
place_pad(["D3", "F3", "A3", "C4", "E4"], boot + 0.2, collapse + 0.05, -15, cutoff=500, bright=2600, attack=1.4, release=0.25)
music.add(filt(sine(note("D2"), int((collapse - boot) * SR)) * adsr(int((collapse - boot) * SR), 1.0, 0.2, 0.8, 0.2), "low", 200), boot + 0.2, -16)
place_arp(["D4", "F4", "A4", "C5", "E5", "C5", "A4", "F4"], c0, c1, BEAT / 4, -21, 700, 4200, tau=0.18)
place_bass(["D2"], c0, c1, BEAT / 2, -19, cutoff=380)
both(music, music_verb, pad(["D3", "A3", "D4", "F4", "A4"], 1.3, cutoff=3200, attack=0.005, release=1.0), c1, -14, wet_db=-2)
music.add(reverse_swell(zero - collapse, 1600), collapse, -16)
both(music, music_verb, bell(note("D6"), 4.0, 2.4, 0.4), zero, -18, wet_db=2)

# C · l'origine : boîte à musique
light_on = ev1("chime")
pull = ev("whoosh")[0]["t"]
flash = ev1("flash")
c_start = zero + 0.1
place_pad(["Bb2", "D3", "F3", "A3"], c_start, c_start + 2.1, -17, cutoff=1300)
place_pad(["G2", "Bb2", "D3", "F3", "A3"], c_start + 2.1, light_on, -17, cutoff=1300)
place_pad(["F2", "A2", "C3", "E3", "A3"], light_on, flash + 0.1, -16, cutoff=1700, release=0.6)
mel = ["A5", "F5", "D6", "C6", "A5", "G5"]
for k, nn in enumerate(mel):
    t = T(8) + k * (light_on - T(8)) / len(mel)
    both(music, music_verb, bell(note(nn), 2.0, 0.8), t, -22, pan=0.25 * np.sin(k), wet_db=0)
both(music, music_verb, chime_chord(["D6", "A6", "E7"], 3.5, 1.6), light_on, -20, wet_db=1)
for e in ev("ping"):
    pans = [-0.55, 0.55, 0.65, -0.65, 0.0]
    both(music, music_verb, bell(note(["D5", "F5", "G5", "A5", "C6"][e["i"]]), 2.2, 1.0), e["t"], -21, pan=pans[e["i"]], wet_db=0)

# D · le fondateur
reveal2 = ev1("reveal2")
unlock = ev1("unlock")
d_end = ev("chapter")[2]["t"]  # chapitre III
place_pad(["Bb2", "D3", "F3", "C4"], flash, reveal2, -16, cutoff=1400, attack=0.6, release=0.5)
place_pad(["F2", "C3", "F3", "A3", "C4"], reveal2, d_end + 0.1, -15, cutoff=2000, attack=0.25, release=0.5)
for k, nn in enumerate(["F5", "A5", "C6", "F6"]):
    both(music, music_verb, pluck(note(nn), 1.4, 0.5), unlock + k * 0.075, -17, pan=-0.3 + 0.2 * k, wet_db=-1)

# E · l'ascension : pulsation
e0 = ev("type")[0]["t"]
fall = ev("fall")[0]
glitch = ev("glitch")[0]
shrink = ev1("shrink")
f_start = ev("chapter")[3]["t"]  # chapitre IV
place_drums(e0, fall["t"], -16)
place_bass(["D2", "D2", "F2", "G2"], e0, fall["t"], BEAT / 2, -18, cutoff=450)
place_pad(["D3", "F3", "A3", "C4"], d_end, fall["t"] + 0.05, -19, cutoff=1100, attack=0.4, release=0.3)
place_pad(["F2", "C3", "F3", "A3"], shrink, f_start + 0.2, -18, cutoff=1500, attack=0.5, release=0.6)
place_arp(["F4", "A4", "C5", "A4"], shrink + 0.2, f_start, BEAT / 2, -24, 1400, 2400, tau=0.3)

# F · le golem
lv = ev("levelup")
g_end = ev("chapter")[4]["t"]  # chapitre V
place_pad(["D3", "F3", "A3"], f_start, lv[0]["t"], -17, cutoff=1200, attack=0.8, release=0.4)
place_pad(["Bb2", "D3", "F3", "A3"], lv[0]["t"], lv[1]["t"], -16, cutoff=1700, attack=0.08, release=0.4)
place_pad(["C3", "E3", "G3", "C4"], lv[1]["t"], g_end + 0.1, -15, cutoff=2200, attack=0.08, release=0.6)
core = ev1("core")
n = int((g_end - core + 0.5) * SR)
hum = (sine(note("D2"), n) * 0.6 + sine(note("A2"), n) * 0.3 + sine(note("D3") * (1 + 0.003 * np.sin(2 * np.pi * 0.9 * np.arange(n) / SR)), n) * 0.2)
music.add(hum * adsr(n, 0.4, 0.2, 0.8, 0.6), core, -22)

# G · la règle : ostinato sombre, puis silence
title = ev1("title")
silence = ev("silence")[0]
sv0, sv1 = silence["t"], silence["until"]
place_bass(["D2", "D2", "D2", "D3"], title, sv0, BEAT / 2, -18, cutoff=600)
place_pad(["D2", "A2", "F3"], title, sv0 + 0.03, -16, cutoff=900, attack=0.5, release=0.05)
n = int((sv0 - (title + 1.8)) * SR)
trem = saw(note("A4"), n) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * np.arange(n) / SR))
trem = filt(trem, "low", 2500) * adsr(n, 1.5, 0.1, 0.9, 0.03)
both(music, music_verb, trem, title + 1.8, -28, pan=0.3)
place_drums(title, sv0, -18, hats=False, kick_every=2)
both(music, music_verb, impact(3.0, 60, 32, 1.4, 0.2, 500) + bell(note("D2"), 3.0, 1.6, 0.3) * 0.6, title, -12, wet_db=-1)
swell_dur = sv0 - T(23)
music.add(reverse_swell(swell_dur, 3000) * 0.9, T(23), -18)
# le souffle suspendu
n = int((sv1 - sv0) * SR)
air = (sine(note("A6"), n) * 0.5 + sine(note("E7"), n) * 0.3) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * np.arange(n) / SR))
air *= adsr(n, 0.35, 0.2, 0.8, 0.4)
music.add(reverse_swell(0.55, 2500), sv1 - 0.55, -20)

# H · l'objectif
boom = ev1("boom")
asc = ev("riser")[0]
place_drums(boom, asc["t"], -15)
place_bass(["Bb1", "Bb1", "Bb2", "Bb1", "C2", "C2", "C3", "C2", "D2", "D2", "D3", "D2", "Bb1", "Bb1", "Bb2", "C2"], boom, asc["t"], BEAT / 2, -17, cutoff=520)
chords_h = [(boom, ["Bb2", "D3", "F3", "A3"]), (T(25) + 0.85, ["C3", "E3", "G3", "C4"]), (T(27), ["D3", "F3", "A3", "D4"]), (T(28), ["Bb2", "D3", "F3", "C4"])]
for k, (t0, ch) in enumerate(chords_h):
    t1 = chords_h[k + 1][0] if k + 1 < len(chords_h) else asc["t"] + 0.1
    place_pad(ch, t0, t1, -15, cutoff=2200, attack=0.05 if k == 0 else 0.15, release=0.35)
music.add(impact(3.5, 110, 30, 1.5, 0.7, 1200), boom - 0.01, -9)

# I · l'ascension finale, sommet, appel à l'action
place_pad(["C3", "G3", "C4", "D4"], asc["t"], asc["t"] + asc["dur"], -15, cutoff=800, bright=4000, attack=0.8, release=0.1)
summit = ev1("summit")
both(music, music_verb, impact(4.0, 100, 30, 1.6, 0.6, 1500), summit - 0.01, -6, wet_db=-4)
cta_end = ev1("logo")
chords_i = [(summit, ["D3", "F#3", "A3", "D4"]), (T(30) + 1.45, ["Bb2", "D3", "F3", "Bb3"]), (T(31), ["F2", "C3", "F3", "A3"]), (T(31) + 0.85, ["C3", "E3", "G3", "C4"])]
for k, (t0, ch) in enumerate(chords_i):
    t1 = chords_i[k + 1][0] if k + 1 < len(chords_i) else cta_end - 0.6
    place_pad(ch, t0, t1, -13, cutoff=2600, attack=0.1, release=0.5)
    both(music, music_verb, choir(ch[:3], t1 - t0, attack=0.4, release=0.8), t0, -15, wet_db=-1)
place_drums(summit, cta_end - 0.75, -17, hats=True, kick_every=2)
place_bass(["D2", "D2", "D2", "D2", "Bb1", "Bb1", "F2", "F2", "C2", "C2"], summit, cta_end - 0.75, BEAT / 2, -18, cutoff=500)
place_arp(["D5", "A4", "F#5", "A4", "D5", "A4", "E5", "A4"], summit + 0.3, cta_end - 0.75, BEAT / 4, -26, 1800, 3500, tau=0.2)
music.add(reverse_swell(0.8, 3500), cta_end - 0.8, -14)

# J · signature
logo = ev1("logo")
both(music, music_verb, impact(5.0, 90, 28, 2.0, 0.6, 1300), logo - 0.01, -3, wet_db=-3)
place_pad(["D2", "A2", "D3", "F#3", "A3", "E4"], logo, DUR - 0.4, -12, cutoff=3000, attack=0.08, release=1.2)
both(music, music_verb, choir(["D3", "F#3", "A3"], DUR - logo - 0.8, 0.3, 1.2), logo, -14, wet_db=0)
both(music, music_verb, chime_chord(["D6", "F#6", "A6", "E7"], 4.0, 2.0), ev1("tag"), -22, wet_db=2)

# ------------------------------------------------------------------ SFX
for e in EVENTS:
    t, k = e["t"], e["type"]
    if k == "ignite":
        s = sine(note("D6") * 2 ** (np.linspace(-0.5, 0, int(1.4 * SR))), int(1.4 * SR)) * expdec(int(1.4 * SR), 0.5, 0.05)
        both(sfx, sfx_verb, s * 0.5 + bell(note("A6"), 1.4, 0.6) * 0.4, t, -16, wet_db=2)
        sfx.add(impact(2.5, 55, 28, 1.0, 0.1, 300), t, -16)
    elif k == "reveal":
        both(sfx, sfx_verb, whoosh(1.6, 200, 2500, 0.7), t - 0.3, -22, wet_db=-2)
    elif k == "tilt":
        both(sfx, sfx_verb, whoosh(1.1, 3500, 250, 0.35), t, -13, wet_db=-4)
    elif k == "boot":
        for j in range(6):
            sfx.add(blip(600 * 1.26 ** j, 900 * 1.26 ** j, 0.05, "tri"), t + j * 0.06, -26, pan=-0.6 + j * 0.24)
        sfx.add(filt(noise(int(0.5 * SR)), "bandpass", [1500, 6000]) * adsr(int(0.5 * SR), 0.2, 0.1, 0.5, 0.2), t, -34)
    elif k == "draw":
        both(sfx, sfx_verb, sweep(noise(int(0.9 * SR), "pink"), "bandpass", 400, 3200, order=1) * adsr(int(0.9 * SR), 0.3, 0.2, 0.7, 0.3) * 0.5, t, -24, wet_db=-3)
    elif k == "snap":
        both(sfx, sfx_verb, bell(note("A6"), 2.0, 0.7) + bell(note("E7"), 2.0, 0.5) * 0.5, t, -17, pan=0.1, wet_db=1)
        sfx.add(click(5, 3000, 9000), t, -20)
    elif k == "decode":
        for j in range(e["n"]):
            for r in range(3):
                sfx.add(click(4, 2500, 8000), t + j * e["step"] + r * 0.022, -30 - r * 3, pan=-0.5 + j / e["n"])
            sfx.add(blip(1800 + j * 90, 1700 + j * 90, 0.03), t + j * e["step"] + 0.25, -32)
    elif k == "compile":
        n = int(e["dur"] * SR)
        u = np.linspace(0, 1, n)
        tick_t = np.cumsum(0.09 * (1 - u[:: int(SR * 0.05)] * 0.6))
        for tt in tick_t:
            if tt < e["dur"]:
                sfx.add(click(3, 4000, 9000), t + tt, -33, pan=0.3)
        sfx.add(sweep(noise(n, "pink"), "bandpass", 300, 2500, order=1) * u ** 2 * 0.4, t, -28)
    elif k == "check":
        sfx.add(blip(1200, 1800, 0.06, "tri") * 0.7, t, -24, pan=0.2)
        sfx.add(blip(1800, 1800, 0.08, "sine"), t + 0.06, -27, pan=0.2)
    elif k == "impact":
        both(sfx, sfx_verb, impact(2.5, 120, 40, 0.8, 0.4), t, -14, wet_db=-4)
    elif k == "collapse":
        sfx.add(whoosh(0.7, 3000, 300, 0.85), t, -20)
    elif k == "zero":
        sfx.add(blip(2400, 2400, 0.12), t, -30)
    elif k == "chapter":
        sfx.add(blip(1400, 1400, 0.05, "tri"), t, -32, pan=-0.6)
        sfx.add(blip(2100, 2100, 0.05, "tri"), t + 0.07, -34, pan=-0.6)
    elif k == "toast":
        both(sfx, sfx_verb, bell(note("A5"), 1.2, 0.4) * 0.8, t + 0.02, -22, pan=0.55, wet_db=-2)
        both(sfx, sfx_verb, bell(note("E6"), 1.6, 0.6) * 0.8, t + 0.14, -22, pan=0.55, wet_db=-2)
    elif k == "block":
        base = 140 if e["m"] in ("grass", "earth", "rock") else 210 if e["m"] in ("wood", "plank") else 320
        f = base * 2 ** (max(e["k"], 0) * 0.17) * (1 + (rng.random() - 0.5) * 0.08)
        n = int(0.18 * SR)
        tt = np.arange(n) / SR
        thock = sine(f * (1 + 0.6 * np.exp(-tt / 0.01)), n) * np.exp(-tt / 0.05)
        knock = filt(noise(n), "bandpass", [f * 3, f * 9]) * np.exp(-tt / 0.012) * 0.5
        sig = (thock + knock) * (0.55 if e.get("soft") else 1.0)
        if e["m"] in ("glow", "crystal"):
            sig = sig + bell(note("A6") if e["m"] == "glow" else note("E6"), 1.2, 0.4)[:n] * 0.3
        sfx.add(sig, t, -21 + rng.random() * 2, pan=(rng.random() - 0.5) * 0.5)
    elif k == "whoosh":
        both(sfx, sfx_verb, whoosh(1.3, 2600, 300, 0.3), t, -18, wet_db=-3)
    elif k == "flash":
        both(sfx, sfx_verb, whoosh(0.7, 500, 6000, 0.85), t - 0.45, -20)
        both(sfx, sfx_verb, impact(2.0, 80, 35, 0.6, 0.3, 2000) * 0.6 + chime_chord(["D6", "A6"], 2.0, 1.0) * 0.5, t, -16, wet_db=0)
    elif k == "frame":
        sfx.add(whoosh(0.35, 800, 5000, 0.6), t, -26, pan=-0.4)
    elif k == "scan":
        n = int(e["dur"] * SR)
        u = np.linspace(0, 1, n)
        sc = sweep(noise(n), "bandpass", 600, 5000, order=1) * (0.35 + 0.65 * (np.sin(2 * np.pi * 22 * np.arange(n) / SR) > 0)) * adsr(n, 0.05, 0.1, 0.8, 0.1)
        sfx.add(sc * 0.5 + blip(500, 2500, e["dur"], "sine") * 0.15, t, -24, pan=-0.45)
    elif k == "fill":
        for j in range(12):
            sfx.add(blip(900 * 2 ** (j / 12), 900 * 2 ** (j / 12), 0.03, "tri"), t + j * e["dur"] / 12, -31, pan=0.35)
    elif k == "reveal2":
        both(sfx, sfx_verb, whoosh(0.5, 1000, 6000, 0.7), t - 0.2, -27, pan=0.3)
    elif k == "unlock":
        sfx.add(impact(1.6, 90, 40, 0.5, 0.2), t, -18)
    elif k == "type":
        for j in range(e["n"]):
            tt = t + e["dur"] * (j + rng.random() * 0.6) / e["n"]
            sfx.add(click(6, 1800, 6500) + filt(noise(int(0.006 * SR)), "low", 600) * 0.6, tt, -30 + rng.random() * 4, pan=-0.2 + rng.random() * 0.2)
    elif k == "jump":
        f0 = 500 * 2 ** (e["i"] / 6)
        sfx.add(blip(f0, f0 * 2, 0.12, "sine"), t, -22, pan=0.1)
    elif k == "glitch":
        n = int(e["dur"] * SR)
        g = np.zeros(n)
        pos = 0
        while pos < n:
            ln = int(SR * (0.02 + rng.random() * 0.07))
            kind = rng.integers(0, 3)
            if kind == 0:
                seg = noise(ln) * 0.5
            elif kind == 1:
                seg = np.sign(sine(200 + rng.random() * 2500, ln)) * 0.35
            else:
                seg = np.zeros(ln)
            g[pos:pos + ln] = seg[: n - pos]
            pos += ln
        g = np.round(g * 6) / 6
        g = np.repeat(g[::6], 6)[:n]
        sfx.add(filt(g, "low", 7000) * 0.8, t, -19)
    elif k == "fall":
        n = int((e["dur"] + 0.2) * SR)
        f = 1600 * (180 / 1600) ** (np.arange(n) / n)
        both(sfx, sfx_verb, sine(f, n) * adsr(n, 0.01, 0.1, 0.8, 0.15) * 0.4, t, -20, wet_db=-2)
        sfx.add(whoosh(e["dur"] + 0.2, 3000, 400, 0.6), t, -16)
    elif k == "thud":
        sfx.add(impact(1.6, 110, 38, 0.35, 0.6, 700), t, -10)
        sfx.add(filt(noise(int(0.4 * SR), "pink"), "bandpass", [300, 3000]) * expdec(int(0.4 * SR), 0.08), t, -22)
    elif k == "shrink":
        both(sfx, sfx_verb, whoosh(0.7, 4000, 400, 0.5), t, -20, wet_db=-3)
    elif k == "card":
        sfx.add(whoosh(0.35, 700, 4500, 0.65), t - 0.15, -26, pan=0.35)
        sfx.add(blip(700, 520, 0.06, "sine"), t + 0.18, -24, pan=0.35)
    elif k == "gather":
        n = int((e["dur"] + 0.3) * SR)
        g = np.zeros(n)
        cnt = 70
        for j in range(cnt):
            u = (j / cnt) ** 0.7
            p = int(u * e["dur"] * SR)
            gr = bell(note("A5") * 2 ** (rng.integers(0, 12) / 12 * 2), 0.25, 0.06)
            g[p:p + len(gr)] += gr[: n - p] * (0.3 + 0.7 * u)
        both(sfx, sfx_verb, g * 0.5, t, -24, wet_db=0)
    elif k == "shards":
        for j in range(14):
            tt = t + j * 0.035 + rng.random() * 0.02
            f = 300 + rng.random() * 500
            n = int(0.12 * SR)
            cl = filt(noise(n), "bandpass", [f, f * 2.4]) * expdec(n, 0.02) + sine(f * 0.3, n) * expdec(n, 0.03) * 0.5
            sfx.add(cl, tt, -22, pan=(rng.random() - 0.5) * 1.2)
        sfx.add(impact(2.0, 70, 30, 0.8, 0.5, 400), t + 0.45, -16)
    elif k == "core":
        both(sfx, sfx_verb, whoosh(0.8, 300, 3000, 0.9), t - 0.5, -22, wet_db=-2)
        both(sfx, sfx_verb, chime_chord(["D5", "A5"], 2.0, 1.2), t + 0.1, -22, wet_db=0)
    elif k == "levelup":
        seq = ["D5", "F5", "A5", "D6"] if e["n"] == 2 else ["F5", "A5", "C6", "F6", "A6"]
        for j, nn in enumerate(seq):
            both(sfx, sfx_verb, pluck(note(nn), 1.2, 0.35) * 0.9 + tri(note(nn), int(1.2 * SR)) * expdec(int(1.2 * SR), 0.15) * 0.2, t + j * 0.06, -16, pan=-0.3 + j * 0.15, wet_db=-1)
        sfx.add(impact(1.8, 90, 40, 0.5, 0.3, 1200), t, -15)
        both(sfx, sfx_verb, whoosh(0.6, 400, 4000, 0.15), t, -24, wet_db=-2)
    elif k == "title":
        both(sfx, sfx_verb, whoosh(1.0, 300, 2000, 0.8), t - 0.7, -26)
    elif k == "slash":
        n = int(0.35 * SR)
        sl = sweep(noise(n), "high", 1500, 9000) * adsr(n, 0.01, 0.05, 0.5, 0.2)
        both(sfx, sfx_verb, sl * 0.6 + metal(1900, 0.9, 0.3)[:n] * 0.6, t - 0.03, -17, pan=0.0, wet_db=-1)
        sfx.add(metal(1900, 1.2, 0.4), t + 0.05, -22)
    elif k == "shatter":
        for j in range(40):
            tt = t + rng.random() ** 1.6 * 0.6
            sfx.add(blip(3000 + rng.random() * 5000, 2500 + rng.random() * 4000, 0.02 + rng.random() * 0.04), tt, -30 - rng.random() * 6, pan=-0.8 + rng.random() * 0.6)
        sfx.add(filt(noise(int(0.5 * SR)), "high", 3000) * expdec(int(0.5 * SR), 0.09), t, -23, pan=-0.4)
    elif k == "coins":
        for j in range(12):
            tt = t + j * 0.05 + rng.random() * 0.06
            both(sfx, sfx_verb, metal(2200 + rng.random() * 1800, 0.5, 0.12), tt, -25, pan=0.2 + rng.random() * 0.6, wet_db=-2)
        for j in range(8):
            both(sfx, sfx_verb, bell(note(["A6", "D7", "E7", "F#6"][j % 4]), 1.0, 0.3), t + 0.4 + j * 0.08, -29, pan=0.3 + rng.random() * 0.5, wet_db=1)
    elif k == "boom":
        both(sfx, sfx_verb, impact(3.0, 140, 32, 1.2, 0.8, 2500), t - 0.005, -12, wet_db=-3)
    elif k == "ring":
        for j in range(26):
            sfx.add(click(3, 3500, 8000), t + j * e["dur"] / 26, -30, pan=np.sin(j / 26 * 2 * np.pi) * 0.5 - 0.3)
    elif k == "slot":
        sfx.add(impact(0.6, 160, 70, 0.08, 0.3, 1800), t, -18, pan=-0.2 + e["k"] * 0.2)
        sfx.add(blip(note(["D5", "F5", "A5"][e["k"]]), note(["D5", "F5", "A5"][e["k"]]), 0.12, "tri"), t + 0.02, -25, pan=-0.2 + e["k"] * 0.2)
    elif k == "check2":
        both(sfx, sfx_verb, bell(note(["A5", "C6", "D6"][e["k"]]), 1.2, 0.4), t + 0.05, -22, pan=0.5, wet_db=-1)
        sfx.add(click(4, 2000, 6000), t + 0.05, -26, pan=0.5)
    elif k == "victory":
        both(sfx, sfx_verb, chime_chord(["F5", "A5", "C6", "G6"], 2.0, 0.9), t, -20, pan=0.5, wet_db=0)
    elif k == "riser":
        both(sfx, sfx_verb, riser(e["dur"] + 0.05), t, -15, wet_db=-4)
        for j in range(24):
            tt = t + e["dur"] * (1 - (1 - j / 24) ** 1.7)
            sfx.add(filt(noise(int(0.05 * SR)), "bandpass", [1500, 6000]) * expdec(int(0.05 * SR), 0.012), tt, -30 + j * 0.4, pan=(-1) ** j * 0.2)
    elif k == "summit":
        both(sfx, sfx_verb, chime_chord(["D6", "F#6", "A6"], 3.0, 1.5), t, -18, wet_db=2)
    elif k == "button":
        both(sfx, sfx_verb, whoosh(0.5, 500, 4000, 0.8), t - 0.3, -24)
        sfx.add(blip(600, 900, 0.1, "tri"), t + 0.15, -26)
    elif k == "press":
        sfx.add(impact(0.5, 200, 90, 0.05, 0.4, 3000), t, -16)
        both(sfx, sfx_verb, pluck(note("A5"), 1.0, 0.3) + pluck(note("D6"), 1.0, 0.3), t + 0.04, -18, wet_db=-1)
    elif k == "tile":
        sfx.add(whoosh(0.3, 600, 4000, 0.7), t - 0.15, -27, pan=-0.4 if e["k"] == 0 else 0.4)
        sfx.add(blip(note("D5") * (1.5 if e["k"] else 1), note("D5") * (1.5 if e["k"] else 1), 0.1, "tri"), t + 0.12, -23, pan=-0.4 if e["k"] == 0 else 0.4)
    elif k == "logo":
        sfx.add(reverse_swell(1.0, 5000) * 0.8, t - 1.0, -16)
    elif k == "sparkle":
        n = int(1.4 * SR)
        f = 2600 * 2 ** (np.linspace(0, 1, n))
        sp = sine(f, n) * expdec(n, 0.3, 0.01) * (0.5 + 0.5 * np.sin(2 * np.pi * 18 * np.arange(n) / SR))
        both(sfx, sfx_verb, sp * 0.4 + bell(note("D7"), 1.4, 0.6) * 0.5, t, -22, pan=0.15, wet_db=2)


# ------------------------------------------------------------------ réverbération
def make_ir(rt=3.2, seed=3):
    r = np.random.default_rng(seed)
    n = int(rt * SR)
    t = np.arange(n) / SR
    ir = np.zeros((2, n))
    for c in range(2):
        w = r.standard_normal(n)
        lo = filt(w, "low", 2800) * np.exp(-6.91 * t / rt)
        hi = filt(w, "high", 2800) * np.exp(-6.91 * t / (rt * 0.35))
        x = lo + hi * 0.5
        x[: int(0.018 * SR)] = 0
        for k in range(8):
            p = int((0.008 + r.random() * 0.06) * SR)
            x[p] += (r.random() - 0.5) * 3
        ir[c] = x
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


IR = make_ir()


def reverb(bus, gain=0.9):
    return np.stack([signal.fftconvolve(bus.x[c], IR[c])[:N] for c in range(2)]) * gain


music_mix = music.x + reverb(music_verb, 0.55)
sfx_mix = sfx.x + reverb(sfx_verb, 0.55)

# coupure franche sur « sans voix » : seule une nappe d'air reste
gate = np.ones(N)
a, b = int(sv0 * SR), int((sv1 - 0.55) * SR)
f = int(0.03 * SR)
gate[a:a + f] = np.linspace(1, 0.0, f)
gate[a + f:b] = 0.0
music_mix = music_mix * gate
air_bus, air_rev = Bus(), Bus()
air_bus.add(air, sv0 + 0.05, -33)
air_rev.add(air, sv0 + 0.05, -36)
music_mix = music_mix + air_bus.x + reverb(air_rev, 0.6)

# bégaiement de la musique pendant le bug, puis chute
g0, g1 = glitch["t"], glitch["t"] + glitch["dur"]
stut = np.ones(N)
step = int(BEAT / 4 * SR)
for i, p in enumerate(range(int(g0 * SR), int(g1 * SR), step)):
    if rng.random() < 0.45:
        stut[p:p + step] = 0.15
fa = int(fall["t"] * SR)
fb = int(shrink * SR)
stut[fa:fb] = np.minimum(stut[fa:fb], np.linspace(1, 0.1, fb - fa) ** 2)
music_mix *= signal.savgol_filter(stut, 101, 1)

# ------------------------------------------------------------------ voix + ducking
sr_vo, vo = wavfile.read(ROOT / "audio" / "vo.wav")
vo = vo.astype(np.float64) / 32768
if sr_vo != SR:
    vo = signal.resample_poly(vo, SR, sr_vo)
vo = np.pad(vo, (0, max(0, N - len(vo))))[:N]
# légère compression de la voix
env = np.abs(signal.hilbert(vo))
env = signal.sosfilt(sos("low", 12), env)
gr = np.minimum(1, (0.25 / np.maximum(env, 1e-6)) ** 0.35)
vo_c = vo * np.where(env > 0.25, gr, 1.0)
vo_c = norm(vo_c, 0.9)
vo_st = np.stack([vo_c, vo_c])

# enveloppe de parole → ducking musique (-7 dB) et SFX (-3 dB)
spk = signal.sosfilt(sos("low", 4), np.abs(vo_c))
spk = np.clip(spk / 0.06, 0, 1)
hold = maximum_filter1d(spk, size=int(0.25 * SR))
duck = uniform_filter1d(hold, int(0.08 * SR))
music_mix *= 10 ** ((-7 * duck) / 20)
sfx_mix *= 10 ** ((-3 * duck) / 20)

# ------------------------------------------------------------------ niveaux & master
meter = pyln.Meter(SR)


def lufs(x):
    return meter.integrated_loudness(x.T)


L_music, L_sfx, L_vo = lufs(music_mix), lufs(sfx_mix), lufs(vo_st)
print(f"avant réglage : musique {L_music:.1f} LUFS · SFX {L_sfx:.1f} · VO {L_vo:.1f}")
# objectifs relatifs : VO devant, musique ~10 dB dessous, SFX ~8 dB dessous (ponctuels)
music_mix *= 10 ** ((L_vo - 11 - L_music) / 20)
sfx_mix *= 10 ** ((L_vo - 9 - L_sfx) / 20)
# assainissement du grave : passe-haut 32 Hz et plateau -4 dB sous ~90 Hz sur la musique
def low_shelf_cut(x, fc=90, db=-4):
    lo = np.stack([filt(c, "low", fc, 2) for c in x])
    return x + lo * (10 ** (db / 20) - 1)


music_mix = np.stack([filt(c, "high", 32, 2) for c in low_shelf_cut(music_mix)])
sfx_mix = np.stack([filt(c, "high", 28, 2) for c in sfx_mix])
music_mix *= 10 ** ((L_vo - 11 - lufs(music_mix)) / 20)
bed = music_mix + sfx_mix


def momentary(x, t, win=0.4):
    a = int(t * SR)
    seg = x[:, a:a + int(win * SR)]
    return meter.integrated_loudness(seg.T) if seg.shape[1] > int(0.4 * SR) - 1 else -99


print("instant   VO     fond   (LUFS momentané, 400 ms)")
for name, tt in [("braam", 3.65), ("compile", 11.5), ("origine", 16.0), ("unlock", 22.75), ("bug", 26.8), ("chute", 27.95),
                 ("golem", 33.4), ("slash", 38.08), ("boom", 44.15), ("sommet", 51.17), ("cta", 53.0), ("logo", 56.06)]:
    print(f"{name:8s} {tt:5.2f}  {momentary(vo_st, tt):6.1f} {momentary(bed, tt):6.1f}")


def master(x, target=-14.0, ceiling=-1.0):
    # glue douce
    x = np.tanh(x * 1.1) / 1.1
    l = lufs(x)
    x = x * 10 ** ((target - l) / 20)
    # limiteur à anticipation (crête échantillon, suréchantillonnée ×4 pour approcher la crête vraie)
    c = 10 ** (ceiling / 20)
    up = signal.resample_poly(np.max(np.abs(x), axis=0), 4, 1)
    peak = np.maximum(np.abs(up[::4]), np.max(np.abs(x), axis=0))
    g = np.minimum(1, c / np.maximum(peak, 1e-9))
    g = -maximum_filter1d(-g, size=int(0.005 * SR))
    g = uniform_filter1d(g, int(0.004 * SR))
    g = np.minimum(g, 1)
    x = x * g
    return x


mix = master(bed + vo_st)
stem = master(bed, target=-16.0)
# fondu de fin
fo = int(0.35 * SR)
end = int(DUR * SR)
for y in (mix, stem):
    y[:, end - fo:end] *= np.linspace(1, 0, fo)
    y[:, end:] = 0
mix, stem = mix[:, :end], stem[:, :end]
print(f"master : {lufs(mix):.1f} LUFS, crête {20 * np.log10(np.max(np.abs(mix))):.2f} dBFS · stem {lufs(stem):.1f} LUFS")
(ROOT / "out").mkdir(exist_ok=True)
wavfile.write(ROOT / "out" / "mix.wav", SR, (mix.T * 32767).astype(np.int16))
wavfile.write(ROOT / "out" / "altherion-vsl_musique-sfx.wav", SR, (stem.T * 32767).astype(np.int16))
print("→ out/mix.wav, out/altherion-vsl_musique-sfx.wav")
