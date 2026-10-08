"""Réparation de ffmpeg sur Mac depuis l'interface (bouton « Réparer ffmpeg »).

Même source que l'installeur (install-mac.sh) : des versions autonomes de ffmpeg et ffprobe,
rangées dans ~/KrokCut/bin. Les nouveaux fichiers ne remplacent les anciens qu'une fois les deux
téléchargés et vérifiés : une coupure en plein téléchargement ne laisse jamais ffmpeg à moitié installé.
"""

from __future__ import annotations

import http.client
import os
import platform
import shutil
import ssl
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .ffmpeg_utils import APP_DIR, FFmpegError

PROGRAMS = ("ffmpeg", "ffprobe")
MARTIN_RIEDL = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{prog}.zip"
EVERMEET = {  # builds Intel uniquement : secours pour les Mac Intel
    "ffmpeg": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "ffprobe": "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
}


def repair_supported() -> bool:
    return sys.platform == "darwin"


def sources(prog: str, machine: str | None = None) -> list[str]:
    machine = machine or platform.machine()
    intel = machine in ("x86_64", "amd64", "i386")
    # evermeet (Intel) en dernier recours, même sur Apple Silicon : il y tourne avec Rosetta, et la
    # vérification qui suit le refuse si Rosetta n'est pas installé.
    return [MARTIN_RIEDL.format(arch="amd64" if intel else "arm64", prog=prog), EVERMEET[prog]]


TMP_NAME = ".ffmpeg-telechargement"


def clean_repair_leftovers(bin_dir: Path | None = None) -> None:
    """Dossiers temporaires laissés par une réparation interrompue (KrokCut fermé en plein téléchargement)."""
    bin_dir = bin_dir or APP_DIR / "bin"
    if bin_dir.is_dir():
        for leftover in bin_dir.glob(".ffmpeg-*"):
            shutil.rmtree(leftover, ignore_errors=True)


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # installé avec les dépendances (le Python de KrokCut n'a pas les certificats du Mac)

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _download(url: str, dest: Path, on_progress: Callable[[float], None] | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "KrokCut"})
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if on_progress and total:
                on_progress(min(1.0, done / total))


def _extract(archive: Path, prog: str, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        member = next(
            (m for m in zf.infolist() if not m.is_dir() and Path(m.filename).name == prog and "__MACOSX" not in m.filename),
            None,
        )
        if member is None:
            raise FFmpegError(f"{prog} absent de l'archive téléchargée.")
        with zf.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
    dest.chmod(0o755)


def works(folder: Path) -> bool:
    """Même vérification que l'installeur : ffmpeg sait encoder en H.264 et ffprobe se lance."""
    try:
        enc = subprocess.run([str(folder / "ffmpeg"), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=60)
        probe = subprocess.run([str(folder / "ffprobe"), "-version"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return enc.returncode == 0 and "libx264" in enc.stdout and probe.returncode == 0


def install(
    bin_dir: Path | None = None,
    *,
    log: Callable[[str], None] = lambda _msg: None,
    on_progress: Callable[[float], None] | None = None,
    machine: str | None = None,
    urls: dict[str, list[str]] | None = None,
) -> Path:
    """Télécharge ffmpeg et ffprobe dans `bin_dir` (~/KrokCut/bin par défaut)."""
    bin_dir = bin_dir or APP_DIR / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    clean_repair_leftovers(bin_dir)
    tmp = bin_dir / TMP_NAME  # dans bin/ : même disque, le remplacement final est instantané
    tmp.mkdir()
    try:
        for i, prog in enumerate(PROGRAMS):
            errors = []
            for url in (urls or {}).get(prog) or sources(prog, machine):
                log(f"Téléchargement de {prog}…")
                try:
                    _download(url, tmp / f"{prog}.zip", on_progress and (lambda f, i=i: on_progress((i + f) / len(PROGRAMS))))
                    _extract(tmp / f"{prog}.zip", prog, tmp / prog)
                    break
                except (OSError, http.client.HTTPException, zipfile.BadZipFile, EOFError, FFmpegError) as exc:
                    errors.append(f"{url} : {exc!r}" if not str(exc) else f"{url} : {exc}")
            else:
                raise FFmpegError(f"Téléchargement de {prog} impossible (connexion internet ?). " + " ; ".join(errors))
        if not works(tmp):
            raise FFmpegError("Le ffmpeg téléchargé ne fonctionne pas sur ce Mac.")
        for prog in PROGRAMS:
            os.replace(tmp / prog, bin_dir / prog)  # remplace aussi un lien cassé vers un ancien ffmpeg
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log("ffmpeg réparé.")
    return bin_dir


class Repair:
    """Réparation lancée depuis l'interface, en arrière-plan (une seule à la fois)."""

    def __init__(self, on_done: Callable[[], None] | None = None):
        self.lock = threading.Lock()
        self.running = False
        self.progress = 0.0
        self.error = ""
        self.on_done = on_done

    def state(self) -> dict:
        return {"supported": repair_supported(), "running": self.running, "progress": round(self.progress, 2), "error": self.error}

    def start(self, target: Callable[..., Path] = install) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.progress, self.error = True, 0.0, ""
        threading.Thread(target=self._run, args=(target,), daemon=True).start()
        return True

    def _run(self, target: Callable[..., Path]) -> None:
        try:
            target(on_progress=lambda f: setattr(self, "progress", f))
            if self.on_done:
                self.on_done()
        except Exception as exc:  # affiché tel quel dans le bandeau
            self.error = str(exc)
        finally:
            self.running = False
