"""File d'attente : un seul traitement lourd à la fois (le PC en a déjà assez à faire)."""

from __future__ import annotations

import itertools
import os
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
# Les vidéos de référence et le guide passent avant les épisodes en attente :
# un épisode lancé juste après avoir déposé des vidéos profite ainsi du guide à jour.
PRIORITY = {"reference": 0, "guide": 1, "project": 2}
_counter = itertools.count()


@dataclass
class Job:
    target: str
    from_step: str | None = None
    until: str | None = None
    kind: JobKind = "project"
    seq: int = 0


class JobManager:
    def __init__(self, start: bool = True):
        self._lock = threading.Lock()
        self._wakeup = threading.Condition(self._lock)
        self.current: Job | None = None
        self.pending: list[Job] = []
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="krokcut-jobs")
        if start:
            self._thread.start()

    def _push_locked(self, job: Job) -> None:
        job.seq = next(_counter)
        self.pending.append(job)
        self._wakeup.notify()

    def submit(self, target: str, from_step: str | None = None, until: str | None = None, kind: JobKind = "project") -> None:
        with self._lock:
            if self._busy_locked(target, kind):
                raise RuntimeError("Déjà en cours de traitement.")
            self._push_locked(Job(target, from_step, until, kind))

    def submit_guide(self) -> bool:
        """Reconstruit le guide de style, sauf s'il est déjà prévu (évite de le refaire 5 fois de suite)."""
        with self._lock:
            if any(j.kind == "guide" for j in self.pending):
                return False
            self._push_locked(Job(GUIDE_TARGET, kind="guide"))
        return True

    def next_job_locked(self) -> Job | None:
        if not self.pending:
            return None
        job = min(self.pending, key=lambda j: (PRIORITY[j.kind], j.seq))
        self.pending.remove(job)
        return job

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

    def waiting_for(self, target: str, kind: JobKind = "project") -> list[Job]:
        """Traitements qui passeront avant celui-ci (celui en cours compris), s'il est en file d'attente."""
        with self._lock:
            mine = next((j for j in self.pending if j.target == target and j.kind == kind), None)
            if mine is None:
                return []
            key = lambda j: (PRIORITY[j.kind], j.seq)  # noqa: E731
            ahead = sorted((j for j in self.pending if key(j) < key(mine)), key=key)
            return ([self.current] if self.current else []) + ahead

    def any_busy(self, kind: JobKind) -> bool:
        with self._lock:
            return bool((self.current and self.current.kind == kind) or any(j.kind == kind for j in self.pending))

    def _loop(self) -> None:
        while True:
            with self._lock:
                while not self.pending:
                    self._wakeup.wait()
                job = self.next_job_locked()
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
            if ok and not self._cancel.is_set():
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
