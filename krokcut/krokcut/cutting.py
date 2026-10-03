"""Coupes automatiques : on ne garde que la parole et les réactions, on supprime les blancs."""

from __future__ import annotations

from .audio import Levels
from .config import StyleProfile

MAX_WORD = 1.5  # Whisper étire parfois un mot sur plusieurs secondes
MIN_PIECE = 0.25
MAX_ACTIVE_GAP = 4.0  # un « blanc » bruyant (rires, action) plus long que ça est quand même coupé


def line_intervals(line: dict, pad: float) -> list[tuple[float, float]]:
    if line["kind"] == "event" or not line.get("words"):
        return [(line["start"], line["end"])]
    out = []
    for _, s, e in line["words"]:
        e = min(e, s + MAX_WORD)
        out.append((s - pad, e + pad))
    return out


def moment_pieces(
    lines: list[dict],
    start_id: int,
    end_id: int,
    levels: Levels,
    style: StyleProfile,
    removed: set[int] | frozenset[int] = frozenset(),
) -> list[tuple[float, float]]:
    """Plages (temps maître) à garder pour un moment allant de la ligne start_id à end_id."""
    if end_id < start_id:
        start_id, end_id = end_id, start_id
    by_id = {line["id"]: line for line in lines}
    kept = [by_id[i] for i in range(start_id, end_id + 1) if i in by_id and i not in removed]
    if not kept:
        return []

    pad = style.keep_pad
    intervals: list[tuple[float, float, int]] = []
    for line in kept:
        intervals += [(s, e, line["id"]) for s, e in line_intervals(line, pad)]
    intervals.sort()

    pieces: list[list[float]] = []
    last_id = None
    for s, e, line_id in intervals:
        if not pieces:
            pieces.append([s, e])
            last_id = line_id
            continue
        prev_end = pieces[-1][1]
        gap = s - prev_end
        crosses_removed = any(r in removed for r in range(min(last_id, line_id) + 1, max(last_id, line_id)))
        if gap <= 0:
            pieces[-1][1] = max(prev_end, e)
        elif crosses_removed:
            pieces.append([s, e])
        elif gap <= style.max_silence or (gap <= MAX_ACTIVE_GAP and not levels.is_quiet(prev_end, s)):
            pieces[-1][1] = max(prev_end, e)
        else:
            pieces.append([s, e])
        last_id = line_id

    # Laisse respirer la fin (réaction) sans mordre sur la réplique suivante
    next_line = by_id.get(end_id + 1)
    tail_limit = next_line["start"] - 0.05 if next_line else pieces[-1][1] + style.reaction_tail
    pieces[-1][1] = max(pieces[-1][1], min(pieces[-1][1] + style.reaction_tail, tail_limit))
    prev_line = by_id.get(start_id - 1)
    if prev_line:
        pieces[0][0] = max(pieces[0][0], prev_line["end"] + 0.02)
    pieces[0][0] = max(0.0, pieces[0][0])

    return [(round(s, 3), round(e, 3)) for s, e in pieces if e - s >= MIN_PIECE]


def pieces_duration(pieces: list[tuple[float, float]]) -> float:
    return sum(e - s for s, e in pieces)
