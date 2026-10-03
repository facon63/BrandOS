"""Passe 3 : décisions de montage (plans, zooms, bruitages, personnages, textes, musique)."""

from __future__ import annotations

import base64
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable

from .config import StyleProfile
from .ffmpeg_utils import extract_frame
from .library import Library
from .llm import INT, LLM, NUM, STR, arr, enum, obj
from .project import Source
from .prompts import EDIT_INSTRUCTIONS
from .timeline import POSITIONS
from .transcribe import fmt_time, format_lines

EDIT_SCHEMA = obj(
    {
        "moments": arr(
            obj(
                {
                    "moment": STR,
                    "camera": arr(obj({"line": INT, "pov": enum("A", "B", "both")})),
                    "zooms": arr(obj({"line": INT, "word": STR, "kind": enum("punch", "slow", "shake"), "duration": NUM})),
                    "sfx": arr(
                        obj(
                            {
                                "asset": STR,
                                "line": INT,
                                "word": STR,
                                "timing": enum("on_word", "end_of_line"),
                                "volume": enum("low", "normal", "high"),
                            }
                        )
                    ),
                    "characters": arr(
                        obj({"asset": STR, "line": INT, "word": STR, "position": enum(*POSITIONS), "duration": NUM})
                    ),
                    "texts": arr(obj({"line": INT, "word": STR, "text": STR, "style": enum("impact", "caption", "meme")})),
                    "remove_lines": arr(INT),
                }
            )
        ),
        "music": arr(obj({"asset": STR, "from_moment": STR, "to_moment": STR})),
    }
)

EMPTY_EDIT = {"camera": [], "zooms": [], "sfx": [], "characters": [], "texts": [], "remove_lines": []}


def lines_between(lines: list[dict], start_id: int, end_id: int) -> list[dict]:
    return [l for l in lines if start_id <= l["id"] <= end_id]


def batches(sequence: list[dict], max_seconds: float = 150.0) -> list[list[dict]]:
    out, current, total = [], [], 0.0
    for item in sequence:
        if current and total + item["est_duration"] > max_seconds:
            out.append(current)
            current, total = [], 0.0
        current.append(item)
        total += item["est_duration"]
    if current:
        out.append(current)
    return out


def _frames_blocks(item: dict, lines_by_id: dict, sources: dict[str, Source], names: dict[str, str], tmp: Path) -> list[dict]:
    start = lines_by_id[item["start_line"]]["start"]
    end = lines_by_id[item["end_line"]]["end"]
    t = (start + end) / 2
    blocks = []
    for key in ("A", "B"):
        src = sources[key]
        if not src.covers(t, t + 0.1) or not src.path:
            continue
        out = tmp / f"{item['moment']}_{key}.jpg"
        if extract_frame(src.path, src.to_source_time(t), out, width=480):
            blocks.append({"type": "text", "text": f"Image du moment {item['moment']} — POV {key} ({names[key]}) :"})
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(out.read_bytes()).decode()},
                }
            )
    return blocks


def edit_with_claude(
    llm: LLM,
    system: str,
    story: dict,
    lines: list[dict],
    names: dict[str, str],
    sources: dict[str, Source],
    effort: str,
    use_frames: bool = True,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict:
    by_id = {l["id"]: l for l in lines}
    groups = batches(story["sequence"])
    edits: dict[str, dict] = {}
    music: list[dict] = []
    used: Counter = Counter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for gi, group in enumerate(groups):
            text_parts = []
            for item in group:
                block = format_lines(lines_between(lines, item["start_line"], item["end_line"]), names)
                text_parts.append(
                    f"### Moment {item['moment']} — « {item['title']} » ({item['est_duration']:.0f}s une fois les "
                    f"blancs coupés, {fmt_time(by_id[item['start_line']]['start'])})\n{block}"
                )
            used_txt = ", ".join(f"{k} ×{v}" for k, v in used.most_common(15)) or "aucun"
            frames_note = (
                " Des images des deux POV au milieu de chaque moment sont jointes pour t'aider à choisir les plans."
                if use_frames
                else ""
            )
            prompt = EDIT_INSTRUCTIONS.format(
                batch_index=gi + 1,
                batch_total=len(groups),
                frames_note=frames_note,
                used=used_txt,
                moments="\n\n".join(text_parts),
            )
            content: list[dict] = []
            if use_frames:
                for item in group:
                    content += _frames_blocks(item, by_id, sources, names, tmp)
            content.append({"type": "text", "text": prompt})
            result = llm.ask_json(
                system=system, content=content, schema=EDIT_SCHEMA, effort=effort, max_tokens=48000, label=f"edit{gi:02d}"
            )
            group_ids = {item["moment"] for item in group}
            for m in result.get("moments", []):
                if m["moment"] in group_ids:
                    edits[m["moment"]] = m
                    for kind in ("sfx", "characters"):
                        used.update(x["asset"] for x in m[kind])
            music += [x for x in result.get("music", []) if x["from_moment"] in group_ids]
            if on_progress:
                on_progress((gi + 1) / len(groups), f"Montage {gi + 1}/{len(groups)}")
    return {"source": "claude", "moments": edits, "music": music}


# -------------------------------------------------------------- hors ligne
def edit_heuristic(story: dict, lines: list[dict], library: Library, style: StyleProfile, names: dict[str, str]) -> dict:
    """Montage simple sans Claude : effets posés sur les pics d'énergie."""
    sfx_pool = library.find_by_tags(("sfx",), "rire", "laugh", "lol", "boing", "cartoon", "drole", "fun", "bruh", "vine") or library.of_kind("sfx")
    char_pool = library.of_kind("character")
    edits: dict[str, dict] = {}
    n_sfx = n_char = 0
    for item in story["sequence"]:
        seg_lines = lines_between(lines, item["start_line"], item["end_line"])
        minutes = max(item["est_duration"], 1.0) / 60
        hot = sorted(
            (l for l in seg_lines if l.get("loud") or l.get("laugh") or (l["kind"] == "event" and l.get("loud"))),
            key=lambda l: (l.get("laugh", False), l.get("loud", False)),
            reverse=True,
        )
        speech_hot = [l for l in hot if l["kind"] == "speech"]
        e = {k: [] for k in EMPTY_EDIT}
        for line in speech_hot[: max(1, round(style.zooms_per_minute * minutes))]:
            e["zooms"].append({"line": line["id"], "word": "", "kind": "punch", "duration": 1.2})
        if sfx_pool:
            for line in hot[: round(style.sfx_per_minute * minutes)]:
                asset = sfx_pool[n_sfx % len(sfx_pool)]
                n_sfx += 1
                e["sfx"].append({"asset": asset["id"], "line": line["id"], "word": "", "timing": "end_of_line", "volume": "normal"})
        if char_pool:
            for i, line in enumerate(hot[: round(style.characters_per_minute * minutes)]):
                asset = char_pool[n_char % len(char_pool)]
                n_char += 1
                e["characters"].append(
                    {"asset": asset["id"], "line": line["id"], "word": "", "position": ("bottom_right", "bottom_left")[i % 2], "duration": 0}
                )
        edits[item["moment"]] = e
    music = []
    pool = library.of_kind("music")
    if pool and style.music and story["sequence"]:
        music.append({"asset": pool[0]["id"], "from_moment": story["sequence"][0]["moment"], "to_moment": story["sequence"][-1]["moment"]})
    return {"source": "heuristic", "moments": edits, "music": music}


# ------------------------------------------------------------ plan final
def build_plan(story: dict, edits: dict, style: StyleProfile) -> dict:
    """Assemble teaser + moments + décisions en un plan lisible par build_timeline."""
    segments = []
    moment_edits = edits.get("moments", {})
    cold = story.get("cold_open")
    if cold and style.cold_open:
        src = moment_edits.get(cold["moment"], EMPTY_EDIT)

        def inside(x):
            return cold["start_line"] <= x["line"] <= cold["end_line"]

        segments.append(
            {
                "moment_id": "cold_open",
                "title": f"Teaser — {cold['title']}",
                "start_line": cold["start_line"],
                "end_line": cold["end_line"],
                "removed": [i for i in src.get("remove_lines", []) if cold["start_line"] <= i <= cold["end_line"]],
                "chapter": "",
                "transition": "cut",
                **{k: [x for x in src.get(k, []) if inside(x)] for k in ("camera", "zooms", "sfx", "characters", "texts")},
            }
        )
    index_of = {}
    for item in story["sequence"]:
        e = moment_edits.get(item["moment"], EMPTY_EDIT)
        index_of[item["moment"]] = len(segments)
        first = not segments
        transition = item.get("transition", "cut")
        if cold and len(segments) == 1 and transition == "cut":
            transition = "whoosh"  # sortie du teaser
        segments.append(
            {
                "moment_id": item["moment"],
                "title": item.get("title", ""),
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "removed": e.get("remove_lines", []),
                "chapter": item.get("chapter", "") or ("Introduction" if first else ""),
                "transition": transition,
                "camera": e.get("camera", []),
                "zooms": e.get("zooms", []),
                "sfx": e.get("sfx", []),
                "characters": e.get("characters", []),
                "texts": e.get("texts", []),
            }
        )
    music = []
    if style.music:
        for m in edits.get("music", []):
            a, b = index_of.get(m.get("from_moment")), index_of.get(m.get("to_moment"))
            if a is None:
                continue
            b = a if b is None or b < a else b
            if music and music[-1]["asset"] == m["asset"] and music[-1]["to_segment"] >= a - 1:
                music[-1]["to_segment"] = max(music[-1]["to_segment"], b)
            else:
                music.append({"asset": m["asset"], "from_segment": a, "to_segment": b})
    return {"segments": segments, "music": music}
