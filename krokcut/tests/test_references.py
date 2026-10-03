"""Vidéos déjà montées : mesures, bruitages reconnus, guide de style et API."""

import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from krokcut.config import AppConfig, StyleProfile
from krokcut.jobs import JobManager
from krokcut.library import Library
from krokcut.llm import LLM
from krokcut.pipeline import Pipeline
from krokcut.project import Project
from krokcut.references import ReferenceAnalyzer, ReferenceStore, build_guide, rhythm_metrics, timeline_text
from krokcut.sfx_detect import Detector

from .conftest import SR, _ffmpeg, _write_wav

BOING_TIMES = [5.0, 21.0, 37.5]
WHOOSH_TIME = 14.8


def _read_wav_mono(path):
    with wave.open(str(path)) as wf:
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2").astype(np.float32) / 32768
        return data.reshape(-1, wf.getnchannels()).mean(axis=1)


@pytest.fixture(scope="module")
def published(tmp_path_factory, library_dir):
    """Une « vidéo publiée » de 45 s : 3 plans (luminosités bien différentes), de la parole, des bruitages."""
    root = tmp_path_factory.mktemp("publiee")
    duration = 45.0
    rng = np.random.default_rng(11)
    n = int(duration * SR)
    env = np.zeros(n, np.float32)
    t = 0
    while t < n:
        length, gap = int(rng.uniform(0.15, 0.5) * SR), int(rng.uniform(0.05, 0.4) * SR)
        env[t : t + length] = rng.uniform(0.3, 1.0)
        t += length + gap
    track = (rng.standard_normal(n).astype(np.float32) * env * 0.12)
    boing = _read_wav_mono(library_dir / "sfx" / "boing_cartoon.wav")
    whoosh = _read_wav_mono(library_dir / "sfx" / "whoosh_transition.wav")
    for at in BOING_TIMES:
        i = int(at * SR)
        track[i : i + len(boing)] += boing * 0.6
    i = int(WHOOSH_TIME * SR)
    track[i : i + len(whoosh)] += whoosh * 0.6
    _write_wav(root / "son.wav", track)
    _ffmpeg(
        "-f", "lavfi", "-i", "color=c=red:s=640x360:r=30:d=15",
        "-f", "lavfi", "-i", "color=c=yellow:s=640x360:r=30:d=15",
        "-f", "lavfi", "-i", "color=c=blue:s=640x360:r=30:d=15",
        "-i", str(root / "son.wav"),
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        str(root / "episode_publie.mp4"),
    )
    words = []
    for start, text in ((3.4, "mais t'es nul"), (19.6, "il est tombé encore"), (36.0, "c'est la bonne"), (40.0, "trop fort")):
        for k, w in enumerate(text.split()):
            words.append({"w": w, "s": round(start + 0.3 * k, 2), "e": round(start + 0.3 * k + 0.25, 2), "p": 0.9})
    return {"path": root / "episode_publie.mp4", "words": words}


def setup_cfg(library_dir):
    cfg = AppConfig.load()
    cfg.library_dir = str(library_dir)
    cfg.save()
    Library.scan(library_dir)
    return cfg


# ------------------------------------------------------------------ détection
def test_detector_finds_sounds_without_false_positives():
    sr = 8000
    rng = np.random.default_rng(0)
    n = 90 * sr
    env = 0.1 + np.repeat(rng.uniform(0, 1, n // 800 + 1) > 0.4, 800)[:n] * 0.2  # bruit jamais coupé
    tt = np.arange(n) / sr
    signal = np.convolve(rng.standard_normal(n), np.ones(4) / 4, "same") * env + 0.05 * np.sin(2 * np.pi * 440 * tt)
    ts = np.arange(int(0.6 * sr)) / sr
    boing = 0.4 * np.sin(2 * np.pi * (300 + 900 * ts) * ts) * np.exp(-3 * ts)
    for at in (10.0, 47.3):
        i = int(at * sr)
        signal[i : i + len(boing)] += 0.5 * boing
    detector = Detector(signal.astype(np.float32), sr)
    hits = detector.find(boing.astype(np.float32))
    assert [round(t, 1) for t, _ in hits] == [10.0, 47.3]
    tone = 0.4 * np.sin(2 * np.pi * 440 * np.arange(int(0.5 * sr)) / sr)  # même note que le fond (bourdonnement) : piège
    assert detector.find(tone.astype(np.float32)) == []
    assert detector.find(np.zeros(100, np.float32)) == []  # trop court


class FakeLibrary:
    """Bibliothèque en mémoire pour tester la détection sans fichiers."""

    def __init__(self, sounds: dict, music: dict | None = None):
        self.sounds = {f"sfx/{k}": v for k, v in sounds.items()}
        self.sounds.update({f"music/{k}": v for k, v in (music or {}).items()})

    def of_kind(self, kind):
        return [
            {"id": i, "name": i.split("/")[1], "kind": kind, "duration": len(x) / 8000}
            for i, x in self.sounds.items()
            if i.startswith(kind)
        ]

    def path_of(self, asset):
        return Path(asset["id"])


def fake_audio(lib):
    return lambda path, cache_dir: lib.sounds[str(path)]


def voice_like(seconds, seed):
    """Bruit modulé comme de la parole : syllabes et pauses, spectre de voix."""
    sr = 8000
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    syll = np.repeat(rng.uniform(0.2, 1.0, n // 1200 + 1) * (rng.uniform(0, 1, n // 1200 + 1) > 0.25), 1200)[:n]
    env = np.convolve(syll, np.hanning(400) / 200, "same")
    noise = np.convolve(rng.standard_normal(n), np.hanning(12) / 6, "same")
    pitch = np.sin(2 * np.pi * np.cumsum(140 + 30 * np.sin(np.arange(n) / sr * 2.1)) / sr)
    return (0.08 * env * (noise + 1.5 * pitch)).astype(np.float32)


def music_like(seconds, seed):
    """Morceau synthétique : accords qui changent, batterie, mélodie (jamais deux fois pareil)."""
    sr = 8000
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    out = np.zeros(n)
    beat = int(sr * 60 / rng.uniform(90, 130))
    tt = np.arange(beat) / sr
    for k, i0 in enumerate(range(0, n - beat, beat)):
        f = 110 * 2 ** (rng.integers(0, 24) / 12)
        seg = sum(np.sin(2 * np.pi * f * m * tt + rng.uniform(0, 6)) / m for m in (1, 2, 3))
        seg += 0.5 * rng.standard_normal(beat) * np.exp(-tt * 40)  # charleston
        out[i0 : i0 + beat] += seg * np.exp(-tt * 3)
    return (0.3 * out / np.max(np.abs(out))).astype(np.float32)


def test_music_found_under_voice_but_not_a_lookalike(monkeypatch):
    from krokcut import sfx_detect

    sr = 8000
    track, other = music_like(60, 1), music_like(60, 2)
    voice = voice_like(90, 3)
    mixed = voice.copy()
    gain = np.sqrt(np.mean(voice**2) / np.mean(track**2)) * 10 ** (-16 / 20)  # 16 dB sous les voix
    mixed[10 * sr : 50 * sr] += gain * track[5 * sr : 45 * sr]
    lib = FakeLibrary({}, {"generique": track, "autre": other})
    monkeypatch.setattr(sfx_detect, "load_asset_audio", fake_audio(lib))
    result = sfx_detect.detect_library_sounds(mixed, lib, Path("."))
    assert [m["asset"] for m in result["music"]] == ["music/generique"]
    assert result["hits"] == []
    # Seule, au tout début de la vidéo (intro de 10 s), elle est aussi reconnue
    intro = voice.copy()
    intro[: 10 * sr] = track[: 10 * sr]
    assert [m["asset"] for m in sfx_detect.detect_library_sounds(intro, lib, Path("."))["music"]] == ["music/generique"]


def test_layered_sounds_kept_but_echoes_dropped(monkeypatch):
    from krokcut import sfx_detect

    sr = 8000
    rng = np.random.default_rng(4)
    ts = np.arange(int(0.6 * sr)) / sr
    chirp = (0.5 * np.sin(2 * np.pi * (300 + 1800 * ts) * ts) * np.exp(-3 * ts)).astype(np.float32)
    tb = np.arange(int(1.5 * sr)) / sr
    blast = (np.convolve(rng.standard_normal(len(tb)), np.ones(3) / 3, "same") * np.exp(-2.5 * tb) * 0.5).astype(np.float32)
    jingle = music_like(6, 5)
    signal = (0.002 * rng.standard_normal(40 * sr)).astype(np.float32)  # pièce calme : pas de voix pour masquer
    for at, x in ((5.0, blast), (5.0, chirp), (12.0, chirp), (12.25, chirp), (20.0, jingle), (30.0, blast)):
        i = int(at * sr)
        signal[i : i + len(x)] += x
    lib = FakeLibrary({"chirp": chirp, "explosion": blast}, {"jingle": jingle})
    monkeypatch.setattr(sfx_detect, "load_asset_audio", fake_audio(lib))
    result = sfx_detect.detect_library_sounds(signal, lib, Path("."))
    found = [(h["asset"], h["t"]) for h in result["hits"]]
    assert found == [
        ("sfx/chirp", 5.0),
        ("sfx/explosion", 5.0),  # deux sons superposés : les deux comptent
        ("sfx/chirp", 12.0),
        ("sfx/chirp", 12.25),  # répété aussitôt : deux fois
        ("sfx/explosion", 30.0),
    ]
    assert [m["asset"] for m in result["music"]] == ["music/jingle"]  # musique courte : comptée comme musique


def test_rhythm_metrics_and_timeline_text():
    m = rhythm_metrics([10.0, 20.0, 25.0], 60.0)
    assert m["cuts"] == 3 and m["cuts_per_min"] == 3.0 and m["median_shot"] == 10.0
    text = timeline_text(
        [{"start": 1.0, "text": "salut"}, {"start": 4.0, "text": "bye"}], [{"t": 2.5, "asset": "sfx/boing", "score": 0.7}]
    )
    assert text.splitlines() == ["[0:00:01] salut", "[0:00:02] 🔊 sfx/boing", "[0:00:04] bye"]


# --------------------------------------------------------- analyse complète
def test_reference_analysis_offline(workspace, library_dir, published):
    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    doc = store.add(published["path"])
    assert store.add(published["path"]).id == doc.id  # pas de doublon
    ok = ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run()
    assert ok, doc.state.last_error
    m = doc.state.metrics
    assert m["cuts"] == 2 and m["duration_min"] == pytest.approx(0.8, abs=0.06)

    hits = doc.read_json("bruitages.json")["hits"]
    boings = [h["t"] for h in hits if h["asset"] == "sfx/boing_cartoon"]
    assert boings == pytest.approx(BOING_TIMES, abs=0.05)
    assert any(h["asset"] == "sfx/whoosh_transition" and abs(h["t"] - WHOOSH_TIME) < 0.05 for h in hits)
    assert not any(h["asset"] == "sfx/rire_public" for h in hits)  # jamais posé : pas reconnu
    assert m["sfx_top"][0] == ["sfx/boing_cartoon", 3]

    assert (doc.root / "vignette.jpg").exists() and len(list((doc.root / "images").glob("*.jpg"))) >= 8
    analysis = doc.read_json("analyse.json")
    assert analysis["source"] == "heuristic"
    assert any(e["quote"] == "mais t'es nul" and e["effects"] == "sfx/boing_cartoon" for e in analysis["examples"])

    data = build_guide(store, cfg)
    assert data["source"] == "heuristic" and data["sources"] == [doc.id]
    assert "sfx/boing_cartoon (3×)" in store.guide_md.read_text("utf-8")
    assert data["suggested"]["values"]["sfx_per_minute"] > 0
    block = store.prompt_block()
    assert "mais t'es nul" in block and "Format et rythme" in block
    assert block.count("- Durée") == 1  # les mesures ne sont pas répétées deux fois

    # le dérush d'un épisode en tient compte
    project = Project.create("Ep", [str(published["path"])], [str(published["path"])])
    assert "sfx/boing_cartoon" in Pipeline(project, cfg).system_prompt()

    # retirer la vidéo vide le guide
    store.remove(doc.id)
    assert build_guide(store, cfg) == {} and store.prompt_block() == ""


def fake_ask_json(self, *, system, content, schema, effort="medium", max_tokens=0, label=""):
    if label == "reference":
        text = content[-1]["text"]
        assert "🔊 sfx/boing_cartoon" in text and "mais t'es nul" in text
        assert sum(1 for b in content if b["type"] == "image") >= 8
        return {
            "summary": "Ils ratent des sauts.",
            "structure": "Teaser puis tentatives.",
            "humor": "Les échecs répétés.",
            "editing": "Zoom sur chaque chute, texte jaune en gros.",
            "sound_design": "Boing après chaque chute.",
            "rules": ["Après une chute, zoom + boing."],
            "examples": [{"time": "0:03", "quote": "mais t'es nul", "why_kept": "vanne", "effects": "boing + zoom"}],
            "estimates": {"zooms_per_minute": 5.2, "texts_per_minute": 1.0, "characters_per_minute": 0, "has_music": "inconnu", "cold_open": "oui"},
        }
    if label == "guide":
        assert "Ils ratent des sauts." in content
        return {
            "guide": "## Format et rythme\n- Court et nerveux.\n\n## Règles d'or\n- **Toujours** un boing après une chute.",
            "examples": [{"video": "episode_publie", "time": "0:03", "quote": "mais t'es nul", "why_kept": "vanne", "effects": "boing"}],
            "estimates": {"zooms_per_minute": 5.0, "texts_per_minute": 1.0, "characters_per_minute": 0, "has_music": "non", "cold_open": "oui"},
        }
    raise AssertionError(label)


def test_reference_analysis_with_claude_and_apply(workspace, library_dir, published, monkeypatch):
    from krokcut import server

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(LLM, "ask_json", fake_ask_json)
    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    doc = store.add(published["path"])
    assert ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run(), doc.state.last_error
    assert doc.read_json("analyse.json")["source"] == "claude"
    data = build_guide(store, cfg)
    assert data["source"] == "claude"
    values, sources = data["suggested"]["values"], data["suggested"]["sources"]
    assert values["zooms_per_minute"] == 5.0 and sources["zooms_per_minute"].startswith("estimé")
    assert values["sfx_per_minute"] > 0 and sources["sfx_per_minute"].startswith("mesuré")
    assert values["cold_open"] is True and "music" not in values  # Claude n'entend pas : jamais « pas de musique »
    assert set(data["suggested"]["checked"]) == {"target_min_minutes", "target_max_minutes", "sfx_per_minute"}
    assert "Toujours" in store.prompt_block()

    monkeypatch.setattr(server, "jobs", JobManager(start=False))
    client = TestClient(server.app)
    listing = client.get("/api/references").json()
    assert listing["guide"]["text"].startswith("## Format") and listing["references"][0]["analysis_source"] == "claude"
    detail = client.get(f"/api/references/{doc.id}").json()
    assert detail["analysis"]["rules"] == ["Après une chute, zoom + boing."]
    applied = client.post("/api/guide/apply").json()  # par défaut : seulement ce qui est mesuré
    assert applied["sfx_per_minute"] == values["sfx_per_minute"] and applied["zooms_per_minute"] == 4.0
    applied = client.post("/api/guide/apply", json={"fields": ["zooms_per_minute"]}).json()
    assert applied["zooms_per_minute"] == 5.0
    assert StyleProfile.load().zooms_per_minute == 5.0
    assert client.post("/api/guide/apply", json={"fields": []}).status_code == 400


# ------------------------------------------------------------------- API
def test_reference_api(workspace, published, monkeypatch):
    from krokcut import server

    manager = JobManager(start=False)
    monkeypatch.setattr(server, "jobs", manager)
    client = TestClient(server.app)
    assert client.get("/api/references").json()["references"] == []
    assert client.post("/api/guide/apply").status_code == 400
    assert client.post("/api/references", json={"paths": ["/nexiste/pas.mp4"]}).status_code == 400

    # envoi dans le dossier des références, sans jamais écraser
    content = published["path"].read_bytes()
    first = client.put("/api/upload/publiee.mp4?folder=references", content=content).json()["path"]
    second = client.put("/api/upload/publiee.mp4?folder=references", content=content).json()["path"]
    assert "references" in first and first != second and second.endswith("publiee-2.mp4")

    added = client.post("/api/references", json={"paths": [first]}).json()["added"][0]
    assert added["busy"] == "queued"
    assert [(j.kind, j.target) for j in manager.pending] == [("reference", added["id"])]
    assert client.post(f"/api/references/{added['id']}/run", json={}).status_code == 409  # déjà prévue
    assert client.get(f"/api/references/{added['id']}/thumb").status_code == 404

    # retirer : annule l'analyse prévue, supprime la copie, recalcule le guide
    assert client.delete(f"/api/references/{added['id']}").json()["ok"]
    assert [j.kind for j in manager.pending] == ["guide"]
    assert client.post("/api/guide/rebuild").json()["ok"] and [j.kind for j in manager.pending] == ["guide"]
    assert not (ReferenceStore().files_dir / "publiee.mp4").exists()
    assert client.get(f"/api/references/{added['id']}").status_code == 404


def test_recover_interrupted_reference(workspace, published):
    store = ReferenceStore()
    doc = store.add(published["path"])
    doc.set_step("rhythm", status="running", progress=0.3)
    assert store.open(doc.id).recover_interrupted()
    assert "Reprendre" in store.open(doc.id).state.steps["rhythm"].message


# ------------------------------------------------- corrections après relecture
def analysed(store, cfg, published):
    doc = store.add(published["path"])
    assert ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run(), doc.state.last_error
    return store.open(doc.id)


def test_rerun_keeps_images_when_source_moved(workspace, library_dir, published, tmp_path, monkeypatch):
    from krokcut import server

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    moved = tmp_path / "copie.mp4"
    moved.write_bytes(published["path"].read_bytes())
    doc = store.add(moved)
    assert ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run()
    images = len(list((doc.root / "images").glob("*.jpg")))
    moved.unlink()  # la vidéo d'origine a été déplacée

    manager = JobManager(start=False)
    monkeypatch.setattr(server, "jobs", manager)
    TestClient(server.app).post(f"/api/references/{doc.id}/run", json={})
    doc.reload()
    # « Réanalyser » ne refait que les bruitages et le style
    assert [s for s, st in doc.state.steps.items() if st.status != "done"] == ["sfx", "analyze"]
    assert ReferenceAnalyzer(doc, cfg, store).run(), doc.state.last_error
    assert len(list((doc.root / "images").glob("*.jpg"))) == images
    # relancer les images sans la source : on garde les anciennes
    words = lambda pcm, levels: published["words"]  # noqa: E731
    assert ReferenceAnalyzer(store.open(doc.id), cfg, store, words_provider=words).run(from_step="frames")
    assert "conservées" in store.open(doc.id).state.steps["frames"].message
    assert len(list((doc.root / "images").glob("*.jpg"))) == images
    # reprendre une analyse qui a besoin de la source : message clair
    assert not ReferenceAnalyzer(store.open(doc.id), cfg, store, words_provider=words).run(from_step="rhythm")
    assert "introuvable" in store.open(doc.id).state.last_error


def test_speech_ratio_and_measured_summary(workspace, published):
    from krokcut.references import measured_summary, speech_ratio, suggested_style

    words = [{"s": 0.0, "e": 0.4}, {"s": 0.5, "e": 1.0}, {"s": 5.0, "e": 6.0}]
    assert speech_ratio(words, 10.0) == pytest.approx(0.2)
    assert speech_ratio([], 10.0) == 0.0

    store = ReferenceStore()
    docs = []
    for i, metrics in enumerate(
        [
            {"duration_min": 12, "height": 1080, "cuts_per_min": 10.0, "median_shot": 4.0, "sfx_checked": True, "sfx_per_min": 6.0, "sfx_top": [["sfx/a", 70]], "speech_ratio": 0.7},
            {"duration_min": 11, "height": 1080, "cuts_per_min": 8.0, "median_shot": 5.0, "sfx_checked": True, "sfx_per_min": 0.0, "speech_ratio": 0.8},
            {"duration_min": 10, "height": 0, "cuts_per_min": 0, "median_shot": 600.0, "sfx_checked": False, "music_used": ["music/x"], "sfx_top": [["sfx/b", 9]]},
        ]
    ):
        doc = store.add(published["path"].parent / "son.wav") if i == 0 else None
        if doc is None:
            src = published["path"].parent / f"copie{i}.wav"
            src.write_bytes((published["path"].parent / "son.wav").read_bytes() + bytes([i]))
            doc = store.add(src)
        doc.set_metrics(**metrics)
        docs.append(doc)
    text, measured = measured_summary(docs)
    assert "Rythme : 9 changements de plan par minute, plan médian 4.5 s" in text  # le fichier audio ne compte pas
    assert "au moins 3 par minute" in text  # 6 et 0 : les zéros comptent
    assert "sfx/b" not in text and "music/x" not in text  # non vérifié : on n'en parle pas
    assert "Parole : 75 %" in text
    low = suggested_style([], {"durations": [12], "sfx_rate": 0.2, "sfx_checked": True}, None)
    assert "sfx_per_minute" not in low["values"]  # 0,2/min mesuré n'est pas une consigne


def test_stale_sfx_metrics_reset_and_rush_excluded(workspace, library_dir, published, tmp_path):
    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    doc = analysed(store, cfg, published)
    assert doc.state.metrics["sfx_hits"] == 4
    cfg.library_dir = str(tmp_path / "vide")  # bibliothèque débranchée
    (tmp_path / "vide").mkdir()
    cfg.save()
    assert ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run(from_step="sfx")
    m = store.open(doc.id).state.metrics
    assert m["sfx_checked"] is False and m["sfx_hits"] == 0 and m["sfx_top"] == []
    analysis = store.open(doc.id).read_json("analyse.json")
    assert not any("boing" in r for r in analysis["rules"])

    doc = store.open(doc.id)
    doc.set_metrics(duration_min=182)  # un rush déposé par erreur
    data = build_guide(store, cfg)
    assert data == {} and store.prompt_block() == ""


def test_duplicate_upload_is_detected(workspace, published, monkeypatch):
    from krokcut import server

    monkeypatch.setattr(server, "jobs", JobManager(start=False))
    client = TestClient(server.app)
    content = published["path"].read_bytes()
    first = client.put("/api/upload/a.mp4?folder=references", content=content).json()["path"]
    r1 = client.post("/api/references", json={"paths": [first]}).json()
    second = client.put("/api/upload/a.mp4?folder=references", content=content).json()["path"]
    r2 = client.post("/api/references", json={"paths": [second]}).json()
    assert r1["duplicates"] == [] and r2["duplicates"] == [r1["added"][0]["name"]]
    assert len(ReferenceStore().list()) == 1
    files = sorted(p.name for p in ReferenceStore().files_dir.iterdir())
    assert files == ["a.mp4"]  # la 2e copie a été supprimée, pas de .part qui traîne


def test_job_priority_and_cancel_during_analyze(workspace, library_dir, published, monkeypatch):
    manager = JobManager(start=False)
    manager.submit("episode", kind="project")
    manager.submit("ref1", kind="reference")
    manager.submit_guide()
    manager.submit("ref2", kind="reference")
    order = []
    with manager._lock:
        while manager.pending:
            job = manager.next_job_locked()
            order.append((job.kind, job.target))
    assert order == [("reference", "ref1"), ("reference", "ref2"), ("guide", "guide"), ("project", "episode")]

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    doc = store.add(published["path"])
    analyzer = ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    def cancelled_call(self, **kwargs):
        analyzer.cancel.set()  # l'utilisateur clique « Annuler » pendant l'appel à Claude
        return fake_ask_json(self, **kwargs)

    monkeypatch.setattr(LLM, "ask_json", cancelled_call)
    assert not analyzer.run()
    assert store.open(doc.id).state.steps["analyze"].status == "pending"


def test_sticky_sound_marked_unreliable(monkeypatch, tmp_path):
    from krokcut import sfx_detect

    sr = sfx_detect.DETECT_SR
    rng = np.random.default_rng(3)
    ts = np.arange(int(0.4 * sr)) / sr
    pop = (0.5 * np.sin(2 * np.pi * (500 + 1500 * ts) * ts) * np.exp(-4 * ts)).astype(np.float32)
    signal = (0.01 * rng.standard_normal(120 * sr)).astype(np.float32)
    for k in range(30):  # 15 fois par minute : ce son « colle » partout
        i = int((2 + 3.9 * k) * sr)
        signal[i : i + len(pop)] += pop
    monkeypatch.setattr(sfx_detect, "load_asset_audio", lambda *a, **k: pop)

    class Lib:
        def of_kind(self, kind):
            return [{"id": "sfx/pop", "name": "pop", "kind": "sfx", "duration": 0.4}] if kind == "sfx" else []

        def path_of(self, asset):
            return tmp_path / "pop.wav"

    result = sfx_detect.detect_library_sounds(signal, Lib(), tmp_path)
    assert result["unreliable"] == ["sfx/pop"] and result["hits"] == [] and result["tested"] == 1


def test_guide_precedence_and_corrupt_guide(workspace, library_dir, published, monkeypatch):
    from krokcut import server

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    analysed(store, cfg, published)
    build_guide(store, cfg)
    project = Project.create("Ep", [str(published["path"])], [str(published["path"])])
    prompt = Pipeline(project, cfg).system_prompt()
    assert "la bible de la chaîne et les consignes spécifiques ci-dessous priment" in prompt
    assert "\n#### Format et rythme" in prompt  # titres rangés sous la section des repères
    assert prompt.index("Repères tirés") < prompt.index("## La chaîne")

    store.guide_json.write_text('{"updated": "2026', "utf-8")  # écriture coupée net
    assert store.guide() is None and store.prompt_block() == ""
    assert "Repères tirés" not in Pipeline(project, cfg).system_prompt()
    monkeypatch.setattr(server, "jobs", JobManager(start=False))
    assert TestClient(server.app).get("/api/references").status_code == 200


def fake_refs(store, published, specs):
    """Références factices : seules leurs mesures (et leur analyse) comptent."""
    docs = []
    for i, (metrics, analysis) in enumerate(specs):
        src = published["path"].parent / f"fausse{i}.wav"
        src.write_bytes((published["path"].parent / "son.wav").read_bytes() + bytes([i, 7]))
        doc = store.add(src, name=f"video{i}")
        doc.set_metrics(height=1080, cuts_per_min=10.0, median_shot=4.0, **metrics)
        if analysis is not None:
            doc.write_json("analyse.json", analysis)
            doc.set_step("analyze", status="done")
        docs.append(doc)
    return docs


def test_suggestions_ignore_outliers_and_unknowns(workspace, published):
    from krokcut.references import duration_targets, flag, measured_summary, suggested_style

    assert duration_targets([12, 13, 14]) == (11.0, 15.0)
    assert duration_targets([10, 12, 14, 40]) == (10.0, 22.0)  # une vidéo très longue n'étire pas la fourchette
    assert duration_targets([55, 59]) == (54.0, 60.0)
    assert flag("oui") is True and flag("non") is False and flag("inconnu") is None
    assert flag(False) is None  # anciennes analyses : « false » voulait aussi dire « je ne sais pas »

    store = ReferenceStore()
    claude = lambda **est: {"source": "claude", "rules": [], "examples": [], "estimates": est}  # noqa: E731
    docs = fake_refs(
        store,
        published,
        [
            ({"duration_min": 0.9, "sfx_checked": True, "sfx_per_min": 30.0}, claude(texts_per_minute=9, has_music="non", cold_open="non")),
            ({"duration_min": 12, "sfx_checked": True, "sfx_per_min": 4.0}, claude(texts_per_minute=0.2, has_music="non", cold_open="oui")),
            ({"duration_min": 14, "sfx_checked": True, "sfx_per_min": 2.0}, claude(texts_per_minute=0.2, has_music="inconnu", cold_open="inconnu")),
        ],
    )
    text, measured = measured_summary(docs)
    assert measured["durations"] == [12, 14] and measured["shorts"] == ["video0"]  # le Short ne compte pas
    assert "au moins 3 par minute" in text and "video0" in text
    analyses = [(d, d.read_json("analyse.json")) for d in docs]
    out = suggested_style(analyses, measured, None)
    values = out["values"]
    assert (values["target_min_minutes"], values["target_max_minutes"]) == (11.0, 15.0)
    assert values["texts_per_minute"] == 0.2  # « rarement » ne devient pas « jamais »
    assert "music" not in values  # deux « non » vus à l'image : pas de quoi couper la musique
    assert values["cold_open"] is True  # le Short ne vote pas, l'inconnu non plus
    assert "texts_per_minute" not in out["checked"] and "cold_open" not in out["checked"]

    docs[2].set_metrics(music_used=["music/generique"])
    _, measured = measured_summary(docs)
    out = suggested_style(analyses, measured, None)
    assert out["values"]["music"] is True and "music" in out["checked"]


def test_claude_failure_falls_back_to_measurements(workspace, library_dir, published, monkeypatch):
    from krokcut.llm import LLMError

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(LLM, "ask_json", fake_ask_json)
    doc = analysed(store, cfg, published)
    assert build_guide(store, cfg)["source"] == "claude"

    def down(self, **kwargs):
        raise LLMError("Limite de débit de l'API atteinte : réessaie dans quelques minutes.")

    monkeypatch.setattr(LLM, "ask_json", down)
    data = build_guide(store, cfg)  # le guide n'est jamais laissé périmé
    assert data["source"] == "heuristic" and "Limite de débit" in data["claude_error"] and data["sources"] == [doc.id]
    assert "Toujours" not in store.prompt_block()

    assert ReferenceAnalyzer(doc, cfg, store, words_provider=lambda pcm, levels: published["words"]).run(from_step="analyze")
    doc = store.open(doc.id)
    analysis = doc.read_json("analyse.json")
    assert analysis["source"] == "heuristic" and "Limite de débit" in analysis["claude_error"]
    assert "Réanalyser" in doc.state.steps["analyze"].message
    assert [d.id for d, _ in store.analyses()] == [doc.id]  # la vidéo compte toujours


def test_rebuild_reanalyses_with_claude_and_queue_is_explained(workspace, library_dir, published, monkeypatch):
    from krokcut import server

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    doc = analysed(store, cfg, published)  # sans clé : mesures seules
    manager = JobManager(start=False)
    monkeypatch.setattr(server, "jobs", manager)
    client = TestClient(server.app)
    assert client.post("/api/guide/rebuild").json()["reanalysing"] == 0  # pas de clé : simple mise à jour
    assert [j.kind for j in manager.pending] == ["guide"]
    manager.pending.clear()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert client.post("/api/guide/rebuild").json()["reanalysing"] == 1
    assert [(j.kind, j.target, j.from_step) for j in manager.pending] == [("reference", doc.id, "analyze")]

    project = Project.create("Ep", [str(published["path"])], [str(published["path"])])
    manager.submit(project.id)
    note = client.get(f"/api/projects/{project.id}").json()["queue_note"]
    assert "l'analyse d'une vidéo de « Mes vidéos »" in note and "guide de style" in note
    assert client.get("/api/references").json()["references"][0]["queue_note"] == ""


def test_legacy_notes_guide_header_and_authoritative_settings(workspace, library_dir, published, monkeypatch):
    from krokcut import references
    from krokcut.config import workspace_dir

    cfg = setup_cfg(library_dir)
    store = ReferenceStore()
    project = Project.create("Ep", [str(published["path"])], [str(published["path"])])
    legacy = workspace_dir() / "references.md"
    legacy.write_text("Notes à la main.\n<!-- analyse-auto:debut -->\n45 changements de plan par minute. Vise ce rythme.\n<!-- analyse-auto:fin -->\n", "utf-8")
    assert "Vise ce rythme" in Pipeline(project, cfg).reference_notes()  # pas encore de guide : l'ancienne analyse sert
    doc = analysed(store, cfg, published)
    build_guide(store, cfg)
    notes = Pipeline(project, cfg).reference_notes()
    assert "Notes à la main" in notes and "Vise ce rythme" not in notes
    assert "font foi" in Pipeline(project, cfg).system_prompt()

    doc.set_metrics(sfx_checked=False)
    assert "bruitages non vérifiés" in references._guide_block(doc, doc.read_json("analyse.json"))

    # Trop de vidéos pour une seule relecture : la plus ancienne n'est pas envoyée, et c'est dit
    src = published["path"].parent / "episode_bis.mp4"
    src.write_bytes(published["path"].read_bytes() + b"\0")
    second = store.add(src, name="bis")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(LLM, "ask_json", fake_ask_json)
    for d in (store.open(doc.id), second):
        assert ReferenceAnalyzer(d, cfg, store, words_provider=lambda pcm, levels: published["words"]).run(from_step="analyze")
    monkeypatch.setattr(references, "GUIDE_INPUT_MAX_CHARS", 10)
    data = build_guide(store, cfg)
    assert data["source"] == "claude" and data["claude_left_out"] == [doc.state.name] and len(data["sources"]) == 2
