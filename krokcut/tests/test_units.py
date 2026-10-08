import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from krokcut import audio
from krokcut.config import StyleProfile
from krokcut.cutting import moment_pieces, pieces_duration
from krokcut.derush import DERUSH_SCHEMA, STORY_SCHEMA, chunk_lines, fit_duration
from krokcut.editing import EDIT_SCHEMA, build_plan
from krokcut.export import export_chapters, export_srt, export_xml
from krokcut.library import Library
from krokcut.project import Source
from krokcut.timeline import anchor_time, build_timeline, camera_switches
from krokcut.transcribe import attribute_speakers, build_lines, format_lines


# ------------------------------------------------------------------ helpers
def make_levels(duration=60.0, speech=(), hop=audio.HOP):
    """speech : liste de (t0, t1, 'A'|'B', niveau dB)."""
    n = int(duration / hop) + 1
    a = np.full(n, -70.0, np.float32)
    b = np.full(n, -70.0, np.float32)
    for t0, t1, who, db in speech:
        s = slice(int(t0 / hop), int(t1 / hop) + 1)
        if who == "A":
            a[s], b[s] = db, db - 10
        else:
            b[s], a[s] = db, db - 10
    return audio.Levels.compute_thresholds(a, b, hop)


def line(i, start, end, speaker="A", text="bla bla", words=None, kind="speech", loud=False):
    if words is None:
        n = max(1, len(text.split()))
        step = (end - start) / n
        words = [[w, round(start + k * step, 3), round(start + (k + 1) * step - 0.02, 3)] for k, w in enumerate(text.split())]
    return {"id": i, "start": start, "end": end, "speaker": speaker, "text": text, "words": words, "kind": kind, "loud": loud, "laugh": False}


def sources(dur=600.0):
    info = {"duration": dur, "has_audio": True, "audio_streams": 1, "fps": 30.0}
    return {
        "A": Source(key="A", name="Krok", files=["a.mp4"], path="a.mp4", info=info),
        "B": Source(key="B", name="Mil", files=["b.mp4"], path="b.mp4", info=info, offset=2.0),
    }


# ------------------------------------------------------------------ synchro
def test_sync_recovers_offset_and_discord_echo(tmp_path):
    rng = np.random.default_rng(0)
    sr, dur = audio.SR, 240

    def bursts(seed):
        r = np.random.default_rng(seed)
        env = np.zeros(dur * sr, np.float32)
        t = 0
        while t < len(env):
            length, gap = int(r.uniform(0.1, 0.5) * sr), int(r.uniform(0.05, 0.7) * sr)
            env[t : t + length] = r.uniform(0.2, 1)
            t += length + gap
        return rng.standard_normal(len(env)).astype(np.float32) * env * 0.2

    va, vb = bursts(1), bursts(2)
    lat = int(0.15 * sr)
    delay = lambda x: np.concatenate([np.zeros(lat, np.float32), x[:-lat]])  # noqa: E731
    a = va + 0.6 * delay(vb)
    b_full = vb + 0.6 * delay(va)
    b = np.concatenate([np.zeros(int(2.4 * sr), np.float32), b_full])  # B a démarré 2,4 s avant
    for name, x in (("a", a), ("b", b)):
        (np.clip(x, -1, 1) * 32767).astype("<i2").tofile(tmp_path / f"{name}.pcm")
    res = audio.synchronize(tmp_path / "a.pcm", tmp_path / "b.pcm")
    assert abs(res.lag - 2.4) < 0.02
    assert res.double_peak
    offsets = audio.sources_offsets(res.lag)
    assert offsets["B"][0] == 0.0 and abs(offsets["A"][0] - 2.4) < 0.02


# ---------------------------------------------------------- qui parle / lignes
def test_speaker_attribution_and_events():
    levels = make_levels(30, [(1, 1.9, "A", -20), (4.1, 5.0, "B", -18), (10, 11.5, "A", -8)])
    words = [
        {"w": "salut", "s": 1.1, "e": 1.5, "p": 1}, {"w": "ça", "s": 1.6, "e": 1.8, "p": 1},
        {"w": "va", "s": 4.2, "e": 4.5, "p": 1}, {"w": "bien", "s": 4.6, "e": 5.0, "p": 1},
    ]
    assert attribute_speakers(words, levels) == ["A", "A", "B", "B"]
    lines = build_lines(words, levels)
    speech = [l for l in lines if l["kind"] == "speech"]
    assert [l["speaker"] for l in speech] == ["A", "B"]
    events = [l for l in lines if l["kind"] == "event"]
    assert len(events) == 1 and 9.8 <= events[0]["start"] <= 10.2
    text = format_lines(lines, {"A": "Krok", "B": "Mil"})
    assert "Krok : salut ça" in text and "son fort sans parole" in text


# ------------------------------------------------------------------- coupes
def test_moment_pieces_cut_silences_but_keep_reactions():
    style = StyleProfile(max_silence=0.5, keep_pad=0.1, reaction_tail=0.5)
    # rires (son fort) entre 3,2 et 5 s : le blanc entre les lignes 0 et 1 n'est pas coupé
    levels = make_levels(40, [(1, 3, "A", -20), (3.2, 5.0, "B", -10), (5, 6, "B", -20), (12, 13, "A", -20)])
    lines = [line(0, 1, 3, "A", "un deux trois"), line(1, 5, 6, "B", "quatre cinq"), line(2, 12, 13, "A", "six sept")]
    pieces = moment_pieces(lines, 0, 2, levels, style)
    assert len(pieces) == 2  # le blanc silencieux de 6 à 12 s est coupé
    assert pieces[0][0] == pytest.approx(0.9, abs=0.01) and pieces[0][1] > 5.9
    assert pieces_duration(pieces) < 13 - 1
    # une ligne retirée crée une coupe
    removed = moment_pieces(lines, 0, 2, levels, style, removed={1})
    assert all(not (p[0] < 5.5 < p[1]) for p in removed)


# ------------------------------------------------------------------ caméra
def test_camera_follows_speaker_with_min_shot():
    style = StyleProfile(min_shot=2.5, keep_pad=0.1)
    lines = [line(0, 0, 3, "A"), line(1, 3.2, 3.8, "B"), line(2, 4.0, 7, "A"), line(3, 7.5, 12, "B")]
    switches = camera_switches(lines, [(0, 12)], [], style)
    # B répond trop vite après le changement de plan : on rebascule sur A 2,5 s plus tard
    assert [(round(t, 2), p) for t, p in switches] == [(0, "A"), (3.1, "B"), (5.6, "A"), (8.1, "B")]
    # directives explicites
    sw = camera_switches(lines, [(0, 12)], [{"line": 2, "pov": "both"}], style)
    assert sw[-1][1] == "both"


def test_anchor_time_finds_word():
    l = line(0, 10, 12, "A", "mais t'es sérieux là")
    assert anchor_time(l, "sérieux") == pytest.approx(l["words"][2][1])
    assert anchor_time(l, "SERIEUX!") == pytest.approx(l["words"][2][1])
    assert anchor_time(l, "inconnu") == 10
    assert anchor_time(l, "", "end_of_line") == 12


# ---------------------------------------------------------------- schémas
@pytest.mark.parametrize("schema", [DERUSH_SCHEMA, STORY_SCHEMA, EDIT_SCHEMA])
def test_schemas_are_strict(schema):
    Draft202012Validator.check_schema(schema)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)


# ---------------------------------------------------------------- timeline
def test_build_timeline_maps_effects(library_dir):
    lib = Library.scan(library_dir)
    style = StyleProfile(max_silence=0.5)
    levels = make_levels(100, [(10, 30, "A", -20), (40, 50, "B", -20)])
    lines = [
        line(0, 10, 13, "A", "regarde ce saut incroyable"),
        line(1, 20, 23, "B", "mdr tu es tombé"),
        line(2, 40, 44, "B", "on recommence encore une fois"),
    ]
    plan = {
        "segments": [
            {
                "moment_id": "m001", "start_line": 0, "end_line": 1, "removed": [], "chapter": "Le saut",
                "transition": "cut", "camera": [],
                "zooms": [{"line": 1, "word": "tombé", "kind": "punch", "duration": 1.0}],
                "sfx": [{"asset": "sfx/boing_cartoon", "line": 1, "word": "", "timing": "end_of_line", "volume": "high"}],
                "characters": [{"asset": "perso/krok/krok_rire", "line": 1, "word": "mdr", "position": "bottom_left", "duration": 0}],
                "texts": [{"line": 0, "word": "saut", "text": "Le saut de l'ange", "style": "impact"}],
            },
            {
                "moment_id": "m002", "start_line": 2, "end_line": 2, "removed": [], "chapter": "", "transition": "whoosh",
                "camera": [], "zooms": [], "sfx": [], "characters": [], "texts": [],
            },
        ],
        "music": [{"asset": "music/chill_lofi", "from_segment": 0, "to_segment": 1}],
    }
    tl = build_timeline(plan, lines, levels, style, sources(), lib, 30.0, 640, 360)
    assert tl.clips and all(c.frames >= 2 for c in tl.clips)
    # les plans s'enchaînent sans trou
    for prev, nxt in zip(tl.clips, tl.clips[1:]):
        assert nxt.start_f == prev.start_f + prev.frames
    # le blanc de 13 à 20 s a été coupé : moins de 10 s pour le premier moment
    seg0 = [c for c in tl.clips if c.segment == 0]
    assert sum(c.frames for c in seg0) / 30 < 8
    assert seg0[0].pov == "A" and seg0[-1].pov == "B"
    assert any(c.zooms for c in seg0)
    assert {s.asset_id for s in tl.sfx} >= {"sfx/boing_cartoon", "sfx/whoosh_transition"}
    assert tl.overlays[0].asset_id == "perso/krok/krok_rire" and tl.overlays[0].duration == pytest.approx(2.0, abs=0.1)
    assert tl.texts[0].start < tl.overlays[0].start
    assert tl.music and tl.music[0].end == pytest.approx(tl.duration, abs=0.05)
    assert tl.markers[0].name == "Le saut"


def test_exports(tmp_path, library_dir):
    lib = Library.scan(library_dir)
    levels = make_levels(100, [(10, 30, "A", -20)])
    lines = [line(0, 10, 13, "A", "regarde ce saut incroyable"), line(1, 20, 23, "B", "mdr tu es tombé")]
    plan = build_plan(
        {"cold_open": None, "sequence": [{"moment": "m001", "title": "Le saut", "start_line": 0, "end_line": 1, "chapter": "", "transition": "cut", "est_duration": 6}]},
        {"moments": {"m001": {"camera": [], "zooms": [{"line": 1, "word": "", "kind": "punch", "duration": 1}], "sfx": [], "characters": [], "texts": [], "remove_lines": []}}, "music": []},
        StyleProfile(),
    )
    tl = build_timeline(plan, lines, levels, StyleProfile(), sources(), lib, 30.0, 1920, 1080)
    xml_path = export_xml(tl, tmp_path / "t.xml", "Test")
    root = ET.parse(xml_path).getroot()
    assert root.tag == "xmeml"
    items = root.findall(".//clipitem")
    assert len(items) >= len(tl.clips)
    assert root.find(".//sequence/rate/timebase").text == "30"
    assert any(p.find("value").text == "125.00" for p in root.iter("parameter") if p.findtext("parameterid") == "scale")
    # chaque fichier est entièrement décrit à sa première apparition (exigence de Premiere)
    seen = set()
    for f in root.iter("file"):
        if f.get("id") not in seen:
            assert f.find("pathurl") is not None and f.findtext("pathurl").startswith("file://localhost/")
            seen.add(f.get("id"))
        else:
            assert len(f) == 0
    srt = export_srt(tl, lines, tmp_path / "s.srt").read_text("utf-8")
    assert "regarde ce saut" in srt and "-->" in srt
    chapters = export_chapters(tl, tmp_path / "c.txt").read_text("utf-8")
    assert chapters.startswith("0:00 ")


# ---------------------------------------------------------------- bibliothèque
def test_library_scan(library_dir):
    lib = Library.scan(library_dir)
    by_id = {a["id"]: a for a in lib.assets}
    assert by_id["sfx/boing_cartoon"]["kind"] == "sfx"
    assert by_id["music/chill_lofi"]["kind"] == "music"
    krok = by_id["perso/krok/krok_rire"]
    assert krok["kind"] == "character" and krok["key"] == "alpha" and krok["character"] == "Krok"
    assert by_id["perso/mil/mil_choque"]["character"] == "Mil"
    assert by_id["clip/choc_fond_vert"]["key"] == "green"
    assert lib.resolve("perso/krok/krok_rir", ("character",))["id"] == "perso/krok/krok_rire"
    catalog = lib.catalog()
    assert "BRUITAGES" in catalog and "perso/krok/krok_rire" in catalog
    # les retouches manuelles survivent à un nouveau scan
    lib.update("sfx/boing_cartoon", {"tags": ["fail", "chute"], "description": "boing de chute"})
    again = Library.scan(library_dir)
    assert again.get("sfx/boing_cartoon")["tags"] == ["fail", "chute"]
    assert again.get("sfx/boing_cartoon")["description"] == "boing de chute"


# ------------------------------------------------------------------ histoire
def test_chunking_and_fit_duration():
    lines = [line(i, i * 30.0, i * 30.0 + 5, "A") for i in range(200)]
    chunks = chunk_lines(lines, minutes=20)
    assert len(chunks) >= 5 and chunks[1][0]["start"] < chunks[0][-1]["start"] + 1  # chevauchement
    style = StyleProfile(target_min_minutes=1, target_max_minutes=2)
    moments = [
        {"id": f"m{i:03d}", "start": i * 100.0, "end": i * 100 + 40, "start_line": i, "end_line": i, "title": "",
         "story": 2, "score": float(i), "est_duration": 40.0}
        for i in range(6)
    ]
    story = {"cold_open": None, "sequence": [{"moment": m["id"], "est_duration": 40.0} for m in moments]}
    fitted = fit_duration(story, moments, lines, make_levels(10), style)
    assert 60 <= fitted["total_estimate"] <= 120
    assert "m000" not in [i["moment"] for i in fitted["sequence"]]  # le plus faible saute en premier
    json.dumps(fitted)


# ------------------------------------------------------------ transcription
class _Word:
    def __init__(self, word, start, end):
        self.word, self.start, self.end, self.probability = word, start, end, 0.9


class _Segment:
    def __init__(self, words):
        self.words = words
        self.end = words[-1].end


class FakeWhisper:
    def __init__(self, device, fail=False):
        self.device, self.fail, self.calls = device, fail, 0

    def transcribe(self, audio, **kwargs):
        assert kwargs["word_timestamps"] and kwargs["language"] == "fr"
        self.calls += 1

        def gen():
            if self.fail:
                raise RuntimeError("Library cudnn_ops64_9.dll is not found")
            yield _Segment([_Word(" salut", 1.0, 1.4), _Word(" toi", 1.5, 1.8)])

        return gen(), None


def test_transcribe_mix_chunks_cache_and_gpu_fallback(tmp_path, monkeypatch):
    from krokcut import transcribe
    from krokcut.config import WhisperSettings

    duration = 130.0
    np.zeros(int(duration * audio.SR), "<i2").tofile(tmp_path / "mix.pcm")
    levels = make_levels(duration)
    loaded = []

    def fake_load(settings, device):
        model = FakeWhisper(device, fail=device == "cuda")
        loaded.append(model)
        return model

    monkeypatch.setattr(transcribe, "resolve_device", lambda s: "cuda")
    monkeypatch.setattr(transcribe, "load_whisper", fake_load)
    logs = []
    settings = WhisperSettings(chunk_minutes=1.0)
    words = transcribe.transcribe_mix(tmp_path / "mix.pcm", levels, settings, tmp_path / "cache", log=logs.append)
    assert [m.device for m in loaded] == ["cuda", "cpu"] and "processeur" in logs[0]
    starts = sorted({round(w["s"]) for w in words if w["w"] == "salut"})
    assert starts == [1, 61]  # un « salut » par morceau (coupé dans le calme près de 60 s), recalé
    # 2e passage : tout vient du cache, Whisper n'est pas rechargé
    loaded.clear()
    again = transcribe.transcribe_mix(tmp_path / "mix.pcm", levels, settings, tmp_path / "cache")
    assert again == words and loaded == []


def test_standard_fps():
    from krokcut.pipeline import standard_fps

    assert standard_fps(59.87) == pytest.approx(60000 / 1001)
    assert standard_fps(30.0) == 30.0
    assert standard_fps(25.02) == 25.0
    assert standard_fps(120.0) == 120.0
