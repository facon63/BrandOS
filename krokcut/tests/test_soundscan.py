"""Mesures du son (onglet « Comparer ») validées sur des signaux synthétiques à vérité connue."""

from __future__ import annotations

import json
import time
import wave

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from krokcut import soundscan as ss
from krokcut.ffmpeg_utils import extract_pcm

from . import synth_media as sm

SR = sm.SR
NUM = {"type": "number"}
EVENTS_SCHEMA = {
    "type": "object", "required": ["version", "events"],
    "properties": {"version": {"const": ss.SOUND_VERSION}, "events": {"type": "array", "items": {
        "type": "object",
        "required": ["id", "t", "dur", "cat", "label", "rise_db", "peak_vs_voice_db", "f_line", "in_speech",
                     "with_visual", "salience", "confidence"],
        "properties": {"id": {"type": "string", "pattern": r"^S\d{3,}$"}, "t": NUM, "dur": NUM,
                       "cat": {"enum": list(ss.CATEGORIES)}, "label": {"type": "string"}, "rise_db": NUM,
                       "peak_vs_voice_db": NUM, "f_line": NUM, "in_speech": {"type": "boolean"},
                       "with_visual": {"type": "string", "pattern": r"^$|^[PZF]\d+$"}, "salience": NUM,
                       "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}}},
}
MUSIC_SCHEMA = {
    "type": "object", "required": ["version", "pct", "segments"],
    "properties": {"version": {"const": ss.SOUND_VERSION}, "pct": NUM, "segments": {"type": "array", "items": {
        "type": "object",
        "required": ["id", "start", "end", "kind", "bpm", "level_vs_voice_db", "start_kind", "end_kind", "changes"],
        "properties": {"id": {"type": "string", "pattern": r"^M\d+$"}, "start": NUM, "end": NUM,
                       "kind": {"enum": ["rythmee", "nappe"]}, "bpm": NUM, "level_vs_voice_db": NUM,
                       "start_kind": {"enum": ["nette", "progressive"]},
                       "end_kind": {"enum": ["coupure_nette", "fondu", "normale"]},
                       "changes": {"type": "array", "items": {"type": "object", "required": ["t", "why"],
                                                              "properties": {"t": NUM, "why": {"type": "string"}}}}}}}},
}
SILENCES_SCHEMA = {
    "type": "object", "required": ["version", "silences", "dead_air", "pauses", "reaction_tail"],
    "properties": {
        "silences": {"type": "array", "items": {"type": "object", "required": ["id", "t", "dur", "abrupt"],
                                                "properties": {"id": {"type": "string", "pattern": r"^C\d{2,}$"},
                                                               "abrupt": {"type": "boolean"}}}},
        "dead_air": {"type": "array", "items": {"type": "object", "required": ["t", "dur"]}},
        "pauses": {"type": "object", "required": ["p50", "p90", "p95", "over_0_5s_pct", "n"]},
        "reaction_tail": {"type": "object", "required": ["median", "n"]},
    },
}
RHYTHM_SCHEMA = {
    "type": "object", "required": ["version", "windows"],
    "properties": {"windows": {"type": "array", "items": {
        "type": "object", "required": ["t0", "cuts_per_min", "zooms_per_min", "sounds_per_min", "speech_share", "loudness_m"]}}},
}
METRIC_KEYS = (
    "sound_events_per_min", "sound_by_cat", "sound_level_vs_voice_db", "events_with_visual_pct", "zooms_with_sound_pct",
    "music_pct", "music_segments", "music_bpm_median", "music_level_vs_voice_db", "music_changes_per_10min",
    "music_cuts_per_10min", "silences_per_10min", "sound_cuts_per_10min", "dead_air_pct", "pause_p50", "pause_p90",
    "pause_p95", "pauses_over_0_5s_pct", "reaction_tail_median", "cuts_in_word_pct", "speech_source",
    "library_recall", "library_recall_n", "sound_version",
)
# vérité visuelle du faux montage (tests/test_vision.py) : la bande-son y est calée
MONTAGE_CUTS = [8.0, 16.0, 20.0, 25.0, 29.5, 33.0, 36.0, 40.0, 40.5, 41.0, 41.5, 42.0, 42.5, 43.0, 46.5]
MONTAGE_VISUAL = [{"id": "Z01", "type": "zoom", "t": 4.0}, {"id": "F01", "type": "flash_blanc", "t": 12.0},
                  {"id": "F02", "type": "noir_bref", "t": 18.0}, {"id": "F03", "type": "image_inseree", "t": 37.0},
                  {"id": "Z02", "type": "zoom", "t": 38.4}]


def room(n: int, seed: int = 0) -> np.ndarray:
    return (0.002 * np.random.default_rng(seed).standard_normal(n)).astype(np.float32)


def features(x, words, key=None):
    """Descripteurs et masque de parole ; `key` : mis en cache (signal réutilisé par plusieurs tests)."""
    def build():
        feats = ss.stft_features(x)
        return feats, ss.speech_mask(feats.n, words)
    return sm.cached(("descripteurs", key), build) if key else build()


def editorial(events):
    return [e for e in events if e["cat"] in ss.EDITORIAL]


@pytest.fixture(scope="module")
def voices():
    """100 s de voix (aiguë, grave) et la mesure du niveau médian de la voix, réutilisées par plusieurs tests."""
    def build():
        out = {}
        for key, (make, seed) in {"voix": (sm.voice16, 2), "grave": (sm.deep_voice16, 3)}.items():
            v, words = make(100.0, seed=seed)
            x = v + room(len(v), seed)
            out[key] = (x, words, sm.voice_median_db(x, words))
        return out
    return sm.cached("voix_100s", build)


# ------------------------------------------------------------- sons marquants
def test_huit_categories_sur_la_voix():
    """Bip et ding sur une syllabe, les autres dans un trou de parole : instant à ±30 ms, catégorie exacte."""
    found = missed = 0
    for seed, deep in ((1, False), (2, False), (1, True), (2, True)):
        x, words, plan = sm.sound_mix(seed, deep)
        events = ss.detect_events(*features(x, words))
        matched = set()
        for t, cat, dur in plan:
            want = t + dur if cat == "montee" else t  # une montée se repère à sa coupure
            hit = next((i for i, e in enumerate(events) if e["cat"] == cat
                        and abs((e["t"] + e["dur"] if cat == "montee" else e["t"]) - want) <= 0.03), None)
            if hit is None:
                missed += 1
            else:
                found += 1
                matched.add(hit)
                e = events[hit]
                if cat == "bip":
                    assert abs(e["f_line"] - 1000) < 15 and e["in_speech"] >= ss.IN_SPEECH
                if cat == "tonal":
                    assert abs(e["f_line"] - 1568) < 20 or abs(e["f_line"] - 3136) < 30
        extra = [e for i, e in enumerate(events) if i not in matched and e["cat"] in ss.EDITORIAL]
        assert not extra, (seed, deep, extra)  # précision : aucun son éditorial inventé
    assert found >= 31 and missed <= 1, (found, missed)  # rappel : 31 sur 32 au moins (une montée sous la voix)


def test_pas_de_fausse_alerte_voix_grave_moteur(voices):
    minutes = 100 / 60
    for key in ("voix", "grave"):
        x, words, _ = voices[key]
        events = editorial(ss.detect_events(*features(x, words, key)))
        assert len(events) / minutes <= 0.5, (key, events)
        if key == "grave":
            assert not [e for e in events if e["cat"] == "boum"]
        x_engine = x + sm.drone16(100.0, level=0.03)
        assert len(editorial(ss.detect_events(*features(x_engine, words, key + "+moteur")))) / minutes <= 0.5
    engine = sm.drone16(100.0, level=0.08)
    assert not editorial(ss.detect_events(*features(engine + room(len(engine)), [], "moteur")))


def test_grosse_caisse_sous_la_voix_n_est_pas_un_bruitage(voices):
    x, words, vmed = voices["voix"]
    x = x.copy()
    sm.place(x, 20.0, sm.music_at(sm.music16(60.0, 110), vmed, -12))
    events = ss.detect_events(*features(x, words))
    beat = 60 / 110
    on_beats = [e for e in events if 20 <= e["t"] <= 80 and abs((e["t"] - 20 + 0.03) % beat) <= 0.06]
    assert not [e for e in on_beats if e["cat"] in ("tonal", "boum")]
    assert len(editorial(events)) / (100 / 60) <= 0.5
    music_only = sm.music16(60.0, 110, level=0.2)
    assert not editorial(ss.detect_events(*features(music_only + room(len(music_only)), [])))


# --------------------------------------------------------------------- musique
def _music(x, words, key=None):
    feats, sp = features(x, words, key)
    return ss.detect_music(feats, sp)


def test_musique_rythmee_sous_la_voix_coupee_net(voices):
    x, words, vmed = voices["voix"]
    x = x.copy()
    sm.place(x, 20.0, sm.music_at(sm.music16(40.0, 110), vmed, -12))
    segs = _music(x, words)["segments"]
    assert len(segs) == 1
    m = segs[0]
    assert abs(m["start"] - 20) <= 6 and abs(m["end"] - 60) <= 4
    assert abs(m["start"] - 20) <= 0.3  # en pratique : le premier temps
    assert m["kind"] == "rythmee" and m["bpm"] == pytest.approx(110, rel=0.03)
    assert m["level_vs_voice_db"] == pytest.approx(-12, abs=4)
    assert m["end_kind"] == "coupure_nette" and abs(m["end"] - 60) <= 0.25
    assert m["start_kind"] == "nette" and not m["changes"]


def test_nappe_dans_les_trous_de_parole(voices):
    x, words, vmed = voices["voix"]
    x = x.copy()
    sm.place(x, 20.0, sm.music_at(sm.pad16(60.0), vmed, -12))
    segs = _music(x, words)["segments"]
    assert segs and all(s["kind"] == "nappe" for s in segs)
    covered = sum(min(s["end"], 80) - max(s["start"], 20) for s in segs)
    assert covered >= 0.8 * 60 and segs[0]["start"] >= 14 and segs[-1]["end"] <= 84


def test_pas_de_musique_voix_moteur(voices):
    for key in ("voix", "grave"):
        x, words, _ = voices[key]
        assert _music(x, words, key)["segments"] == []
        assert _music(x + sm.drone16(100.0, level=0.03), words, key + "+moteur")["segments"] == []
    engine = sm.drone16(100.0, level=0.08)
    assert _music(engine + room(len(engine)), [], "moteur")["segments"] == []


def test_changement_de_morceau_et_fondu(voices):
    x, words, vmed = voices["voix"]
    a = x.copy()
    sm.place(a, 20.0, sm.music_at(sm.music16(20.0, 90), vmed, -12))
    sm.place(a, 40.0, sm.music_at(sm.music16(20.0, 128, chords=sm.CHORDS[::-1]), vmed, -12))
    segs = _music(a, words)["segments"]
    assert len(segs) == 1 and abs(segs[0]["start"] - 20) <= 1 and abs(segs[0]["end"] - 60) <= 1
    changes = segs[0]["changes"]
    assert len(changes) == 1 and abs(changes[0]["t"] - 40) <= 4 and changes[0]["why"] == "tempo"
    b = x.copy()
    sm.place(b, 20.0, sm.music_at(sm.music16(40.0, 110, fade_out=4.0), vmed, -12))
    segs = _music(b, words)["segments"]
    assert len(segs) == 1 and segs[0]["end_kind"] == "fondu" and abs(segs[0]["end"] - 60) <= 4


# -------------------------------------------------------- silences et pauses
def test_silence_coupe_net_ou_progressif(voices):
    x, words, _ = voices["voix"]
    x = x.copy()
    rng = np.random.default_rng(5)
    syl = sm._syllable(rng, 1.0, 160.0, 150.0) * 0.25  # on parle jusqu'à la coupure...
    x[int(84.0 * SR):int(85.0 * SR)] = syl
    x[int(85.0 * SR):int(85.6 * SR)] = 0.0  # ... puis 0,6 s de silence complet
    x[int(60.0 * SR):int(61.0 * SR)] = sm._syllable(rng, 1.0, 160.0, 150.0) * 0.25 * np.linspace(1, 0, SR)  # baisse
    x[int(61.0 * SR):int(61.6 * SR)] = 0.0
    feats, sp = features(x, words)
    res = ss.detect_silences(feats.E, sp)
    by_t = {round(s["t"]): s for s in res["silences"]}
    assert 85 in by_t and abs(by_t[85]["t"] - 85.0) <= 0.02 and by_t[85]["abrupt"] is True
    assert by_t[85]["dur"] == pytest.approx(0.6, abs=0.03) and by_t[85]["id"].startswith("C")
    late = [s for s in res["silences"] if 59.5 <= s["t"] <= 61.2]
    assert len(late) == 1 and late[0]["abrupt"] is False
    assert all(s["t"] >= 1.0 for s in res["silences"])


def test_pauses_respiration_coupes_dans_un_mot():
    words = [(0.0, 0.5), (0.6, 1.0), (1.8, 2.2), (2.3, 3.0), (6.5, 7.0)]
    p = ss.pause_stats(words)  # écarts 0,1 0,8 0,1 (3,5 s : au-delà de 3 s, pas une pause)
    assert p["n"] == 3 and p["p50"] == pytest.approx(0.1) and p["p90"] == pytest.approx(0.66)
    assert p["over_0_5s_pct"] == pytest.approx(33.3)
    cuts = [0.25, 1.3, 2.25, 2.6, 3.4, 6.0, 7.1]
    tail = ss.reaction_tail(words, cuts)  # 0,3 (1,3) 0,05 (2,25) 0,4 (3,4) 0,1 (7,1) ; 6,0 : plus de 2 s
    assert tail["n"] == 4 and tail["median"] == pytest.approx(0.2)
    # coupes près de la parole : 0,25 1,3 2,25 2,6 3,4 7,1 ; dans un mot : 0,25 et 2,6
    assert ss.cuts_in_word(words, cuts) == pytest.approx(33.3)


# ---------------------------------------------------------------------- volume
def _wav(path, x, sr=48000):
    data = (np.clip(np.stack([x, x], axis=1), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    return path


def test_volume_ebu_r128(tmp_path):
    t = np.arange(10 * 48000) / 48000
    sine = (10 ** (-20 / 20)) * np.sin(2 * np.pi * 1000 * t)  # crête à −20 dBFS sur les deux canaux
    m = ss.measure_loudness(_wav(tmp_path / "sinus.wav", sine), tmp_path, 10.0)
    assert m["loudness_i"] == pytest.approx(-20, abs=1)
    vol = json.loads((tmp_path / "volume.json").read_text("utf-8"))
    assert abs(len(vol["M"]) - 100) <= 2 and len(vol["S"]) == len(vol["M"]) and vol["hop"] == 0.1
    assert set(vol) == {"I", "LRA", "true_peak_db", "hop", "M", "S"}
    assert vol["true_peak_db"] == pytest.approx(-20, abs=0.5)
    assert m["loudness_spikes_per_min"] == 0 and not (tmp_path / "r128.txt").exists()
    t = np.arange(30 * 48000) / 48000
    x = (10 ** (-20 / 20)) * np.sin(2 * np.pi * 1000 * t)
    x[15 * 48000:16 * 48000] *= 10 ** (12 / 20)  # une seconde 12 dB plus fort
    m = ss.measure_loudness(_wav(tmp_path / "pic.wav", x), tmp_path, 30.0)
    assert m["loudness_spikes_per_min"] == pytest.approx(2.0)  # un pic en 30 s
    assert set(m) == {"loudness_i", "loudness_lra", "true_peak_db", "loudness_spikes_per_min", "shortterm_p95_p10"}


# --------------------------------------------- analyse complète (bande-son du faux montage)
@pytest.fixture(scope="module")
def soundtrack(tmp_path_factory):
    def build():
        base = tmp_path_factory.mktemp("bande_son")
        x, truth = sm.edit_soundtrack()
        sm.write_wav(base / "bande.wav", x, stereo=True)
        extract_pcm(base / "bande.wav", base / "audio.pcm")  # même chemin que l'étape « audio »
        return base, truth
    return sm.cached("bande_son", build)


def _analyze(base, out, truth, **kw):
    kw.setdefault("speech_provider", None)
    return ss.analyze_sound(base / "audio.pcm", out, duration=50.0, words=truth["words"], cuts=MONTAGE_CUTS,
                            visual_events=MONTAGE_VISUAL, **kw)


def test_bande_son_du_montage(soundtrack, tmp_path):
    base, truth = soundtrack
    m = _analyze(base, tmp_path, truth)
    events = json.loads((tmp_path / "son_evenements.json").read_text("utf-8"))["events"]
    for want in truth["events"]:  # ±50 ms : certains sont posés sur la musique (attaque moins nette)
        ref = want["t"] + want["dur"] if want["cat"] == "montee" else want["t"]
        hits = [e for e in events if e["cat"] == want["cat"]
                and abs((e["t"] + e["dur"] if want["cat"] == "montee" else e["t"]) - ref) <= 0.05]
        assert len(hits) == 1, want
        assert hits[0]["label"] == ss.CATEGORIES[want["cat"]]
    assert len(editorial(events)) == len(truth["events"])  # aucun son inventé (ni sur les temps de la musique)
    by_cat = {e["cat"]: e for e in events}
    assert by_cat["clic"]["with_visual"] == "Z01"  # clic sur le zoom sec
    assert by_cat["boum"]["with_visual"] == "P002"  # boum sur la coupe de 8,0 (début du plan 2)
    assert by_cat["whoosh"]["with_visual"] == "P003"  # whoosh juste avant la coupe de 16,0
    assert by_cat["bip"]["in_speech"] is True and by_cat["sature"]["in_speech"] is False
    assert [e["id"] for e in events] == [f"S{i + 1:03d}" for i in range(len(events))]
    music = json.loads((tmp_path / "musique.json").read_text("utf-8"))
    (seg,) = music["segments"]
    want = truth["music"]
    assert abs(seg["start"] - want["start"]) <= 1 and abs(seg["end"] - want["end"]) <= 0.25
    assert seg["end_kind"] == "coupure_nette" and seg["bpm"] == pytest.approx(want["bpm"], rel=0.03)
    sil = json.loads((tmp_path / "silences.json").read_text("utf-8"))
    (c,) = sil["silences"]
    assert abs(c["t"] - truth["silence"]["t"]) <= 0.02 and c["abrupt"] is True
    minutes = 50 / 60
    assert m["sound_events_per_min"] == pytest.approx(len(truth["events"]) / minutes, abs=0.01)
    assert m["sound_by_cat"]["boum"] == pytest.approx(1 / minutes, abs=0.01)
    assert m["events_with_visual_pct"] == pytest.approx(100 * 3 / 8, abs=0.1)
    assert m["zooms_with_sound_pct"] == 50.0  # le clic sur Z01 ; rien sur Z02
    assert m["music_segments"] == 1 and m["music_cuts_per_10min"] == pytest.approx(12.0)
    assert m["sound_cuts_per_10min"] == pytest.approx(12.0) and m["silences_per_10min"] == pytest.approx(12.0)
    assert m["speech_source"] == "whisper" and m["library_recall"] is None and m["library_recall_n"] == 0
    assert m["pause_p90"] == ss.pause_stats(truth["words"])["p90"]
    assert m["cuts_in_word_pct"] == ss.cuts_in_word(truth["words"], MONTAGE_CUTS)
    assert set(METRIC_KEYS) <= set(m)


def test_fichiers_et_schemas(soundtrack, tmp_path):
    base, truth = soundtrack
    _analyze(base, tmp_path, truth)
    for name, schema in (("son_evenements.json", EVENTS_SCHEMA), ("musique.json", MUSIC_SCHEMA),
                         ("silences.json", SILENCES_SCHEMA), ("rythme.json", RHYTHM_SCHEMA)):
        Draft202012Validator(schema).validate(json.loads((tmp_path / name).read_text("utf-8")))
    rhythm = json.loads((tmp_path / "rythme.json").read_text("utf-8"))["windows"]
    assert [w["t0"] for w in rhythm] == [0.0, 30.0]
    assert rhythm[0]["cuts_per_min"] == pytest.approx(5 / 0.5)  # 8, 16, 20, 25 et 29,5 dans les 30 premières s
    series = np.load(tmp_path / "son_trames.npz")
    assert set(series.files) == {"E", "D", "Dk", "flatness", "speech"}
    assert all(len(series[k]) == 5000 for k in series.files) and series["speech"].dtype == bool


def test_rappel_sur_la_bibliotheque(soundtrack, tmp_path):
    base, truth = soundtrack
    _analyze(base, tmp_path / "a", truth)
    found = [e["t"] for e in json.loads((tmp_path / "a" / "son_evenements.json").read_text("utf-8"))["events"]]
    hits = [t + 0.1 for t in found[:8]] + [2.0, 48.7]  # 10 bruitages posés, dont 8 sur un son détecté
    m = _analyze(base, tmp_path / "b", truth, library_hits=hits)
    assert m["library_recall"] == pytest.approx(0.8) and m["library_recall_n"] == 10


def test_parole_vad_ou_mots_seuls(soundtrack, tmp_path):
    pytest.importorskip("faster_whisper")
    t = np.arange(20 * SR) / SR
    pure = sm.write_pcm(tmp_path / "sinus.pcm", 0.3 * np.sin(2 * np.pi * 1000 * t))
    assert ss.vad_available() and ss.default_vad(pure) == []  # un son pur n'est pas de la parole
    base, truth = soundtrack
    m = _analyze(base, tmp_path / "vad", truth, speech_provider=ss.DEFAULT_VAD)
    assert m["speech_source"] == "whisper+vad"
    called = []

    def provider(pcm):
        called.append(pcm)
        return [(30.0, 33.0)]
    m = _analyze(base, tmp_path / "fourni", truth, speech_provider=provider)
    assert called and m["speech_source"] == "whisper+vad"
    speech = np.load(tmp_path / "fourni" / "son_trames.npz")["speech"]
    assert speech[3000:3300].all()  # le segment fourni compte comme parole


def test_performances_120_s(tmp_path):
    x, words, _ = sm.sound_mix(3, seconds=120.0)
    pcm = sm.write_pcm(tmp_path / "audio.pcm", x)
    calls = []
    t0 = time.time()
    m = ss.analyze_sound(pcm, tmp_path, duration=120.0, words=words, cuts=[10.0, 50.0], visual_events=[],
                         speech_provider=None, progress=lambda f, msg: calls.append(f))
    assert time.time() - t0 < 20
    assert calls[0] == 0.0 and calls[-1] == 1.0 and calls == sorted(calls)
    assert m["sound_version"] == ss.SOUND_VERSION
