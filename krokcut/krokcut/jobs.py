"""File d'attente : un seul traitement lourd à la fois (le PC en a déjà assez à faire)."""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Literal

from .config import AppConfig
from .pipeline import Pipeline
from .project import Project
from .references import ReferenceAnalyzer, ReferenceStore, build_guide

JobKind = Literal["project", "reference", "guide"]
GUIDE_TARGET = "guide"


@dataclass
class Job:
    target: str
    from_step: str | None = None
    until: str | None = None
    kind: JobKind = "project"


class JobManager:
    def __init__(self, start: bool = True):
        self._queue: "queue.Queue[Job]" = queue.Queue()
        self._lock = threading.Lock()
        self.current: Job | None = None
        self.pending: list[Job] = []
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="krokcut-jobs")
        if start:
            self._thread.start()

    def submit(self, target: str, from_step: str | None = None, until: str | None = None, kind: JobKind = "project") -> None:
        with self._lock:
            if self._busy_locked(target, kind):
                raise RuntimeError("Déjà en cours de traitement.")
            job = Job(target, from_step, until, kind)
            self.pending.append(job)
        self._queue.put(job)

    def submit_guide(self) -> bool:
        """Reconstruit le guide de style, sauf s'il est déjà prévu (évite de le refaire 5 fois de suite)."""
        with self._lock:
            if any(j.kind == "guide" for j in self.pending):
                return False
            job = Job(GUIDE_TARGET, kind="guide")
            self.pending.append(job)
        self._queue.put(job)
        return True

    def cancel(self, target: str, kind: JobKind = "project") -> None:
        with self._lock:
            self.pending = [j for j in self.pending if not (j.target == target and j.kind == kind)]
            if self.current and self.current.target == target and self.current.kind == kind:
                self._cancel.set()

    def _busy_locked(self, target: str, kind: JobKind) -> str | None:
        if self.current and self.current.target == target and self.current.kind == kind:
            return "running"
        if any(j.target == target and j.kind == kind for j in self.pending):
            return "queued"
        return None

    def busy(self, target: str, kind: JobKind = "project") -> str | None:
        with self._lock:
            return self._busy_locked(target, kind)

    def any_busy(self, kind: JobKind) -> bool:
        with self._lock:
            return bool((self.current and self.current.kind == kind) or any(j.kind == kind for j in self.pending))

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            with self._lock:
                if job not in self.pending:  # annulé avant de démarrer
                    continue
                self.pending.remove(job)
                self.current = job
                self._cancel.clear()
            awake = _keep_awake()
            try:
                self._run(job)
            except Exception as exc:  # les traitements gèrent leurs erreurs ; ici seulement l'imprévu
                _record_error(job, exc)
            finally:
                if awake:
                    awake.terminate()
                with self._lock:
                    self.current = None

    def _run(self, job: Job) -> None:
        cfg = AppConfig.load()
        if job.kind == "project":
            Pipeline(Project.open(job.target), cfg, cancel_event=self._cancel).run(job.from_step, job.until)
        elif job.kind == "reference":
            store = ReferenceStore()
            ok = ReferenceAnalyzer(store.open(job.target), cfg, store, cancel_event=self._cancel).run(job.from_step)
            if ok:
                self.submit_guide()
        elif job.kind == "guide":
            store = ReferenceStore()
            build_guide(store, cfg)


def _record_error(job: Job, exc: Exception) -> None:
    try:
        if job.kind == "project":
            doc = Project.open(job.target)
        elif job.kind == "reference":
            doc = ReferenceStore().open(job.target)
        else:
            (ReferenceStore().root / "guide_erreur.txt").write_text(str(exc), "utf-8")
            return
        doc.state.last_error = str(exc)
        doc.save()
    except Exception:
        pass


def _keep_awake() -> subprocess.Popen | None:
    """Sur Mac, empêche la mise en veille pendant un dérush de plusieurs heures."""
    if not shutil.which("caffeinate"):
        return None
    try:
        # -w : s'arrête tout seul si KrokCut est fermé en plein traitement
        return subprocess.Popen(
            ["caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError:
        return None
