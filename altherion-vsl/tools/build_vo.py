"""Remonte la voix off brute : resserre les silences selon le rythme voulu,
nettoie le signal et exporte la timeline des phrases (timeline.json + .srt).

Usage : python3 tools/build_vo.py
"""
import json, subprocess, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
LEAD_IN = 1.25    # la VO démarre après l'allumage de l'étoile
TAIL = 1.55       # logo final après « De zéro à studio »

# Segments de parole (texte) dans l'ordre, séparés par les silences détectés.
SEGMENTS = [
    "Tous les studios vous montrent le sommet.", "Le jeu fini.", "La bande-annonce parfaite.",
    "Jamais l'ascension.", "Altherion,", "c'est l'inverse :",
    "un studio de jeux vidéo qui se construit sous vos yeux.", "À partir de zéro.",
    "Au départ,", "un enfant qui bâtissait des refuges dans Minecraft.",
    "Plus chez lui dans les mondes imaginaires que dans le vrai.", "Aujourd'hui,",
    "il construit les siens.", "Chaque ligne de code est une prise.", "Chaque bug,", "une chute.",
    "Et chaque chute devient un épisode.", "À ses côtés,", "un golem de lumière,",
    "qui grandit à chaque palier.", "Une seule règle sur cette montagne :", "jamais de jeu bâclé.",
    "Jamais de mécanique pour vider vos poches.", "Seulement des jeux qui laissent sans voix.",
    "Six mois.", "Deux à trois jeux.", "Les vrais chiffres,", "les vrais doutes,",
    "les vraies victoires.", "L'ascension commence.", "Rejoignez l'expédition dès le premier épisode,",
    "sur YouTube et Instagram.", "Altherion.", "De zéro à studio.",
]
# Durée cible de chaque silence (entre segment i et i+1).
GAPS = [0.45, 0.35, 0.55, 0.90, 0.20, 0.30, 0.35, 0.75, 0.20, 0.30, 0.55, 0.25, 1.00,
        0.30, 0.20, 0.45, 0.70, 0.20, 0.20, 0.80, 0.30, 0.30, 0.50, 1.10, 0.30, 0.35,
        0.20, 0.20, 0.70, 0.40, 0.20, 0.70, 0.35]
assert len(GAPS) == len(SEGMENTS) - 1


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def detect_silences(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af",
                          "silencedetect=noise=-38dB:d=0.18", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def main():
    src = ROOT / "audio" / "vo_raw.mp3"
    x = load(src)
    sil = detect_silences(src)
    assert len(sil) == len(GAPS), (len(sil), len(GAPS))
    # bornes de parole, avec une petite marge pour garder attaques et queues de mots
    bounds, prev = [], 0.0
    for s, e in sil:
        bounds.append((prev, s))
        prev = e
    bounds.append((prev, len(x) / SR))
    PRE, POST = 0.045, 0.11
    pieces, timeline, t = [np.zeros(int(LEAD_IN * SR), np.float32)], [], LEAD_IN
    for i, (a, b) in enumerate(bounds):
        a0, b0 = max(0, a - PRE), min(len(x) / SR, b + POST)
        seg = x[int(a0 * SR):int(b0 * SR)].copy()
        f = int(0.012 * SR)
        seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        timeline.append({"i": i, "text": SEGMENTS[i], "start": round(t + (a - a0), 3),
                         "end": round(t + (a - a0) + (b - a), 3)})
        pieces.append(seg)
        t += len(seg) / SR
        if i < len(GAPS):
            g = max(0.0, GAPS[i] - PRE - POST)
            pieces.append(np.zeros(int(g * SR), np.float32))
            t += g
    pieces.append(np.zeros(int(TAIL * SR), np.float32))
    vo = np.concatenate(pieces)
    # nettoyage : passe-haut 75 Hz, léger lift de présence, normalisation
    sos = signal.butter(2, 75, "hp", fs=SR, output="sos")
    vo = signal.sosfilt(sos, vo)
    b, a = signal.iirpeak(3200, 1.2, fs=SR)
    vo = vo + 0.18 * signal.lfilter(b, a, vo)
    vo = vo / (np.max(np.abs(vo)) + 1e-9) * 0.89
    out = ROOT / "audio" / "vo.wav"
    wavfile.write(out, SR, (vo * 32767).astype(np.int16))
    total = len(vo) / SR
    meta = {"duration": round(total, 3), "fps": 30, "segments": timeline}
    (ROOT / "src" / "timeline.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    # sous-titres
    def ts(v):
        h, r = divmod(v, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"
    srt = [f"{k + 1}\n{ts(s['start'])} --> {ts(s['end'] + 0.15)}\n{s['text']}\n" for k, s in enumerate(timeline)]
    (ROOT / "out" / "altherion-vsl.fr.srt").write_text("\n".join(srt))
    print(f"VO {total:.2f}s, {len(timeline)} segments")
    for s in timeline:
        print(f"{s['start']:6.2f} {s['end']:6.2f}  {s['text']}")


if __name__ == "__main__":
    main()
