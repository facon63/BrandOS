"""Mesure le rythme des vidéos déjà publiées pour caler le montage dessus."""

from __future__ import annotations

import re
import statistics
import subprocess
from pathlib import Path

from .config import workspace_dir
from .ffmpeg_utils import binary, probe

AUTO_START = "<!-- analyse-auto:debut -->"
AUTO_END = "<!-- analyse-auto:fin -->"


def scene_cuts(path: str | Path, threshold: float = 0.32) -> list[float]:
    cmd = [
        binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-an",
        "-vf", f"scale=320:-2,select='gt(scene,{threshold})',metadata=print:file=-",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stdout)]


def analyze_references(videos: list[str]) -> str:
    rows, rates, shots = [], [], []
    for video in videos:
        info = probe(video)
        cuts = scene_cuts(video)
        minutes = max(info.duration / 60, 0.01)
        edges = [0.0] + cuts + [info.duration]
        lengths = [b - a for a, b in zip(edges[:-1], edges[1:]) if b > a]
        rate = len(cuts) / minutes
        rates.append(rate)
        shots += lengths
        rows.append(f"- {Path(video).name} : {info.duration / 60:.1f} min, {rate:.0f} changements de plan/min")
    if not rates:
        return ""
    summary = [
        AUTO_START,
        f"Rythme mesuré sur {len(rates)} vidéo(s) publiée(s) : en moyenne {statistics.mean(rates):.0f} changements "
        f"de plan par minute, un plan dure {statistics.median(shots):.1f} s en médiane. Vise ce rythme.",
        *rows,
        AUTO_END,
    ]
    block = "\n".join(summary)
    path = workspace_dir() / "references.md"
    existing = path.read_text("utf-8") if path.exists() else ""
    if AUTO_START in existing and AUTO_END in existing:
        before, rest = existing.split(AUTO_START, 1)
        after = rest.split(AUTO_END, 1)[1]
        existing = before + block + after
    else:
        existing = (existing.rstrip() + "\n\n" + block).strip() + "\n"
    path.write_text(existing, "utf-8")
    return block
