"""Timeline du montage : modèle de données et construction à partir du plan de montage.

Le plan (produit par Claude ou par l'heuristique hors-ligne) parle en
« lignes de transcription » et en mots ; ce module le traduit en plans
précis à l'image près, en temps de timeline.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from .audio import Levels
from .config import StyleProfile
from .cutting import moment_pieces
from .library import Library
from .project import Source

Pov = Literal["A", "B", "both"]
POSITIONS = ("bottom_left", "bottom_right", "top_left", "top_right", "center", "left", "right")


class Zoom(BaseModel):
    t0: float  # relatif au début du plan
    t1: float
    kind: Literal["punch", "slow", "shake"] = "punch"
    scale: float = 1.25
    cx: float = 0.5
    cy: float = 0.45


class Clip(BaseModel):
    id: str
    segment: int
    moment_id: str
    src_in: float  # temps maître
    src_out: float
    pov: Pov
    start_f: int = 0  # position sur la timeline (images)
    frames: int = 0
    zooms: list[Zoom] = Field(default_factory=list)
    fade_in: float = 0.0
    fade_out: float = 0.0

    @property
    def duration(self) -> float:
        return self.src_out - self.src_in


class Overlay(BaseModel):
    asset_id: str
    path: str
    kind: str
    key: str = "alpha"
    start: float
    duration: float
    position: str = "bottom_right"
    scale: float = 0.38
    with_audio: bool = False


class TextItem(BaseModel):
    text: str
    start: float
    duration: float = 1.6
    style: Literal["impact", "caption", "meme"] = "impact"


class Sfx(BaseModel):
    asset_id: str
    path: str
    start: float
    volume_db: float = -6.0
    duration: float = 0.0


class Music(BaseModel):
    asset_id: str
    path: str
    start: float
    end: float
    volume_db: float = -24.0


class Marker(BaseModel):
    start: float
    name: str


class Segment(BaseModel):
    index: int
    moment_id: str
    title: str = ""
    chapter: str = ""
    start: float = 0.0
    end: float = 0.0


class Timeline(BaseModel):
    version: int = 1
    fps: float
    width: int
    height: int
    layout: str = "switch"
    audio_mode: str = "follow"
    sources: dict[str, Source]
    clips: list[Clip] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    overlays: list[Overlay] = Field(default_factory=list)
    texts: list[TextItem] = Field(default_factory=list)
    sfx: list[Sfx] = Field(default_factory=list)
    music: list[Music] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)

    @property
    def total_frames(self) -> int:
        return sum(c.frames for c in self.clips)

    @property
    def duration(self) -> float:
        return self.total_frames / self.fps


# ------------------------------------------------------------------ ancrages
def _norm(word: str) -> str:
    word = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9']+", "", word)


def anchor_time(line: dict, word: str = "", timing: str = "on_word") -> float:
    """Instant (temps maître) d'un mot dans une ligne, ou de la fin de la ligne."""
    if timing == "end_of_line":
        return float(line["end"])
    target = [_norm(w) for w in (word or "").split() if _norm(w)]
    words = line.get("words") or []
    if target and words:
        normed = [_norm(w[0]) for w in words]
        first = target[0]
        for i, w in enumerate(normed):
            if w == first or (len(first) >= 4 and w.startswith(first[:5])):
                return float(words[i][1])
    return float(line["start"])


# --------------------------------------------------------------- caméra
def camera_switches(
    lines: list[dict],
    pieces: list[tuple[float, float]],
    directives: list[dict],
    style: StyleProfile,
) -> list[tuple[float, str]]:
    """Liste (instant, pov) des changements de plan pour un segment."""
    if not pieces:
        return []
    seg_start = pieces[0][0]
    by_id = {l["id"]: l for l in lines}
    if directives:
        out = []
        for d in sorted(directives, key=lambda d: by_id.get(d["line"], {"start": 0})["start"]):
            line = by_id.get(d["line"])
            if not line:
                continue
            t = max(seg_start, line["start"] - style.keep_pad)
            out.append((t, d["pov"]))
        if not out or out[0][0] > seg_start:
            out.insert(0, (seg_start, out[0][1] if out else "A"))
        return out

    # Automatique : on suit celui qui parle, sans changer de plan trop souvent
    speech = [l for l in lines if l["kind"] == "speech" and l.get("speaker") in ("A", "B")]
    if not speech:
        return [(seg_start, "A")]
    current = speech[0]["speaker"]
    out = [(seg_start, current)]
    shot_start = seg_start
    for line in speech[1:]:
        if line["speaker"] == current:
            continue
        # Trop tôt pour changer de plan ? On bascule un peu plus tard dans la réplique.
        t = max(seg_start, line["start"] - style.keep_pad, shot_start + style.min_shot)
        if t < line["end"] - 0.5:
            current = line["speaker"]
            out.append((t, current))
            shot_start = t
    return out


def _available(pov: str, sources: dict[str, Source], t0: float, t1: float) -> bool:
    if pov == "both":
        return sources["A"].covers(t0, t1) and sources["B"].covers(t0, t1)
    return sources[pov].covers(t0, t1)


def _resolve_pov(pov: str, sources: dict[str, Source], t0: float, t1: float) -> str:
    for candidate in (pov, "A" if pov != "A" else "B", "B"):
        if _available(candidate, sources, t0, t1):
            return candidate
    return pov


# --------------------------------------------------------------- construction
def build_timeline(
    plan: dict,
    lines: list[dict],
    levels: Levels,
    style: StyleProfile,
    sources: dict[str, Source],
    library: Library,
    fps: float,
    width: int,
    height: int,
) -> Timeline:
    by_id = {l["id"]: l for l in lines}
    tl = Timeline(
        fps=fps, width=width, height=height, layout=style.layout, audio_mode=style.audio_mode, sources=sources
    )
    frame_cursor = 0
    clip_n = 0
    seg_clips: dict[int, list[Clip]] = {}
    whooshes = library.find_by_tags(("sfx",), "whoosh", "swoosh", "transition", "woosh", "swish")

    for index, seg in enumerate(plan.get("segments", [])):
        removed = set(seg.get("removed", []))
        pieces = moment_pieces(lines, seg["start_line"], seg["end_line"], levels, style, removed)
        if not pieces:
            continue
        seg_lines = [
            by_id[i]
            for i in range(min(seg["start_line"], seg["end_line"]), max(seg["start_line"], seg["end_line"]) + 1)
            if i in by_id and i not in removed
        ]
        directives = [d for d in seg.get("camera", []) if d.get("pov") in ("A", "B", "both")]
        if style.layout == "split":
            directives = [{"line": seg_lines[0]["id"], "pov": "both"}]
        switches = camera_switches(seg_lines, pieces, directives, style)

        clips: list[Clip] = []
        for p0, p1 in pieces:
            cuts = [p0] + [t for t, _ in switches if p0 < t < p1] + [p1]
            for c0, c1 in zip(cuts[:-1], cuts[1:]):
                pov = next((p for t, p in reversed(switches) if t <= c0 + 1e-6), switches[0][1])
                n = int(round((c1 - c0) * fps))
                if n < 2:
                    continue
                clip_n += 1
                clips.append(
                    Clip(
                        id=f"c{clip_n:04d}",
                        segment=index,
                        moment_id=seg.get("moment_id", f"s{index}"),
                        src_in=round(c0, 4),
                        src_out=round(c0 + n / fps, 4),
                        pov=_resolve_pov(pov, sources, c0, c0 + n / fps),
                        start_f=frame_cursor,
                        frames=n,
                    )
                )
                frame_cursor += n
        if not clips:
            continue
        seg_clips[index] = clips
        tl.clips += clips
        seg_start = clips[0].start_f / fps
        seg_end = (clips[-1].start_f + clips[-1].frames) / fps
        tl.segments.append(
            Segment(
                index=index,
                moment_id=seg.get("moment_id", ""),
                title=seg.get("title", ""),
                chapter=seg.get("chapter", ""),
                start=seg_start,
                end=seg_end,
            )
        )
        if seg.get("chapter"):
            tl.markers.append(Marker(start=seg_start, name=seg["chapter"]))

        # Transitions
        transition = seg.get("transition", "cut")
        if transition == "fade" and len(tl.segments) > 1:
            prev = seg_clips[tl.segments[-2].index][-1]
            prev.fade_out = min(0.25, prev.duration / 3)
            clips[0].fade_in = min(0.25, clips[0].duration / 3)
        elif transition == "whoosh" and style.transition_sfx and whooshes and len(tl.segments) > 1:
            w = whooshes[index % len(whooshes)]
            tl.sfx.append(
                Sfx(
                    asset_id=w["id"],
                    path=str(library.path_of(w)),
                    start=max(0.0, seg_start - min(0.3, w["duration"] / 2)),
                    volume_db=style.sfx_volume_db - 2,
                    duration=w["duration"],
                )
            )

        def to_tl(t: float, prefer_before: bool = False) -> float:
            return map_time(clips, t, fps, prefer_before)

        # Zooms
        for z in seg.get("zooms", []):
            line = by_id.get(z.get("line"))
            if not line:
                continue
            t = anchor_time(line, z.get("word", ""))
            kind = z.get("kind", "punch") if z.get("kind") in ("punch", "slow", "shake") else "punch"
            duration = float(z.get("duration") or 1.5)
            duration = max(0.4, min(duration, 6.0))
            scale = {"punch": style.punch_scale, "slow": 1.15, "shake": 1.12}[kind]
            apply_zoom(clips, t, duration, kind, scale)

        # Bruitages
        vol = {"low": -6.0, "normal": 0.0, "high": 4.0}
        for s in seg.get("sfx", []):
            line = by_id.get(s.get("line"))
            asset = library.resolve(s.get("asset", ""), ("sfx",))
            if not line or not asset:
                continue
            t = anchor_time(line, s.get("word", ""), s.get("timing", "on_word"))
            tl.sfx.append(
                Sfx(
                    asset_id=asset["id"],
                    path=str(library.path_of(asset)),
                    start=to_tl(t, prefer_before=s.get("timing") == "end_of_line"),
                    volume_db=style.sfx_volume_db + vol.get(s.get("volume", "normal"), 0.0),
                    duration=asset["duration"],
                )
            )

        # Personnages / memes incrustés
        for c in seg.get("characters", []):
            line = by_id.get(c.get("line"))
            asset = library.resolve(c.get("asset", ""), ("character", "image", "video"))
            if not line or not asset:
                continue
            t = anchor_time(line, c.get("word", ""))
            natural = asset["duration"] if asset["duration"] > 0.2 else 2.0
            duration = float(c.get("duration") or natural)
            if asset["kind"] in ("character", "video") and asset["duration"] > 0.2:
                duration = min(duration, asset["duration"])
            duration = max(0.5, min(duration, 8.0))
            position = c.get("position") if c.get("position") in POSITIONS else "bottom_right"
            tl.overlays.append(
                Overlay(
                    asset_id=asset["id"],
                    path=str(library.path_of(asset)),
                    kind=asset["kind"],
                    key=asset.get("key", "alpha"),
                    start=to_tl(t),
                    duration=duration,
                    position=position,
                    scale=1.0 if position == "center" and asset["kind"] == "video" else style.character_scale,
                    with_audio=bool(asset.get("has_audio")) and asset["kind"] in ("character", "video"),
                )
            )

        # Textes à l'écran
        for x in seg.get("texts", []):
            line = by_id.get(x.get("line"))
            text = (x.get("text") or "").strip()
            if not line or not text:
                continue
            t = anchor_time(line, x.get("word", ""))
            style_name = x.get("style") if x.get("style") in ("impact", "caption", "meme") else "impact"
            tl.texts.append(TextItem(text=text[:80], start=to_tl(t), duration=1.6, style=style_name))

    # Musiques de fond (par plages de segments)
    seg_by_index = {s.index: s for s in tl.segments}
    for m in plan.get("music", []):
        asset = library.resolve(m.get("asset", ""), ("music",))
        start_seg = seg_by_index.get(m.get("from_segment"))
        end_seg = seg_by_index.get(m.get("to_segment"))
        if not asset or not start_seg or not end_seg or end_seg.end <= start_seg.start:
            continue
        tl.music.append(
            Music(
                asset_id=asset["id"],
                path=str(library.path_of(asset)),
                start=start_seg.start,
                end=end_seg.end,
                volume_db=style.music_volume_db,
            )
        )

    tl.overlays.sort(key=lambda o: o.start)
    tl.sfx.sort(key=lambda s: s.start)
    tl.texts.sort(key=lambda t: t.start)
    return tl


def map_time(clips: list[Clip], t: float, fps: float, prefer_before: bool = False) -> float:
    """Temps maître -> temps timeline, en restant dans les plans d'un segment."""
    for clip in clips:
        if clip.src_in - 1e-6 <= t < clip.src_out:
            return clip.start_f / fps + (t - clip.src_in)
    # l'instant tombe dans un blanc coupé : on se cale sur le plan voisin
    after = [c for c in clips if c.src_in > t]
    before = [c for c in clips if c.src_out <= t]
    if prefer_before and before:
        c = before[-1]
        return max(c.start_f / fps, (c.start_f + c.frames) / fps - 0.1)
    if after:
        return after[0].start_f / fps
    c = clips[-1]
    return max(c.start_f / fps, (c.start_f + c.frames) / fps - 0.3)


def apply_zoom(clips: list[Clip], t: float, duration: float, kind: str, scale: float) -> None:
    """Pose un zoom à l'instant t ; il continue sur les plans suivants si la coupe tombe dedans."""
    remaining = duration
    started = False
    for clip in clips:
        if not started:
            if t >= clip.src_out:
                continue
            started = True
            rel0 = max(0.0, t - clip.src_in)
        else:
            rel0 = 0.0
        rel1 = min(clip.duration, rel0 + remaining)
        if rel1 - rel0 >= 0.15:
            # évite les zooms qui se chevauchent sur un même plan
            if not any(z.t0 < rel1 and rel0 < z.t1 for z in clip.zooms):
                clip.zooms.append(Zoom(t0=round(rel0, 3), t1=round(rel1, 3), kind=kind, scale=scale))
        remaining -= rel1 - rel0
        if remaining <= 0.05 or kind != "punch":
            break
