"""Onglet « Comparer » : étapes, passes Claude (faux LLM), comptes, réglages proposés et rapport.

Les modules de mesure (vision, soundscan, sheets) sont remplacés par des faux qui écrivent, à la main, les
fichiers JSON au format exact du contrat : ces tests ne dépendent que de leur forme, pas de leur précision.
"""

import json
import math
import re
import shutil
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import jsonschema
import pytest

from krokcut import benchmark
from krokcut import benchmark_report as br
from krokcut import sheets as real_sheets
from krokcut import techniques
from krokcut.benchmark import (
    BenchAnalyzer,
    BenchDoc,
    BenchmarkStore,
    aggregate_observations,
    approve_claude,
    estimate,
    inspiration_block,
    observe_fp,
    validate_observation,
)
from krokcut.config import AppConfig, StyleProfile
from krokcut.jobs import JobManager
from krokcut.llm import LLM, LLMError
from krokcut.pipeline import Pipeline
from krokcut.project import Project
from krokcut.prompts import base_system
from krokcut.references import ReferenceAnalyzer, ReferenceStore
from krokcut.sfx_detect import SFX_DETECTOR_VERSION
from krokcut.steps import Cancelled, StepRunner, StepStatus

SHEET_W, SHEET_H = 2256, 1396
CHUNK_S = 15.0
TILES_PER_SHEET = 9


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    """Trois petites vidéos (40 s, contenus différents) et les JPEG factices des faux modules."""
    root = tmp_path_factory.mktemp("comparer")
    sources = {"wankil": "testsrc2", "club": "smptehdbars", "krok": "rgbtestsrc"}
    clips = {}
    for key, src in sources.items():
        path = root / f"{key}_episode.mp4"
        _ffmpeg(
            "-f", "lavfi", "-i", f"{src}=s=320x180:r=30:d=40",
            "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:d=40",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        )
        clips[key] = path
    _ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=2256x1396", "-frames:v", "1", "-q:v", "8", str(root / "planche.jpg"))
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=64x36", "-frames:v", "1", str(root / "petite.jpg"))
    return {"root": root, **clips, "sheet": root / "planche.jpg", "small": root / "petite.jpg"}


# ------------------------------------------------------------------ faux modules de mesure (contrat A)
def make_fake_media(media) -> dict:
    vision = types.ModuleType("krokcut.vision")
    vision.IMAGE_VERSION = 1
    vision.calls = []
    vision.fail = False

    def analyze_image(src, out_dir, info, *, progress, hwaccel=None):
        if vision.fail:
            raise AssertionError("l'image ne devait pas être réanalysée")
        vision.calls.append(Path(src).name)
        out_dir = Path(out_dir)
        d = round(info.duration, 2)
        cuts = [8.0, 16.0, 25.0, 33.0]
        edges = [0.0, *cuts, d]
        plans = [
            {"id": f"P{i + 1:03d}", "start": a, "end": b, "cut_in": "debut" if i == 0 else "changement"}
            for i, (a, b) in enumerate(zip(edges[:-1], edges[1:]))
        ]
        (out_dir / "plans.json").write_text(json.dumps({
            "version": 1, "fps": 30, "duration": d, "content_box": [0, 0, 128, 72], "plans": plans,
            "cuts": [{"t": t, "kind": "meme_decor" if t == 16.0 else "changement", "pc": 0.12, "dhist": 0.8, "dpix": 0.2} for t in cuts],
        }))
        events = [
            {"id": "Z01", "type": "zoom", "t": 4.0, "end": 5.0, "dir": "avant", "scale": 1.25, "cx": 0.5, "cy": 0.5,
             "zone": "centre", "whole_frame": True, "ncc": 0.99, "gain": 0.17, "plan": "P001"},
            {"id": "F01", "type": "flash_blanc", "t": 12.0, "dur": 0.067, "plan": "P002"},
            {"id": "Z02", "type": "zoom", "t": 18.0, "end": 19.0, "dir": "avant", "scale": 1.5, "cx": 0.3, "cy": 0.3,
             "zone": "haut gauche", "whole_frame": False, "ncc": 0.9, "gain": 0.12, "plan": "P003"},
            {"id": "G01", "type": "fige", "t": 21.0, "dur": 1.0, "plan": "P003"},
            {"id": "N01", "type": "fondu_noir", "t": 28.0, "dur": 1.0, "plan": "P004"},
            {"id": "B01", "type": "noir_et_blanc", "t": 34.0, "dur": 2.0, "plan": "P005"},
        ]
        (out_dir / "image_evenements.json").write_text(json.dumps({"version": 1, "events": events}))
        (out_dir / "images4").mkdir(exist_ok=True)
        for k in range(3):
            shutil.copy(media["small"], out_dir / "images4" / f"f_{k:06d}.jpg")
        shutil.copy(media["small"], out_dir / "vignette.jpg")
        progress(1.0, "Analyse de l'image")
        minutes = d / 60
        return {
            "cuts": 4, "cuts_per_min": round(4 / minutes, 1), "median_shot": 8.0, "shot_p25": 7.0, "shot_p75": 8.0,
            "shot_p90": 9.0, "shots_under_1s_pct": 0.0, "jump_cut_pct": 25.0, "punch_ins": 2,
            "punch_ins_per_min": round(2 / minutes, 2), "zoom_scale_median": 1.375, "zoom_hold_median_s": 1.0,
            "zoom_layer_only_pct": 50.0, "flashes_per_min": 1.5, "inserts_per_min": 0.0, "freezes_per_min": 1.5,
            "fades_per_min": 1.5, "bw_per_10min": 15.0, "letterbox_pct": 0.0, "visual_changes_per_min": 10.5,
            "motion_mean": 0.02, "image_version": 1, "decode": "logiciel",
        }

    vision.analyze_image = analyze_image

    soundscan = types.ModuleType("krokcut.soundscan")
    soundscan.SOUND_VERSION = 1
    soundscan.DEFAULT_VAD = object()
    soundscan.calls = []

    def measure_loudness(src, out_dir, duration, on_progress):
        (Path(out_dir) / "volume.json").write_text(json.dumps({"I": -14.2, "LRA": 6.0, "true_peak_db": -1.0, "hop": 0.1, "M": [], "S": []}))
        on_progress(1.0)
        return {"loudness_i": -14.2, "loudness_lra": 6.0, "true_peak_db": -1.0, "loudness_spikes_per_min": 0.5, "shortterm_p95_p10": 8.0}

    def analyze_sound(pcm, out_dir, *, duration, words, cuts, visual_events, speech_provider=soundscan.DEFAULT_VAD,
                      library_hits=None, progress):
        soundscan.calls.append({"words": list(words), "cuts": list(cuts), "visual": len(visual_events),
                                "speech_provider": speech_provider, "library_hits": library_hits})
        out_dir = Path(out_dir)
        events = [
            {"id": "S001", "t": 4.05, "dur": 0.4, "cat": "boum", "label": "boum / impact grave", "rise_db": 14.0,
             "peak_vs_voice_db": 8.0, "f_line": 0, "in_speech": False, "with_visual": "Z01", "salience": 22.0, "confidence": 0.7},
            {"id": "S002", "t": 12.0, "dur": 0.5, "cat": "whoosh", "label": "whoosh / transition", "rise_db": 11.0,
             "peak_vs_voice_db": -2.0, "f_line": 0, "in_speech": False, "with_visual": "F01", "salience": 9.0, "confidence": 0.6},
            {"id": "S003", "t": 20.0, "dur": 0.6, "cat": "bip", "label": "bip (censure ?)", "rise_db": 15.0,
             "peak_vs_voice_db": 1.0, "f_line": 1000, "in_speech": True, "with_visual": "", "salience": 16.0, "confidence": 0.8},
            {"id": "S004", "t": 30.0, "dur": 0.3, "cat": "autre", "label": "autre son marquant", "rise_db": 12.0,
             "peak_vs_voice_db": -9.0, "f_line": 0, "in_speech": False, "with_visual": "", "salience": 3.0, "confidence": 0.3},
            {"id": "S005", "t": 36.0, "dur": 0.4, "cat": "boum", "label": "boum / impact grave", "rise_db": 13.0,
             "peak_vs_voice_db": 6.0, "f_line": 0, "in_speech": False, "with_visual": "", "salience": 19.0, "confidence": 0.6},
        ]
        (out_dir / "son_evenements.json").write_text(json.dumps({"version": 1, "events": events}))
        (out_dir / "musique.json").write_text(json.dumps({"version": 1, "pct": 50.0, "segments": [
            {"id": "M1", "start": 14.0, "end": 34.0, "kind": "rythmee", "bpm": 110.0, "level_vs_voice_db": -12.4,
             "start_kind": "progressive", "end_kind": "coupure_nette", "changes": [{"t": 24.0, "why": "tempo"}]}]}))
        (out_dir / "silences.json").write_text(json.dumps({
            "version": 1, "silences": [{"id": "C01", "t": 26.0, "dur": 0.6, "abrupt": True}], "dead_air": [],
            "pauses": {"p50": 0.2, "p90": 0.6, "p95": 0.8, "over_0_5s_pct": 12.0, "n": 40}, "reaction_tail": {"median": 0.4, "n": 4}}))
        (out_dir / "rythme.json").write_text(json.dumps({"windows": [
            {"t0": 0.0, "cuts_per_min": 4.0, "zooms_per_min": 2.0, "sounds_per_min": 6.0, "speech_share": 0.5, "loudness_m": -15.0},
            {"t0": 30.0, "cuts_per_min": 6.0, "zooms_per_min": 0.0, "sounds_per_min": 4.0, "speech_share": 0.4, "loudness_m": -14.0}]}))
        (out_dir / "son_trames.npz").write_bytes(b"")
        progress(1.0, "Analyse du son")
        recall = None
        if library_hits:
            recall = round(sum(any(abs(h - e["t"]) <= 0.15 for e in events) for h in library_hits) / len(library_hits), 2)
        minutes = duration / 60
        return {
            "sound_events_per_min": round(4 / minutes, 2), "sound_by_cat": {"boum": 3.0, "whoosh": 1.5, "bip": 1.5},
            "sound_level_vs_voice_db": 3.0, "events_with_visual_pct": 50.0, "zooms_with_sound_pct": 50.0,
            "music_pct": 50.0, "music_segments": 1, "music_bpm_median": 110.0, "music_level_vs_voice_db": -12.4,
            "music_changes_per_10min": 15.0, "music_cuts_per_10min": 15.0, "silences_per_10min": 15.0,
            "sound_cuts_per_10min": 15.0, "dead_air_pct": 2.0, "pause_p50": 0.2, "pause_p90": 0.6, "pause_p95": 0.8,
            "pauses_over_0_5s_pct": 12.0, "reaction_tail_median": 0.4, "cuts_in_word_pct": 10.0,
            "speech_source": "whisper", "library_recall": recall, "library_recall_n": len(library_hits or []), "sound_version": 1,
        }

    soundscan.measure_loudness = measure_loudness
    soundscan.analyze_sound = analyze_sound

    sheets = types.ModuleType("krokcut.sheets")
    sheets.SHEETS_VERSION = 1
    sheets.MAX_SHEETS_PER_CALL = 14
    sheets.PRESETS = {q: types.SimpleNamespace(observe_effort=e) for q, e in (("eco", "low"), ("standard", "medium"), ("detaille", "medium"))}
    sheets.chunk_s = CHUNK_S
    sheets.tiles_per_sheet = TILES_PER_SHEET
    sheets.calls = []
    sheets.effect_instant = real_sheets.effect_instant  # règle pure (instant et fenêtre de la case d'un effet)

    def build_sheets(src, work, *, quality, duration, plans, image_events, sound_events, music, silences, words, progress):
        sheets.calls.append(quality)
        work = Path(work)
        (work / "planches").mkdir(exist_ok=True)
        plan_of = lambda t: next((p for p in plans["plans"] if p["start"] <= t < p["end"]), plans["plans"][-1])  # noqa: E731
        times = [k + 0.5 for k in range(int(duration))]
        n_chunks = max(1, int(duration // sheets.chunk_s))
        if duration - n_chunks * sheets.chunk_s >= 0.4 * sheets.chunk_s:
            n_chunks += 1
        tiles, sheet_rows, chunk_rows, prev_plan = [], [], [], None
        for c in range(n_chunks):
            t0 = c * sheets.chunk_s
            t1 = duration if c == n_chunks - 1 else (c + 1) * sheets.chunk_s
            mine = [t for t in times if t0 <= t < t1]
            sheet_ids = []
            for k in range(0, len(mine), sheets.tiles_per_sheet):
                n = len(sheet_rows)
                block = mine[k : k + sheets.tiles_per_sheet]
                first = len(tiles)
                for cell, t in enumerate(block):
                    plan = plan_of(t)["id"]
                    tiles.append({"id": f"T{len(tiles) + 1:04d}", "t": t, "plan": plan, "new_plan": plan != prev_plan,
                                  "reasons": ["grille"], "tags": [], "chunk": c, "sheet": n, "cell": cell, "source": "images4"})
                    prev_plan = plan
                file = f"planches/planche_{n:03d}.jpg"
                shutil.copy(media["sheet"], work / file)
                sheet_rows.append({"n": n, "file": file, "w": SHEET_W, "h": SHEET_H, "tokens": math.ceil(SHEET_W * SHEET_H / 750),
                                   "chunk": c, "t0": block[0], "t1": block[-1], "first": tiles[first]["id"], "last": tiles[-1]["id"]})
                sheet_ids.append(n)
            chunk_rows.append({"n": c, "t0": t0, "t1": t1, "sheets": sheet_ids})
        data = {"version": 1, "quality": quality, "tile_w": 448, "tile_h": 252, "cols": 3, "rows": 3, "tiles": tiles,
                "sheets": sheet_rows, "chunks": chunk_rows, "image_tokens": sum(s["tokens"] for s in sheet_rows), "extracted": 0}
        (work / "planches.json").write_text(json.dumps(data))
        shutil.copy(media["small"], work / "controle.jpg")
        progress(1.0, "Planches")
        return data

    sheets.build_sheets = build_sheets
    return {"vision": vision, "soundscan": soundscan, "sheets": sheets}


REAL_MEDIA_TESTS = {"test_end_to_end_with_real_measures"}  # vrais modules de mesure (intégration)


@pytest.fixture(autouse=True)
def fake_media(media, monkeypatch, request):
    monkeypatch.setattr(benchmark, "SHORT_MINUTES", 0.5)  # nos vidéos de test font 40 s
    if request.node.name in REAL_MEDIA_TESTS:
        return {}
    mods = make_fake_media(media)
    for name, mod in mods.items():
        monkeypatch.setitem(sys.modules, f"krokcut.{name}", mod)
    return mods


# ------------------------------------------------------------------ faux Claude, aiguillé par label
IDS_RE = re.compile(r"\b(T\d{4}|S\d{3}|Z\d{2}|M\d+|L\d{3})\b")


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")


class FakeClaude:
    def __init__(self, usage=(20000, 500)):
        self.calls: list[dict] = []
        self.errors: dict[str, list[LLMError]] = {}
        self.usage = usage
        self.lock = threading.Lock()
        self.on_call = None
        self.observe = self.default_observe

    def __call__(self, llm, *, system, content, schema, effort="medium", max_tokens=0, label=""):
        with self.lock:
            self.calls.append({"label": label, "content": content, "system": system, "effort": effort, "max_tokens": max_tokens})
            n = len(self.calls)
            error = self.errors.get(label, []).pop(0) if self.errors.get(label) else None
        with llm._lock:
            llm.usage["calls"] += 1
            llm.usage["input"] += self.usage[0]
            llm.usage["output"] += self.usage[1]
        if self.on_call:
            self.on_call(label, n)
        if error:
            raise error
        if label.startswith("observe_"):
            result = self.observe(content_text(content))
        elif label == "video":
            result = VIDEO_PROFILE
        elif label.startswith("chaine_"):
            result = CHANNEL_PROFILE
        elif label == "comparaison":  # ne cite que des propositions que le schéma autorise
            allowed = schema["properties"]["recommandations"]["items"]["properties"]["proposition"]["enum"]
            result = json.loads(json.dumps(COMPARISON))
            for rec in result["recommandations"]:
                if rec["proposition"] not in allowed:
                    rec["proposition"] = allowed[-1]
        else:
            raise AssertionError(label)
        jsonschema.validate(result, schema)  # ce que renverrait l'API avec ce schéma
        return result

    @staticmethod
    def default_observe(text: str) -> dict:
        ids = list(dict.fromkeys(IDS_RE.findall(text)))
        tiles = [i for i in ids if i.startswith("T")]
        lines = [i for i in ids if i.startswith("L")]
        return {
            "resume": "Ils jouent.",
            "occurrences": [
                {"technique": "texte_impact", "tuile_debut": tiles[0], "tuile_fin": tiles[1], "texte_ecran": f"OUI {tiles[0]}",
                 "description": "texte jaune", "position": "centre", "lie_a": [], "certitude": "vu"},
                {"technique": "arret_sur_image", "tuile_debut": tiles[-1], "tuile_fin": tiles[-1], "texte_ecran": "",
                 "description": "image figée", "position": "plein_ecran", "lie_a": [], "certitude": "probable"},
            ],
            "verdicts": [{"id": i, "origine": "montage", "role": "ponctue_vanne"} for i in ids if i[0] in "SMZ"],
            "gags": [{"ligne": lines[0] if lines else "", "tuile": tiles[0], "citation": "mais t'es nul", "mise_en_place": "",
                      "chute": "il tombe", "mecaniques": ["contre_pied"], "techniques": ["texte_impact"], "sons": [],
                      "pourquoi": "", "force": 9}],
            "rythme": "nerveux", "style_textes": "jaune, contour noir", "mise_en_page": "deux_pov_cote_a_cote", "doutes": "",
        }

    def labels(self, prefix=""):
        return [c["label"] for c in self.calls if c["label"].startswith(prefix)]


VIDEO_PROFILE = {
    "resume": "Vidéo nerveuse.",
    "accroche": {"teaser": "oui", "duree_s": 8, "description": "le meilleur fail"},
    "structure": [{"debut": "0:00", "fin": "0:12", "role": "teaser", "titre": "Teaser"},
                  {"debut": "0:12", "fin": "0:40", "role": "partie", "titre": "La partie"}],
    "signatures": [{"technique": "texte_impact", "comment": "après chaque vanne", "quand": "chute", "frequence": "souvent", "exemple": "0:04 (T0004)"}],
    "mecaniques_dominantes": ["contre_pied"],
    "humour": "", "image": "", "textes": "", "son": "", "rythme": "",
    "meilleurs_exemples": [{"temps": "0:04", "tuile": "T0004", "quoi": "zoom", "pourquoi": "vanne", "techniques": ["zoom_sec"]}],
    "regles": ["Quand ça rate, alors zoom et boum."],
}
CHANNEL_PROFILE = {
    "identite": "Montage très rythmé.",
    "constantes": [{"technique": "arret_sur_image", "comment": "sur chaque fail", "prevalence": "toutes_les_videos"}],
    "recettes": [{"nom": "Fail figé", "quand": "un fail", "etapes": ["arrêt sur image", "zoom", "boum"],
                  "techniques": ["arret_sur_image", "zoom_sec"], "exemples": ["V1 0:04 (T0004)"]}],
    "humour": "", "image": "", "son": "", "rythme": "", "structure": "", "differences_entre_videos": "",
}
COMPARISON = {
    "verdict": "Ils coupent plus vite.",
    "axes": [{"axe": "rythme", "references": "très rapide", "vous": "plus posé", "ecart": "ecart", "preuves": "V1 0:04"}],
    "recommandations": [
        {"titre": "Plus de zooms", "pourquoi": "", "preuves": "", "exemple": "", "priorite": "haute", "type": "reglage",
         "proposition": "p_zooms_per_minute", "technique": "zoom_sec", "consigne": ""},
        {"titre": "Figer les fails", "pourquoi": "", "preuves": "", "exemple": "", "priorite": "moyenne", "type": "consigne",
         "proposition": "", "technique": "arret_sur_image", "consigne": "Fige l'image sur chaque fail."},
        {"titre": "Texte sur les vannes", "pourquoi": "", "preuves": "", "exemple": "", "priorite": "basse", "type": "consigne",
         "proposition": "", "technique": "texte_impact", "consigne": "Après une vanne, un texte impact de deux mots."},
    ],
    "a_garder": ["Vos vannes entre vous."],
    "resume_equipe": "…",
}


@pytest.fixture()
def claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(LLM, "ask_json", lambda self, **kw: fake(self, **kw))
    return fake


def with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


WORDS = [
    {"w": w, "s": round(2.0 + 0.4 * i, 2), "e": round(2.3 + 0.4 * i, 2), "p": 0.9}
    for i, w in enumerate("mais t'es nul regarde ça il est tombé encore une fois".split())
] + [
    {"w": w, "s": round(37.0 + 0.2 * i, 2), "e": round(37.15 + 0.2 * i, 2), "p": 0.5}
    for i, w in enumerate("Sous-titres réalisés par la communauté d'Amara.org".split())
]


def words(pcm, levels):
    return WORDS


def analyzer(store, doc, cfg, **kw):
    kw.setdefault("words_provider", words)
    kw.setdefault("speech_provider", None)
    return BenchAnalyzer(store.open(doc.id), cfg, store, **kw)


def chunk_count(doc) -> int:
    return len(doc.read_json("planches.json")["chunks"])


# ------------------------------------------------------------------ 1. de bout en bout, hors ligne
def test_end_to_end_offline(workspace, media, fake_media):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    assert [c.id for c in store.settings().channels] == ["wankil-studio", "club-pungouin", "krok-et-mil"]
    assert store.own_channel().members == "Krok, Mil"
    doc, created = store.add_or_get(media["wankil"], "wankil-studio")
    assert created and doc.state.blind_id == "V1"
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    st = doc.state.steps
    assert all(st[s].status == "done" for s in benchmark.LOCAL_STEPS)
    assert st["observe"].status == "skipped" and "Pas de clé Claude" in st["observe"].message
    assert st["synthesize"].status == "done"
    profile = doc.read_json("profil.json")
    assert profile["source"] == "mesures" and profile["regles"]
    assert doc.state.instrument == {"image": 1, "sound": 1, "whisper": "small", "sheets": 1, "quality": "standard"}
    m = doc.state.metrics
    assert m["cuts_per_min"] > 0 and m["loudness_i"] == -14.2 and m["music_pct"] == 50.0 and m["whisper_model"] == "small"
    assert m["duration_min"] == pytest.approx(0.7, abs=0.05) and not m["short"]
    lines = doc.read_json("transcription.json")["lines"]
    assert lines and not any("Amara" in l["text"] for l in lines)  # crédits inventés par Whisper retirés
    assert m["words"] == 11
    sound_call = fake_media["soundscan"].calls[-1]
    assert sound_call["cuts"] == [8.0, 16.0, 25.0, 33.0] and sound_call["speech_provider"] is None
    assert len(sound_call["words"]) == 11 and sound_call["library_hits"] is None
    assert doc.state.estimate["usd"] > 0 and doc.state.estimate["chunks"] == 3
    summary = benchmark.video_summary(doc, None, "", store.settings(), cfg)
    assert summary["status"] == "mesures_seules" and summary["has_thumb"] and "plans/min" in summary["headline"]

    # Le son seul est remis à zéro : l'image n'est pas refaite
    doc.invalidate(["sound"])
    fake_media["vision"].fail = True
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    assert store.open(doc.id).state.steps["sound"].status == "done"


def test_end_to_end_with_real_measures(workspace, media):
    """Intégration : les vrais modules de mesure (sautée tant qu'ils ne sont pas là)."""
    for name in ("vision", "soundscan", "sheets"):
        pytest.importorskip(f"krokcut.{name}")
    cfg = AppConfig.load()
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    assert all(doc.state.steps[s].status == "done" for s in benchmark.LOCAL_STEPS)
    assert doc.state.steps["observe"].status == "skipped" and doc.read_json("profil.json")["source"] == "mesures"
    for name in ("plans.json", "image_evenements.json", "son_evenements.json", "musique.json", "silences.json",
                 "rythme.json", "volume.json", "planches.json"):
        assert (doc.root / name).exists(), name
    planches = doc.read_json("planches.json")
    assert planches["tiles"] and planches["chunks"]
    assert doc.state.estimate["image_tokens"] == sum(math.ceil(s["w"] * s["h"] / 750) for s in planches["sheets"])
    content, ids = benchmark.build_chunk_request(doc, planches["chunks"][0], planches, store.settings())
    assert 1 <= sum(b["type"] == "image" for b in content) <= 14 and any(i.startswith("T") for i in ids)
    assert benchmark.local_fp(doc) == benchmark.current_local_fp(cfg)
    doc.invalidate(["sound"])
    vision = sys.modules["krokcut.vision"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(vision, "analyze_image", lambda *a, **k: (_ for _ in ()).throw(AssertionError("image refaite")))
        assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error


# ------------------------------------------------------------------ 2. attente de validation
def test_waits_for_approval_without_any_call(workspace, media, claude, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["club"], "club-pungouin")
    assert not analyzer(store, doc, cfg).run()
    doc = store.open(doc.id)
    assert doc.state.steps["observe"].status == "pending"
    assert doc.state.steps["observe"].message.startswith("En attente de ta validation : « Analyser avec Claude » (≈ ")
    assert claude.calls == []
    summary = benchmark.video_summary(doc, None, "", store.settings(), cfg)
    assert summary["status"] == "pret_claude" and summary["estimate"]["high"] > summary["estimate"]["low"] > 0


def jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i < len(data):
        marker, length = data[i + 1], int.from_bytes(data[i + 2 : i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(data[i + 5 : i + 7], "big")
        i += 2 + length
    raise ValueError("pas un JPEG")


def analysed_doc(store, cfg, media, key, channel, monkeypatch=None):
    doc, _ = store.add_or_get(media[key], channel)
    assert analyzer(store, doc, cfg).run(until="sheets"), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    approve_claude(doc)
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    return store.open(doc.id)


# ------------------------------------------------------------------ 3. extraits, images, aveugle
def test_chunks_are_blind_and_self_contained(workspace, media, claude, monkeypatch):
    import base64

    with_key(monkeypatch)
    cfg = AppConfig.load()
    store = BenchmarkStore()
    wankil = analysed_doc(store, cfg, media, "wankil", "wankil-studio")
    calls_wankil = list(claude.calls)
    nous = analysed_doc(store, cfg, media, "krok", "krok-et-mil")
    observes = [c for c in calls_wankil if c["label"].startswith("observe_")]
    assert len(observes) == chunk_count(wankil) == 3
    assert sorted(c["label"] for c in observes) == ["observe_00", "observe_01", "observe_02"]
    assert calls_wankil[-1]["label"] == "video"
    planches = wankil.read_json("planches.json")
    for call in observes:
        n = int(call["label"].split("_")[1])
        images = [b for b in call["content"] if b["type"] == "image"]
        assert 1 <= len(images) <= 14
        for img in images:
            assert max(jpeg_size(base64.b64decode(img["source"]["data"]))) <= 2576
        text = content_text(call["content"])
        mine = {t["id"] for t in planches["tiles"] if t["chunk"] == n}
        chunk = planches["chunks"][n]
        cited_tiles = set(re.findall(r"\bT\d{4}\b", text))
        assert cited_tiles and cited_tiles <= mine
        sounds = {e["id"] for e in wankil.read_json("son_evenements.json")["events"] if chunk["t0"] <= e["t"] < chunk["t1"]}
        assert set(re.findall(r"\bS\d{3}\b", text)) == sounds
        assert call["effort"] == "medium" and call["max_tokens"] == 32000
    first = content_text(next(c for c in observes if c["label"] == "observe_00")["content"])
    assert "Vidéo V1 — extrait 1/3, de 0:00.0 à 0:15.0 (vidéo de 0:40)" in first
    assert "[0:04.0] Z01 zoom sec ×1,25 (centre) jusqu'à 0:05.0 · tout le cadre · ≈T0005" in first
    assert "[0:04.0] S001 boum / impact grave · fort (+8 dB sur les voix) · hors parole · même instant que Z01" in first
    assert "MESURES DE L'EXTRAIT : 2 plans" in first
    for call in claude.calls:  # passes vidéo à l'aveugle : ni nom de chaîne ni nom de fichier
        blob = content_text(call["content"]) + call["system"]
        assert "Wankil" not in blob and "wankil" not in blob and "Krok" not in blob
    systems = {c["system"] for c in claude.calls if c["label"].startswith("observe_")}
    assert len(systems) == 1  # même système pour toutes les vidéos, toutes chaînes confondues
    detail = benchmark.video_detail(wankil, None, "", store.settings(), cfg)
    assert detail["status"] == "analysee" and len(detail["sheets"]) == 6 and detail["tiles"][0]["id"] == "T0001"
    first_occ = detail["observations"]["occurrences"][0]
    assert first_occ["label"] == "Texte d'impact (gros, centre)" and first_occ["sheet"] == 0 and first_occ["tile"] == "T0001"
    assert detail["profile"]["source"] == "claude" and detail["agregats"]["coverage"] == 1.0 and detail["log"]
    assert len([c for c in claude.calls if c["label"] == "video"]) == 2

    # Les passes chaîne et comparaison, elles, connaissent les noms
    for d in (wankil, nous):
        assert d.state.steps["synthesize"].status == "done" and d.read_json("profil.json")["source"] == "claude"
    status = br.report_status(store, cfg)
    assert status["can_run"] and status["estimate_usd"] > 0.5
    report = br.build_benchmark_report(store, cfg)
    chaine = [c for c in claude.calls if c["label"].startswith("chaine_")]
    assert {c["label"] for c in chaine} == {"chaine_wankil-studio", "chaine_krok-et-mil"}
    assert "Wankil Studio" in content_text(next(c for c in chaine if c["label"] == "chaine_wankil-studio")["content"])
    comparison = [c for c in claude.calls if c["label"] == "comparaison"]
    assert len(comparison) == 1 and "Wankil Studio" in comparison[0]["content"] and "Krok et Mil" in comparison[0]["content"]
    assert report["claude"]["verdict"] and report["recommendations"][0]["id"] == "r01"
    assert (store.root / "rapport.md").read_text("utf-8").startswith("# Comparaison du montage")
    assert store.settings().report_cost["calls"] == 3
    assert not br.report_status(store, cfg)["outdated"]
    # Profils de chaîne inchangés : pas redemandés
    before = len(claude.calls)
    br.build_benchmark_report(store, cfg)
    assert [c["label"] for c in claude.calls[before:]] == ["comparaison"]


# ------------------------------------------------------------------ 4. reprise
def test_resume_costs_nothing_and_cancel_keeps_finished_chunks(workspace, media, claude, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    cfg.llm_parallel_requests = 1
    store = BenchmarkStore()
    doc = analysed_doc(store, cfg, media, "wankil", "wankil-studio")
    n = len(claude.calls)
    assert analyzer(store, doc, cfg).run()
    assert len(claude.calls) == n  # déjà tout fait : aucun appel

    other, _ = store.add_or_get(media["club"], "club-pungouin")
    assert analyzer(store, other, cfg).run(until="sheets")
    other = store.open(other.id)
    approve_claude(other)
    claude.calls.clear()
    runner = analyzer(store, other, cfg)

    def cancel_after_second(label, n):
        if n == 2:
            runner.cancel.set()

    claude.on_call = cancel_after_second
    assert not runner.run()
    other = store.open(other.id)
    assert other.state.steps["observe"].status == "pending"
    done = len(list((other.root / "observations").glob("morceau_*.json")))
    assert done == 2 and other.state.claude["calls"] == 2
    claude.on_call = None
    claude.calls.clear()
    assert analyzer(store, other, cfg).run()
    assert claude.labels("observe_") == ["observe_02"] and claude.labels("video") == ["video"]


# ------------------------------------------------------------------ 5. robustesse
def test_split_on_truncation_refusal_and_network_error(workspace, media, claude, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    cfg.llm_parallel_requests = 1
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(until="sheets")
    approve_claude(store.open(doc.id))
    claude.errors = {"observe_01": [LLMError("Réponse tronquée", kind="tronque")]}
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    assert {"observe_01", "observe_01a", "observe_01b"} <= set(claude.labels("observe_"))
    rec = doc.read_json("observations/morceau_01.json")
    assert len(rec["analysed"]) == 2 and rec["failed"] == []
    assert len([o for o in rec["result"]["occurrences"] if o["technique"] == "texte_impact"]) == 2  # les deux moitiés
    assert doc.state.coverage == pytest.approx(1.0) and doc.state.failed_chunks == []

    # Refus, puis refus d'une moitié : la vidéo continue, couverture réduite, la synthèse le sait
    other, _ = store.add_or_get(media["club"], "club-pungouin")
    assert analyzer(store, other, cfg).run(until="sheets")
    approve_claude(store.open(other.id))
    claude.calls.clear()
    claude.errors = {"observe_01": [LLMError("refus", kind="refus")], "observe_01a": [LLMError("refus", kind="refus")]}
    assert analyzer(store, other, cfg).run(), store.open(other.id).state.last_error
    other = store.open(other.id)
    assert other.state.failed_chunks == [1] and other.state.coverage < 1
    video = next(c for c in claude.calls if c["label"] == "video")
    assert "refusés par Claude" in video["content"] and "extrait 2" in video["content"]
    assert benchmark.video_summary(other, None, "", store.settings(), cfg)["status"] == "partielle"

    # Erreur réseau : l'étape s'arrête en erreur, les extraits finis restent acquis
    third, _ = store.add_or_get(media["krok"], "krok-et-mil")
    assert analyzer(store, third, cfg).run(until="sheets")
    approve_claude(store.open(third.id))
    claude.errors = {"observe_01": [LLMError("Impossible de joindre l'API", kind="reseau")]}
    assert not analyzer(store, third, cfg).run()
    third = store.open(third.id)
    assert third.state.steps["observe"].status == "error" and "joindre" in third.state.last_error
    assert (third.root / "observations" / "morceau_00.json").exists()
    assert not (third.root / "observations" / "morceau_02.json").exists()  # rien d'envoyé après l'erreur
    claude.calls.clear()
    assert analyzer(store, third, cfg).run()
    assert sorted(claude.labels("observe_")) == ["observe_01", "observe_02"]


# ------------------------------------------------------------------ 6. garde-fou de budget
def test_budget_guard_pauses(workspace, media, claude, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    cfg.llm_parallel_requests = 1
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(until="sheets")
    approve_claude(store.open(doc.id))
    claude.usage = (5_000_000, 100_000)  # ≈ 22 $ par appel : bien plus que prévu
    assert not analyzer(store, doc, cfg).run()
    doc = store.open(doc.id)
    assert len(claude.labels("observe_")) == 1
    assert doc.state.claude_ok is False and doc.state.claude["usd"] == pytest.approx(22.0)
    assert doc.state.steps["observe"].message.startswith("Coût plus élevé que prévu : analyse en pause (22 $ dépensés)")
    assert "Continuer l'analyse Claude" in doc.state.steps["observe"].message
    # Continuer : nouvelle validation, le garde-fou repart de la dépense déjà faite
    claude.usage = (1000, 100)
    approve_claude(doc)
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error


# ------------------------------------------------------------------ 7. comptes déterministes
def hand_doc(store, name, *, duration=60.0, channel="wankil-studio") -> BenchDoc:
    src = store.files_dir / f"{name}.bin"
    src.write_bytes(name.encode() * 1000)
    doc, _ = store.add_or_get(src, channel)
    doc.state.metrics.update(duration_s=duration, duration_min=round(duration / 60, 1))
    doc.state.instrument.update(sheets=1, quality="standard", observe=1, model=AppConfig.load().model)
    doc.save()
    tiles = [{"id": f"T{k + 1:04d}", "t": k + 0.5, "plan": "P001", "sheet": k // 30, "cell": k % 30, "chunk": k // 30} for k in range(int(duration))]
    doc.write_json("planches.json", {"tiles": tiles, "sheets": [], "chunks": [{"n": 0, "t0": 0, "t1": 30, "sheets": [0]}, {"n": 1, "t0": 30, "t1": 60, "sheets": [1]}]})
    doc.write_json("son_evenements.json", {"events": [
        {"id": "S001", "t": 5.0, "cat": "boum"}, {"id": "S002", "t": 10.0, "cat": "whoosh"}, {"id": "S003", "t": 40.0, "cat": "boum"}]})
    doc.write_json("image_evenements.json", {"events": [{"id": "Z01", "type": "zoom", "t": 8.0, "dir": "avant"}]})
    return doc


def record(doc, n, t0, t1, occurrences, verdicts=(), gags=()):
    (doc.root / "observations").mkdir(exist_ok=True)
    doc.write_json(f"observations/morceau_{n:02d}.json", {
        "chunk": n, "t0": t0, "t1": t1, "observe_version": 1, "fp": observe_fp(doc), "invalid_refs": 1,
        "analysed": [[t0, t1]], "failed": [], "usage": {},
        "result": {"resume": "", "occurrences": list(occurrences), "verdicts": list(verdicts), "gags": list(gags),
                   "rythme": "", "style_textes": "", "mise_en_page": "jeu_et_facecams", "doutes": ""}})


def occ(tech, t, text="", tile=None, links=(), certitude="vu"):
    return {"technique": tech, "tuile_debut": tile or f"T{int(t) + 1:04d}", "tuile_fin": tile or f"T{int(t) + 1:04d}", "t": t, "end": t,
            "sheet": 0, "cell": int(t), "texte_ecran": text, "description": "", "position": "centre", "lie_a": list(links), "certitude": certitude}


def test_deterministic_counts(workspace):
    store = BenchmarkStore()
    doc = hand_doc(store, "comptes")
    # Validation : ids inventés retirés et comptés, Z sans verdict « incertain », fin avant début échangée
    ids = {"T0001", "T0002", "T0003", "S001", "Z01", "L001"}
    tiles = {f"T000{k}": {"t": k - 0.5, "sheet": 0, "cell": k - 1} for k in (1, 2, 3)}
    raw = {
        "resume": "", "rythme": "", "style_textes": "", "mise_en_page": "inconnue", "doutes": "",
        "occurrences": [
            {"technique": "texte_impact", "tuile_debut": "T0003", "tuile_fin": "T0001", "texte_ecran": "NON", "description": "",
             "position": "centre", "lie_a": ["S001", "S999"], "certitude": "vu"},
            {"technique": "meme_image", "tuile_debut": "T9999", "tuile_fin": "T9999", "texte_ecran": "", "description": "",
             "position": "coin", "lie_a": [], "certitude": "vu"},
        ],
        "verdicts": [{"id": "S001", "origine": "montage", "role": "ponctue_vanne"}, {"id": "S999", "origine": "montage", "role": "inconnu"}],
        "gags": [{"ligne": "L001", "tuile": "T0002", "citation": "x", "mise_en_place": "", "chute": "", "mecaniques": ["absurde"],
                  "techniques": [], "sons": [], "pourquoi": "", "force": 12}],
    }
    result, invalid = validate_observation(raw, ids, tiles)
    assert invalid == 4  # T9999 deux fois, S999 dans lie_a et dans les verdicts
    assert [o["technique"] for o in result["occurrences"]] == ["texte_impact"]
    first = result["occurrences"][0]
    assert (first["tuile_debut"], first["tuile_fin"], first["t"]) == ("T0001", "T0003", 0.5) and first["lie_a"] == ["S001"]
    verdicts = {v["id"]: v["origine"] for v in result["verdicts"]}
    assert verdicts == {"S001": "montage", "Z01": "incertain"}
    assert result["gags"][0]["force"] == 5 and result["gags"][0]["t"] == 1.5

    # 3 textes en 30 s regardées = 6/min ; doublon à cheval sur deux extraits retiré
    record(doc, 0, 0.0, 30.0, [occ("texte_impact", 1, "UN"), occ("texte_impact", 10, "DEUX"), occ("texte_impact", 29.5, "Trois !")],
           verdicts=[{"id": "S001", "origine": "montage", "role": "ponctue_vanne"}, {"id": "S002", "origine": "jeu_ou_joueurs", "role": "bruit_du_jeu"},
                     {"id": "Z01", "origine": "incertain", "role": "inconnu", "auto": True}])
    agg = aggregate_observations(doc)
    assert agg["techniques"]["texte_impact"]["per_min"] == 6.0 and agg["analysed_s"] == 30.0 and agg["coverage"] == 0.5
    assert agg["sounds"]["montage_per_min"] == 2.0 and agg["sounds"]["jeu_per_min"] == 2.0  # S002 (jeu) exclu des bruitages
    assert agg["zooms"]["confirmed_per_min"] == 0.0
    record(doc, 1, 30.0, 60.0, [occ("texte_impact", 30.5, "trois")], verdicts=[{"id": "S003", "origine": "montage", "role": "ponctue_vanne"}])
    agg = aggregate_observations(doc)
    assert agg["techniques"]["texte_impact"]["n"] == 3  # « Trois ! » et « trois » à 1 s d'écart : un seul texte
    assert agg["sounds"]["montage_by_cat"] == {"boum": 2.0}
    assert agg["invalid_refs"] == 2
    m = store.open(doc.id).state.metrics
    assert m["sfx_montage_per_min"] == 2.0 and m["claude_texts_per_min"] == 3.0 and m["layout"] == "jeu_et_facecams"


# ------------------------------------------------------------------ 8. estimation et coût
def test_estimate_cost_and_calibration(workspace, media, claude, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(until="sheets")
    doc = store.open(doc.id)
    planches = doc.read_json("planches.json")
    est = estimate(doc, store.settings())
    assert est["image_tokens"] == sum(math.ceil(s["w"] * s["h"] / 750) for s in planches["sheets"]) == 6 * 4200
    assert est["low"] < est["usd"] < est["high"] and est["tokens_out"] == 3 * 10000 + 10000
    approve_claude(doc)
    assert analyzer(store, doc, cfg).run()
    doc = store.open(doc.id)
    per_call = (20000 * 4 + 500 * 20) / 1e6
    assert doc.state.claude["calls"] == 4 and doc.state.claude["usd"] == pytest.approx(4 * per_call)
    assert store.settings().calib_output["standard"] == pytest.approx(0.7 * 10000 + 0.3 * 500)
    # Refaire l'analyse : la dépense s'ajoute
    benchmark.reset_claude(doc)
    approve_claude(store.open(doc.id))
    assert analyzer(store, doc, cfg).run()
    assert store.open(doc.id).state.claude["usd"] == pytest.approx(8 * per_call)


# ------------------------------------------------------------------ 9. reprise depuis « Mes vidéos »
def reference_with_audio(media, key, *, model="small"):
    from krokcut.ffmpeg_utils import extract_pcm
    import numpy as np
    from krokcut.audio import level_curve

    refs = ReferenceStore()
    ref = refs.add(media[key])
    extract_pcm(media[key], ref.root / "audio.pcm")
    np.save(ref.root / "niveaux.npy", level_curve(ref.root / "audio.pcm"))
    ref.write_json("transcription.json", {"lines": [{"id": 0, "start": 2.0, "end": 2.6, "speaker": None, "text": "reprise de mes vidéos",
                                                     "words": [["reprise", 2.0, 2.2], ["de", 2.2, 2.3], ["mes", 2.3, 2.4], ["vidéos", 2.4, 2.6]],
                                                     "kind": "speech", "loud": False, "laugh": False}], "whisper_model": model})
    metrics = {"sfx_checked": True, "sfx_detector": SFX_DETECTOR_VERSION, "sfx_per_min": 3.0}
    if model:
        metrics["whisper_model"] = model
    ref.set_metrics(**metrics)
    ref.write_json("bruitages.json", {"hits": [{"t": 4.0, "asset": "sfx/boum"}, {"t": 31.0, "asset": "sfx/boum"}], "music": []})
    return refs, ref


def test_import_from_my_videos(workspace, media, fake_media, monkeypatch):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    refs, ref = reference_with_audio(media, "krok")

    def no_extract(*a, **k):
        raise AssertionError("le son de « Mes vidéos » doit être repris")

    def no_words(pcm, levels):
        raise AssertionError("la transcription (même modèle) doit être reprise")

    monkeypatch.setattr(benchmark, "extract_pcm", no_extract)
    doc, created = store.import_reference(ref, cfg)
    assert created and doc.state.channel == "krok-et-mil" and doc.state.origin == "mes_videos" and doc.state.origin_id == ref.id
    assert doc.state.copied and Path(doc.state.path).parent == store.files_dir
    assert Path(doc.state.path).stat().st_ino == Path(ref.state.path).stat().st_ino or Path(doc.state.path).exists()
    assert (doc.root / "audio.pcm").exists() and doc.read_json("transcription.json")["reused_from"] == ref.id
    assert store.import_reference(ref, cfg)[1] is False  # pas deux fois
    assert analyzer(store, doc, cfg, words_provider=no_words).run(), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    assert doc.state.metrics["words"] == 4
    assert fake_media["vision"].calls == [Path(doc.state.path).name]  # image refaite par l'instrument commun
    assert fake_media["soundscan"].calls[-1]["library_hits"] == [4.0, 31.0]
    assert doc.state.metrics["library_recall"] == 0.5 and doc.state.metrics["library_recall_n"] == 2
    assert refs.open(ref.id)  # sans « déplacer », la vidéo reste dans « Mes vidéos »

    # Modèle inconnu : on retranscrit (gratuit) ; déplacement vers une chaîne modèle
    refs2, ref2 = reference_with_audio(media, "wankil", model="")
    called = []
    doc2, _ = store.import_reference(ref2, cfg, channel="wankil-studio", move=True)
    assert doc2.state.channel == "wankil-studio" and not doc2.read_json("transcription.json")
    assert ref2.id not in [r.id for r in ReferenceStore().list()] and Path(doc2.state.path).exists()
    assert analyzer(store, doc2, cfg, words_provider=lambda p, l: called.append(1) or WORDS).run()
    assert called == [1]

    # « Mes vidéos » enregistre maintenant le modèle de transcription
    ref3 = ReferenceStore().open(ref.id)
    ref3.set_metrics(duration_s=40.0)
    runner = ReferenceAnalyzer(ref3, cfg, ReferenceStore(), words_provider=lambda p, l: WORDS[:3])
    runner.step_transcribe()
    assert ref3.state.metrics["whisper_model"] == "fourni" and ref3.read_json("transcription.json")["whisper_model"] == "fourni"
    assert ReferenceAnalyzer(ref3, cfg, ReferenceStore()).whisper_model() == "small"


# ------------------------------------------------------------------ 10. doublons
def test_duplicates_across_channels(workspace, media):
    store = BenchmarkStore()
    doc, created = store.add_or_get(media["wankil"], "wankil-studio")
    again, created2 = store.add_or_get(media["wankil"], "club-pungouin")
    assert created and not created2 and again.id == doc.id
    assert benchmark.duplicate_info(store, again)["channel_name"] == "Wankil Studio"
    copy = store.files_dir / "copie.mp4"
    shutil.copy(media["wankil"], copy)
    assert store.add_or_get(copy, "club-pungouin")[0].id == doc.id and not copy.exists()  # copie en double supprimée
    with pytest.raises(FileNotFoundError):
        store.add_or_get(store.files_dir / "absent.mp4", "wankil-studio")
    with pytest.raises(KeyError):
        store.add_or_get(media["club"], "inconnue")
    # Règles des chaînes
    with pytest.raises(ValueError):
        store.add_channel("Encore nous", role="nous")
    kc = store.add_channel("", role="krokcut")
    assert kc.name == "Montages KrokCut"
    with pytest.raises(ValueError):
        store.add_channel("Deuxième", role="krokcut")
    with pytest.raises(ValueError):
        store.remove_channel("krok-et-mil")
    with pytest.raises(ValueError):
        store.remove_channel("wankil-studio")
    store.remove_channel("wankil-studio", with_videos=True)
    assert not store.list() and "wankil-studio" not in [c.id for c in store.settings().channels]
    assert store.update_channel("club-pungouin", name="Club Pingouin").name == "Club Pingouin"


# ------------------------------------------------------------------ 11. invalidation
def test_invalidation_quality_and_version(workspace, media, fake_media, monkeypatch):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(until="sheets")
    doc = store.open(doc.id)
    for s in ("observe", "synthesize"):  # comme après une analyse Claude
        doc.state.steps[s] = StepStatus(status="done", finished=time.time())
    doc.state.instrument.update(observe=1, model=cfg.model)
    doc.state.claude_ok = True
    doc.state.claude["calls"] = 4
    doc.save()
    doc.write_json("profil.json", {"source": "claude"})
    (doc.root / "observations").mkdir()
    doc.write_json("observations/morceau_00.json", {"chunk": 0, "fp": benchmark.observe_fp(doc), "result": {}})
    assert benchmark.quality_change_usd(store, "eco") == pytest.approx(0.7 * 0.075, abs=0.01)
    touched = benchmark.set_quality(store, cfg, "eco")
    doc = store.open(doc.id)
    assert [d.id for d in touched] == [doc.id]
    assert not (doc.root / "observations").exists() and not (doc.root / "profil.json").exists()  # lus avec l'ancien instrument
    assert [s for s in benchmark.BENCH_STEP_IDS if doc.state.steps[s].status == "pending"] == ["sheets", "observe", "synthesize"]
    assert doc.state.claude_ok is False
    assert analyzer(store, doc, cfg).run(until="sheets")
    assert fake_media["sheets"].calls[-1] == "eco"
    with_key(monkeypatch)
    assert benchmark.video_summary(store.open(doc.id), None, "", store.settings(), cfg)["status"] == "a_mettre_a_jour"
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    # Nouvelle version des mesures d'image : au démarrage, image et la suite à refaire, en local seulement
    monkeypatch.setattr(fake_media["vision"], "IMAGE_VERSION", 2)
    doc = store.open(doc.id)
    doc.state.claude_ok = True
    doc.save()
    plan = benchmark.startup_plan(store, cfg)
    doc = store.open(doc.id)
    assert plan == [(doc.id, "sheets")]
    assert [s for s in benchmark.BENCH_STEP_IDS if doc.state.steps[s].status == "pending"] == [
        "image", "sound", "sheets", "observe", "synthesize"]
    # Interruption : l'étape « en cours » repasse en attente au démarrage
    doc.set_step("image", status="running")
    assert benchmark.startup_plan(store, cfg) == [(doc.id, "sheets")]
    assert store.open(doc.id).state.steps["image"].message == BenchDoc.INTERRUPTED_MSG


# ------------------------------------------------------------------ 12. réglages proposés
def row(rid, unit, values):
    return {"id": rid, "unit": unit, "note": "", "values": {
        c: {"median": v, "min": v, "max": v, "n": n, "sum": s} for c, (v, n, s) in values.items()}}


def proposal(props, field):
    return next(p for p in props if p["field"] == field)


def test_proposals(workspace):
    style = StyleProfile(zooms_per_minute=4.0, max_silence=0.55)
    table = [
        row("zooms_total_per_min", "/min", {"wankil": (6.0, 2, 12), "nous": (2.0, 2, 4)}),
        row("punch_ins", "", {"wankil": (4.0, 2, 8), "nous": (3.0, 2, 6)}),
        row("zoom_scale_median", "×", {"wankil": (1.5, 2, 3), "nous": (1.2, 2, 2.4)}),
        row("pause_p90", "s", {"wankil": (0.70, 2, 1.4), "nous": (0.50, 2, 1.0)}),
        row("sound_events_per_min", "/min", {"wankil": (9.0, 2, 18), "nous": (3.0, 2, 6)}),
        row("median_shot", "s", {"wankil": (2.5, 2, 5), "nous": (2.5, 2, 5)}),
    ]
    props = br.propose_settings(table, style, 0.5, "nous", ["wankil"], names={"wankil": "Wankil Studio"})
    zooms = proposal(props, "zooms_per_minute")
    assert zooms["proposed"] == 7.0 and zooms["checked"] and zooms["source"] == "mesuré + confirmé par Claude"
    assert zooms["why"] == "Wankil Studio 6/min · vous 2/min · réglage actuel 4 → à mi-chemin : 7"
    assert proposal(br.propose_settings(table, style, 1.0, "nous", ["wankil"]), "zooms_per_minute")["proposed"] == 12.0
    assert proposal(br.propose_settings(table, style, 1 / 3, "nous", ["wankil"]), "zooms_per_minute")["proposed"] == 6.0
    silence = proposal(props, "max_silence")
    assert silence["proposed"] == 0.65 and silence["checked"]
    scale = proposal(props, "punch_scale")
    assert scale["proposed"] == 1.4 and not scale["checked"]  # moins de 10 zooms mesurés de chaque côté
    sfx = proposal(props, "sfx_per_minute")
    assert sfx["source"].startswith("estimé") and not sfx["checked"]
    shot = proposal(props, "min_shot")
    assert shot["close"] and not shot["checked"] and "déjà proche" in shot["why"]
    # Base nulle : repli additif ; bornes respectées
    table0 = [row("zooms_total_per_min", "/min", {"wankil": (3.0, 2, 6), "nous": (0.0, 2, 0)})]
    z0 = proposal(br.propose_settings(table0, style, 0.5, "nous", ["wankil"]), "zooms_per_minute")
    assert z0["proposed"] == 5.5 and z0["rule"] == "ratio_additif"
    huge = [row("zooms_total_per_min", "/min", {"wankil": (60.0, 2, 120), "nous": (1.0, 2, 2)})]
    assert proposal(br.propose_settings(huge, style, 1.0, "nous", ["wankil"]), "zooms_per_minute")["proposed"] == 15.0
    # Une seule vidéo d'un côté : rien de coché
    thin = [row("zooms_total_per_min", "/min", {"wankil": (6.0, 1, 6), "nous": (2.0, 2, 4)})]
    assert not proposal(br.propose_settings(thin, style, 0.5, "nous", ["wankil"]), "zooms_per_minute")["checked"]
    # Les cibles changent R
    two = [row("zooms_total_per_min", "/min", {"wankil": (6.0, 2, 12), "club": (2.0, 2, 4), "nous": (2.0, 2, 4)})]
    both = proposal(br.propose_settings(two, style, 1.0, "nous", ["wankil", "club"]), "zooms_per_minute")
    only = proposal(br.propose_settings(two, style, 1.0, "nous", ["wankil"]), "zooms_per_minute")
    assert both["ref"] == 4.0 and only["ref"] == 6.0 and only["proposed"] > both["proposed"]
    # Claude ne donne jamais de valeur : aucun nombre dans le schéma de la comparaison
    schema = json.dumps(br.comparison_schema(["p_zooms_per_minute"]))
    assert '"number"' not in schema and '"integer"' not in schema and "p_zooms_per_minute" in schema


# ------------------------------------------------------------------ 13. équité (vidéos factices)
def fake_video(store, cfg, cid, name, metrics, *, claude=True, quality="standard", coverage=1.0, image_version=1,
               profile=None, agg=None):
    src = store.files_dir / f"{name}.bin"
    src.write_bytes(name.encode() * 500)
    doc, _ = store.add_or_get(src, cid)
    doc.state.metrics.update({"duration_s": 720.0, "duration_min": 12.0, "short": False, **metrics})
    for s in benchmark.LOCAL_STEPS:
        doc.state.steps[s] = StepStatus(status="done", finished=time.time())
    doc.state.instrument = {"image": image_version, "sound": 1, "whisper": "small", "sheets": 1, "quality": quality}
    if claude:
        for s in benchmark.CLAUDE_STEPS:
            doc.state.steps[s] = StepStatus(status="done", finished=time.time())
        doc.state.instrument.update(observe=1, model=cfg.model)
        doc.state.coverage = coverage
        doc.write_json("profil.json", profile or {"source": "claude", **VIDEO_PROFILE})
        (doc.root / "observations").mkdir(exist_ok=True)
        doc.write_json("observations/agregats.json", agg or {"analysed_s": 720.0, "techniques": {}, "verdicts": {}})
    doc.save()
    return doc


def test_fairness_and_exclusions(workspace, claude):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    fake_video(store, cfg, "wankil-studio", "w1", {"cuts_per_min": 20.0, "claude_texts_per_min": 3.0})
    nous = fake_video(store, cfg, "krok-et-mil", "k1", {"cuts_per_min": 10.0, "claude_texts_per_min": 1.0}, claude=False)
    ok, why = br.Study(store, cfg).can_run()
    assert not ok and why == br.REFUSED_MSG
    with pytest.raises(ValueError, match="Reprendre depuis Mes vidéos"):
        br.build_benchmark_report(store, cfg)
    assert br.report_status(store, cfg)["why_not"] == br.REFUSED_MSG
    # Ancienne version des mesures : exclue, avec sa raison
    fake_video(store, cfg, "wankil-studio", "w-old", {"cuts_per_min": 99.0}, image_version=0)
    study = br.Study(store, cfg)
    assert {"id": "w-old", "name": "w-old", "reason": "mesurée par une ancienne version : relance les mesures (gratuit)"} in study.excluded["wankil-studio"]
    table = {r["id"]: r for r in br.metrics_table(store, cfg)}
    assert table["cuts_per_min"]["values"]["wankil-studio"]["median"] == 20.0  # w-old ne compte pas
    assert table["cuts_per_min"]["ecart"]["wankil-studio"]["label"] == "gros_ecart"  # r = 2, fourchettes disjointes
    assert table["cuts_per_min"]["ecart"]["wankil-studio"]["confirm"] == "à confirmer (1 seule vidéo)"
    # Vos vidéos analysées dans une autre qualité : ce que Claude a vu n'est pas comparable
    nous.state.steps["observe"] = nous.state.steps["synthesize"] = StepStatus(status="done", finished=time.time())
    nous.state.instrument.update(quality="eco", sheets=1, observe=1, model=cfg.model)
    nous.state.coverage = 1.0
    nous.save()
    nous.write_json("profil.json", {"source": "claude", **VIDEO_PROFILE})
    study = br.Study(store, cfg)
    assert study.claude_excluded["krok-et-mil"][0]["reason"] == "analyse Claude en qualité Économique"
    table = {r["id"]: r for r in br.metrics_table(store, cfg)}
    assert table["claude_texts_per_min"]["note"] == br.INCOMPLETE and table["claude_texts_per_min"]["ecart"] == {}
    assert table["cuts_per_min"]["note"] == ""
    # La base est la colonne « Montages KrokCut » dès qu'elle a une vidéo comptée
    kc = store.add_channel("", role="krokcut")
    assert br.Study(store, cfg).base == "krok-et-mil"
    fake_video(store, cfg, kc.id, "rendu1", {"cuts_per_min": 12.0}, claude=False)
    assert br.Study(store, cfg).base == kc.id
    # Couverture trop faible
    fake_video(store, cfg, "club-pungouin", "c1", {"cuts_per_min": 15.0}, coverage=0.4)
    assert br.Study(store, cfg).claude_excluded["club-pungouin"][0]["reason"] == "couverture Claude 40 %"
    # Le tableau en direct n'appelle jamais Claude
    def boom(self, **kw):
        raise AssertionError("pas d'appel à Claude")

    import krokcut.llm as llm_mod
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(llm_mod.LLM, "ask_json", boom)
        live = br.live_report(store, cfg, intensity="comme_eux", targets=["wankil-studio"])
    assert live["intensity"] == "comme_eux" and live["targets"] == ["wankil-studio"] and live["table"]
    assert live["guarantee"].startswith("✓ Les ")


# ------------------------------------------------------------------ 14. recommandations et faisabilité
def test_recommendations_feasibility_and_library_gaps(workspace, claude):
    proposals = [{"id": "p_zooms_per_minute", "close": False}, {"id": "p_min_shot", "close": True}]
    recs = br.normalize_recommendations([
        {"titre": "Réglage inconnu", "type": "reglage", "proposition": "", "technique": "", "consigne": "Plus de zooms punch.", "priorite": "basse"},
        {"titre": "Réglage déjà proche", "type": "reglage", "proposition": "p_min_shot", "technique": "", "consigne": "", "priorite": "basse"},
        {"titre": "Figer", "type": "consigne", "proposition": "", "technique": "arret_sur_image", "consigne": "Fige l'image.", "priorite": "haute"},
        {"titre": "Zoom", "type": "pas_encore_faisable", "proposition": "", "technique": "zoom_sec", "consigne": "Zoom punch sur la chute." + "x" * 400, "priorite": "moyenne"},
        {"titre": "Zooms", "type": "reglage", "proposition": "p_zooms_per_minute", "technique": "", "consigne": "", "priorite": "haute"},
        {"titre": "Zooms bis", "type": "reglage", "proposition": "p_zooms_per_minute", "technique": "", "consigne": "", "priorite": "haute"},
    ], proposals)
    kinds = [(r["id"], r["type"], r["technique"]) for r in recs]
    assert kinds == [("r01", "pas_encore_faisable", "arret_sur_image"), ("r02", "reglage", ""), ("r03", "consigne", "zoom_sec"), ("r04", "consigne", "")]
    assert len(recs[2]["consigne"]) == 300

    cfg = AppConfig.load()
    store = BenchmarkStore()
    freeze = {"n": 7, "per_min": 0.6, "vu": 7, "probable": 0,
              "examples": [{"t": 63.0, "tile": "T0064", "sheet": 2, "cell": 13, "texte": "", "description": "fail figé"}]}
    zoom = {"n": 30, "per_min": 2.5, "vu": 30, "probable": 0, "examples": []}
    for k in range(2):
        fake_video(store, cfg, "wankil-studio", f"w{k}", {"sfx_montage_by_cat": {"boum": 2.1}},
                   agg={"analysed_s": 700.0, "verdicts": {}, "techniques": {"arret_sur_image": freeze, "zoom_sec": zoom}})
    fake_video(store, cfg, "krok-et-mil", "k0", {"sfx_montage_by_cat": {}})
    study = br.Study(store, cfg)
    rates = br.technique_rates(store, cfg, study=study)
    assert rates["techniques"]["arret_sur_image"]["rates"] == {"wankil-studio": 0.6, "krok-et-mil": 0.0}
    roadmap = br.feasibility(rates, {"wankil-studio": CHANNEL_PROFILE}, study.base)
    first = roadmap[0]
    assert first["technique"] == "arret_sur_image" and first["constant"] and first["examples"][0]["tile"] == "T0064"
    assert first["examples"][0]["video"] == "w0" and first["todo"] and first["workaround"]
    assert all(techniques.support(r["technique"]) != "oui" for r in roadmap)  # une technique faisable n'y entre jamais
    gaps = br.library_gaps(cfg, rates)  # bibliothèque vide
    boum = next(g for g in gaps if g["category"] == "boum")
    assert boum["text"].startswith("Wankil Studio utilise souvent des boums (≈ 2,1/min) : votre bibliothèque n'en a aucun")


# ------------------------------------------------------------------ 15. inspirations
def test_inspirations(workspace, claude, monkeypatch):
    assert inspiration_block() == "" and not workspace.exists()  # rien créé sur un espace de travail vide
    store = BenchmarkStore()
    (store.root / "rapport.json").write_text(json.dumps({"updated": "2026-10-07T10:00:00", "recommendations": [
        {"id": "r01", "titre": "Vannes", "type": "consigne", "technique": "texte_impact", "consigne": "Après une vanne, un texte impact."},
        {"id": "r02", "titre": "Figer", "type": "pas_encore_faisable", "technique": "arret_sur_image", "consigne": "Fige l'image."},
    ]}))
    with pytest.raises(ValueError, match="ne sait pas encore"):
        br.save_inspirations(store, True, ["r02"])
    saved = br.save_inspirations(store, False, ["r01"])
    assert saved["text"] == "- Après une vanne, un texte impact." and inspiration_block() == ""
    br.save_inspirations(store, True)
    block = inspiration_block()
    assert block.startswith("## Pistes d'inspiration choisies par l'équipe") and "texte impact" in block
    assert "les consignes spécifiques puis la bible de la chaîne priment sur ces pistes" in block
    br.save_inspirations(store, True, text="y" * 9000)
    assert len(json.loads((store.root / "inspirations.json").read_text())["text"]) == 5000
    br.save_inspirations(store, True, text="- Après une vanne, un texte impact.")

    style = StyleProfile(notes="Pas de gros mots.")
    prompt = base_system("La bible.", style, {"A": "Krok", "B": "Mil"}, reference="Guide.", inspiration=inspiration_block())
    assert prompt.index("Repères tirés") < prompt.index("Pistes d'inspiration") < prompt.index("## La chaîne") < prompt.index("Consignes spécifiques")
    project = Project.create("Ep", [str(store.root / "x.mp4")], [str(store.root / "y.mp4")])
    assert "Après une vanne, un texte impact." in Pipeline(project, AppConfig.load()).system_prompt()
    br.save_inspirations(store, False)
    assert "Pistes d'inspiration" not in Pipeline(project, AppConfig.load()).system_prompt()


# ------------------------------------------------------------------ 16. file d'attente
def test_job_order_and_report_dedup():
    manager = JobManager(start=False)
    manager.submit("rapport-bidon", kind="project")
    manager.submit("v1", kind="benchmark", until="sheets")
    assert manager.submit_benchmark_report() and not manager.submit_benchmark_report()
    manager.submit("ref1", kind="reference")
    manager.submit_guide()
    order = []
    with manager._lock:
        while manager.pending:
            job = manager.next_job_locked()
            order.append(job.kind)
    assert order == ["reference", "guide", "project", "benchmark", "benchmark_report"]


def test_job_errors_are_recorded(workspace):
    from krokcut.jobs import Job, _record_error

    store = BenchmarkStore()
    src = store.files_dir / "a.bin"
    src.write_bytes(b"x" * 10)
    doc, _ = store.add_or_get(src, "wankil-studio")
    _record_error(Job(doc.id, kind="benchmark"), RuntimeError("panne imprévue"))
    assert store.open(doc.id).state.last_error == "panne imprévue"
    _record_error(Job("benchmark_report", kind="benchmark_report"), ValueError(br.REFUSED_MSG))
    assert br.report_status(store, AppConfig.load())["error"] == br.REFUSED_MSG


def test_techniques_table():
    from krokcut.prompts import BENCH_SYSTEM

    by_support = {s: {t.id for t in techniques.TECHNIQUES if t.support == s} for s in ("oui", "partiel", "non")}
    assert {"zoom_sec", "zoom_lent", "tremblement", "changement_pov", "ecran_partage", "incrustation_pov", "jump_cut",
            "personnage_detoure", "meme_image", "texte_impact", "texte_meme", "texte_legende", "fondu_noir",
            "transition_whoosh", "teaser", "chapitrage", "bruitage_ponctuel", "musique_fond", "changement_musique"} == by_support["oui"]
    assert {"zoom_cible", "meme_video", "sticker_emoji", "sous_titres_continus", "carton_titre", "bip_censure",
            "montee_riser"} == by_support["partiel"]
    easy = {t.id for t in techniques.TECHNIQUES if t.support == "non" and t.effort == "facile"}
    assert easy == {"flash", "filtre_couleur", "bandes_cinema", "silence_comique", "musique_coupee_net", "son_sature", "generique"}
    assert {t.id for t in techniques.TECHNIQUES if t.effort == "difficile"} == {"annotation", "habillage_graphique"}
    assert len(set(techniques.ALL_IDS)) == len(techniques.ALL_IDS) and techniques.VISUAL_IDS[-1] == "autre"
    assert all(t.todo and t.workaround and t.effort for t in techniques.TECHNIQUES if t.support != "oui")
    assert all(f"- {tid} : " in BENCH_SYSTEM for tid in techniques.VISUAL_IDS)  # une définition chacune
    assert all(f"- {h} : " in BENCH_SYSTEM for h in techniques.HUMOR_IDS)
    assert techniques.support("inconnue") == "non" and techniques.label("zoom_sec") == "Zoom sec (punch-in)"


# ------------------------------------------------------------------ 17. rétrocompatibilité
def test_backward_compatibility(workspace):
    assert LLMError("x").kind == "api" and LLMError("y", kind="refus").kind == "refus" and LLMError("z", kind="?").kind == "api"
    store = BenchmarkStore()
    src = store.files_dir / "a.bin"
    src.write_bytes(b"abc" * 100)
    doc, _ = store.add_or_get(src, "krok-et-mil")

    class Runner(StepRunner):
        step_ids = benchmark.BENCH_STEP_IDS

        def __init__(self, doc, exc):
            super().__init__(doc)
            self.exc = exc

        def step_probe(self):
            raise self.exc

    assert not Runner(doc, Cancelled("En attente de ta validation")).run()
    assert doc.state.steps["probe"].message == "En attente de ta validation"
    assert not Runner(doc, Cancelled()).run()
    assert doc.state.steps["probe"].message == "Annulé" and doc.state.steps["probe"].status == "pending"


def test_apply_proposals_only_touches_chosen_fields(workspace, claude):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    for k in range(2):
        fake_video(store, cfg, "wankil-studio", f"w{k}", {"zooms_total_per_min": 6.0, "pause_p90": 0.7})
        fake_video(store, cfg, "krok-et-mil", f"k{k}", {"zooms_total_per_min": 2.0, "pause_p90": 0.5})
    with pytest.raises(ValueError, match="Aucun réglage choisi."):
        br.apply_proposals(store, cfg, [])
    style, applied = br.apply_proposals(store, cfg, ["zooms_per_minute"])
    assert applied == ["zooms_per_minute"] and style.zooms_per_minute == 7.0 and style.max_silence == 0.55
    assert StyleProfile.load().zooms_per_minute == 7.0


def test_big_chunk_is_split_and_ui_helpers(workspace, media, claude, fake_media, monkeypatch):
    with_key(monkeypatch)
    cfg = AppConfig.load()
    cfg.llm_parallel_requests = 1
    store = BenchmarkStore()
    fake_media["sheets"].chunk_s = 200.0  # un seul extrait…
    fake_media["sheets"].tiles_per_sheet = 2  # … de 20 planches : trop pour une seule requête
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run(until="sheets")
    doc = store.open(doc.id)
    assert len(doc.read_json("planches.json")["chunks"][0]["sheets"]) == 20
    pending = benchmark.pending_claude(store)
    assert pending["count"] == 1 and pending["ids"] == [doc.id] and pending["low"] < pending["usd"] < pending["high"]
    approve_claude(doc)
    assert benchmark.pending_claude(store)["count"] == 0  # validée : plus « en attente »
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    assert claude.labels("observe_") == ["observe_00a", "observe_00b"]
    assert all(len([b for b in c["content"] if b["type"] == "image"]) == 10 for c in claude.calls if c["label"].startswith("observe_"))
    assert benchmark.spent_usd(store) == benchmark.spent_usd(store, "wankil-studio") > 0
    assert store.open(doc.id).state.coverage == pytest.approx(1.0)


def test_report_outdated_when_a_video_moves(workspace, claude):
    cfg = AppConfig.load()
    store = BenchmarkStore()
    w = fake_video(store, cfg, "wankil-studio", "w1", {"cuts_per_min": 20.0})
    fake_video(store, cfg, "club-pungouin", "c1", {"cuts_per_min": 15.0})
    fake_video(store, cfg, "krok-et-mil", "k1", {"cuts_per_min": 10.0})
    report = br.build_benchmark_report(store, cfg)
    assert report["claude_error"].startswith("Pas de clé Claude") and claude.calls == []
    assert br.report_status(store, cfg)["exists"] and not br.report_status(store, cfg)["outdated"]
    store.move(w.id, "club-pungouin")
    assert br.report_status(store, cfg)["outdated"]
    assert br.live_report(store, cfg)["outdated"]


def test_unmeasurable_values_are_unknown_not_zero(workspace):
    """Sans zoom, sans musique, sans son marquant : 0 veut dire « pas mesuré » (ni médiane, ni réglage)."""
    cfg = AppConfig.load()
    store = BenchmarkStore()
    for k in range(2):
        fake_video(store, cfg, "wankil-studio", f"w{k}", {
            "punch_ins": 30, "zoom_scale_median": 1.5, "music_segments": 2, "music_level_vs_voice_db": -18.0,
            "music_pct": 60.0, "sound_events_per_min": 8.0, "sound_level_vs_voice_db": 2.0, "pause_p90": 0.7,
            "events_with_visual_pct": 40.0, "gags_per_min": 1.5, "gag_force_mean": 3.2, "shot_p25": 0.8})
        fake_video(store, cfg, "krok-et-mil", f"k{k}", {
            "punch_ins": 0, "zoom_scale_median": 0.0, "music_segments": 0, "music_level_vs_voice_db": 0.0,
            "music_pct": 0.0, "sound_events_per_min": 0.0, "sound_level_vs_voice_db": 0.0, "pause_p90": 0.0,
            "events_with_visual_pct": 0.0, "gags_per_min": 0.0, "gag_force_mean": 0.0, "shot_p25": 0.0})
    table = {r["id"]: r for r in br.metrics_table(store, cfg)}
    for rid in ("zoom_scale_median", "music_level_vs_voice_db", "sound_level_vs_voice_db", "pause_p90",
                "events_with_visual_pct", "gag_force_mean", "shot_p25"):
        assert "krok-et-mil" not in table[rid]["values"] and table[rid]["values"]["wankil-studio"]["n"] == 2, rid
    assert table["music_pct"]["values"]["krok-et-mil"]["median"] == 0.0  # 0 % de musique, lui, est une mesure
    props = {p["field"] for p in br.live_report(store, cfg)["proposals"]}
    assert not props & {"punch_scale", "sfx_volume_db", "music_volume_db", "max_silence"}
    assert "music" in props  # « mettre de la musique » reste proposé


def test_key_added_after_measures_only(workspace, media, claude, monkeypatch):
    """Mesurée sans clé (« mesures seules ») : une fois la clé ajoutée, Claude se lance sans rien remesurer."""
    cfg = AppConfig.load()
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["wankil"], "wankil-studio")
    assert analyzer(store, doc, cfg).run()
    doc = store.open(doc.id)
    assert doc.state.steps["observe"].status == "skipped"
    assert benchmark.video_summary(doc, None, "", store.settings(), cfg)["status"] == "mesures_seules"
    assert benchmark.pending_claude(store, cfg)["count"] == 0
    with_key(monkeypatch)
    assert benchmark.video_summary(doc, None, "", store.settings(), cfg)["status"] == "pret_claude"
    assert benchmark.pending_claude(store, cfg)["ids"] == [doc.id]
    approve_claude(doc)
    assert benchmark.startup_plan(store, cfg) == [(doc.id, None)]  # validée puis KrokCut fermé : reprise au démarrage
    fake_media = {name: sys.modules[f"krokcut.{name}"] for name in ("vision", "soundscan")}
    fake_media["vision"].fail = True  # rien n'est remesuré
    assert analyzer(store, doc, cfg).run(), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    assert doc.state.steps["observe"].status == "done" and doc.read_json("profil.json")["source"] == "claude"
    assert claude.labels("video") == ["video"] and len(claude.labels("observe_")) == chunk_count(doc)
    assert benchmark.video_summary(doc, None, "", store.settings(), cfg)["status"] == "analysee"


def test_move_while_running_is_kept(workspace, media):
    """« Déplacer vers… » pendant les mesures : le traitement en cours n'écrase pas la nouvelle chaîne."""
    store = BenchmarkStore()
    doc, _ = store.add_or_get(media["club"], "wankil-studio")
    running = store.open(doc.id)  # l'état gardé en mémoire par le traitement
    store.move(doc.id, "club-pungouin")
    running.set_step("probe", status="running")
    running.set_metrics(duration_s=40.0)
    disk = store.open(doc.id)
    assert disk.state.channel == "club-pungouin" and disk.state.steps["probe"].status == "running"
    assert disk.state.metrics["duration_s"] == 40.0 and running.state.channel == "club-pungouin"
    with pytest.raises(KeyError):
        store.move(doc.id, "inconnue")
    with pytest.raises(ValueError):
        disk.edit(name="autre")  # seuls la chaîne et la propriété du fichier se changent ainsi


def test_move_out_of_my_videos_without_hard_link(workspace, media, monkeypatch):
    """Lien dur impossible (autre disque) : la comparaison garde la copie de « Mes vidéos » et l'efface avec elle."""
    cfg = AppConfig.load()
    store = BenchmarkStore()
    refs = ReferenceStore()
    copy = refs.files_dir / "wankil_episode.mp4"
    shutil.copy(media["wankil"], copy)
    ref = refs.add(copy)
    assert ref.state.copied

    def no_link(src, dst):
        raise OSError("lien dur impossible")

    monkeypatch.setattr(benchmark.os, "link", no_link)
    doc, created = store.import_reference(ref, cfg, channel="wankil-studio")  # d'abord sans déplacer
    assert created and not doc.state.copied and Path(doc.state.path) == copy.resolve()
    doc2, created2 = store.import_reference(refs.open(ref.id), cfg, channel="wankil-studio", move=True)
    assert not created2 and doc2.id == doc.id
    assert ref.id not in [r.id for r in ReferenceStore().list()] and copy.exists()  # le fichier reste
    doc = store.open(doc.id)
    assert doc.state.copied
    store.remove(doc.id)
    assert not copy.exists()  # plus personne ne s'en sert : effacé avec la vidéo de comparaison
    # Un fichier de « Mes vidéos » encore utilisé par une référence n'est jamais effacé
    other = refs.files_dir / "club_episode.mp4"
    shutil.copy(media["club"], other)
    ref2 = refs.add(other)
    doc3, _ = store.import_reference(ref2, cfg)
    doc3.edit(copied=True)
    store.remove(doc3.id)
    assert other.exists() and refs.open(ref2.id)
