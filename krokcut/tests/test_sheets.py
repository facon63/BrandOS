"""Planches d'images pour Claude (onglet « Comparer ») : choix des cases, extraits, dessin, planche de contrôle."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from krokcut import sheets
from krokcut.ffmpeg_utils import decode_jpegs
from krokcut.steps import Cancelled

from . import synth_media as sm

NUM = {"type": "number"}
INT = {"type": "integer"}
PLANCHES_SCHEMA = {
    "type": "object",
    "required": ["version", "quality", "tile_w", "tile_h", "cols", "rows", "tiles", "sheets", "chunks", "image_tokens", "extracted"],
    "properties": {
        "version": {"const": sheets.SHEETS_VERSION}, "quality": {"enum": list(sheets.PRESETS)},
        "tile_w": INT, "tile_h": INT, "cols": INT, "rows": INT, "image_tokens": INT, "extracted": INT,
        "tiles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "t", "plan", "new_plan", "reasons", "tags", "chunk", "sheet", "cell", "source"],
            "properties": {"id": {"type": "string", "pattern": r"^T\d{4,}$"}, "t": NUM,
                           "plan": {"type": "string", "pattern": r"^P\d{3,}$"}, "new_plan": {"type": "boolean"},
                           "reasons": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                           "tags": {"type": "array", "items": {"enum": list(sheets.TAG_ORDER)}},
                           "chunk": INT, "sheet": INT, "cell": INT, "source": {"enum": ["images4", "extrait"]}}}},
        "sheets": {"type": "array", "items": {
            "type": "object", "required": ["n", "file", "w", "h", "tokens", "chunk", "t0", "t1", "first", "last"],
            "properties": {"n": INT, "file": {"type": "string", "pattern": r"^planches/planche_\d{3}\.jpg$"}, "w": INT,
                           "h": INT, "tokens": INT, "chunk": INT, "t0": NUM, "t1": NUM}}},
        "chunks": {"type": "array", "items": {
            "type": "object", "required": ["n", "t0", "t1", "sheets"],
            "properties": {"n": INT, "t0": NUM, "t1": NUM, "sheets": {"type": "array", "items": INT}}}},
    },
}


# --------------------------------------------------------- données écrites à la main
def hand_made(duration: float = 120.0):
    """Plans (dont des très courts), effets d'image, sons, musique et silences d'une fausse vidéo."""
    edges = [0.0]
    t = 0.0
    rng = np.random.default_rng(4)
    while t < duration - 3:
        t += float(rng.choice([0.2, 0.6, 1.3, 2.7, 4.1, 7.0]))  # quelques plans de 0,2 s
        edges.append(round(t, 3))
    edges.append(duration)
    plans = [{"id": f"P{i + 1:03d}", "start": a, "end": b, "cut_in": "debut" if i == 0 else "changement"}
             for i, (a, b) in enumerate(zip(edges[:-1], edges[1:]))]
    long_plans = [p for p in plans if p["end"] - p["start"] >= 2.5]
    events = []
    for i, p in enumerate(long_plans[:12]):
        a = p["start"]
        kind = ("zoom", "flash_blanc", "fige", "fondu_noir", "noir_et_blanc", "bandes_cinema")[i % 6]
        if kind == "zoom":
            events.append({"type": "zoom", "t": a + 0.4, "end": a + 1.4, "dir": "avant", "scale": 1.25, "cx": 0.5, "cy": 0.5,
                           "zone": "centre", "whole_frame": True, "ncc": 0.99, "gain": 0.2, "plan": p["id"], "returned": True})
        elif kind == "flash_blanc":
            events.append({"type": kind, "t": a + 0.9, "dur": 0.067, "plan": p["id"]})
        else:
            events.append({"type": kind, "t": a + 0.5, "dur": 1.2, "plan": p["id"]})
    counters: dict[str, int] = {}
    for e in sorted(events, key=lambda e: e["t"]):
        letter = {"zoom": "Z", "flash_blanc": "F", "fige": "G", "fondu_noir": "N"}.get(e["type"], "B")
        counters[letter] = counters.get(letter, 0) + 1
        e["id"] = f"{letter}{counters[letter]:02d}"
    sounds = [{"id": f"S{i + 1:03d}", "t": round(3.3 + 7.1 * i, 2), "dur": 0.3, "cat": "boum" if i % 3 else "autre",
               "salience": 10.0 + i} for i in range(16)]
    music = [{"id": "M1", "start": 30.4, "end": 70.2, "kind": "rythmee"}]
    silences = [{"id": "C01", "t": 95.3, "dur": 0.6, "abrupt": True}]
    return ({"plans": plans, "cuts": [{"t": p["start"], "kind": "changement"} for p in plans[1:]]},
            {"events": events}, {"events": sounds}, {"segments": music}, {"silences": silences})


def plan_of(plans: list[dict], t: float) -> str:
    return next(p["id"] for p in plans if p["start"] <= t < p["end"])


def event_instants(image_events, sound_events, music, silences):
    """Instants du tableau du §3.7, recalculés indépendamment du module."""
    out = []
    for e in image_events["events"]:
        k = e["type"]
        if k == "zoom":
            out.append((e["t"] + 0.10, e))
        elif k in ("flash_blanc", "noir_bref", "image_inseree", "fondu_noir", "fondu_depuis_noir", "noir"):
            out.append((e["t"] + e["dur"] / 2, e))
        elif k == "fige":
            out.append((e["t"] + 0.20, e))
        else:
            out.append((e["t"] + 0.30, e))
    out += [(s["t"] + 0.15, s) for s in sound_events["events"] if s["cat"] != "autre"]
    out += [(t + 0.20, m) for m in music["segments"] for t in (m["start"], m["end"])]
    out += [(c["t"] + 0.10, c) for c in silences["silences"]]
    return out


# ------------------------------------------------------------------ choix des cases
def test_choix_des_cases_couverture_effets_ids():
    data = hand_made()
    plans = data[0]["plans"]
    tiles = sheets.select_tiles(120.0, *data, "standard", candidates=481)
    assert [t["id"] for t in tiles] == [f"T{i + 1:04d}" for i in range(len(tiles))]
    assert [t["t"] for t in tiles] == sorted(t["t"] for t in tiles)
    for t in tiles:
        assert t["plan"] == plan_of(plans, t["t"])
        if t["source"] == "images4":  # calée sur une image candidate (k / 4 s)
            assert abs(t["t"] * 4 - round(t["t"] * 4)) < 1e-6
    for p in plans:
        mine = [t for t in tiles if t["plan"] == p["id"]]
        assert mine, p  # chaque plan a sa case
        assert mine[0]["new_plan"] and not any(t["new_plan"] for t in mine[1:])
        if p["end"] - p["start"] < 0.25 and not any(p["start"] <= k / 4 < p["end"] for k in range(481)):
            assert all(t["source"] == "extrait" for t in mine)  # aucune candidate dans ce plan très court
    for at, ev in event_instants(*data[1:]):
        plan = ev.get("plan") or plan_of(plans, min(at, 119.99))
        assert any(t["plan"] == plan and abs(t["t"] - at) <= 0.35 for t in tiles), (at, ev)
    flash = next(e for e in data[1]["events"] if e["type"] == "flash_blanc")
    tile = next(t for t in tiles if abs(t["t"] - (flash["t"] + flash["dur"] / 2)) < 1e-3)
    assert tile["source"] == "extrait" and "FL" in tile["tags"]  # un transitoire est toujours extrait
    zooms = [e for e in data[1]["events"] if e["type"] == "zoom"]
    z = [t for t in tiles if "Z+" in t["tags"]]
    assert len(zooms) == 2 and all(any(abs(t["t"] - e["t"]) <= 0.35 for e in zooms) for t in z)
    for e in zooms:
        assert any(e["t"] <= t["t"] <= e["t"] + 0.35 for t in z)  # une case montre l'image zoomée
        assert any("Z-" in t["tags"] and abs(t["t"] - e["end"]) <= 0.35 for t in tiles)  # et son retour
    editorial = [s for s in data[2]["events"] if s["cat"] != "autre"]
    for t in tiles:
        if "S" in t["tags"]:
            assert any(abs(s["t"] - t["t"]) <= 0.35 for s in editorial)
    # un « autre son marquant » n'a pas de case à lui
    assert sum(t["reasons"].count("son") for t in tiles) <= len(editorial)


def test_plafond_par_minute_sans_retirer_les_plans():
    plans = [{"id": f"P{i + 1:03d}", "start": 2.0 * i, "end": 2.0 * (i + 1)} for i in range(30)]
    sounds = [{"id": f"S{i + 1:03d}", "t": round(0.6 + 1.2 * i, 2), "cat": "clic", "salience": float((i * 37) % 50)}
              for i in range(50)]
    eco = sheets.PRESETS["eco"]  # plafond de 45 cases par minute : 30 plans protégés, 50 sons
    tiles = sheets.select_tiles(60.0, {"plans": plans}, {"events": []}, {"events": sounds}, {}, {}, eco, candidates=241)
    assert len(tiles) <= eco.max_per_min
    assert {t["plan"] for t in tiles} == {p["id"] for p in plans}  # aucun plan sans case

    def tile_of(snd):
        return next((t for t in tiles if snd["t"] <= t["t"] <= snd["t"] + 0.35 and "son" in t["reasons"]), None)
    alone = [s["salience"] for s in sounds if tile_of(s) and tile_of(s)["reasons"] == ["son"]]
    lost = [s["salience"] for s in sounds if tile_of(s) is None]
    assert alone and lost and max(lost) < min(alone)  # les sons les moins saillants partent d'abord
    dense = [{"id": f"P{i + 1:03d}", "start": round(0.4 * i, 2), "end": round(0.4 * (i + 1), 2)} for i in range(150)]
    detail = sheets.PRESETS["detaille"]  # grille de 0,5 s + 150 plans + 50 sons, plafond de 160
    tiles = sheets.select_tiles(60.0, {"plans": dense}, {"events": []}, {"events": sounds}, {}, {}, detail, candidates=241)
    assert len(tiles) <= detail.max_per_min
    assert {t["plan"] for t in tiles} == {p["id"] for p in dense}


def test_plafond_et_extractions_bornees():
    plans = [{"id": f"P{i + 1:03d}", "start": round(i * 0.2, 3), "end": round((i + 1) * 0.2, 3)} for i in range(300)]
    tiles = sheets.select_tiles(60.0, {"plans": plans}, {}, {}, {}, {}, "standard", candidates=241)
    assert sum(1 for t in tiles if t["source"] == "extrait") <= sheets.MAX_EXTRACTED
    assert all(abs(t["t"] * 4 - round(t["t"] * 4)) < 1e-6 for t in tiles if t["source"] == "images4")


# ----------------------------------------------------------------------- extraits
def test_extraits_bornes_sur_les_coupes():
    # coupes toutes les 2,3 s ; parole continue sauf deux trous (vers 184,0 et 520,1)
    cuts = [round(2.3 * i, 2) for i in range(1, 261)]
    cuts += [184.0, 520.1]
    cuts = sorted(set(cuts))
    words, t = [], 0.2
    while t < 600:
        words.append((round(t, 3), round(t + 0.3, 3)))
        t += 0.35
    words = [w for w in words if not (183.4 < w[1] and w[0] < 184.5) and not (519.95 < w[1] and w[0] < 520.25)]
    std = sheets.PRESETS["standard"]
    chunks = sheets.make_chunks(600.0, cuts, words, std)
    assert chunks[0]["t0"] == 0 and chunks[-1]["t1"] == 600
    assert all(a["t1"] == b["t0"] for a, b in zip(chunks, chunks[1:]))
    assert [c["n"] for c in chunks] == list(range(len(chunks)))
    assert sheets._speech_gap(184.0, words) >= 0.3 and sheets._speech_gap(179.4, words) < 0.3
    assert chunks[1]["t0"] == 184.0  # coupe dans un trou de parole, à 4 s de la cible, plutôt que 179,4 (à 0,6 s)
    second = chunks[2]["t0"]  # cible 364 : aucun trou de parole à ±15 s, donc la coupe la plus proche
    assert second in cuts and abs(second - 364.0) == min(abs(c - 364.0) for c in cuts)
    # cible suivante 543,4 (le trou de 520,1 est à plus de 15 s) : il resterait 57 s < 0,4 × 180, fusionnées
    assert len(chunks) == 3 and chunks[2]["t1"] == 600
    short = sheets.make_chunks(400.0, cuts, words, std)  # 184 + 180 + 36 : le petit dernier rejoint le précédent
    assert len(short) == 2 and short[-1]["t1"] == 400 and short[-1]["t1"] - short[-1]["t0"] > 180
    no_cut = sheets.make_chunks(400.0, [], [], std)  # sans coupe : la cible
    assert [c["t0"] for c in no_cut] == [0.0, 180.0]


def test_au_plus_14_planches_par_extrait_et_jamais_a_cheval():
    std = sheets.PRESETS["standard"]
    cuts = [round(0.5 * i, 2) for i in range(1, 360)]
    tiles = [{"id": f"T{i + 1:04d}", "t": i * 0.25} for i in range(720)]  # 4 cases/s : 720 cases en 180 s
    chunks = sheets.make_chunks(180.0, cuts, [], std, tiles=tiles)
    assert len(chunks) >= 3
    pages, chunks = sheets.layout(tiles, chunks, std)
    assert all(len(c["sheets"]) <= sheets.MAX_SHEETS_PER_CALL for c in chunks)
    for page in pages:
        mine = [t for t in tiles if t["sheet"] == page["n"]]
        assert len({t["chunk"] for t in mine}) == 1 and mine[0]["chunk"] == page["chunk"]
        assert 1 <= len(mine) <= std.per_sheet and [t["cell"] for t in mine] == list(range(len(mine)))
    assert sorted(n for c in chunks for n in c["sheets"]) == list(range(len(pages)))


# ------------------------------------------------------------------- police bitmap
def expected_mask(text: str, scale: int) -> np.ndarray:
    cols = []
    for ch in text:
        rows = sheets.GLYPHS[ch]
        glyph = np.array([[c == "1" for c in r] for r in rows])
        cols += [glyph, np.zeros((7, 1), bool)]
    mask = np.concatenate(cols, axis=1)
    return np.kron(mask, np.ones((scale, scale), bool)).astype(bool)


def test_police_pixel_par_pixel():
    text = "T0012 0:12.5 P003"
    img = sheets.render_text(text, 3, "#ffffff", (0, 0, 0))
    mask = expected_mask(text, 3)
    assert img.shape == (21, sheets.text_width(text, 3), 3) == (21, 17 * 18, 3)
    assert np.array_equal(img[..., 0] == 255, mask) and np.array_equal(img.min(axis=2) == 255, mask)
    assert set(np.unique(img)) <= {0, 255}
    for ch in "0123456789:.+-TPZFLIGNORBS ":
        assert ch in sheets.GLYPHS and len(sheets.GLYPHS[ch]) == 7 and all(len(r) == 5 for r in sheets.GLYPHS[ch])
    assert len({sheets.GLYPHS[c] for c in "0123456789TPZFLIGNORBS"}) == 22  # glyphes tous différents
    assert sheets.fmt_tile_time(462.5) == "7:42.5" and sheets.fmt_tile_time(59.96) == "1:00.0"


# ------------------------------------------------------------ planches de couleurs codées
@pytest.fixture(scope="module")
def colored(tmp_path_factory):
    """Images candidates unies (couleur = numéro de l'image) et planches Standard construites dessus."""
    def build():
        work = tmp_path_factory.mktemp("couleurs")
        n = sm.color_candidates(work, 40.0)
        plans = [{"id": f"P{i + 1:03d}", "start": float(a), "end": float(min(40.0, a + 3.0))} for i, a in enumerate(range(0, 40, 3))]
        events = {"events": [{"id": "Z01", "type": "zoom", "t": 6.4, "end": 7.4, "dir": "avant", "scale": 1.25, "cx": 0.5,
                              "cy": 0.5, "zone": "centre", "whole_frame": True, "ncc": 0.99, "gain": 0.2, "plan": "P003",
                              "returned": True}]}
        data = sheets.build_sheets(work / "absent.mp4", work, quality="standard", duration=40.0,
                                   plans={"plans": plans, "cuts": [{"t": p["start"]} for p in plans[1:]]},
                                   image_events=events, sound_events={}, music={}, silences={}, words=[])
        return work, data, n
    return sm.cached("planches_couleurs", build)


def _cell_origin(cell: int, preset) -> tuple[int, int]:
    r, c = divmod(cell, preset.cols)
    return c * (preset.tile_w + sheets.GUTTER), r * (preset.band_h + preset.tile_h + sheets.GUTTER)


def test_couleurs_ordre_de_lecture_bandeau_et_liseré(colored):
    work, data, _ = colored
    std = sheets.PRESETS["standard"]
    Draft202012Validator(PLANCHES_SCHEMA).validate(data)
    assert json.loads((work / "planches.json").read_text("utf-8")) == data
    assert data["extracted"] == 0 and all(t["source"] == "images4" for t in data["tiles"])
    for page in data["sheets"]:
        img = decode_jpegs([work / page["file"]], page["w"], page["h"])[0].astype(int)
        mine = sorted((t for t in data["tiles"] if t["sheet"] == page["n"]), key=lambda t: t["cell"])
        for tile in mine:
            x, y = _cell_origin(tile["cell"], std)
            iy = y + std.band_h
            want = np.array(sm.color_of(int(round(tile["t"] * 4))))
            center = img[iy + std.tile_h // 2, x + std.tile_w // 2]
            assert np.abs(center - want).max() <= 12, (tile, center, want)  # la case montre la bonne image
            band = np.array(sheets.rgb(sheets.BAND_COLORS[(int(tile["plan"][1:]) - 1) % 6]))
            assert np.abs(img[y + 2, x + std.tile_w - 2] - band).max() <= 16  # couleur du plan
            edge = img[iy + std.tile_h // 2, x + 1]
            if tile["new_plan"]:
                assert edge.min() >= 235  # liseré blanc
            else:
                assert np.abs(edge - want).max() <= 12
        for cell in range(len(mine), std.per_sheet):  # cellules vides
            x, y = _cell_origin(cell, std)
            assert np.abs(img[y + std.band_h + 50, x + 50] - 0x20).max() <= 6
    plans_seen = [t["plan"] for t in data["tiles"]]
    assert plans_seen == sorted(plans_seen)


def test_le_bandeau_porte_le_texte_et_les_etiquettes(colored):
    work, data, _ = colored
    std = sheets.PRESETS["standard"]
    tile = next(t for t in data["tiles"] if t["id"] == "T0012")
    page = data["sheets"][tile["sheet"]]
    img = decode_jpegs([work / page["file"]], page["w"], page["h"])[0].astype(int)
    x, y = _cell_origin(tile["cell"], std)
    label = sheets.tile_label(tile)
    assert label == f"T0012 {sheets.fmt_tile_time(tile['t'])} {tile['plan']}"
    mask = expected_mask(label, std.font_scale)
    ty = (std.band_h - mask.shape[0]) // 2
    region = img[y + ty : y + ty + mask.shape[0], x + sheets.TEXT_PAD : x + sheets.TEXT_PAD + mask.shape[1]]
    assert np.mean((region.min(axis=2) > 160) == mask) >= 0.97  # le texte blanc, pixel pour pixel (au JPEG près)
    zoomed = next(t for t in data["tiles"] if "Z+" in t["tags"])
    page = data["sheets"][zoomed["sheet"]]
    img = decode_jpegs([work / page["file"]], page["w"], page["h"])[0].astype(int)
    x, y = _cell_origin(zoomed["cell"], std)
    tags = " ".join(zoomed["tags"])
    ink = sheets.text_width(tags, std.font_scale) - std.font_scale
    tag_mask = expected_mask(tags, std.font_scale)[:, :ink]
    x0 = x + std.tile_w - sheets.TEXT_PAD - ink
    region = img[y + ty : y + ty + tag_mask.shape[0], x0 : x0 + ink]
    yellow = (region[..., 0] > 180) & (region[..., 1] > 160) & (region[..., 2] < 110)
    assert np.mean(yellow == tag_mask) >= 0.95  # étiquettes jaunes alignées à droite


def test_dimensions_jetons_et_taille_par_qualite(tmp_path_factory):
    path, truth, res = sm.analyzed_montage(tmp_path_factory)
    out = res["out"]
    r = lambda name: json.loads((out / name).read_text("utf-8"))  # noqa: E731
    expected = {"eco": (2324, 1424, 4413), "standard": (2256, 1396, 4200), "detaille": (2252, 1368, 4108)}
    for quality, (w, h, tokens) in expected.items():
        calls = []
        data = sheets.build_sheets(path, out, quality=quality, duration=50.0, plans=r("plans.json"),
                                   image_events=r("image_evenements.json"), sound_events={}, music={}, silences={},
                                   words=truth["words"], progress=lambda f, m: calls.append(f))
        Draft202012Validator(PLANCHES_SCHEMA).validate(data)
        assert calls[0] == 0 and calls[-1] == 1 and calls == sorted(calls)
        preset = sheets.PRESETS[quality]
        assert (data["tile_w"], data["tile_h"], data["cols"], data["rows"]) == (preset.tile_w, preset.tile_h, preset.cols, preset.rows)
        assert data["sheets"] and data["image_tokens"] == tokens * len(data["sheets"])
        for page in data["sheets"]:
            f = out / page["file"]
            assert (page["w"], page["h"], page["tokens"]) == (w, h, tokens) and max(w, h) <= sheets.MAX_SHEET_SIDE
            assert page["tokens"] == math.ceil(w * h / 750) and f.stat().st_size < 900 * 1024
            assert decode_jpegs([f], w, h).shape == (1, h, w, 3)
        # les transitoires (flash, noir bref, image insérée) sont extraits : la case montre bien l'image brève
        transients = [e for e in res["events"] if e["type"] in sheets.TRANSIENT_TYPES]
        assert data["extracted"] == len(transients) == 3
        for e in transients:
            tile = next(t for t in data["tiles"] if abs(t["t"] - (e["t"] + e["dur"] / 2)) < 0.02)
            assert tile["source"] == "extrait" and "FL" in tile["tags"]
            page = data["sheets"][tile["sheet"]]
            img = decode_jpegs([out / page["file"]], page["w"], page["h"])[0].astype(int)
            x, y = _cell_origin(tile["cell"], preset)
            pixels = img[y + preset.band_h + 10 : y + preset.band_h + preset.tile_h - 10, x + 10 : x + preset.tile_w - 10]
            if e["type"] == "flash_blanc":
                assert pixels.mean() > 230, (quality, e)
            elif e["type"] == "noir_bref":
                assert pixels.mean() < 25, (quality, e)
        assert not (out / "planches" / "extraits").exists()
        files = sorted(p.name for p in (out / "planches").iterdir())
        assert files == [f"planche_{i:03d}.jpg" for i in range(len(data["sheets"]))]  # ancienne qualité effacée


def test_planche_de_controle(colored, tmp_path):
    work, data, n = colored
    plans = [{"id": f"P{i + 1:03d}", "start": round(i * 1.5, 2), "end": round((i + 1) * 1.5, 2)} for i in range(26)]
    events = [{"id": f"Z{i + 1:02d}", "type": "zoom", "t": 0.7 + 3 * i} for i in range(12)]
    events += [{"id": f"F{i + 1:02d}", "type": "flash_blanc", "t": 1.1 + 5 * i, "dur": 0.07} for i in range(6)]
    events += [{"id": f"G{i + 1:02d}", "type": "fige", "t": 2.2 + 6 * i, "dur": 1.0} for i in range(3)]
    events += [{"id": f"N{i + 1:02d}", "type": "fondu_noir", "t": 3.3 + 9 * i, "dur": 1.0} for i in range(3)]
    items = sheets.control_items({"plans": plans}, {"events": events}, "video-1")
    kinds = [it["kind"] for it in items]
    assert len(items) == 24 and kinds.count("cut") == 8 and kinds.count("zoom") == 8
    assert kinds.count("transient") == 4 and kinds.count("still") == 4
    assert items == sheets.control_items({"plans": plans}, {"events": events}, "video-1")  # tirage déterministe
    assert items != sheets.control_items({"plans": plans}, {"events": events}, "video-2")
    (tmp_path / "images4").symlink_to(work / "images4", target_is_directory=True)
    dst = sheets.build_control(tmp_path, {"plans": plans}, {"events": events}, "video-1", n)
    w, h = 4 * 640 + 3 * sheets.GUTTER, 6 * (sheets.CONTROL_BAND + sheets.CONTROL_H)
    assert (w, h) == (2572, 1188)
    img = decode_jpegs([dst], w, h)[0].astype(int)
    for i, it in enumerate(items):
        r, c = divmod(i, 4)
        x, y = c * (640 + sheets.GUTTER), r * (sheets.CONTROL_BAND + sheets.CONTROL_H) + sheets.CONTROL_BAND
        before = sm.color_of(math.ceil(it["t"] * 4) - 1)
        after = sm.color_of(math.ceil(it["t"] * 4 + 1e-6))
        assert np.abs(img[y + 90, x + 160] - before).max() <= 12  # juste avant l'instant
        assert np.abs(img[y + 90, x + 480] - after).max() <= 12  # juste après
    # jamais envoyée à Claude : elle n'est dans aucune planche des requêtes
    assert all(sheets.CONTROL_FILE not in page["file"] for page in data["sheets"])
    assert (work / sheets.CONTROL_FILE).exists()


def test_requete_trop_lourde_reencodee(tmp_path, monkeypatch):
    n = sm.color_candidates(tmp_path, 6.0)
    rng = np.random.default_rng(0)
    for k in range(n):  # du bruit : des JPEG lourds
        noisy = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
        sheets.encode_rgb_jpeg(noisy, tmp_path / "images4" / f"f_{k:06d}.jpg", q=2)
    args = dict(quality="detaille", duration=6.0, plans={}, image_events={}, sound_events={}, music={}, silences={}, words=[])
    data = sheets.build_sheets(tmp_path / "absent.mp4", tmp_path, **args)
    heavy = [(tmp_path / s["file"]).stat().st_size for s in data["sheets"]]
    monkeypatch.setattr(sheets, "MAX_REQUEST_B64", 1000)
    data = sheets.build_sheets(tmp_path / "absent.mp4", tmp_path, **args)
    light = [(tmp_path / s["file"]).stat().st_size for s in data["sheets"]]
    assert all(b < a for a, b in zip(heavy, light))


def test_annulation_entre_deux_planches(colored, tmp_path):
    work, _, _ = colored
    (tmp_path / "images4").symlink_to(work / "images4", target_is_directory=True)
    seen = []

    def cancel(fraction, message):
        seen.append(fraction)
        if len(seen) > 2:
            raise Cancelled()
    with pytest.raises(Cancelled):
        sheets.build_sheets(tmp_path / "absent.mp4", tmp_path, quality="detaille", duration=40.0, plans={}, image_events={},
                            sound_events={}, music={}, silences={}, words=[], progress=cancel)
    assert not (tmp_path / "planches.json").exists()
