"""Un projet = un épisode : deux POV, un dossier de travail et l'état du pipeline."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import StyleProfile, workspace_dir
from .steps import StepDoc, StepState, StepStatus

__all__ = ["STEPS", "STEP_IDS", "Project", "ProjectState", "Source", "StepState", "StepStatus", "slugify"]

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


class Project(StepDoc):
    STATE_FILE = "project.json"
    INTERRUPTED_MSG = "Interrompu (KrokCut a été fermé) : clique sur Continuer"
    state_model = ProjectState
    step_ids = STEP_IDS
    state: ProjectState

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
    def data_dir(self) -> Path:
        return self.work

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
