"""Un projet = un épisode : deux POV, un dossier de travail et l'état du pipeline."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import StyleProfile, workspace_dir

STEPS: list[tuple[str, str]] = [
    ("probe", "Lecture des fichiers"),
    ("audio", "Extraction audio"),
    ("sync", "Synchronisation des 2 POV"),
    ("features", "Analyse du son (pics, rires, blancs)"),
    ("transcribe", "Transcription"),
    ("derush", "Dérush : repérage des moments"),
    ("story", "Construction de l'histoire"),
    ("edit", "Montage : coupes, zooms, sons, persos"),
    ("render", "Rendu vidéo"),
    ("export", "Export Premiere/DaVinci, sous-titres, chapitres"),
]
STEP_IDS = [s for s, _ in STEPS]

StepState = Literal["pending", "running", "done", "error", "skipped"]


class StepStatus(BaseModel):
    status: StepState = "pending"
    progress: float = 0.0
    message: str = ""
    started: float | None = None
    finished: float | None = None


class Source(BaseModel):
    key: Literal["A", "B"]
    name: str
    files: list[str]
    audio_track: int = 0
    path: str = ""  # fichier unique (concaténé si la caméra a découpé)
    info: dict = Field(default_factory=dict)
    offset: float = 0.0  # instant (timeline maître) où démarre ce fichier
    rate: float = 1.0  # correction de dérive d'horloge

    def to_source_time(self, t_master: float) -> float:
        return (t_master - self.offset) * self.rate

    def to_master_time(self, t_src: float) -> float:
        return t_src / self.rate + self.offset

    @property
    def duration(self) -> float:
        return float(self.info.get("duration") or 0.0)

    def covers(self, t0: float, t1: float) -> bool:
        s0, s1 = self.to_source_time(t0), self.to_source_time(t1)
        return s0 >= -0.05 and s1 <= self.duration + 0.05


class ProjectState(BaseModel):
    id: str
    name: str
    created: str
    sources: dict[str, Source]
    manual_offset: float | None = None  # décalage B/A forcé à la main (secondes)
    steps: dict[str, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in STEP_IDS})
    render_quality: Literal["preview", "final"] = "preview"
    use_claude: bool = True
    last_error: str = ""


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "projet"


class Project:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.RLock()
        self.state = ProjectState.model_validate_json((root / "project.json").read_text("utf-8"))
        for step in STEP_IDS:
            self.state.steps.setdefault(step, StepStatus())

    # ------------------------------------------------------------------ création
    @classmethod
    def projects_dir(cls) -> Path:
        path = workspace_dir() / "projects"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def create(
        cls,
        name: str,
        pov_a: list[str],
        pov_b: list[str],
        name_a: str = "Krok",
        name_b: str = "Mil",
        style: StyleProfile | None = None,
    ) -> "Project":
        base = slugify(name)
        project_id = base
        i = 2
        while (cls.projects_dir() / project_id).exists():
            project_id = f"{base}-{i}"
            i += 1
        root = cls.projects_dir() / project_id
        (root / "work").mkdir(parents=True)
        (root / "out").mkdir()
        state = ProjectState(
            id=project_id,
            name=name,
            created=datetime.now().isoformat(timespec="seconds"),
            sources={
                "A": Source(key="A", name=name_a, files=[str(Path(p)) for p in pov_a]),
                "B": Source(key="B", name=name_b, files=[str(Path(p)) for p in pov_b]),
            },
        )
        (root / "project.json").write_text(state.model_dump_json(indent=2), "utf-8")
        (style or StyleProfile.load()).save(root / "style.yaml")
        return cls(root)

    @classmethod
    def open(cls, project_id: str) -> "Project":
        root = cls.projects_dir() / project_id
        if not (root / "project.json").exists():
            raise FileNotFoundError(f"Projet introuvable : {project_id}")
        return cls(root)

    @classmethod
    def list(cls) -> list["Project"]:
        projects = []
        for path in sorted(cls.projects_dir().iterdir()):
            if (path / "project.json").exists():
                try:
                    projects.append(cls(path))
                except Exception:  # projet corrompu : on l'ignore dans la liste
                    continue
        return projects

    # ------------------------------------------------------------------ chemins
    @property
    def id(self) -> str:
        return self.state.id

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def out(self) -> Path:
        return self.root / "out"

    def style(self) -> StyleProfile:
        return StyleProfile.load(self.root / "style.yaml")

    def save_style(self, style: StyleProfile) -> None:
        style.save(self.root / "style.yaml")

    def source(self, key: str) -> Source:
        return self.state.sources[key]

    def master_duration(self) -> float:
        return max(
            (s.to_master_time(s.duration) for s in self.state.sources.values() if s.duration),
            default=0.0,
        )

    def speaker_name(self, key: str | None) -> str:
        if key in self.state.sources:
            return self.state.sources[key].name
        return "?"

    # ------------------------------------------------------------------ JSON
    def read_json(self, name: str, default=None):
        path = self.work / name
        if not path.exists():
            return default
        return json.loads(path.read_text("utf-8"))

    def write_json(self, name: str, data) -> Path:
        path = self.work / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(path)
        return path

    # ------------------------------------------------------------------ état
    def save(self) -> None:
        with self._lock:
            tmp = self.root / "project.json.tmp"
            tmp.write_text(self.state.model_dump_json(indent=2), "utf-8")
            tmp.replace(self.root / "project.json")

    def reload(self) -> None:
        with self._lock:
            self.state = ProjectState.model_validate_json(
                (self.root / "project.json").read_text("utf-8")
            )

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
        start = STEP_IDS.index(step)
        with self._lock:
            for s in STEP_IDS[start:]:
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
                    status.message = "Interrompu (KrokCut a été fermé) : clique sur Continuer"
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
