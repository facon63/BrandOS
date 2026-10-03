"""Petites briques autour de ffmpeg / ffprobe.

Tout le traitement média passe par les binaires ffmpeg installés sur la
machine : aucune vidéo n'est envoyée sur internet.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Sequence

ProgressCallback = Callable[[float], None]


class FFmpegError(RuntimeError):
    pass


def binary(name: str) -> str:
    """Chemin de ffmpeg/ffprobe (variable KROKCUT_FFMPEG_DIR possible)."""
    custom_dir = os.environ.get("KROKCUT_FFMPEG_DIR")
    if custom_dir:
        candidate = Path(custom_dir) / (name + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if not found:
        raise FFmpegError(
            f"'{name}' est introuvable. Installe ffmpeg (https://ffmpeg.org/download.html) "
            "et ajoute-le au PATH, ou définis KROKCUT_FFMPEG_DIR."
        )
    return found


def run_ffmpeg(
    args: Sequence[str],
    *,
    duration: float | None = None,
    on_progress: ProgressCallback | None = None,
    cwd: str | Path | None = None,
) -> None:
    """Lance ffmpeg et remonte la progression (0..1) si `duration` est connue."""
    cmd = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    if on_progress and duration:
        cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += [str(a) for a in args]

    if not (on_progress and duration):
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", cwd=cwd)
        if proc.returncode != 0:
            raise FFmpegError(_format_error(cmd, proc.stderr))
        return

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        cwd=cwd,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    # out_time_ms est en réalité exprimé en microsecondes.
                    on_progress(min(1.0, int(value) / 1_000_000 / duration))
    except BaseException:  # annulation : on ne laisse pas ffmpeg tourner seul
        proc.kill()
        proc.wait()
        raise
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        raise FFmpegError(_format_error(cmd, stderr))
    on_progress(1.0)


_VERSION: int | None = None


def ffmpeg_major_version() -> int:
    global _VERSION
    if _VERSION is None:
        proc = subprocess.run([binary("ffmpeg"), "-version"], capture_output=True, text=True, errors="replace")
        match = re.search(r"ffmpeg version n?(\d+)", proc.stdout)
        _VERSION = int(match.group(1)) if match else 6
    return _VERSION


def filter_script_args(script: Path) -> list[str]:
    """Passe un gros graphe de filtres par fichier (limite de longueur de commande sous Windows)."""
    if ffmpeg_major_version() >= 7:
        return ["-/filter_complex", str(script)]
    return ["-filter_complex_script", str(script)]


def _format_error(cmd: Sequence[str], stderr: str) -> str:
    tail = "\n".join(stderr.strip().splitlines()[-15:])
    short_cmd = " ".join(cmd)
    if len(short_cmd) > 1500:
        short_cmd = short_cmd[:1500] + " …"
    return f"ffmpeg a échoué :\n{tail}\n\nCommande : {short_cmd}"


@dataclass
class MediaInfo:
    path: str
    duration: float
    has_video: bool
    has_audio: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0
    fps_fraction: str = ""
    pix_fmt: str = ""
    video_codec: str = ""
    alpha: bool = False
    audio_streams: int = 0
    sample_rate: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


_ALPHA_PIX_FMTS = ("yuva", "rgba", "argb", "bgra", "abgr", "ya8", "ya16", "gbrap", "pal8")


def probe(path: str | Path) -> MediaInfo:
    cmd = [
        binary("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"Impossible de lire {path} :\n{proc.stderr.strip()}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video"
            and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    audios = [s for s in streams if s.get("codec_type") == "audio"]

    duration = float(data.get("format", {}).get("duration") or 0.0)
    if not duration and video and video.get("duration"):
        duration = float(video["duration"])

    info = MediaInfo(
        path=str(path),
        duration=duration,
        has_video=video is not None,
        has_audio=bool(audios),
        audio_streams=len(audios),
    )
    if video:
        info.width = int(video.get("width") or 0)
        info.height = int(video.get("height") or 0)
        info.video_codec = video.get("codec_name", "")
        info.pix_fmt = video.get("pix_fmt", "")
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        if rate in ("0/0", "0/1"):
            rate = video.get("r_frame_rate") or "0/1"
        try:
            frac = Fraction(rate)
            info.fps = float(frac) if frac else 0.0
            info.fps_fraction = f"{frac.numerator}/{frac.denominator}"
        except (ValueError, ZeroDivisionError):
            info.fps = 0.0
        tags = {k.lower(): v for k, v in (video.get("tags") or {}).items()}
        info.alpha = info.pix_fmt.startswith(_ALPHA_PIX_FMTS) or tags.get("alpha_mode") == "1"
    if audios:
        info.sample_rate = int(audios[0].get("sample_rate") or 0)
    return info


def decoder_args(info: MediaInfo) -> list[str]:
    """Arguments à placer avant `-i` pour décoder correctement la couche alpha."""
    if info.alpha and info.video_codec in ("vp9", "vp8"):
        return ["-c:v", "libvpx-vp9" if info.video_codec == "vp9" else "libvpx"]
    return []


def extract_pcm(
    src: str | Path,
    dst: str | Path,
    *,
    sample_rate: int = 16000,
    audio_track: int = 0,
    duration: float | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Extrait une piste audio en PCM 16 bits mono brut (facile à lire avec numpy)."""
    tmp = Path(str(dst) + ".part")
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-map",
            f"0:a:{audio_track}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            str(tmp),
        ],
        duration=duration,
        on_progress=on_progress,
    )
    tmp.replace(dst)


def extract_frame(src: str | Path, t: float, dst: str | Path, *, width: int = 512) -> bool:
    try:
        run_ffmpeg(
            [
                "-ss",
                f"{max(0.0, t):.3f}",
                "-i",
                str(src),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:-2",
                "-q:v",
                "5",
                str(dst),
            ]
        )
    except FFmpegError:
        return False
    return Path(dst).exists()


def concat_files(files: Sequence[str | Path], dst: str | Path) -> None:
    """Concatène sans réencoder (pour une caméra qui a découpé ses fichiers)."""
    dst = Path(dst)
    listing = dst.with_suffix(".txt")
    concat_listing(files, listing)
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dst)])
    listing.unlink(missing_ok=True)


def _concat_escape(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "'\\''")


def concat_listing(files: Sequence[str | Path], listing: Path) -> None:
    listing.write_text(
        "".join(f"file '{_concat_escape(Path(f).resolve())}'\n" for f in files),
        encoding="utf-8",
    )
