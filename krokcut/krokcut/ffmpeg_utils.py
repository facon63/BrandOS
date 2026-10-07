"""Petites briques autour de ffmpeg / ffprobe.

Tout le traitement média passe par les binaires ffmpeg installés sur la
machine : aucune vidéo n'est envoyée sur internet.
"""

from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterator, Sequence

import numpy as np

ProgressCallback = Callable[[float], None]

APP_DIR = Path(__file__).resolve().parent.parent  # ~/KrokCut : l'installeur Mac y range ffmpeg dans bin/
# Emplacements habituels (Homebrew Apple Silicon / Intel, MacPorts) : l'app lancée depuis le Finder
# hérite d'un PATH minimal qui ne les contient pas.
EXTRA_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
# Repères stables des messages (« 'ffmpeg' est introuvable … », « 'ffmpeg' ne se lance pas … ») : ils
# permettent de reconnaître les traitements arrêtés faute de ffmpeg, pour les relancer une fois réparé.
MISSING_MARK = "' est introuvable"
BROKEN_MARK = "' ne se lance pas"


class FFmpegError(RuntimeError):
    pass


class FFmpegUnavailable(FFmpegError):
    """ffmpeg ou ffprobe absent, ou présent mais impossible à lancer : rien ne marchera avant réparation."""


def search_dirs(windows: bool | None = None) -> list[Path]:
    """Dossiers où chercher ffmpeg/ffprobe, du plus spécifique au plus général."""
    windows = os.name == "nt" if windows is None else windows
    dirs: list[Path] = []
    custom = os.environ.get("KROKCUT_FFMPEG_DIR")
    if custom:
        dirs.append(Path(custom).expanduser())
    dirs.append(APP_DIR / "bin")
    if windows:  # ffmpeg.exe posé à côté de KrokCut, comme le trouvait l'ancienne recherche
        dirs += [APP_DIR / "ffmpeg" / "bin", APP_DIR, Path.cwd()]
    dirs += [Path(d) for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    if not windows:
        dirs += [Path(d) for d in EXTRA_DIRS]
    unique: list[Path] = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def _usable(path: Path) -> bool:
    # os.path.isfile suit les liens (un lien cassé est ignoré) et ne lève jamais d'erreur, même sur un
    # dossier du PATH qu'on n'a pas le droit de lire : on passe simplement au suivant.
    return os.path.isfile(path) and os.access(path, os.X_OK)


_LAUNCH_CACHE: dict[tuple, str] = {}


def launch_problem(path: str) -> str:
    """« » si le programme se lance ; sinon pourquoi (mauvais processeur, fichier abîmé…). Mis en cache."""
    try:
        st = os.stat(path)
    except OSError as exc:
        return exc.strerror or str(exc)
    key = (path, st.st_ino, st.st_mtime_ns, st.st_size)
    if key not in _LAUNCH_CACHE:
        try:
            proc = subprocess.run([path, "-version"], capture_output=True, timeout=60)
            _LAUNCH_CACHE[key] = "" if proc.returncode == 0 else f"il s'arrête avec le code {proc.returncode}"
        except subprocess.TimeoutExpired:
            _LAUNCH_CACHE[key] = "il ne répond pas"
        except OSError as exc:
            _LAUNCH_CACHE[key] = exc.strerror or str(exc)
    return _LAUNCH_CACHE[key]


def _locate(name: str) -> tuple[str | None, str]:
    """(premier programme trouvé qui se lance, sinon le premier trouvé qui ne se lance pas et pourquoi)."""
    exe = name + (".exe" if os.name == "nt" else "")
    broken = ""
    for d in search_dirs():
        candidate = d / exe
        if not _usable(candidate):
            continue
        problem = launch_problem(str(candidate))
        if not problem:
            return str(candidate), ""
        broken = broken or f"{candidate} ({problem})"
    return None, broken


def find_binary(name: str) -> str | None:
    return _locate(name)[0]


def _fix_hint() -> str:
    if sys.platform == "darwin":
        return (
            "Clique sur « Réparer ffmpeg » en haut de la page de KrokCut, ou relance la commande "
            "d'installation de KrokCut dans le Terminal : elle réinstalle ffmpeg dans ~/KrokCut/bin."
        )
    if os.name == "nt":
        return (
            "Relance installer.bat (il installe ffmpeg avec winget). Si ça ne suffit pas, installe la version "
            "complète (avec ffprobe) depuis https://ffmpeg.org/download.html et définis KROKCUT_FFMPEG_DIR "
            "vers son dossier bin."
        )
    return "Installe ffmpeg (sudo apt install ffmpeg) ou définis KROKCUT_FFMPEG_DIR."


def missing_message(name: str, broken: str = "") -> str:
    if broken:
        return f"'{name}{BROKEN_MARK} : {broken}. KrokCut ne peut pas lire les vidéos sans lui. {_fix_hint()}"
    return f"'{name}{MISSING_MARK} : KrokCut ne peut pas lire les vidéos sans lui. {_fix_hint()}"


def is_missing_error(text: str) -> bool:
    """Erreur enregistrée parce que ffmpeg ou ffprobe manquait ou ne se lançait pas (anciens messages compris)."""
    text = text or ""
    return any(f"'{name}{mark}" in text for name in ("ffmpeg", "ffprobe") for mark in (MISSING_MARK, BROKEN_MARK))


def binary(name: str) -> str:
    """Chemin de ffmpeg/ffprobe : KROKCUT_FFMPEG_DIR, ~/KrokCut/bin, le PATH, puis Homebrew."""
    found, broken = _locate(name)
    if not found:
        raise FFmpegUnavailable(missing_message(name, broken))
    return found


def ffmpeg_status() -> dict:
    """État affiché par l'interface (bandeau « ffmpeg introuvable » + bouton Réparer)."""
    paths, errors = {}, []
    for name in ("ffmpeg", "ffprobe"):
        found, broken = _locate(name)
        paths[name] = found or ""
        if not found:
            errors.append(missing_message(name, broken))
    return {"ok": not errors, "ffmpeg": paths["ffmpeg"], "ffprobe": paths["ffprobe"], "error": errors[0] if errors else ""}


def _launch_error(program: str, exc: OSError) -> FFmpegUnavailable:
    _LAUNCH_CACHE.clear()  # il se lançait au premier essai : on revérifiera tout au prochain appel
    return FFmpegUnavailable(missing_message(Path(program).stem, f"{program} ({exc.strerror or exc})"))


def _launch(cmd: Sequence[str], **kwargs):
    """subprocess.run, avec une erreur claire si le programme existe mais ne se lance pas."""
    try:
        return subprocess.run(cmd, **kwargs)
    except OSError as exc:  # mauvais processeur, fichier abîmé, droits…
        raise _launch_error(cmd[0], exc) from exc


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
        raise _launch_error(cmd[0], exc) from exc
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
    except FFmpegUnavailable:
        raise
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


# ------------------------------------------------------------- images brutes (numpy)
STDERR_TAIL_LINES = 40
_PROGRESS_KEY = re.compile(r"^[a-z_0-9]+=")  # lignes de -progress, à ne pas confondre avec les erreurs


def _passthrough_args() -> list[str]:
    """Une image en entrée = une image en sortie (ni duplication ni suppression)."""
    return ["-fps_mode", "passthrough"] if ffmpeg_major_version() >= 6 else ["-vsync", "0"]


def stream_raw_frames(
    args: Sequence[str],
    frame_shape: tuple[int, int, int],
    *,
    block: int = 300,
    duration: float | None = None,
    on_progress: ProgressCallback | None = None,
) -> Iterator[np.ndarray]:
    """Lance ffmpeg (sortie rawvideo sur `pipe:1`) et produit des blocs uint8 (n, h, w, 3).

    ffmpeg est tué dès que le consommateur s'arrête (exception, annulation, `close()`) : à utiliser
    avec `contextlib.closing` pour que l'arrêt soit immédiat. Code de sortie non nul → FFmpegError
    avec la fin de la sortie d'erreur.
    """
    h, w, c = frame_shape
    frame_bytes = h * w * c
    cmd = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    if on_progress and duration:
        cmd += ["-progress", "pipe:2", "-nostats"]
    cmd += [str(a) for a in args]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise _launch_error(cmd[0], exc) from exc
    tail: collections.deque[str] = collections.deque(maxlen=STDERR_TAIL_LINES)
    out_time = [0.0]

    def drain() -> None:  # lit la sortie d'erreur à part : un tube plein bloquerait ffmpeg
        assert proc.stderr is not None
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                value = line.split("=", 1)[1]
                if value.isdigit():
                    out_time[0] = int(value) / 1_000_000
            elif line and not _PROGRESS_KEY.match(line):
                tail.append(line)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    assert proc.stdout is not None
    try:
        while True:
            buf = np.empty(block * frame_bytes, dtype=np.uint8)
            view = memoryview(buf)
            got = 0
            while got < len(buf):
                n = proc.stdout.readinto(view[got:])
                if not n:
                    break
                got += n
            frames = got // frame_bytes
            if frames:
                yield buf[: frames * frame_bytes].reshape(frames, h, w, c)
            if on_progress and duration:
                on_progress(min(1.0, out_time[0] / duration))
            if got < len(buf):
                break
    except BaseException:  # annulation, erreur du consommateur, close() : on ne laisse pas ffmpeg tourner
        proc.kill()
        proc.wait()
        reader.join(timeout=5)
        raise
    code = proc.wait()
    reader.join(timeout=5)
    if code != 0:
        raise FFmpegError(_format_error(cmd, "\n".join(tail)))


def encode_rgb_jpeg(rgb: np.ndarray, dst: str | Path, q: int = 3) -> None:
    """Écrit une image RGB (h, w, 3) uint8 en JPEG (sans Pillow : ffmpeg lit les pixels sur son entrée)."""
    dst = Path(dst)
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w = rgb.shape[:2]
    tmp = dst.with_name(dst.stem + ".part" + dst.suffix)
    cmd = [
        binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-i", "pipe:0",
        "-frames:v", "1", "-q:v", str(q), str(tmp),
    ]
    proc = _launch(cmd, input=rgb.tobytes(), capture_output=True)
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise FFmpegError(_format_error(cmd, proc.stderr.decode("utf-8", "replace")))
    tmp.replace(dst)


def decode_jpegs(paths: Sequence[str | Path], w: int, h: int) -> np.ndarray:
    """Décode des JPEG (tous au même format) en un tableau uint8 (n, h, w, 3), redimensionnés à w×h."""
    if not paths:
        return np.zeros((0, h, w, 3), dtype=np.uint8)
    fd, name = tempfile.mkstemp(prefix="krokcut_images_", suffix=".txt")
    os.close(fd)
    listing = Path(name)
    try:
        concat_listing(paths, listing)
        cmd = [
            binary("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-vf", f"scale={w}:{h}:flags=area,format=rgb24", *_passthrough_args(),
            "-f", "rawvideo", "pipe:1",
        ]
        proc = _launch(cmd, capture_output=True)
    finally:
        listing.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise FFmpegError(_format_error(cmd, proc.stderr.decode("utf-8", "replace")))
    data = np.frombuffer(proc.stdout, dtype=np.uint8)
    if len(data) != len(paths) * h * w * 3:
        raise FFmpegError(f"ffmpeg a rendu {len(data) // (h * w * 3)} images au lieu de {len(paths)}.")
    return data.reshape(len(paths), h, w, 3)


def extract_padded(src: str | Path, t: float, dst: str | Path, w: int = 640, h: int = 360) -> bool:
    """Une image à l'instant t, au même cadrage que les images candidates (réduite, bandes noires)."""
    try:
        run_ffmpeg(
            [
                "-ss", f"{max(0.0, t):.3f}", "-i", str(src), "-frames:v", "1", "-an",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-q:v", "4", str(dst),
            ]
        )
    except FFmpegUnavailable:
        raise
    except FFmpegError:
        return False
    return Path(dst).exists()
