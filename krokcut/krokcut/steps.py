"""Moteur commun aux traitements par étapes (épisodes et vidéos de référence), avec reprise."""

from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

StepState = Literal["pending", "running", "done", "error", "skipped"]


class StepStatus(BaseModel):
    status: StepState = "pending"
    progress: float = 0.0
    message: str = ""
    started: float | None = None
    finished: float | None = None


class Cancelled(Exception):
    pass


class StepTarget(Protocol):
    """Ce qu'un traitement doit savoir faire : Project et ReferenceDoc le respectent."""

    state: object

    def save(self) -> None: ...
    def set_step(self, step: str, **changes) -> None: ...
    def invalidate_from(self, step: str) -> None: ...
    def log(self, message: str) -> None: ...


class StepDoc:
    """Un dossier sur disque avec un état JSON (étapes, erreurs) et un journal."""

    STATE_FILE = "state.json"
    INTERRUPTED_MSG = "Interrompu (KrokCut a été fermé)"
    state_model: type[BaseModel]
    step_ids: list[str] = []

    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.RLock()
        self.state = self.state_model.model_validate_json((root / self.STATE_FILE).read_text("utf-8"))
        for step in self.step_ids:
            self.state.steps.setdefault(step, StepStatus())

    @property
    def data_dir(self) -> Path:
        return self.root

    # -------------------------------------------------------------- JSON
    def read_json(self, name: str, default=None):
        path = self.data_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text("utf-8"))

    def write_json(self, name: str, data) -> Path:
        path = self.data_dir / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(path)
        return path

    # -------------------------------------------------------------- état
    def save(self) -> None:
        with self._lock:
            tmp = self.root / (self.STATE_FILE + ".tmp")
            tmp.write_text(self.state.model_dump_json(indent=2), "utf-8")
            tmp.replace(self.root / self.STATE_FILE)

    def reload(self) -> None:
        with self._lock:
            self.state = self.state_model.model_validate_json((self.root / self.STATE_FILE).read_text("utf-8"))

    def set_step(self, step: str, **changes) -> None:
        with self._lock:
            status = self.state.steps[step]
            for key, value in changes.items():
                setattr(status, key, value)
            if changes.get("status") == "running":
                status.started = time.time()
                status.finished = None
            if changes.get("status") in ("done", "error", "skipped"):
                status.finished = time.time()
            self.save()

    def invalidate_from(self, step: str) -> None:
        """Remet à zéro une étape et toutes celles qui en dépendent."""
        start = self.step_ids.index(step)
        with self._lock:
            for s in self.step_ids[start:]:
                self.state.steps[s] = StepStatus()
            self.save()

    def invalidate(self, steps: list[str]) -> None:
        """Remet à zéro seulement certaines étapes (les autres restent faites)."""
        with self._lock:
            for s in steps:
                self.state.steps[s] = StepStatus()
            self.save()

    def recover_interrupted(self) -> bool:
        """Étapes restées « en cours » parce que KrokCut a été fermé : on les remet en attente."""
        changed = False
        with self._lock:
            for status in self.state.steps.values():
                if status.status == "running":
                    status.status = "pending"
                    status.progress = 0.0
                    status.message = self.INTERRUPTED_MSG
                    changed = True
            if changed:
                self.save()
        return changed

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self._lock, open(self.root / "log.txt", "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")

    def log_tail(self, lines: int = 80) -> list[str]:
        path = self.root / "log.txt"
        if not path.exists():
            return []
        return path.read_text("utf-8", errors="replace").splitlines()[-lines:]


class StepRunner:
    """Exécute `step_<id>()` pour chaque étape non terminée, dans l'ordre."""

    step_ids: list[str] = []

    def __init__(self, target: StepTarget, cancel_event: threading.Event | None = None):
        self.target = target
        self.cancel = cancel_event or threading.Event()
        self._last_save = 0.0

    def progress(self, step: str, fraction: float, message: str = "") -> None:
        if self.cancel.is_set():
            raise Cancelled()
        now = time.time()
        if now - self._last_save > 0.7 or fraction >= 1.0:
            self._last_save = now
            self.target.set_step(step, progress=round(min(1.0, fraction), 4), message=message)

    def run(self, from_step: str | None = None, until: str | None = None) -> bool:
        t = self.target
        if from_step:
            t.invalidate_from(from_step)
        last = self.step_ids.index(until) if until else len(self.step_ids) - 1
        t.state.last_error = ""
        t.save()
        for i, step in enumerate(self.step_ids):
            if i > last:
                break
            if t.state.steps[step].status == "done":
                continue
            t.set_step(step, status="running", progress=0.0, message="")
            t.log(f"▶ {step}")
            try:
                message = getattr(self, f"step_{step}")() or ""
                if self.cancel.is_set():  # annulé pendant une étape sans point d'arrêt (appel à Claude…)
                    raise Cancelled()
            except Cancelled:
                t.set_step(step, status="pending", message="Annulé")
                t.log("■ annulé")
                return False
            except Exception as exc:  # on remonte l'erreur dans l'interface
                t.log(traceback.format_exc())
                t.state.last_error = f"{step} : {exc}"
                t.set_step(step, status="error", message=str(exc)[:500])
                return False
            t.set_step(step, status="done", progress=1.0, message=message)
            t.log(f"✔ {step} {message}")
        return True
