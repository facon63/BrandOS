"""Mesures de l'image (onglet « Comparer ») validées sur un faux montage à vérité connue."""

from __future__ import annotations

import contextlib
import json
import math
import subprocess
import time

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from krokcut import ffmpeg_utils, vision
from krokcut.ffmpeg_utils import probe
from krokcut.steps import Cancelled

from . import synth_media as sm

FRAME = 1 / 30
NUM = {"type": "number"}
PLANS_SCHEMA = {
    "type": "object",
    "required": ["version", "fps", "duration", "content_box", "plans", "cuts"],
    "properties": {
        "version": {"const": vision.IMAGE_VERSION},
        "fps": {"const": 30},
        "duration": NUM,
        "content_box": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
        "plans": {"type": "array", "items": {
            "type": "object", "required": ["id", "start", "end", "cut_in"],
            "properties": {"id": {"type": "string", "pattern": r"^P\d{3}$"}, "start": NUM, "end": NUM,
                           "cut_in": {"enum": ["debut", "changement", "meme_decor"]}}}},
        "cuts": {"type": "array", "items": {
            "type": "object", "required": ["t", "kind", "pc", "dhist", "dpix"],
            "properties": {"t": NUM, "kind": {"enum": ["changement", "meme_decor"]}, "pc": NUM, "dhist": NUM, "dpix": NUM}}},
    },
}
EVENTS_SCHEMA = {
    "type": "object",
    "required": ["version", "events"],
    "properties": {
        "version": {"const": vision.IMAGE_VERSION},
        "events": {"type": "array", "items": {
            "type": "object", "required": ["id", "type", "t", "plan"],
            "properties": {
                "id": {"type": "string", "pattern": r"^[ZFGNB]\d{2,}$"},
                "type": {"enum": ["zoom", "flash_blanc", "noir_bref", "image_inseree", "fige", "fondu_noir",
                                  "fondu_depuis_noir", "noir", "noir_et_blanc", "bandes_cinema"]},
                "t": NUM, "plan": {"type": "string", "pattern": r"^P\d{3}$"},
            },
            "allOf": [
                {"if": {"properties": {"type": {"const": "zoom"}}},
                 "then": {"required": ["end", "dir", "scale", "cx", "cy", "zone", "whole_frame", "ncc", "gain"],
                          "properties": {"dir": {"enum": ["avant", "arriere"]}, "whole_frame": {"type": "boolean"}}},
                 "else": {"required": ["dur"]}},
            ]}},
    },
}


def _analyze(path, out, **kwargs) -> dict:
    metrics = vision.analyze_image(path, out, probe(path), progress=lambda f, m: None, **kwargs)
    return {
        "metrics": metrics,
        "plans": json.loads((out / "plans.json").read_text("utf-8")),
        "events": json.loads((out / "image_evenements.json").read_text("utf-8"))["events"],
        "out": out,
    }


@pytest.fixture(scope="session")
def montage(tmp_path_factory):
    def build():
        base = tmp_path_factory.mktemp("montage")
        path, truth = sm.edit_video(base / "src")
        t0 = time.time()
        res = _analyze(path, base / "analyse")
        res["seconds"] = time.time() - t0
        return path, truth, res
    return sm.cached("montage_640p30", build)


@pytest.fixture(scope="session")
def variants(tmp_path_factory, montage):
    def build():
        base = tmp_path_factory.mktemp("variantes")
        out = {"640p30": montage[2]}
        for key, kwargs in (("720p60", {"size": (1280, 720), "fps": 60}), ("vp9", {"codec": "libvpx-vp9"})):
            path, _ = sm.edit_video(base / "src", audio=False, **kwargs)
            out[key] = _analyze(path, base / key)
        return out
    return sm.cached("variantes", build)


def events_of(res, kind):
    return [e for e in res["events"] if e["type"] == kind]


def cut_times(res):
    return [c["t"] for c in res["plans"]["cuts"]]


# ------------------------------------------------------------------- coupes
def test_coupes_exactes_sans_fausse_alerte(montage):
    _, truth, res = montage
    found = cut_times(res)
    # rappel et précision : chaque coupe vraie à ±1 image, aucune autre
    assert len(found) == len(truth["cuts"])
    for t, f in zip(truth["cuts"], found):
        assert abs(t - f) <= FRAME + 1e-6, (t, f)
    cuts = res["plans"]["cuts"]
    kinds = {c["t"]: c["kind"] for c in cuts}
    assert kinds[20.0] == "meme_decor"  # saut de 7 s dans le même décor
    assert [c["kind"] for c in cuts].count("meme_decor") == 1
    for c in cuts:
        if c["kind"] == "changement":
            assert c["pc"] < vision.CHANGE_PC or c["dhist"] >= vision.CHANGE_DHIST
        else:
            assert c["pc"] >= vision.CHANGE_PC and c["dhist"] < vision.CHANGE_DHIST
    # la corrélation de phase s'effondre sur la plupart des vraies coupes (les mires partagent leurs barres)
    assert np.median([c["pc"] for c in cuts if c["kind"] == "changement"]) < vision.STRONG_PC
    # plans contigus, un de plus que les coupes
    plans = res["plans"]["plans"]
    assert len(plans) == len(found) + 1
    assert plans[0]["start"] == 0 and plans[-1]["end"] == pytest.approx(50.0, abs=0.05)
    assert all(a["end"] == b["start"] for a, b in zip(plans, plans[1:]))
    m = res["metrics"]
    assert m["cuts"] == len(truth["cuts"]) and m["cuts_per_min"] == pytest.approx(len(truth["cuts"]) / (50 / 60), abs=0.1)
    assert m["jump_cut_pct"] == pytest.approx(100 / len(truth["cuts"]), abs=0.1)


def test_flash_noir_et_image_inseree_ne_sont_pas_des_coupes(montage):
    _, truth, res = montage
    flashes = events_of(res, "flash_blanc")
    inserts = events_of(res, "image_inseree")
    blacks = events_of(res, "noir_bref")
    assert len(flashes) == 1 and abs(flashes[0]["t"] - truth["flash"]) <= FRAME
    assert len(inserts) == 1 and abs(inserts[0]["t"] - truth["insert"]) <= FRAME
    assert len(blacks) == 1 and abs(blacks[0]["t"] - truth["black_frame"]) <= FRAME
    assert inserts[0]["dur"] == pytest.approx(4 * FRAME, abs=FRAME)
    assert blacks[0]["dur"] == pytest.approx(2 * FRAME, abs=FRAME) and flashes[0]["dur"] == pytest.approx(2 * FRAME, abs=FRAME)
    for t in (truth["flash"], truth["insert"], truth["black_frame"]):
        assert all(abs(c - t) > 0.3 for c in cut_times(res))
    assert flashes[0]["plan"] == "P002"  # dans le plan mandelbrot, qui n'est pas coupé en deux
    assert blacks[0]["plan"] == "P003"
    assert [e["id"] for e in res["events"] if e["id"].startswith("F")] == ["F01", "F02", "F03"]
    assert not events_of(res, "noir")  # l'image noire brève n'est pas aussi comptée comme un noir
    m = res["metrics"]
    assert m["flashes_per_min"] == pytest.approx(1.2) and m["inserts_per_min"] == pytest.approx(2.4)


def test_zoom_sec_de_krokcut_trouve_et_apparie(montage):
    _, truth, res = montage
    zooms = events_of(res, "zoom")
    assert len(zooms) == 2
    for z, want in zip(zooms, truth["zooms"]):
        assert z["dir"] == "avant"
        assert abs(z["t"] - want["t"]) <= FRAME + 1e-6
        assert z["scale"] == pytest.approx(want["scale"], abs=0.08)
        assert z["cx"] == pytest.approx(want["cx"], abs=0.1) and z["cy"] == pytest.approx(want["cy"], abs=0.1)
        assert z["whole_frame"] is True and z["zone"] == "centre"
        assert z["end"] == pytest.approx(want["end"], abs=FRAME + 1e-6)
        assert z["hold"] == pytest.approx(want["end"] - want["t"], abs=0.07)
        assert z["ncc"] >= vision.ZOOM_NCC
    assert [z["id"] for z in zooms] == ["Z01", "Z02"]  # le retour apparié n'a pas d'id à lui
    for t in (4.0, 5.0, 38.4, 39.2):
        assert all(abs(c - t) > 0.3 for c in cut_times(res))
    m = res["metrics"]
    assert m["punch_ins"] == 2 and m["zoom_hold_median_s"] == pytest.approx(0.9, abs=0.07)
    assert m["zoom_layer_only_pct"] == 0


@pytest.mark.parametrize("scale", [1.25, 1.5])
def test_zoom_d_un_seul_calque(tmp_path, scale):
    """Même zoom sous un cadre fixe texturé de 25 % en coin (facecam) : trouvé, mais pas « tout le cadre »."""
    path = sm.zoom_clip(tmp_path, scale=scale, layer=True)
    res = _analyze(path, tmp_path / "a")
    zooms = events_of(res, "zoom")
    assert len(zooms) == 1 and abs(zooms[0]["t"] - 2.0) <= FRAME
    assert zooms[0]["scale"] == pytest.approx(scale, abs=0.08)
    assert zooms[0]["whole_frame"] is False
    assert zooms[0]["end"] == pytest.approx(3.0, abs=FRAME)
    assert res["metrics"]["zoom_layer_only_pct"] == 100
    assert not res["plans"]["cuts"]


def test_pieges_mouvement_continu(montage, tmp_path):
    _, truth, res = montage
    for a, b in truth["no_cut_zones"]:  # mandelbrot (zoom continu), défilement rapide, jeu de la vie
        assert not [c for c in cut_times(res) if a <= c <= b]
        assert not [e for e in res["events"] if a <= e["t"] <= b and e["type"] != "flash_blanc"]
    path = sm.zoompan_clip(tmp_path)  # zoom lent sur 5 s : ce n'est pas un zoom sec
    slow = _analyze(path, tmp_path / "a")
    assert not events_of(slow, "zoom") and not slow["plans"]["cuts"]


def test_fige_et_cadences_converties(montage, tmp_path):
    _, truth, res = montage
    freezes = events_of(res, "fige")
    assert len(freezes) == 1
    assert abs(freezes[0]["t"] - truth["freeze"][0]) <= 2 * FRAME
    assert abs(freezes[0]["t"] + freezes[0]["dur"] - truth["freeze"][1]) <= 2 * FRAME
    for src_fps, out_fps in ((30, 60), (25, 25)):  # images dupliquées : jamais un figé
        path = sm.rate_clip(tmp_path, src_fps, out_fps)
        other = _analyze(path, tmp_path / f"r{src_fps}_{out_fps}")
        assert not events_of(other, "fige") and not other["plans"]["cuts"]


def test_fondu_noir_et_blanc_bandes(montage):
    _, truth, res = montage
    fades = events_of(res, "fondu_noir")
    assert len(fades) == 1
    assert fades[0]["t"] == pytest.approx(truth["fade"][0], abs=0.1)
    assert fades[0]["t"] + fades[0]["dur"] == pytest.approx(truth["fade"][1], abs=0.1)
    assert fades[0]["black"] == pytest.approx(truth["black"][1] - truth["black"][0], abs=0.1)
    assert not events_of(res, "noir") and not events_of(res, "fondu_depuis_noir")
    for kind, (a, b) in (("noir_et_blanc", truth["bw"]), ("bandes_cinema", truth["bars"])):
        found = events_of(res, kind)
        assert len(found) == 1, kind
        assert found[0]["t"] == pytest.approx(a, abs=0.1) and found[0]["t"] + found[0]["dur"] == pytest.approx(b, abs=0.1)
    m = res["metrics"]
    assert m["fades_per_min"] == pytest.approx(1.2) and m["bw_per_10min"] == pytest.approx(12.0)
    assert m["letterbox_pct"] == pytest.approx(2.0, abs=0.3)


def test_meme_instrument_quelle_que_soit_la_source(variants):
    ref = variants["640p30"]
    for key in ("720p60", "vp9"):
        other = variants[key]
        a, b = cut_times(ref), cut_times(other)
        assert len(a) == len(b), key
        assert all(abs(x - y) <= FRAME + 1e-6 for x, y in zip(a, b)), key
        assert [c["kind"] for c in ref["plans"]["cuts"]] == [c["kind"] for c in other["plans"]["cuts"]]
        assert other["metrics"]["cuts_per_min"] == ref["metrics"]["cuts_per_min"]
        assert other["metrics"]["median_shot"] == pytest.approx(ref["metrics"]["median_shot"], abs=0.05)
        za, zb = events_of(ref, "zoom"), events_of(other, "zoom")
        assert len(za) == len(zb)
        for x, y in zip(za, zb):
            assert abs(x["t"] - y["t"]) <= FRAME + 1e-6 and x["scale"] == pytest.approx(y["scale"], abs=0.05)
        assert sorted(e["type"] for e in ref["events"]) == sorted(e["type"] for e in other["events"]), key


def test_annulation_tue_ffmpeg(montage, monkeypatch):
    path = montage[0]
    procs = []
    real_popen = subprocess.Popen

    def spy(*args, **kwargs):
        procs.append(real_popen(*args, **kwargs))
        return procs[-1]

    monkeypatch.setattr(ffmpeg_utils.subprocess, "Popen", spy)
    args = ["-i", str(path), "-an", "-vf", "fps=30,scale=128:72,format=rgb24", "-f", "rawvideo", "pipe:1"]
    blocks = 0
    with pytest.raises(Cancelled):
        with contextlib.closing(ffmpeg_utils.stream_raw_frames(args, (72, 128, 3), block=30)) as frames:
            for block in frames:
                assert block.shape == (30, 72, 128, 3) and block.dtype == np.uint8
                blocks += 1
                if blocks == 2:
                    raise Cancelled()
    assert len(procs) == 1 and procs[0].poll() is not None  # ffmpeg ne tourne plus

    def cancel(fraction, message):
        raise Cancelled()

    procs.clear()
    with pytest.raises(Cancelled):  # même chose depuis l'étape d'analyse (point d'annulation par bloc)
        vision.analyze_image(path, path.parent / "annule", probe(path), progress=cancel)
    assert procs and all(p.poll() is not None for p in procs)
    assert not (path.parent / "annule" / "luma128.u8").exists()


def test_flux_en_erreur(tmp_path):
    bad = tmp_path / "abime.mp4"
    bad.write_bytes(b"pas une video" * 100)
    with pytest.raises(ffmpeg_utils.FFmpegError):
        list(ffmpeg_utils.stream_raw_frames(["-i", str(bad), "-f", "rawvideo", "pipe:1"], (72, 128, 3)))


def test_decodage_materiel_refuse_repli_logiciel(tmp_path, monkeypatch):
    """L'accélération matérielle (Mac) échoue : on repasse en logiciel, même résultat."""
    path = sm.zoom_clip(tmp_path, name="hw")
    monkeypatch.setattr(vision, "HWACCEL", "accel_inexistante")
    res = _analyze(path, tmp_path / "a", hwaccel=True)
    assert res["metrics"]["decode"] == "logiciel"
    assert len(events_of(res, "zoom")) == 1
    monkeypatch.setattr(vision.sys, "platform", "darwin")
    assert vision.use_hwaccel(probe(path))  # h264 sous macOS : on essaie le matériel
    monkeypatch.setattr(vision.sys, "platform", "linux")
    assert not vision.use_hwaccel(probe(path))


def test_performances_fichiers_et_schemas(montage):
    path, truth, res = montage
    out = res["out"]
    assert res["seconds"] < 15
    assert not (out / "luma128.u8").exists()
    thumbs = vision.thumb_files(out)
    assert abs(len(thumbs) - math.ceil(50 * vision.THUMB_FPS)) <= 1
    assert (out / "vignette.jpg").exists()
    series = np.load(out / "image_trames.npz")
    assert set(series.files) == set(vision.SERIES_KEYS)
    assert all(series[k].dtype == np.float16 and len(series[k]) == 1500 for k in series.files)
    Draft202012Validator(PLANS_SCHEMA).validate(res["plans"])
    Draft202012Validator(EVENTS_SCHEMA).validate(json.loads((out / "image_evenements.json").read_text("utf-8")))
    assert res["plans"]["content_box"] == [0, 0, 128, 72]
    m = res["metrics"]
    for key in ("cuts", "cuts_per_min", "median_shot", "shot_p25", "shot_p75", "shot_p90", "shots_under_1s_pct",
                "jump_cut_pct", "punch_ins", "punch_ins_per_min", "zoom_scale_median", "zoom_hold_median_s",
                "zoom_layer_only_pct", "flashes_per_min", "inserts_per_min", "freezes_per_min", "fades_per_min",
                "bw_per_10min", "letterbox_pct", "visual_changes_per_min", "motion_mean", "image_version", "decode"):
        assert key in m, key
    assert m["decode"] == "logiciel" and m["image_version"] == vision.IMAGE_VERSION


def test_zone_utile_hors_bandes_ajoutees():
    assert vision.content_box(1920, 1080) == (0, 0, 128, 72)
    x0, y0, x1, y1 = vision.content_box(1440, 1080)  # 4:3 : bandes à gauche et à droite
    assert y0 == 0 and y1 == 72 and x0 > 10 and 128 - x1 > 10
    x0, y0, x1, y1 = vision.content_box(1080, 1920)  # vertical
    assert x1 - x0 < 45 and y1 - y0 == 72


def test_reperes_sur_series_ecrites_a_la_main():
    n = 300
    series = {k: np.zeros(n, np.float32) for k in vision.SERIES_KEYS}
    series["dpix"][:] = 0.01
    series["luma"][:] = 0.5
    series["sat"][:] = 0.4
    series["center"][:] = 0.5
    series["bar_top"][:] = series["bar_bot"][:] = 0.5
    series["dpix"][100:120] = 0.0  # 20 images figées
    series["luma"][200:230] = np.linspace(0.5, 0.0, 30)  # fondu au noir sur 1 s...
    series["luma"][230:250] = 0.0  # ... puis noir
    series["dpix"][230:250] = 0.0
    events = vision.detect_static_events(series)
    kinds = {e["type"]: e for e in events}
    assert kinds["fige"]["n"] == 100 and kinds["fige"]["end_n"] == 120
    assert kinds["fondu_noir"]["n"] == 200 and abs(kinds["fondu_noir"]["end_n"] - 229) <= 1
    assert "noir" not in kinds
