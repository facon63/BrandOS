"""Configuration de l'application et profil de style du montage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent.parent


def workspace_dir(create: bool = True) -> Path:
    """Dossier de travail (projets, config). Modifiable via KROKCUT_HOME."""
    path = Path(os.environ.get("KROKCUT_HOME", APP_DIR / "workspace")).expanduser().resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


class WhisperSettings(BaseModel):
    # large-v3-turbo : excellent en français et rapide sur carte NVIDIA.
    # Sur un PC sans GPU, "small" ou "medium" vont 3 à 6 fois plus vite.
    model: str = "large-v3-turbo"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    compute_type: str = "auto"
    language: str = "fr"
    beam_size: int = 5
    chunk_minutes: float = 15.0


class EffortSettings(BaseModel):
    derush: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    story: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    edit: Literal["low", "medium", "high", "xhigh", "max"] = "medium"


class RenderSettings(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: float = 0.0  # 0 = celle de la caméra A
    preview_height: int = 720
    video_codec: str = "libx264"  # h264_nvenc sur carte NVIDIA
    crf: int = 18
    preset: str = "medium"
    font_file: str = ""  # police des textes à l'écran (.ttf/.otf)
    loudness_lufs: float = -14.0  # cible YouTube
    workers: int = 2  # rendus de plans en parallèle


class AppConfig(BaseModel):
    anthropic_api_key: str = ""
    model: str = "claude-opus-5-5"
    use_fallbacks: bool = True
    effort: EffortSettings = Field(default_factory=EffortSettings)
    library_dir: str = ""
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    render: RenderSettings = Field(default_factory=RenderSettings)
    llm_parallel_requests: int = 4
    # Les vidéos de référence servent à apprendre le style : un modèle plus léger suffit et va bien plus vite
    references_whisper_model: str = "small"

    @classmethod
    def path(cls) -> Path:
        return workspace_dir() / "config.yaml"

    @classmethod
    def load(cls) -> "AppConfig":
        path = cls.path()
        data = {}
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg = cls.model_validate(data)
        if not path.exists():
            cfg.save()
        return cfg

    def save(self) -> None:
        self.path().write_text(
            yaml.safe_dump(self.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def api_key(self) -> str:
        return self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")


class StyleProfile(BaseModel):
    """Règles de montage. Copié dans chaque projet, donc modifiable épisode par épisode."""

    target_min_minutes: float = 10.0
    target_max_minutes: float = 15.0
    cold_open: bool = True  # teaser du meilleur moment en ouverture

    # Coupes automatiques des blancs
    max_silence: float = 0.55  # un blanc plus long que ça est coupé
    keep_pad: float = 0.12  # marge conservée avant/après la parole
    reaction_tail: float = 0.6  # on laisse respirer après une chute

    # Réalisation multicam
    layout: Literal["switch", "pip", "split"] = "switch"
    min_shot: float = 2.5  # durée minimale d'un plan avant de changer de POV
    audio_mode: Literal["follow", "mix", "A", "B"] = "follow"

    # Densité d'effets visée (par minute de vidéo finale)
    zooms_per_minute: float = 4.0
    punch_scale: float = 1.25
    sfx_per_minute: float = 6.0
    sfx_volume_db: float = -6.0
    characters_per_minute: float = 2.0
    character_scale: float = 0.38
    texts_per_minute: float = 1.5
    voice_polish: bool = True  # passe-haut + compression légère sur les voix
    denoise: bool = False  # débruitage (utile si micro qui souffle)
    music: bool = True
    music_volume_db: float = -24.0
    transition_sfx: bool = True

    # Ton de la chaîne, gags récurrents, choses à éviter… (lu par Claude)
    notes: str = ""

    @classmethod
    def default_path(cls) -> Path:
        return workspace_dir() / "style.yaml"

    @classmethod
    def load(cls, path: Path | None = None) -> "StyleProfile":
        path = path or cls.default_path()
        if path.exists():
            return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        style = cls()
        if path == cls.default_path():
            style.save(path)
        return style

    def save(self, path: Path) -> None:
        path.write_text(
            yaml.safe_dump(self.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def channel_bible() -> str:
    """Texte libre décrivant la chaîne (workspace/chaine.md), injecté dans les prompts."""
    path = workspace_dir() / "chaine.md"
    if not path.exists():
        template = APP_DIR / "exemples" / "chaine.md"
        if template.exists():
            path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    return path.read_text(encoding="utf-8") if path.exists() else ""
