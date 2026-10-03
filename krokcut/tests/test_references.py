"""Vidéos déjà montées : mesures, bruitages reconnus, guide de style et API."""

import wave

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
    env = np.repeat(rng.uniform(0, 1, n // 800 + 1) > 0.4, 800)[:n] * 0.3
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
    tone = 0.4 * np.sin(2 * np.pi * 440 * np.arange(int(0.5 * sr)) / sr)  # même note que le fond : piège
    assert detector.find(tone.astype(np.float32)) == []
    assert detector.find(np.zeros(100, np.float32)) == []  # trop court


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
    assert "mais t'es nul" in block and "Mesures sur vos vidéos publiées" in block

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
            "estimates": {"zooms_per_minute": 5.2, "texts_per_minute": 1.0, "characters_per_minute": 0, "has_music": False, "cold_open": True},
        }
    if label == "guide":
        assert "Ils ratent des sauts." in content
        return {
            "guide": "## Format et rythme\n- Court et nerveux.\n\n## Règles d'or\n- **Toujours** un boing après une chute.",
            "examples": [{"video": "episode_publie", "time": "0:03", "quote": "mais t'es nul", "why_kept": "vanne", "effects": "boing"}],
            "estimates": {"zooms_per_minute": 5.0, "texts_per_minute": 1.0, "characters_per_minute": 0, "has_music": False, "cold_open": True},
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
    assert values["cold_open"] is True and values["music"] is False
    assert "Toujours" in store.prompt_block()

    monkeypatch.setattr(server, "jobs", JobManager(start=False))
    client = TestClient(server.app)
    listing = client.get("/api/references").json()
    assert listing["guide"]["text"].startswith("## Format") and listing["references"][0]["analysis_source"] == "claude"
    detail = client.get(f"/api/references/{doc.id}").json()
    assert detail["analysis"]["rules"] == ["Après une chute, zoom + boing."]
    applied = client.post("/api/guide/apply").json()
    assert applied["zooms_per_minute"] == 5.0
    assert StyleProfile.load().zooms_per_minute == 5.0


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
