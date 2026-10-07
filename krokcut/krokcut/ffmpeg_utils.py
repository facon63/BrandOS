"""Petites briques autour de ffmpeg / ffprobe.

Tout le traitement média passe par les binaires ffmpeg installés sur la
machine : aucune vidéo n'est envoyée sur internet.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Sequence

ProgressCallback = Callable[[float], None]

APP_DIR = Path(__file__).resolve().parent.parent  # ~/KrokCut : l'installeur Mac y range ffmpeg dans bin/
# Emplacements habituels (Homebrew Apple Silicon / Intel, MacPorts) : l'app lancée depuis le Finder
# hérite d'un PATH minimal qui ne les contient pas.
EXTRA_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
MISSING_MARK = "' est introuvable"  # repère stable : « 'ffmpeg' est introuvable … »


class FFmpegError(RuntimeError):
    pass


def search_dirs() -> list[Path]:
    """Dossiers où chercher ffmpeg/ffprobe, du plus spécifique au plus général."""
    dirs: list[Path] = []
    custom = os.environ.get("KROKCUT_FFMPEG_DIR")
    if custom:
        dirs.append(Path(custom).expanduser())
    dirs.append(APP_DIR / "bin")
    if os.name == "nt":
        dirs.append(APP_DIR / "ffmpeg" / "bin")
    dirs += [Path(d) for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    if os.name != "nt":
        dirs += [Path(d) for d in EXTRA_DIRS]
    unique: list[Path] = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def _usable(path: Path) -> bool:
    # is_file() suit les liens : un lien cassé (ffmpeg de Homebrew désinstallé…) est ignoré
    return path.is_file() and os.access(path, os.X_OK)


def find_binary(name: str) -> str | None:
    exe = name + (".exe" if os.name == "nt" else "")
    for d in search_dirs():
        if _usable(d / exe):
            return str(d / exe)
    return None


def missing_message(name: str) -> str:
    if sys.platform == "darwin":
        fix = (
            "Clique sur « Réparer ffmpeg » en haut de la page de KrokCut, ou relance la commande "
            "d'installation de KrokCut dans le Terminal : elle réinstalle ffmpeg dans ~/KrokCut/bin."
        )
    elif os.name == "nt":
        fix = "Relance installer.bat (il installe ffmpeg), puis rouvre KrokCut."
    else:
        fix = "Installe ffmpeg (sudo apt install ffmpeg) ou définis KROKCUT_FFMPEG_DIR."
    return f"'{name}{MISSING_MARK} : KrokCut ne peut pas lire les vidéos sans lui. {fix}"


def is_missing_error(text: str) -> bool:
    """Erreur enregistrée parce que ffmpeg ou ffprobe manquait (ancien et nouveau message)."""
    return any(f"'{name}{MISSING_MARK}" in (text or "") for name in ("ffmpeg", "ffprobe"))


def binary(name: str) -> str:
    """Chemin de ffmpeg/ffprobe : KROKCUT_FFMPEG_DIR, ~/KrokCut/bin, le PATH, puis Homebrew."""
    found = find_binary(name)
    if not found:
        raise FFmpegError(missing_message(name))
    return found


def ffmpeg_status() -> dict:
    """État affiché par l'interface (bandeau « ffmpeg introuvable » + bouton Réparer)."""
    paths = {name: find_binary(name) for name in ("ffmpeg", "ffprobe")}
    missing = [name for name, path in paths.items() if not path]
    return {
        "ok": not missing,
        "ffmpeg": paths["ffmpeg"] or "",
        "ffprobe": paths["ffprobe"] or "",
        "error": missing_message(missing[0]) if missing else "",
    }


def _launch(cmd: Sequence[str], **kwargs):
    """subprocess.run, avec une erreur claire si le programme existe mais ne se lance pas."""
    try:
        return subprocess.run(cmd, **kwargs)
    except OSError as exc:  # mauvais processeur, fichier abîmé, droits…
        raise FFmpegError(_launch_error(cmd[0], exc)) from exc


def _launch_error(program: str, exc: OSError) -> str:
    return (
        f"Impossible de lancer {program} ({exc.strerror or exc}). "
        + (missing_message(Path(program).stem).split(" : ", 1)[1] if sys.platform == "darwin" else "Réinstalle ffmpeg.")
    )


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
        proc = _launch(cmd, capture_output=True, text=True, errors="replace", cwd=cwd)
        if proc.returncode != 0:
            raise FFmpegError(_format_error(cmd, proc.stderr))
        return

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            cwd=cwd,
        )
    except OSError as exc:
        raise FFmpegError(_launch_error(cmd[0], exc)) from exc
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
        proc = _launch([binary("ffmpeg"), "-version"], capture_output=True, text=True, errors="replace")
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
    proc = _launch(cmd, capture_output=True, text=True, errors="replace")
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
