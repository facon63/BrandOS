"""« Comparer » de bout en bout, hors ligne : les vrais modules de mesure, un faux Claude.

Le faux montage synthétique (tests/synth_media.py) passe par toutes les étapes de BenchAnalyzer, dans la
chaîne Wankil Studio ; une seconde vidéo, reprise de « Mes vidéos » (son et transcription repris, puis
retirée de « Mes vidéos »), passe par les mêmes étapes dans la chaîne « nous ». Le rapport de comparaison
est ensuite établi. On vérifie que tout se tient d'un bout à l'autre : les cases que cite la chronologie
envoyée à Claude montrent bien l'effet mesuré, les cases citées par Claude redonnent les bons temps, les
comptes les retrouvent, et le tableau comme les réglages proposés comparent bien les deux chaînes.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

from krokcut import benchmark, sheets
from krokcut import benchmark_report as br
from krokcut.audio import level_curve
from krokcut.benchmark import BenchAnalyzer, BenchmarkStore, VideoData, approve_claude
from krokcut.config import AppConfig
from krokcut.ffmpeg_utils import decode_jpegs, extract_pcm
from krokcut.llm import LLM
from krokcut.references import ReferenceStore
from krokcut.sfx_detect import SFX_DETECTOR_VERSION

from . import synth_media as sm

CHUNK_S = 20.0  # extraits courts : plusieurs appels « observe » sur 50 s
NOUS_SECONDS = 42.0
LINE_RE = re.compile(r"^\[[^\]]+\] (?P<id>[ZFGNBSMCL]\d+) (?P<rest>.*)$", re.M)
TILE_RE = re.compile(r"≈(T\d{4})")
INVALID_REF = "S999"  # référence inventée, glissée dans chaque réponse : retirée et comptée


# ------------------------------------------------------------------ médias
def nous_video(tmp: Path) -> tuple[Path, list[tuple[float, float]], list[tuple[float, str, float]]]:
    """Notre vidéo : 7 plans de 6 s (mires qui bougent), voix synthétique et 8 sortes de bruitages."""
    x, words, plan = sm.sound_mix(seed=5, seconds=NOUS_SECONDS)
    tmp.mkdir(parents=True, exist_ok=True)
    wav = tmp / "nous.wav"
    sm.write_wav(wav, x)
    looks = ["", ",negate", ",hue=h=120", ",hflip,negate", ",vflip", ",hue=h=240,hflip", ""]
    graph = ";".join(f"testsrc2=s=640x360:r=30:d=6{f},format=yuv420p,setsar=1[s{i}]" for i, f in enumerate(looks))
    graph += ";" + "".join(f"[s{i}]" for i in range(len(looks))) + f"concat=n={len(looks)}:v=1:a=0[v]"
    dst = tmp / "krok_episode.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-filter_complex", graph, "-i", str(wav),
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-t", str(NOUS_SECONDS), str(dst)],
        check=True,
    )
    return dst, words, plan


def lines_of(words: list[tuple[float, float]]) -> list[dict]:
    """Transcription au format de build_lines : une ligne par phrase (blanc de plus de 0,6 s)."""
    groups: list[list[tuple[float, float]]] = []
    for s, e in sorted(words):
        if groups and s - groups[-1][-1][1] <= 0.6:
            groups[-1].append((s, e))
        else:
            groups.append([(s, e)])
    return [
        {"id": i, "start": g[0][0], "end": g[-1][1], "speaker": None, "text": " ".join(f"mot{j}" for j in range(len(g))),
         "words": [[f"mot{j}", s, e] for j, (s, e) in enumerate(g)], "kind": "speech", "loud": False, "laugh": False}
        for i, g in enumerate(groups)
    ]


def as_words(words: list[tuple[float, float]]) -> list[dict]:
    return [{"w": f"mot{i}", "s": s, "e": e, "p": 0.9} for i, (s, e) in enumerate(words)]


# ------------------------------------------------------------------ faux Claude
def text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")


class FakeClaude:
    """Répond comme Claude, en ne citant que ce que la requête lui montre (ids de la chronologie, cases)."""

    def __init__(self):
        self.calls: list[dict] = []
        self.cited: dict[str, dict[str, str]] = {}  # label -> {id d'effet: case citée par la chronologie}

    def __call__(self, llm, *, system, content, schema, effort="medium", max_tokens=0, label=""):
        self.calls.append({"label": label, "content": content, "system": system, "effort": effort})
        with llm._lock:
            llm.usage["calls"] += 1
            llm.usage["input"] += 20000
            llm.usage["output"] += 800
        if label.startswith("observe_"):
            return self.observe(label, text_of(content))
        if label == "video":
            return {"resume": "Vidéo nerveuse.", "accroche": {"teaser": "non", "duree_s": 0, "description": ""},
                    "structure": [], "signatures": [], "mecaniques_dominantes": ["contre_pied"], "humour": "", "image": "",
                    "textes": "", "son": "", "rythme": "", "meilleurs_exemples": [], "regles": ["Quand ça rate, alors boum."]}
        if label.startswith("chaine_"):
            return {"identite": "Montage rythmé.", "constantes": [], "recettes": [], "humour": "", "image": "", "son": "",
                    "rythme": "", "structure": "", "differences_entre_videos": ""}
        if label == "comparaison":
            allowed = schema["properties"]["recommandations"]["items"]["properties"]["proposition"]["enum"]
            prop = "p_zooms_per_minute" if "p_zooms_per_minute" in allowed else allowed[-1]
            return {"verdict": "Ils zooment plus.", "axes": [], "a_garder": ["Vos vannes."], "resume_equipe": "…",
                    "recommandations": [{"titre": "Plus de zooms", "pourquoi": "", "preuves": "", "exemple": "", "priorite": "haute",
                                         "type": "reglage", "proposition": prop, "technique": "zoom_sec", "consigne": ""}]}
        raise AssertionError(label)

    def observe(self, label: str, text: str) -> dict:
        header_tiles = re.findall(r"Cases (T\d{4}) à (T\d{4})", text)[0]
        lines = {m["id"]: m["rest"] for m in LINE_RE.finditer(text)}
        cited = {i: TILE_RE.search(rest).group(1) for i, rest in lines.items() if TILE_RE.search(rest)}
        self.cited[label] = cited
        occurrences, verdicts = [], []
        for i, rest in lines.items():
            if i[0] == "Z":
                occurrences.append(self.occ("zoom_sec", cited[i], [i]))
            elif i[0] == "F" and "flash blanc" in rest:
                occurrences.append(self.occ("flash", cited[i], [i]))
            elif i[0] == "S" and "boum" in rest:  # un texte d'impact sur chaque boum (textes différents : pas de doublon)
                occurrences.append(self.occ("texte_impact", cited[i], [i], texte=f"BOUM {i}"))
            if i[0] in "SMZ":
                origin = "jeu_ou_joueurs" if i[0] == "S" and "bip" in rest else "montage"
                verdicts.append({"id": i, "origine": origin, "role": "ponctue_vanne"})
        first_line = next((i for i in lines if i[0] == "L"), "")
        return {
            "resume": "Ils jouent.", "occurrences": occurrences, "verdicts": verdicts,
            "gags": [{"ligne": first_line, "tuile": header_tiles[0], "citation": "mais t'es nul", "mise_en_place": "", "chute": "",
                      "mecaniques": ["contre_pied"], "techniques": ["texte_impact"], "sons": [], "pourquoi": "", "force": 3}],
            "rythme": "nerveux", "style_textes": "jaune", "mise_en_page": "jeu_plein_ecran", "doutes": "",
        }

    @staticmethod
    def occ(tech: str, tile: str, links: list[str], texte: str = "") -> dict:
        return {"technique": tech, "tuile_debut": tile, "tuile_fin": tile, "texte_ecran": texte, "description": "",
                "position": "centre", "lie_a": [*links, INVALID_REF], "certitude": "vu"}

    def labels(self, prefix: str = "") -> list[str]:
        return [c["label"] for c in self.calls if c["label"].startswith(prefix)]


# ------------------------------------------------------------------ outils
def jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i < len(data):
        marker, length = data[i + 1], int.from_bytes(data[i + 2 : i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(data[i + 5 : i + 7], "big")
        i += 2 + length
    raise ValueError("pas un JPEG")


def measure(store, doc, cfg, **kw):
    """Mesures locales, validation du coût, puis Claude (comme le bouton « Analyser avec Claude »)."""
    assert BenchAnalyzer(store.open(doc.id), cfg, store, speech_provider=None, **kw).run(until="sheets"), store.open(doc.id).state.last_error
    doc = store.open(doc.id)
    assert doc.state.steps["observe"].status == "pending" and doc.state.estimate["usd"] > 0
    approve_claude(doc)
    assert BenchAnalyzer(store.open(doc.id), cfg, store, speech_provider=None, **kw).run(), store.open(doc.id).state.last_error
    return store.open(doc.id)


def observe_calls(claude: FakeClaude, blind: str) -> list[dict]:
    return [c for c in claude.calls if c["label"].startswith("observe_") and text_of(c["content"]).startswith(f"Vidéo {blind} ")]


def check_video(doc, claude: FakeClaude) -> dict:
    """Ce que Claude a reçu et ce que le code en a compté, pour une vidéo analysée de bout en bout."""
    data = VideoData(doc)
    st = doc.state.steps
    assert all(s.status == "done" for s in st.values()), {k: (s.status, s.message) for k, s in st.items()}
    assert doc.read_json("profil.json")["source"] == "claude" and not (doc.root / "images4").exists()
    assert doc.state.instrument == {"image": 1, "sound": 1, "whisper": "small", "sheets": 1, "quality": "standard",
                                    "observe": 1, "model": AppConfig.load().model}
    assert benchmark.local_fp(doc) == benchmark.current_local_fp(AppConfig.load())
    planches = data.planches
    tiles = data.tiles_by_id
    calls = observe_calls(claude, doc.state.blind_id)
    assert len(calls) == len(data.chunks) >= 2

    # Requêtes : planches entières (≤ 14 par appel), à l'aveugle, ids de l'extrait seulement
    seen_ids: list[str] = []
    for call, chunk in zip(sorted(calls, key=lambda c: c["label"]), data.chunks):
        images = [b for b in call["content"] if b["type"] == "image"]
        assert 1 <= len(images) <= sheets.MAX_SHEETS_PER_CALL and len(images) == len(chunk["sheets"])
        for block in images:
            assert jpeg_size(base64.b64decode(block["source"]["data"])) == (2256, 1396)
        text = text_of(call["content"])
        assert "Wankil" not in text and "Krok" not in text and doc.state.name not in text
        cited = claude.cited[call["label"]]
        chunk_tiles = {t["id"] for t in data.sheet_tiles(chunk["sheets"])}
        assert set(cited.values()) <= chunk_tiles  # la chronologie ne cite que des cases de l'extrait
        seen_ids += [i for i in cited if i[0] != "M"]  # une musique peut commencer dans un extrait et finir dans l'autre

    # Chaque effet mesuré est dans un seul extrait, et la case citée est celle qui le montre (étiquette mesurée)
    by_id = {e["id"]: e for e in data.image_events + data.sound_events + data.silences}
    cited_all = {i: tile for c in calls for i, tile in claude.cited[c["label"]].items()}
    assert len(seen_ids) == len(set(seen_ids))
    for e in data.image_events + data.sound_events:
        assert e["id"] in cited_all, e["id"]
    for i, tid in cited_all.items():
        if i[0] not in "ZFS":
            continue
        e, tile = by_id[i], tiles[tid]
        if i[0] == "Z":
            assert "Z+" in tile["tags"] and e["t"] <= tile["t"] <= e["t"] + 0.35 and tile["plan"] == e["plan"], (i, tile)
        elif i[0] == "F":
            assert "FL" in tile["tags"] and tile["plan"] == e["plan"], (i, tile)
        elif e["cat"] != "autre":  # son éditorial : sa case étiquetée « S », même juste après une borne d'extrait
            plan = data.plan_at(e["t"] + 0.15)
            tagged = [x for x in data.tiles if "S" in x["tags"] and e["t"] <= x["t"] <= e["t"] + 0.35 and x["plan"] == plan]
            assert tile in tagged, (i, tile, tagged)

    # Les cases citées par Claude redonnent les temps (jamais un temps écrit par Claude)
    records = benchmark.chunk_records(doc)
    occurrences = [o for rec in records for o in rec["result"]["occurrences"]]
    assert occurrences
    for o in occurrences:
        tile = tiles[o["tuile_debut"]]
        assert (o["t"], o["sheet"], o["cell"]) == (tile["t"], tile["sheet"], tile["cell"])
        assert INVALID_REF not in o["lie_a"]
    assert sum(rec["invalid_refs"] for rec in records) == len(occurrences)

    # Comptes du programme : retrouvent les effets mesurés et les verdicts
    agg = doc.read_json("observations/agregats.json")
    minutes = data.duration / 60
    zooms = [e for e in data.image_events if e["type"] == "zoom"]
    flashes = [e for e in data.image_events if e["type"] == "flash_blanc"]
    editorial = [e for e in data.sound_events if e["cat"] != "autre"]
    bips = [e for e in editorial if e["cat"] == "bip"]
    boums = [e for e in data.sound_events if e["cat"] == "boum"]
    assert agg["coverage"] == 1.0 and agg["analysed_s"] == pytest.approx(data.duration, abs=0.1)
    assert agg["invalid_refs"] == len(occurrences)
    assert agg["techniques"].get("zoom_sec", {}).get("n", 0) == len(zooms)
    assert agg["techniques"].get("flash", {}).get("n", 0) == len(flashes)
    assert agg["techniques"].get("texte_impact", {}).get("n", 0) == len(boums)
    assert agg["zooms"]["confirmed"] == len(zooms)
    assert agg["zooms"]["total_per_min"] == agg["zooms"]["confirmed_per_min"] == round(len(zooms) / minutes, 2)
    assert agg["sounds"]["montage_per_min"] == round((len(editorial) - len(bips)) / minutes, 2)
    assert agg["sounds"]["jeu_per_min"] == round(len(bips) / minutes, 2)
    if data.music:
        assert agg["music"]["montage_pct"] == pytest.approx(doc.state.metrics["music_pct"], abs=0.2)
    for ex in agg["techniques"].get("texte_impact", {}).get("examples", []):
        assert tiles[ex["tile"]]["t"] == ex["t"] and ex["texte"].startswith("BOUM S")
    m = doc.state.metrics
    assert m["zooms_confirmed_per_min"] == agg["zooms"]["confirmed_per_min"]
    assert m["sfx_montage_per_min"] == agg["sounds"]["montage_per_min"]
    assert m["claude_texts_per_min"] == round(len(boums) / minutes, 2)
    assert m["gags_per_min"] == round(len(data.chunks) / minutes, 2) and m["claude_coverage"] == 1.0
    assert doc.state.claude["calls"] == len(data.chunks) + 1 and doc.state.claude["usd"] > 0
    assert planches["band_h"] == 24 and planches["gutter"] == sheets.GUTTER
    return {"data": data, "agg": agg, "zooms": zooms, "flashes": flashes, "editorial": editorial}


def band_color(doc, data: VideoData, tile: dict, box: list[int]) -> np.ndarray:
    """Couleur dominante du bandeau d'une case, lue dans la planche à l'endroit donné par tile_box."""
    sheet = data.sheets_by_n[tile["sheet"]]
    img = decode_jpegs([doc.root / sheet["file"]], sheet["w"], sheet["h"])[0]
    x, y, w, _ = box
    band = img[y : y + data.planches["band_h"], x : x + w].reshape(-1, 3).astype(int)
    return np.median(band, axis=0)


# ------------------------------------------------------------------ le test
def test_benchmark_end_to_end(workspace, tmp_path, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(benchmark, "SHORT_MINUTES", 0.5)  # vidéos de test de 42 et 50 s
    monkeypatch.setitem(sheets.PRESETS, "standard", dataclasses.replace(sheets.PRESETS["standard"], chunk_s=CHUNK_S))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    claude = FakeClaude()
    monkeypatch.setattr(LLM, "ask_json", lambda self, **kw: claude(self, **kw))
    cfg = AppConfig.load()
    store = BenchmarkStore()

    # 1. Le faux montage, dans la chaîne Wankil Studio
    montage, truth, _ = sm.analyzed_montage(tmp_path_factory)
    wankil, created = store.add_or_get(montage, "wankil-studio")
    assert created
    wankil = measure(store, wankil, cfg, words_provider=lambda pcm, levels: as_words(truth["words"]))
    w = check_video(wankil, claude)
    assert [round(z["t"], 1) for z in w["zooms"]] == [4.0, 38.4]
    assert [round(f["t"], 1) for f in w["flashes"]] == [12.0]
    assert len(observe_calls(claude, wankil.state.blind_id)) == len(w["data"].chunks)

    # 2. Notre vidéo, déjà dans « Mes vidéos » : reprise (son et transcription) puis retirée de « Mes vidéos »
    src, words, plan = nous_video(tmp_path / "nous")
    refs = ReferenceStore()
    ref = refs.add(src)
    extract_pcm(src, ref.root / "audio.pcm")
    np.save(ref.root / "niveaux.npy", level_curve(ref.root / "audio.pcm"))
    ref.write_json("transcription.json", {"lines": lines_of(words), "whisper_model": "small"})
    ref.set_metrics(whisper_model="small", sfx_checked=True, sfx_detector=SFX_DETECTOR_VERSION, sfx_per_min=6.0)
    hits = [t for t, _, _ in plan]
    ref.write_json("bruitages.json", {"hits": [{"t": t, "asset": f"sfx/{cat}"} for t, cat, _ in plan], "music": []})

    def no_extract(*a, **k):
        raise AssertionError("le son de « Mes vidéos » doit être repris")

    def no_words(pcm, levels):
        raise AssertionError("la transcription (même modèle) doit être reprise")

    nous, created = store.import_reference(ref, cfg, move=True)
    assert created and nous.state.channel == "krok-et-mil" and nous.state.origin == "mes_videos"
    assert ref.id not in [r.id for r in ReferenceStore().list()] and Path(nous.state.path).is_file()
    with monkeypatch.context() as mp:
        mp.setattr(benchmark, "extract_pcm", no_extract)
        nous = measure(store, nous, cfg, words_provider=no_words)
    assert nous.read_json("transcription.json")["reused_from"] == ref.id
    n = check_video(nous, claude)
    assert not n["zooms"]  # pas de zoom sec chez nous
    found = sum(1 for h in hits if any(abs(e["t"] - h) <= 0.15 for e in n["data"].sound_events))
    assert nous.state.metrics["library_recall_n"] == len(hits) == 8
    assert nous.state.metrics["library_recall"] == round(found / len(hits), 3) >= 0.75  # rappel sur « vos » bruitages

    # Le système est le même pour les deux vidéos ; les noms des chaînes ne vont jamais dans les passes vidéo
    systems = {c["system"] for c in claude.calls if c["label"].startswith(("observe_", "video"))}
    assert len(systems) == 1
    for c in claude.calls:
        if c["label"].startswith(("observe_", "video")):
            assert "Wankil" not in text_of(c["content"]) and "Krok" not in text_of(c["content"])

    # 3. Le rapport : profils des deux chaînes analysées, puis la comparaison (avec les vrais noms)
    report = br.build_benchmark_report(store, cfg)
    assert claude.labels("chaine_") == ["chaine_wankil-studio", "chaine_krok-et-mil"]
    assert claude.labels("comparaison") == ["comparaison"]
    assert "Wankil Studio" in text_of(claude.calls[-1]["content"]) and "Krok et Mil" in text_of(claude.calls[-1]["content"])
    assert report["claude"] and report["claude_error"] == "" and report["cost"]["calls"] == 3
    assert report["sources"] == {d.id: d.state.steps["synthesize"].finished for d in (wankil, nous)}
    assert (store.root / "rapport.json").exists() and (store.root / "rapport.md").read_text("utf-8").strip()
    assert any(r.get("proposition") == "p_zooms_per_minute" for r in report["recommendations"])

    live = br.live_report(store, cfg)
    assert not live["outdated"] and live["base_channel"] == "krok-et-mil"
    chans = {c["id"]: c for c in live["channels"]}
    assert chans["wankil-studio"]["claude_videos"] == [wankil.id] and chans["krok-et-mil"]["claude_videos"] == [nous.id]
    rows = {r["id"]: r for r in live["table"]}
    for rid in ("cuts_per_min", "median_shot", "sound_events_per_min", "loudness_i", "zooms_confirmed_per_min",
                "sfx_montage_per_min", "claude_texts_per_min", "gags_per_min"):
        values = rows[rid]["values"]
        assert set(values) == {"wankil-studio", "krok-et-mil"}, rid
        assert values["wankil-studio"]["median"] == pytest.approx(wankil.state.metrics[rid], abs=1e-3), rid
        assert values["krok-et-mil"]["median"] == pytest.approx(nous.state.metrics[rid], abs=1e-3), rid
    assert "wankil-studio" in rows["cuts_per_min"]["ecart"]
    assert set(rows["punch_ins_per_min"]["values"]) == {"wankil-studio", "krok-et-mil"}
    assert set(rows["zoom_scale_median"]["values"]) == {"wankil-studio"}  # sans zoom chez nous : pas mesurable
    assert live["library_recall"] == {"recall": round(nous.state.metrics["library_recall"], 2), "n": 8}

    props = {p["field"]: p for p in live["proposals"]}
    zp = props["zooms_per_minute"]
    assert zp["base_channel"] == "krok-et-mil" and zp["per_channel"] == {"wankil-studio": wankil.state.metrics["zooms_total_per_min"]}
    assert zp["ref"] == wankil.state.metrics["zooms_total_per_min"] and zp["base"] == nous.state.metrics["zooms_total_per_min"] == 0.0
    assert zp["proposed"] > zp["current"] and "Wankil Studio" in zp["why"]
    assert "punch_scale" not in props  # grossissement : pas mesurable chez nous

    # Feuille de route : le flash (non faisable) avec un exemple découpable dans sa planche
    flash = next(f for f in live["feasibility"] if f["technique"] == "flash")
    assert flash["rates"]["wankil-studio"] == pytest.approx(round(1 / (w["data"].duration / 60), 2), abs=0.01)
    example = flash["examples"][0]
    assert example["video_id"] == wankil.id
    tile = w["data"].tiles_by_id[example["tile"]]
    assert "FL" in tile["tags"] and (example["sheet"], example["cell"]) == (tile["sheet"], tile["cell"])
    assert example["description"] == "flash blanc"
    expected = np.array(sheets.rgb(sheets.BAND_COLORS[sheets.plan_index(tile["plan"]) % len(sheets.BAND_COLORS)]))
    assert np.abs(band_color(wankil, w["data"], tile, example["box"]) - expected).max() <= 24
    detail = benchmark.video_detail(wankil, None, "", store.settings(), cfg)
    assert detail["layout"]["band_h"] == 24 and detail["layout"]["gutter"] == sheets.GUTTER
    assert json.loads((store.root / "rapport.json").read_text("utf-8"))["base_channel"] == "krok-et-mil"
