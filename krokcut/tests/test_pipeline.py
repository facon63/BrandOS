"""Tests de bout en bout sur de faux rush (sans Whisper ni appel réseau)."""

import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from krokcut import pipeline as pipeline_mod
from krokcut.config import AppConfig, StyleProfile
from krokcut.ffmpeg_utils import probe
from krokcut.library import Library
from krokcut.llm import LLM
from krokcut.pipeline import Pipeline
from krokcut.project import STEP_IDS, Project
from krokcut.timeline import Timeline

from .conftest import B_DELAY


def make_project(rushes, library_dir, **style_overrides):
    cfg = AppConfig.load()
    cfg.library_dir = str(library_dir)
    cfg.render.preview_height = 180
    cfg.render.workers = 2
    cfg.save()
    Library.scan(library_dir)
    style = StyleProfile(target_min_minutes=0.4, target_max_minutes=0.9, **style_overrides)
    project = Project.create("Test épisode", [str(rushes["a"])], [str(rushes["b"])], style=style)
    return project, cfg


def pixel(video, t, x, y):
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"crop=1:1:{x}:{y},format=rgb24", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    return raw[0], raw[1], raw[2]


def check_outputs(project: Project):
    tl = Timeline.model_validate(project.read_json("timeline.json"))
    video = project.out / "montage_preview.mp4"
    info = probe(video)
    assert info.height == 180 and info.has_audio
    assert info.duration == pytest.approx(tl.duration, abs=0.25)
    root = ET.parse(project.out / "timeline_premiere_davinci.xml").getroot()
    assert len(root.findall(".//clipitem")) >= len(tl.clips)
    assert (project.out / "sous_titres.srt").read_text("utf-8").count("-->") > 3
    assert (project.out / "chapitres_youtube.txt").read_text("utf-8").startswith("0:00")
    assert "Déroulé" in (project.out / "recap.md").read_text("utf-8")
    return tl


def test_full_pipeline_offline(workspace, rushes, library_dir):
    project, cfg = make_project(rushes, library_dir, denoise=True)
    pipe = Pipeline(project, cfg, words_provider=lambda mix, levels: rushes["words"])
    assert pipe.run(), project.state.last_error
    assert all(project.state.steps[s].status == "done" for s in STEP_IDS)

    # Synchro : B a démarré 3,5 s après A
    assert project.source("A").offset == 0.0
    assert project.source("B").offset == pytest.approx(B_DELAY, abs=0.03)

    lines = project.read_json("transcription.json")["lines"]
    speech = [l for l in lines if l["kind"] == "speech"]
    assert len(speech) > 10
    # Les répliques alternent entre les deux micros
    assert {l["speaker"] for l in speech} == {"A", "B"}
    assert any(l["kind"] == "event" for l in lines)  # les fous rires sans paroles sont repérés

    story = project.read_json("histoire.json")
    assert story["source"] == "heuristic" and story["sequence"]
    tl = check_outputs(project)
    assert tl.duration <= 0.9 * 60 + 15
    assert {c.pov for c in tl.clips} >= {"A", "B"}

    # Relance partielle : seul le rendu est refait, les plans déjà rendus sont réutilisés
    clips_dir = project.work / "plans_preview"
    before = {p.name: p.stat().st_mtime for p in clips_dir.glob("*.mkv")}
    assert Pipeline(project, cfg).run(from_step="render")
    after = {p.name: p.stat().st_mtime for p in clips_dir.glob("*.mkv")}
    assert before == after


def fake_ask_json(self, *, system, content, schema, effort="medium", max_tokens=0, label=""):
    text = content if isinstance(content, str) else "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    if label.startswith("derush"):
        ids = [int(x) for x in re.findall(r"^#(\d+) ", text, re.M)]
        moments = []
        for k in range(0, max(1, len(ids) - 6), 12):
            moments.append(
                {"start_line": ids[k], "end_line": ids[min(k + 5, len(ids) - 1)], "title": f"Moment {k}", "kind": "punchline",
                 "humor": 8, "energy": 7, "story": 5, "key_quote": "t'es sérieux là", "depends_on": "", "why": "drôle"}
            )
        return {"summary": "Ils jouent et rigolent.", "moments": moments}
    if label.startswith("story"):
        rows = re.findall(r"^(m\d{3}) .*?lignes #(\d+)–#(\d+)", text, re.M)
        seq = [{"moment": m, "trim_start_line": -1, "trim_end_line": -1, "chapter": "Partie 1" if i == 0 else "",
                "transition": "whoosh" if i == 2 else "cut"} for i, (m, _, _) in enumerate(rows[:4])]
        m0, s0, e0 = rows[1]
        return {"summary": "Une partie mouvementée.", "title_ideas": ["ON A TOUT RATÉ"], "thumbnail_ideas": ["Krok choqué"],
                "cold_open": {"moment": m0, "start_line": int(s0), "end_line": int(s0) + 1}, "sequence": seq, "notes": ""}
    if label.startswith("edit"):
        assert "perso/krok/krok_rire" in system and "sfx/boing_cartoon" in system
        out = []
        for block in re.split(r"^### Moment ", text, flags=re.M)[1:]:
            mid = block.split()[0]
            ids = [int(x) for x in re.findall(r"^#(\d+) ", block, re.M)]
            speech_words = re.findall(r"^#(\d+) \[[^\]]+\] \w+ : (\S+)", block, re.M)
            first_line, first_word = (int(speech_words[0][0]), speech_words[0][1]) if speech_words else (ids[0], "")
            out.append(
                {
                    "moment": mid,
                    "camera": [{"line": ids[0], "pov": "A"}, {"line": ids[len(ids) // 2], "pov": "both"}],
                    "zooms": [{"line": first_line, "word": first_word, "kind": "punch", "duration": 1.0},
                              {"line": ids[-1], "word": "", "kind": "shake", "duration": 0.6}],
                    "sfx": [{"asset": "sfx/boing_cartoon", "line": ids[-1], "word": "", "timing": "end_of_line", "volume": "normal"},
                            {"asset": "sfx/inexistant", "line": ids[0], "word": "", "timing": "on_word", "volume": "low"}],
                    "characters": [{"asset": "perso/krok/krok_rire", "line": first_line, "word": "", "position": "bottom_right", "duration": 0},
                                   {"asset": "clip/choc_fond_vert", "line": ids[-1], "word": "", "position": "center", "duration": 1.0}],
                    "texts": [{"line": first_line, "word": first_word, "text": "Le moment culte", "style": "impact"}],
                    "remove_lines": [],
                }
            )
        moment_ids = re.findall(r"^### Moment (m\d{3})", text, re.M)
        music = [{"asset": "music/chill_lofi", "from_moment": moment_ids[0], "to_moment": moment_ids[-1]}]
        return {"moments": out, "music": music}
    raise AssertionError(label)


def test_full_pipeline_with_claude_decisions(workspace, rushes, library_dir, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(LLM, "ask_json", fake_ask_json)
    project, cfg = make_project(rushes, library_dir, layout="pip")
    pipe = Pipeline(project, cfg, words_provider=lambda mix, levels: rushes["words"])
    assert pipe.use_claude()
    assert pipe.run(), project.state.last_error

    story = project.read_json("histoire.json")
    assert story["source"] == "claude" and story["cold_open"]
    tl = check_outputs(project)
    assert tl.segments[0].moment_id == "cold_open"
    assert "both" in {c.pov for c in tl.clips}
    assert any(z.kind == "shake" for c in tl.clips for z in c.zooms)
    assert {o.asset_id for o in tl.overlays} == {"perso/krok/krok_rire", "clip/choc_fond_vert"}
    assert "sfx/inexistant" not in {s.asset_id for s in tl.sfx}  # identifiant inconnu ignoré
    assert tl.music and tl.texts

    # Le personnage (webm VP9 avec transparence, rectangle rouge) est bien visible en bas à droite
    krok = next(o for o in tl.overlays if o.asset_id == "perso/krok/krok_rire")
    W, H = 320, 180
    h = int(H * krok.scale) // 2 * 2
    w = h * 200 / 300
    x, y = int(W - int(W * 0.03) - w / 2), int(H - h / 2)
    r, g, b = pixel(project.out / "montage_preview.mp4", krok.start + 1.0, x, y)
    assert r > 170 and g < 90 and b < 90, (r, g, b)

    # La sélection retouchée : on retire un moment, seules les nouvelles décisions sont redemandées
    calls = []
    monkeypatch.setattr(LLM, "ask_json", lambda self, **kw: calls.append(kw["label"]) or fake_ask_json(self, **kw))
    story["sequence"] = story["sequence"][:-1]
    project.write_json("histoire.json", story)
    assert Pipeline(project, cfg).run(from_step="edit")
    assert calls == []  # toutes les décisions étaient déjà en cache


def test_pipeline_reports_missing_file(workspace, tmp_path):
    project = Project.create("Cassé", [str(tmp_path / "absent.mp4")], [str(tmp_path / "absent2.mp4")])
    assert not Pipeline(project, AppConfig.load()).run()
    assert project.state.steps["probe"].status == "error"
    assert "introuvable" in project.state.last_error


def test_pipeline_cancel(workspace, rushes, library_dir):
    project, cfg = make_project(rushes, library_dir)
    pipe = Pipeline(project, cfg, words_provider=lambda mix, levels: rushes["words"])
    pipe.cancel.set()
    assert not pipe.run()
    assert project.state.steps["audio"].status == "pending"


def test_pipeline_module_exports():
    assert hasattr(pipeline_mod, "Pipeline")
