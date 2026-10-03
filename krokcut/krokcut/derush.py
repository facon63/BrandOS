"""Dérush : repérage des moments (passe 1) puis construction de l'histoire (passe 2)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .audio import Levels
from .config import StyleProfile
from .cutting import moment_pieces, pieces_duration
from .llm import INT, LLM, STR, arr, enum, obj
from .prompts import DERUSH_INSTRUCTIONS, MOMENT_KINDS, STORY_INSTRUCTIONS, STORY_REVISION
from .transcribe import fmt_time, format_lines

MOMENT_SCHEMA = obj(
    {
        "start_line": INT,
        "end_line": INT,
        "title": STR,
        "kind": enum(*MOMENT_KINDS),
        "humor": INT,
        "energy": INT,
        "story": INT,
        "key_quote": STR,
        "depends_on": STR,
        "why": STR,
    }
)
DERUSH_SCHEMA = obj({"summary": STR, "moments": arr(MOMENT_SCHEMA)})

STORY_SCHEMA = obj(
    {
        "summary": STR,
        "title_ideas": arr(STR),
        "thumbnail_ideas": arr(STR),
        "cold_open": obj({"moment": STR, "start_line": INT, "end_line": INT}),
        "sequence": arr(
            obj(
                {
                    "moment": STR,
                    "trim_start_line": INT,
                    "trim_end_line": INT,
                    "chapter": STR,
                    "transition": enum("cut", "whoosh", "fade"),
                }
            )
        ),
        "notes": STR,
    }
)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def score(m: dict) -> float:
    return 0.5 * m["humor"] + 0.3 * m["energy"] + 0.2 * m["story"]


# --------------------------------------------------------------------- découpe
def chunk_lines(lines: list[dict], minutes: float = 20.0, overlap_s: float = 60.0) -> list[list[dict]]:
    if not lines:
        return []
    chunks: list[list[dict]] = []
    start_t = lines[0]["start"]
    current: list[dict] = []
    for line in lines:
        if current and line["start"] - start_t > minutes * 60:
            chunks.append(current)
            tail = [l for l in current if l["start"] >= current[-1]["start"] - overlap_s]
            current = list(tail)
            start_t = line["start"]
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def finalize_moments(raw: list[dict], lines: list[dict], levels: Levels, style: StyleProfile) -> list[dict]:
    """Nettoie, dédoublonne et chiffre la durée réelle de chaque moment."""
    by_id = {l["id"]: l for l in lines}
    max_id = lines[-1]["id"] if lines else 0
    cleaned = []
    for m in raw:
        s, e = int(m["start_line"]), int(m["end_line"])
        s, e = clamp(min(s, e), 0, max_id), clamp(max(s, e), 0, max_id)
        if s not in by_id or e not in by_id:
            continue
        m = dict(m)
        for k in ("humor", "energy", "story"):
            m[k] = clamp(int(m.get(k, 0)), 0, 10)
        m["start_line"], m["end_line"] = s, e
        m["start"], m["end"] = by_id[s]["start"], by_id[e]["end"]
        cleaned.append(m)

    cleaned.sort(key=score, reverse=True)
    kept: list[dict] = []
    for m in cleaned:
        dup = False
        for k in kept:
            inter = min(m["end"], k["end"]) - max(m["start"], k["start"])
            if inter > 0 and inter > 0.5 * min(m["end"] - m["start"], k["end"] - k["start"]):
                dup = True
                break
        if not dup:
            kept.append(m)
    kept.sort(key=lambda m: m["start"])
    for i, m in enumerate(kept, start=1):
        m["id"] = f"m{i:03d}"
        m["score"] = round(score(m), 2)
        m["est_duration"] = round(pieces_duration(moment_pieces(lines, m["start_line"], m["end_line"], levels, style)), 1)
    return [m for m in kept if m["est_duration"] >= 2.0]


# --------------------------------------------------------------- passe 1 (Claude)
def find_moments_claude(
    llm: LLM,
    system: str,
    lines: list[dict],
    names: dict[str, str],
    levels: Levels,
    style: StyleProfile,
    effort: str,
    parallel: int = 4,
    on_progress: Callable[[float, str], None] | None = None,
) -> tuple[list[dict], list[dict]]:
    chunks = chunk_lines(lines)
    done = 0

    def work(index_chunk):
        nonlocal done
        index, chunk = index_chunk
        content = DERUSH_INSTRUCTIONS.format(
            index=index + 1,
            total=len(chunks),
            t0=fmt_time(chunk[0]["start"]),
            t1=fmt_time(chunk[-1]["end"]),
            kinds=", ".join(MOMENT_KINDS),
            transcript=format_lines(chunk, names),
        )
        result = llm.ask_json(
            system=system, content=content, schema=DERUSH_SCHEMA, effort=effort, max_tokens=32000, label=f"derush{index:02d}"
        )
        ids = {l["id"] for l in chunk}
        moments = [m for m in result.get("moments", []) if m["start_line"] in ids or m["end_line"] in ids]
        done += 1
        if on_progress:
            on_progress(done / len(chunks), f"Dérush {done}/{len(chunks)} extraits")
        return {"index": index, "t0": chunk[0]["start"], "t1": chunk[-1]["end"], "summary": result.get("summary", "")}, moments

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        results = list(pool.map(work, enumerate(chunks)))
    summaries = [r[0] for r in results]
    raw = [m for r in results for m in r[1]]
    return finalize_moments(raw, lines, levels, style), summaries


# ---------------------------------------------------------- passe 1 (hors ligne)
def find_moments_heuristic(lines: list[dict], levels: Levels, style: StyleProfile, names: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Sans Claude : on repère les pics d'énergie (cris, rires, échanges rapides)."""
    if not lines:
        return [], []
    weights = []
    prev_speaker = None
    for line in lines:
        w = 0.0
        if line["kind"] == "event":
            w += 2.5 if line.get("loud") else 1.0
        else:
            w += 0.2
            if line.get("loud"):
                w += 2.0
            if line.get("laugh"):
                w += 3.0
            if line["text"].rstrip().endswith(("!", "?")):
                w += 0.3
            if prev_speaker and line.get("speaker") and line["speaker"] != prev_speaker:
                w += 0.5
            prev_speaker = line.get("speaker") or prev_speaker
        weights.append(w)

    window = 40.0
    scores = []
    j0 = 0
    for i, line in enumerate(lines):
        while lines[j0]["start"] < line["start"] - window * 0.7:
            j0 += 1
        scores.append(sum(weights[j0 : i + 1]))

    target = style.target_max_minutes * 60 * 2.5
    order = sorted(range(len(lines)), key=lambda i: scores[i], reverse=True)
    taken: list[tuple[float, float]] = []
    raw = []
    total = 0.0
    for i in order:
        if total >= target or scores[i] <= 0.5:
            break
        peak = lines[i]
        t0, t1 = peak["start"] - 25.0, peak["end"] + 6.0
        if any(t0 < b and a < t1 for a, b in taken):
            continue
        ids = [l["id"] for l in lines if l["start"] >= t0 and l["end"] <= t1] or [peak["id"]]
        quote_line = max(
            (l for l in lines if l["id"] in ids and l["kind"] == "speech"),
            key=lambda l: (l.get("loud", False), l.get("laugh", False), len(l["text"])),
            default=peak,
        )
        level = min(10, int(scores[i]))
        raw.append(
            {
                "start_line": ids[0],
                "end_line": ids[-1],
                "title": f"Moment fort vers {fmt_time(peak['start'])}",
                "kind": "moment_fort",
                "humor": level,
                "energy": level,
                "story": 3,
                "key_quote": quote_line["text"][:140],
                "depends_on": "",
                "why": "pic d'énergie sonore (mode hors ligne, sans Claude)",
            }
        )
        taken.append((t0, t1))
        total += t1 - t0
    moments = finalize_moments(raw, lines, levels, style)
    summaries = [{"index": 0, "t0": lines[0]["start"], "t1": lines[-1]["end"], "summary": "(mode hors ligne : pas de résumé)"}]
    return moments, summaries


# ------------------------------------------------------------ passe 2 (histoire)
def _moment_row(m: dict) -> str:
    dep = f" | dépend de : {m['depends_on']}" if m.get("depends_on") else ""
    return (
        f"{m['id']} [{fmt_time(m['start'])}–{fmt_time(m['end'])}] {m['est_duration']:.0f}s | lignes "
        f"#{m['start_line']}–#{m['end_line']} | {m['kind']} | humour {m['humor']} énergie {m['energy']} "
        f"histoire {m['story']} | « {m['title']} » — \"{m['key_quote']}\"{dep}"
    )


def sequence_duration(story: dict) -> float:
    total = sum(item.get("est_duration", 0.0) for item in story["sequence"])
    if story.get("cold_open"):
        total += story["cold_open"].get("est_duration", 0.0)
    return total


def normalize_story(raw: dict, moments: list[dict], lines: list[dict], levels: Levels, style: StyleProfile, source: str) -> dict:
    by_id = {m["id"]: m for m in moments}
    seen = set()
    sequence = []
    for item in raw.get("sequence", []):
        m = by_id.get(item.get("moment"))
        if not m or m["id"] in seen:
            continue
        seen.add(m["id"])
        s, e = m["start_line"], m["end_line"]
        ts, te = int(item.get("trim_start_line", -1)), int(item.get("trim_end_line", -1))
        if s <= ts <= e:
            s = ts
        if s <= te <= e:
            e = te
        sequence.append(
            {
                "moment": m["id"],
                "title": m["title"],
                "start_line": s,
                "end_line": e,
                "chapter": item.get("chapter", ""),
                "transition": item.get("transition", "cut"),
                "est_duration": round(pieces_duration(moment_pieces(lines, s, e, levels, style)), 1),
            }
        )
    cold = None
    co = raw.get("cold_open") or {}
    if style.cold_open and co.get("moment") in by_id:
        m = by_id[co["moment"]]
        s = clamp(int(co.get("start_line", m["start_line"])), m["start_line"], m["end_line"])
        e = clamp(int(co.get("end_line", m["end_line"])), s, m["end_line"])
        dur = pieces_duration(moment_pieces(lines, s, e, levels, style))
        if dur > 25:  # un teaser doit rester court
            e = s
            for line_id in range(s, m["end_line"] + 1):
                if pieces_duration(moment_pieces(lines, s, line_id, levels, style)) > 15:
                    break
                e = line_id
            dur = pieces_duration(moment_pieces(lines, s, e, levels, style))
        cold = {"moment": m["id"], "title": m["title"], "start_line": s, "end_line": e, "est_duration": round(dur, 1)}
    return {
        "source": source,
        "summary": raw.get("summary", ""),
        "title_ideas": raw.get("title_ideas", []),
        "thumbnail_ideas": raw.get("thumbnail_ideas", []),
        "notes": raw.get("notes", ""),
        "cold_open": cold,
        "sequence": sequence,
    }


def fit_duration(story: dict, moments: list[dict], lines: list[dict], levels: Levels, style: StyleProfile) -> dict:
    """Dernier ajustement automatique pour tomber dans la fourchette de durée."""
    lo, hi = style.target_min_minutes * 60, style.target_max_minutes * 60
    by_id = {m["id"]: m for m in moments}
    while sequence_duration(story) > hi and len(story["sequence"]) > 1:
        protected = story["cold_open"]["moment"] if story.get("cold_open") else None
        candidates = [i for i in story["sequence"] if i["moment"] != protected] or story["sequence"]
        worst = min(candidates, key=lambda i: (by_id[i["moment"]]["story"] >= 8, by_id[i["moment"]]["score"]))
        story["sequence"].remove(worst)
    used = {i["moment"] for i in story["sequence"]}
    spare = sorted((m for m in moments if m["id"] not in used), key=lambda m: m["score"], reverse=True)
    for m in spare:
        if sequence_duration(story) >= lo:
            break
        if sequence_duration(story) + m["est_duration"] > hi:
            continue
        story["sequence"].append(
            {
                "moment": m["id"],
                "title": m["title"],
                "start_line": m["start_line"],
                "end_line": m["end_line"],
                "chapter": "",
                "transition": "cut",
                "est_duration": m["est_duration"],
            }
        )
        story["sequence"].sort(key=lambda i: by_id[i["moment"]]["start"])
    story["total_estimate"] = round(sequence_duration(story), 1)
    return story


def build_story_claude(
    llm: LLM,
    system: str,
    moments: list[dict],
    summaries: list[dict],
    lines: list[dict],
    levels: Levels,
    style: StyleProfile,
    effort: str,
) -> dict:
    rule = (
        "choisis le meilleur passage de 5 à 15 secondes (lignes start_line/end_line à l'intérieur d'un "
        "des moments) pour accrocher le spectateur dès la première seconde ; il sera rejoué à sa place normale."
        if style.cold_open
        else 'pas de teaser : mets moment "" et 0 pour les lignes.'
    )
    content = STORY_INSTRUCTIONS.format(
        min_minutes=style.target_min_minutes,
        max_minutes=style.target_max_minutes,
        cold_open_rule=rule,
        moments="\n".join(_moment_row(m) for m in moments),
        summaries="\n".join(f"[{fmt_time(s['t0'])}–{fmt_time(s['t1'])}] {s['summary']}" for s in summaries),
    )
    raw = llm.ask_json(system=system, content=content, schema=STORY_SCHEMA, effort=effort, max_tokens=32000, label="story")
    story = normalize_story(raw, moments, lines, levels, style, "claude")

    actual = sequence_duration(story) / 60
    if not (style.target_min_minutes - 0.5 <= actual <= style.target_max_minutes + 0.5):
        advice = (
            "Retire les moments les plus faibles ou raccourcis-en." if actual > style.target_max_minutes
            else "Ajoute des moments (les durées indiquées sont fiables)."
        )
        revision = STORY_REVISION.format(
            actual=actual,
            min_minutes=style.target_min_minutes,
            max_minutes=style.target_max_minutes,
            advice=advice,
            previous=json.dumps(raw, ensure_ascii=False),
        )
        raw = llm.ask_json(
            system=system, content=content + "\n\n" + revision, schema=STORY_SCHEMA, effort=effort, max_tokens=32000, label="story_rev"
        )
        story = normalize_story(raw, moments, lines, levels, style, "claude")
    return fit_duration(story, moments, lines, levels, style)


def build_story_heuristic(moments: list[dict], lines: list[dict], levels: Levels, style: StyleProfile) -> dict:
    target = (style.target_min_minutes + style.target_max_minutes) / 2 * 60
    chosen, total = [], 0.0
    for m in sorted(moments, key=lambda m: m["score"], reverse=True):
        if total + m["est_duration"] > style.target_max_minutes * 60:
            continue
        chosen.append(m)
        total += m["est_duration"]
        if total >= target:
            break
    chosen.sort(key=lambda m: m["start"])
    raw = {
        "sequence": [
            {"moment": m["id"], "trim_start_line": -1, "trim_end_line": -1, "chapter": "", "transition": "cut"}
            for m in chosen
        ],
        "cold_open": {},
    }
    if chosen and style.cold_open:
        best = max(chosen, key=lambda m: m["score"])
        raw["cold_open"] = {"moment": best["id"], "start_line": max(best["start_line"], best["end_line"] - 3), "end_line": best["end_line"]}
    story = normalize_story(raw, moments, lines, levels, style, "heuristic")
    return fit_duration(story, moments, lines, levels, style)
