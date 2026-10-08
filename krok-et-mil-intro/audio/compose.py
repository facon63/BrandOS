"""Musique + SFX de l'intro Krok et Mil (chiptune + funk/électro, 128 BPM), mixage et mastering.

Usage :
  python3 audio/compose.py                      # -> build/audio/intro_mix.wav, music.wav, sfx.wav, stinger.wav
  python3 audio/compose.py --excerpt 6.5625 3   # + extrait de 3 s à partir de 6,5625 s

Grille : 1 temps = 60/128 = 0,46875 s. Le DROP tombe au temps 16 = 7,5 s exactement.
Les instants des SFX sont dans audio/cues.json (partagé avec l'animation).
"""
import argparse, json, os
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

from synth import (SR, Track, adsr, bandpass, bitcrush, exp_decay, highpass, lowpass, make_ir, midi, noise, pan,
                   reverb, saw, sine, softclip, square, sweep_lowpass, tri)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BPM = 128
BEAT = 60 / BPM
DUR = 10.0
B = lambda b: b * BEAT  # noqa: E731


# ============================================================== instruments (renvoient du mono)
def kick(heavy=False):
    n = int((0.5 if heavy else 0.35) * SR)
    t = np.arange(n) / SR
    f = (120 if heavy else 150) * np.exp(-t / (0.045 if heavy else 0.03)) + (50 if heavy else 54)
    body = sine(f, n) * exp_decay(n, 0.26 if heavy else 0.17)
    click = highpass(noise(n), 3000) * exp_decay(n, 0.0025) * 0.5
    return softclip(body + click, 1.6) * 0.95


def clap(bright=1.0):
    n = int(0.3 * SR)
    out = np.zeros(n)
    for k, d in enumerate([0, 0.011, 0.023]):
        i = int(d * SR)
        m = n - i
        out[i:] += noise(m) * exp_decay(m, 0.006 if k < 2 else 0.09) * (0.8 if k < 2 else 1.0)
    return bandpass(out, 900, 5200 * bright) * 1.6


def snare():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    tone = sine(190 * np.exp(-t / 0.08) + 160, n) * exp_decay(n, 0.06)
    nz = bandpass(noise(n), 1500, 9000) * exp_decay(n, 0.09)
    return softclip(tone * 0.7 + nz * 0.9, 1.3)


def hat(open_=False):
    n = int((0.22 if open_ else 0.06) * SR)
    return highpass(noise(n), 7500) * exp_decay(n, 0.09 if open_ else 0.018) * 0.55


def tom(f0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    return softclip(sine(f0 * (1 + 0.6 * np.exp(-t / 0.03)), n) * exp_decay(n, 0.2) + lowpass(noise(n), 1200) * exp_decay(n, 0.04) * 0.3, 1.4)


def crash(dur=1.6):
    n = int(dur * SR)
    nz = highpass(noise(n), 3500) + bandpass(noise(n), 5000, 11000) * 0.6
    return nz * exp_decay(n, 0.55) * 0.5


def slap_bass(m, dur, pop=False, drive=1.0):
    n = int(dur * SR)
    f = midi(m + (12 if pop else 0))
    raw = saw(f, n) * 0.6 + square(f, n, 0.5) * 0.4
    t = np.arange(n) / SR
    fc = 380 + (3600 if pop else 2400) * np.exp(-t / 0.07)
    y = sweep_lowpass(raw, fc, q=2.6)
    y *= adsr(n, a=0.002, d=0.09, s=0.55, r=0.03)
    trans = bandpass(noise(n), 1200, 5000) * exp_decay(n, 0.005) * (0.7 if pop else 0.4)
    sub = sine(f / (2 if pop else 1), n) * adsr(n, 0.004, 0.1, 0.6, 0.03) * 0.3
    return softclip((y + trans + sub) * drive, 1.2) * 0.8


def dist_bass(m, dur):
    n = int(dur * SR)
    f = midi(m)
    y = saw(f, n) + saw(f * 1.006, n) * 0.6
    y = lowpass(softclip(y, 3.0), 1400)
    return (y + sine(f, n) * 0.4) * adsr(n, 0.003, 0.08, 0.7, 0.03) * 0.55


def chip(m, dur, duty=0.25, crush=False, decay=0.12):
    n = int(dur * SR)
    y = square(midi(m), n, duty, blep=False) * np.maximum(exp_decay(n, decay), 0.25) * adsr(n, 0.001, 0.02, 1.0, 0.01)
    if crush:
        y = bitcrush(y, 5, 4)
    return lowpass(y, 9000) * 0.32


def lead(m, dur, bright=1.0, vib=True):
    n = int(dur * SR)
    t = np.arange(n) / SR
    v = 1 + (0.009 * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.12) / 0.1, 0, 1) if vib else 0)
    f = midi(m) * v
    y = saw(f * 1.004, n) + saw(f * 0.996, n) + 0.5 * square(f / 2, n, 0.5)
    fc = (1800 + 5200 * bright) * (0.55 + 0.45 * np.exp(-t / 0.25))
    y = sweep_lowpass(y, fc, q=1.2)
    return y * adsr(n, 0.006, 0.12, 0.75, 0.06) * 0.28


def stab(ms, dur, bright=1.0):
    n = int(dur * SR)
    y = sum(saw(midi(m), n) for m in ms) / len(ms)
    t = np.arange(n) / SR
    y = sweep_lowpass(y, 600 + 3000 * bright * np.exp(-t / 0.06), q=1.8)
    return y * adsr(n, 0.002, 0.06, 0.3, 0.03) * 0.5


def pad(ms, dur, cutoff=1600):
    n = int(dur * SR)
    y = sum(saw(midi(m) * d, n) for m in ms for d in (0.997, 1.003)) / (2 * len(ms))
    return lowpass(y, cutoff) * adsr(n, 0.08, 0.3, 0.8, min(0.6, dur * 0.5)) * 0.45


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    nz = noise(n)
    y = np.zeros(n)
    for i in range(0, n, 256):
        fc = 400 + 7000 * k[i] ** 2
        y[i:i + 256] = nz[i:i + 256]
    y = sweep_lowpass(y, 400 + 8000 * k ** 2, q=3.0)
    tone = sine(180 * 2 ** (3 * k), n) * 0.35
    return (y * 0.6 + tone) * (k ** 1.6) * 0.8


# ============================================================== SFX (mono)
def sfx_coin():
    """« Coin » d'accroche : arpège montant bref (pas un son existant)."""
    out = np.zeros(int(0.45 * SR))
    for i, m in enumerate([84, 88, 91, 96]):
        s = chip(m, 0.32 - i * 0.04, duty=0.5, decay=0.06)
        j = int(i * 0.035 * SR)
        out[j:j + len(s)] += s * 1.4
    return out


def sfx_whoosh(dur=0.35, up=True, lo=300, hi=4000):
    n = int(dur * SR)
    k = np.linspace(0, 1, n)
    fc = lo + (hi - lo) * (k if up else 1 - k) ** 1.5
    y = sweep_lowpass(noise(n), fc, q=1.5)
    return y * np.sin(np.pi * k) ** 1.2 * 0.9


def sfx_boing():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 260 + 140 * np.exp(-t / 0.2) * np.sin(2 * np.pi * 16 * t) + 220 * t
    return tri(f, n) * exp_decay(n, 0.18) * 0.7


def sfx_zap(seed=0):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 1900 * np.exp(-t / 0.05) + 260 + 40 * seed
    y = square(f, n, 0.5) * 0.6 + saw(f * 1.5, n) * 0.3
    return bitcrush(y, 6, 2) * exp_decay(n, 0.07) * 0.6


def sfx_pop(base=700):
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    tone = sine(base * np.exp(-t / 0.06) + 160, n) * exp_decay(n, 0.08)
    pff = lowpass(noise(n), 1800) * exp_decay(n, 0.12) * 0.5
    return tone * 0.8 + pff


def sfx_roar():
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 26 * t)
    f = 95 + 25 * np.sin(2 * np.pi * 3 * t)
    y = softclip(saw(f, n) + lowpass(noise(n), 700) * 0.8, 2.5) * trem
    return lowpass(y, 1600) * adsr(n, 0.05, 0.2, 0.7, 0.25) * 0.6


def sfx_fwoosh():
    n = int(0.6 * SR)
    k = np.linspace(0, 1, n)
    fc = 300 + 3200 * np.sin(np.pi * k) ** 0.8
    y = sweep_lowpass(noise(n), fc, q=1.2)
    crackle = (noise(n) > 0.985) * noise(n) * 0.8
    return (y + highpass(crackle, 2000)) * np.sin(np.pi * k) ** 0.7 * 0.9


def sfx_glitch(seed):
    rng = np.random.default_rng(100 + seed)
    n = int(0.16 * SR)
    out = np.zeros(n)
    for _ in range(6):
        i = rng.integers(0, n - 800)
        m = rng.integers(400, 1600)
        seg = square(rng.uniform(300, 2400), m, rng.uniform(0.2, 0.6), blep=False) * rng.uniform(0.3, 0.7)
        out[i:i + m] += seg[: n - i]
    out += noise(n) * 0.25
    return bitcrush(out, 4, int(rng.integers(3, 8))) * np.hanning(n) ** 0.3 * 0.55


def sfx_thump():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    return sine(75 * np.exp(-t / 0.1) + 38, n) * exp_decay(n, 0.12) + lowpass(noise(n), 400) * exp_decay(n, 0.05) * 0.4


def sfx_letter(i):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    base = midi([72, 74, 76, 79, 81, 84, 86, 88, 91][i % 9])
    return sine(base * (1 + 0.5 * np.exp(-t / 0.015)), n) * exp_decay(n, 0.035) * 0.6


def sfx_sparkle():
    n = int(0.9 * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(42)
    for k in range(7):
        i = int(k * 0.07 * SR)
        m = n - i
        f = rng.uniform(2600, 5200)
        out[i:] += sine(f, m) * exp_decay(m, 0.12) * 0.25
    return out


# ============================================================== arrangement
def compose():
    cues = json.load(open(os.path.join(HERE, 'cues.json')))
    drums, bass, harm, leadT, fx = (Track(DUR) for _ in range(5))

    # ---- 0 : accroche percussive
    drums.add(0.0, kick(True), 1.0)
    drums.add(0.0, crash(1.0), 0.35)
    drums.add(B(0.5), clap(), 0.6)

    # ---- U1 (temps 1-5) : do majeur, sautillant
    chordsU1 = {1: (36, [72, 76, 79, 84]), 2: (36, [72, 76, 79, 84]), 3: (41, [72, 77, 81, 84]), 4: (43, [74, 79, 83, 86]), 5: (36, [72, 76, 79, 84])}
    for b, (root, arp) in chordsU1.items():
        drums.add(B(b), kick(), 0.9)
        if b % 2 == 0:
            drums.add(B(b), clap(), 0.55)
        for s in (0.5,):
            drums.add(B(b + s), hat(), 0.5)
        drums.add(B(b + 0.25), hat(), 0.22)
        drums.add(B(b + 0.75), hat(), 0.22)
        bass.add(B(b), slap_bass(root, B(0.45)), 0.9)
        bass.add(B(b + 0.5), slap_bass(root, B(0.2), pop=True), 0.6)
        bass.add(B(b + 0.75), slap_bass(root, B(0.2)), 0.6)
        for k in range(4):
            harm.add(B(b + k * 0.25), chip(arp[k], B(0.24)), 0.7, p=-0.3)
    for b, d, m in [(1, 0.5, 79), (1.5, 0.25, 76), (1.75, 0.25, 79), (2, 0.5, 84), (3, 0.5, 81), (3.5, 0.5, 77), (4, 0.25, 83), (4.25, 0.25, 86), (4.5, 0.5, 83), (5, 0.75, 84)]:
        leadT.add(B(b), chip(m, B(d) * 0.95, duty=0.5, decay=0.25), 0.9, p=0.2)

    # ---- U2 (temps 6-10) : plus grave, légèrement distordu
    chordsU2 = {6: (36, [60, 63, 67]), 7: (36, [60, 63, 67]), 8: (32, [60, 63, 68]), 9: (34, [62, 65, 70]), 10: (34, [62, 65, 70])}
    for b, (root, ch) in chordsU2.items():
        drums.add(B(b), kick(True), 0.95)
        if b in (7, 9):
            drums.add(B(b), snare(), 0.7)
        if b in (7, 9):
            drums.add(B(b + 0.75), kick(), 0.6)
        for k in range(4):
            drums.add(B(b + k * 0.25), hat(), 0.28 if k % 2 else 0.4)
        for k, mm in enumerate([root + 12, root + 12, root + 24, root + 12]):
            bass.add(B(b + k * 0.25), dist_bass(mm, B(0.22)), 0.8)
        harm.add(B(b + 0.5), stab([m + 12 for m in ch], B(0.3), bright=0.6), 0.55, p=0.25)
        for k in range(4):
            harm.add(B(b + k * 0.25), chip(ch[k % 3] + 12, B(0.22), duty=0.125, crush=True), 0.45, p=-0.35)

    # ---- U3 (temps 11-14) : tension, la mineur, percussions lourdes
    chordsU3 = {11: (33, [69, 72, 76]), 12: (33, [69, 72, 76]), 13: (29, [69, 72, 77]), 14: (28, [68, 71, 76])}
    for b, (root, ch) in chordsU3.items():
        drums.add(B(b), kick(True), 1.0)
        drums.add(B(b + 0.5), kick(), 0.55)
        drums.add(B(b + 0.25), tom(110), 0.55, p=-0.3)
        drums.add(B(b + 0.75), tom(82), 0.6, p=0.3)
        if b in (12, 14):
            drums.add(B(b), snare(), 0.8)
        for k in range(4):
            bass.add(B(b + k * 0.25), dist_bass(root + 12, B(0.2)), 0.7)
        harm.add(B(b), pad(ch, B(1.0), cutoff=1200), 0.55)
    for k in range(8):  # roulement qui monte vers le break
        drums.add(B(14 + k * 0.125), snare(), 0.25 + 0.06 * k)
    for b, d, m in [(11, 0.5, 69), (11.5, 0.5, 72), (12, 0.5, 76), (12.5, 0.25, 74), (12.75, 0.25, 72), (13, 0.5, 72), (13.5, 0.5, 69), (14, 0.5, 71), (14.5, 0.25, 68), (14.75, 0.25, 71)]:
        leadT.add(B(b), lead(m, B(d) * 0.95, bright=0.35), 0.75, p=0.15)

    # ---- temps 15 : break (silence quasi total) + riser (piste à part, non coupée par le break)
    brk = Track(DUR)
    brk.add(B(15), riser(BEAT), 0.5)
    brk.add(B(15), crash(BEAT)[::-1], 0.3)

    # ---- temps 16 : DROP (7,5 s) puis STINGER (temps 18-20)
    drums.add(B(16), kick(True), 1.1)
    drums.add(B(16), crash(1.8), 0.55)
    drums.add(B(16), clap(1.2), 0.5)
    for b in (17, 18):
        drums.add(B(b), kick(), 0.9)
        drums.add(B(b + 0.5), hat(True), 0.3)
        drums.add(B(b + 0.25), hat(), 0.25)
        drums.add(B(b + 0.75), hat(), 0.25)
    drums.add(B(17), clap(1.2), 0.6)
    for b, mm in [(16, 36), (16.5, 36), (16.75, 48), (17, 41), (17.5, 43), (18, 43), (18.5, 43)]:
        bass.add(B(b), slap_bass(mm, B(0.4), pop=(mm >= 48)), 0.95)
    arps = {16: [72, 76, 79, 84], 17: [77, 81, 84, 89], 18: [79, 83, 86, 91]}
    for b, arp in arps.items():
        for k in range(4):
            harm.add(B(b + k * 0.25), chip(arp[k] + 12, B(0.22), duty=0.25, decay=0.08), 0.5, p=-0.3)
    # hook « lead brillant »
    for b, d, m in [(16, 0.25, 84), (16.25, 0.25, 88), (16.5, 0.5, 91), (17, 0.25, 89), (17.25, 0.25, 88), (17.5, 0.5, 86)]:
        leadT.add(B(b), lead(m, B(d) * 0.95, bright=1.0), 0.9, p=0.1)
    leadT.add(B(16), pad([60, 64, 67, 72], B(2.0), cutoff=2600), 0.4)
    # STINGER signature (temps 18 -> 20) : « Krok - et - Mil ! » puis accord final majeur apaisé
    stinger_start = B(18)
    st = Track(DUR)
    for b, d, m in [(18, 0.25, 79), (18.25, 0.25, 84), (18.5, 0.5, 88)]:
        st.add(B(b), lead(m, B(d) * 0.95, bright=1.0), 1.0, p=0.1)
        st.add(B(b), chip(m + 12, B(d) * 0.9, duty=0.5, decay=0.2), 0.4, p=-0.2)
    st.add(B(19), kick(True), 0.9)
    st.add(B(19), crash(1.2), 0.35)
    st.add(B(19), clap(1.1), 0.4)
    st.add(B(19), slap_bass(36, B(1.0)), 0.9)
    st.add(B(19), pad([48, 55, 60, 64, 67, 72], 1.0, cutoff=2200), 0.9)
    st.add(B(19), lead(84, 0.95, bright=0.8), 0.6, p=0.05)
    for k, m in enumerate([84, 88, 91, 96, 100]):
        st.add(B(19) + k * 0.045, chip(m, 0.3, duty=0.5, decay=0.1), 0.45, p=0.3)

    # ---- SFX (cues partagés avec l'animation)
    for c in cues['sfx']:
        kind, t = c['kind'], c['t']
        snd = {
            'coin': lambda: sfx_coin(),
            'whoosh': lambda: sfx_whoosh(c.get('dur', 0.35), c.get('up', True)),
            'boing': lambda: sfx_boing(),
            'zap': lambda: sfx_zap(c.get('seed', 0)),
            'pop': lambda: sfx_pop(c.get('base', 700)),
            'roar': lambda: sfx_roar(),
            'fwoosh': lambda: sfx_fwoosh(),
            'glitch': lambda: sfx_glitch(c.get('seed', 0)),
            'thump': lambda: sfx_thump(),
            'letter': lambda: sfx_letter(c.get('i', 0)),
            'sparkle': lambda: sfx_sparkle(),
        }[kind]()
        fx.add(t, snd, c.get('gain', 1.0), p=c.get('pan', 0.0))

    music = drums.buf * 0.9 + bass.buf * 0.85 + harm.buf * 0.8 + leadT.buf * 0.85 + st.buf * 0.95
    stinger_only = st.buf
    return music, brk.buf, fx.buf, stinger_only, stinger_start


# ============================================================== mastering
def true_peak_db(x):
    up = signal.resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def limiter(x, ceiling_db=-1.3, look=0.004, release=0.08):
    """Limiteur true-peak à anticipation : enveloppe des crêtes sur-échantillonnée x4,
    gain minimal sur la fenêtre d'anticipation, lissage, relâchement exponentiel."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    ceil = 10 ** (ceiling_db / 20)
    up = signal.resample_poly(x, 4, 1, axis=0)[: 4 * len(x)]
    pk = np.abs(up).reshape(len(x), 4, 2).max(axis=(1, 2))
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    la = max(1, int(look * SR))
    g = uniform_filter1d(minimum_filter1d(need, 2 * la + 1), la)
    a = np.exp(-1 / (release * SR))
    out = np.empty_like(g)
    prev = 1.0
    for i in range(len(g)):
        prev = min(g[i], a * prev + (1 - a) * g[i])
        out[i] = prev
    return x * out[:, None]


def break_gate(n):
    """Coupe nette de la musique (et de sa réverbe) pendant le temps 15 : silence quasi total avant le DROP."""
    t = np.arange(n) / SR
    g = np.ones(n)
    a, b = B(15), B(16)
    g[(t >= a) & (t < b)] = 0.008
    ramp = (t >= a - 0.03) & (t < a)
    g[ramp] = np.linspace(1, 0.008, ramp.sum())
    return g


def master(music, brk, fx, target_lufs=-14.0):
    ir = make_ir(1.6, 0.5)
    music_w = reverb(music, ir, wet=0.18)
    music_w[: len(music)] *= 1  # (longueur conservée)
    gate = break_gate(len(music_w))
    music_w *= gate[:, None]
    music_w[: len(brk)] += reverb(brk, make_ir(0.6, 0.2, seed=9), wet=0.2)[: len(brk)]
    fx_w = reverb(fx, make_ir(0.8, 0.25, seed=5), wet=0.12)
    n = int(DUR * SR)
    music_w = music_w[:n]
    fx_w = fx_w[:n]
    meter = pyln.Meter(SR)
    # hiérarchie : SFX ramenés à -5 dB sous la musique (sonie intégrée), jamais au-dessus
    lm = meter.integrated_loudness(music_w)
    lf = meter.integrated_loudness(fx_w)
    fx_gain = 10 ** ((lm - 5.0 - lf) / 20)
    mix = music_w + fx_w * fx_gain
    # nettoyage du très grave (et de la composante continue) : passe-haut 32 Hz
    b, a = signal.butter(2, 32 / (SR / 2), btype='high')
    mix = signal.lfilter(b, a, mix, axis=0)
    # fondu final propre (queue de reverb) : 9,55 -> 10,0 s
    t = np.arange(n) / SR
    fade = np.clip((DUR - t) / 0.45, 0, 1) ** 1.5
    mix *= fade[:, None]
    # sonie cible puis limiteur true-peak
    mix *= 10 ** ((target_lufs - meter.integrated_loudness(mix)) / 20)
    for _ in range(4):
        mix = limiter(mix, -1.3)
        mix *= 10 ** ((target_lufs - meter.integrated_loudness(mix)) / 20)
    mix = limiter(mix, -1.3)
    stats = {
        'lufs': round(meter.integrated_loudness(mix), 2),
        'true_peak_dbtp': round(true_peak_db(mix), 2),
        'music_lufs_premix': round(lm, 2),
        'sfx_lufs_after_gain': round(lf + 20 * np.log10(fx_gain), 2),
        'sfx_gain_db': round(20 * np.log10(fx_gain), 2),
    }
    return mix, stats, fx_gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'audio'))
    ap.add_argument('--excerpt', nargs=2, type=float, metavar=('START', 'DUR'))
    ap.add_argument('--excerpt-out', default=None)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    music, brk, fx, stinger, st_start = compose()
    mix, stats, fx_gain = master(music, brk, fx)
    sf.write(os.path.join(args.out, 'intro_mix.wav'), mix.astype(np.float32), SR, subtype='PCM_24')
    # stinger seul (jingle) : temps 18 -> fin de la queue, normalisé à -14 LUFS / -1 dBTP
    st = reverb(stinger[int(st_start * SR):], make_ir(1.6, 0.5), wet=0.18)[: int(1.8 * SR)]
    tt = np.arange(len(st)) / SR
    st *= np.clip((1.8 - tt) / 0.5, 0, 1)[:, None] ** 1.5
    meter = pyln.Meter(SR)
    st *= 10 ** ((-14 - meter.integrated_loudness(st)) / 20)
    st = limiter(st, -1.3)
    sf.write(os.path.join(args.out, 'stinger.wav'), st.astype(np.float32), SR, subtype='PCM_24')
    print(json.dumps(stats, indent=2))
    if args.excerpt:
        s0, d = args.excerpt
        ex = mix[int(s0 * SR): int((s0 + d) * SR)].copy()
        k = int(0.01 * SR)
        ex[:k] *= np.linspace(0, 1, k)[:, None]
        out = args.excerpt_out or os.path.join(args.out, f'excerpt_{s0:.3f}_{d:.1f}s.wav')
        sf.write(out, ex.astype(np.float32), SR, subtype='PCM_24')
        print('excerpt ->', out)


if __name__ == '__main__':
    main()
