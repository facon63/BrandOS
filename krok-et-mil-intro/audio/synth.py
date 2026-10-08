"""Briques de synthèse procédurale (numpy / scipy) pour la musique et les SFX de l'intro.

Tout est déterministe (graine fixe) : la même commande produit toujours le même WAV.
"""
import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(7)


def midi(m):
    return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)


def t_axis(dur):
    return np.arange(int(round(dur * SR))) / SR


# ------------------------------------------------------------------ oscillateurs
def _phase(freq, n):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    return np.cumsum(f / SR) % 1.0, f / SR


def _polyblep(ph, dt):
    out = np.zeros_like(ph)
    m = ph < dt
    x = ph[m] / dt[m]
    out[m] = x + x - x * x - 1
    m2 = ph > 1 - dt
    x = (ph[m2] - 1) / dt[m2]
    out[m2] = x * x + x + x + 1
    return out


def saw(freq, n):
    ph, dt = _phase(freq, n)
    return 2 * ph - 1 - _polyblep(ph, dt)


def square(freq, n, duty=0.5, blep=True):
    ph, dt = _phase(freq, n)
    s = np.where(ph < duty, 1.0, -1.0)
    if blep:
        s = s + _polyblep(ph, dt) - _polyblep((ph - duty) % 1.0, dt)
    return s


def sine(freq, n):
    ph, _ = _phase(freq, n)
    return np.sin(2 * np.pi * ph)


def tri(freq, n):
    ph, _ = _phase(freq, n)
    return 4 * np.abs(ph - 0.5) - 1


def noise(n):
    return RNG.uniform(-1, 1, n)


# ------------------------------------------------------------------ enveloppes
def adsr(n, a=0.005, d=0.08, s=0.6, r=0.05, gate=None):
    """Enveloppe ADSR ; `gate` = durée tenue (s) avant le relâchement."""
    gate = n / SR - r if gate is None else gate
    t = np.arange(n) / SR
    env = np.where(t < a, t / max(a, 1e-6), 0.0)
    dec = (t >= a) & (t < a + d)
    env[dec] = 1 - (1 - s) * (t[dec] - a) / max(d, 1e-6)
    sus = (t >= a + d) & (t < gate)
    env[sus] = s
    rel = t >= gate
    lvl = s if gate >= a + d else max(0.0, 1 - (1 - s) * (gate - a) / max(d, 1e-6))
    env[rel] = lvl * np.clip(1 - (t[rel] - gate) / max(r, 1e-6), 0, 1)
    return env


def exp_decay(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


# ------------------------------------------------------------------ filtres
def lowpass(x, fc, q=0.707):
    b, a = signal.iirfilter(2, min(fc, SR / 2 * 0.95) / (SR / 2), btype='low', ftype='butter')
    return signal.lfilter(b, a, x)


def highpass(x, fc):
    b, a = signal.butter(2, fc / (SR / 2), btype='high')
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi):
    b, a = signal.butter(2, [lo / (SR / 2), min(hi, SR / 2 * 0.95) / (SR / 2)], btype='band')
    return signal.lfilter(b, a, x)


def _rbj_lp(fc, q):
    w0 = 2 * np.pi * min(fc, SR * 0.45) / SR
    alpha = np.sin(w0) / (2 * q)
    cw = np.cos(w0)
    b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def sweep_lowpass(x, fc_env, q=2.0, block=64):
    """Passe-bas résonant à fréquence de coupure variable (traitement par blocs)."""
    y = np.zeros_like(x)
    zi = np.zeros(2)
    for i in range(0, len(x), block):
        fc = float(fc_env[min(i, len(fc_env) - 1)])
        b, a = _rbj_lp(max(fc, 30), q)
        y[i:i + block], zi = signal.lfilter(b, a, x[i:i + block], zi=zi)
    return y


def softclip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def bitcrush(x, bits=6, hold=3):
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    if hold > 1:
        y = np.repeat(y[::hold], hold)[: len(x)]
    return y


# ------------------------------------------------------------------ espace
def make_ir(dur=1.4, decay=0.45, seed=3, bright=6000):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for c in range(2):
        nz = rng.normal(0, 1, n) * np.exp(-t / decay)
        nz = lowpass(nz, bright)
        ir[:, c] = nz
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt((ir ** 2).sum(0).max())


def reverb(stereo, ir, wet=0.25, send_hp=250):
    """Réverbe à convolution ; le départ est filtré (passe-haut) pour ne pas noyer basse et grosse caisse."""
    out = np.zeros((len(stereo) + len(ir) - 1, 2))
    for c in range(2):
        out[:, c] = signal.fftconvolve(highpass(stereo[:, c], send_hp), ir[:, c])
    out[: len(stereo)] += 0  # garde la longueur pour la queue
    dry = np.zeros_like(out)
    dry[: len(stereo)] = stereo
    return dry * (1 - wet * 0.5) + out * wet


def pan(mono, p=0.0):
    """p = -1 (gauche) .. +1 (droite), loi à puissance constante."""
    a = (p + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)], -1)


class Track:
    """Piste stéréo de durée fixe sur laquelle on « pose » des sons à des instants donnés."""

    def __init__(self, dur):
        self.buf = np.zeros((int(round(dur * SR)), 2))

    def add(self, t, sound, gain=1.0, p=0.0):
        if t is None:  # section absente de cette version
            return
        if sound.ndim == 1:
            sound = pan(sound, p)
        i = int(round(t * SR))
        if i >= len(self.buf):
            return
        j = min(len(self.buf), i + len(sound))
        self.buf[i:j] += sound[: j - i] * gain
