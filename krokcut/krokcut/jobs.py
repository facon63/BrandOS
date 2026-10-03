"""File d'attente : un seul traitement lourd à la fois (le PC en a déjà assez à faire)."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from .config import AppConfig
from .pipeline import Pipeline
from .project import Project


@dataclass
class Job:
    project_id: str
    from_step: str | None = None
    until: str | None = None


class JobManager:
    def __init__(self):
        self._queue: "queue.Queue[Job]" = queue.Queue()
        self._lock = threading.Lock()
        self.current: Job | None = None
        self.pending: list[Job] = []
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="krokcut-jobs")
        self._thread.start()

    def submit(self, project_id: str, from_step: str | None = None, until: str | None = None) -> None:
        with self._lock:
            if any(j.project_id == project_id for j in self.pending) or (
                self.current and self.current.project_id == project_id
            ):
                raise RuntimeError("Ce projet est déjà en cours de traitement.")
            job = Job(project_id, from_step, until)
            self.pending.append(job)
        self._queue.put(job)

    def cancel(self, project_id: str) -> None:
        with self._lock:
            self.pending = [j for j in self.pending if j.project_id != project_id]
            if self.current and self.current.project_id == project_id:
                self._cancel.set()

    def busy(self, project_id: str) -> str | None:
        with self._lock:
            if self.current and self.current.project_id == project_id:
                return "running"
            if any(j.project_id == project_id for j in self.pending):
                return "queued"
        return None

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            with self._lock:
                if job not in self.pending:  # annulé avant de démarrer
                    continue
                self.pending.remove(job)
                self.current = job
                self._cancel.clear()
            try:
                project = Project.open(job.project_id)
                Pipeline(project, AppConfig.load(), cancel_event=self._cancel).run(job.from_step, job.until)
            except Exception as exc:  # le pipeline gère ses erreurs ; ici seulement l'imprévu
                try:
                    project = Project.open(job.project_id)
                    project.state.last_error = str(exc)
                    project.save()
                except Exception:
                    pass
            finally:
                with self._lock:
                    self.current = None
