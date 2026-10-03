"""Interface web locale (http://localhost:8765) : déposer les rush, suivre, valider, télécharger."""

from __future__ import annotations

import os
import string
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .audio import Levels
from .config import AppConfig, StyleProfile, channel_bible, workspace_dir
from .cutting import moment_pieces, pieces_duration
from .derush import sequence_duration
from .ffmpeg_utils import extract_frame
from .jobs import JobManager
from .library import Library
from .llm import claude_available
from .project import STEPS, Project

WEB = Path(__file__).parent / "web"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".ts", ".flv"}

app = FastAPI(title="KrokCut", version=__version__)
jobs = JobManager()
app.mount("/static", StaticFiles(directory=WEB), name="static")


def _project(project_id: str) -> Project:
    try:
        return Project.open(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


def _summary(p: Project) -> dict:
    state = p.state
    return {
        "id": state.id,
        "name": state.name,
        "created": state.created,
        "sources": {k: {"name": s.name, "files": s.files, "duration": s.duration} for k, s in state.sources.items()},
        "steps": [{"id": sid, "label": label, **state.steps[sid].model_dump()} for sid, label in STEPS],
        "busy": jobs.busy(state.id),
        "last_error": state.last_error,
        "render_quality": state.render_quality,
        "use_claude": state.use_claude,
        "manual_offset": state.manual_offset,
        "outputs": sorted(f.name for f in p.out.iterdir() if f.is_file() and ".part" not in f.name) if p.out.exists() else [],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB / "index.html").read_text("utf-8")


# ------------------------------------------------------------------- réglages
class ConfigUpdate(BaseModel):
    anthropic_api_key: str | None = None
    library_dir: str | None = None
    whisper_model: str | None = None
    whisper_device: str | None = None
    video_codec: str | None = None
    font_file: str | None = None


@app.get("/api/config")
def get_config():
    cfg = AppConfig.load()
    key = cfg.api_key()
    return {
        "version": __version__,
        "claude": claude_available(cfg),
        "api_key_hint": (key[:7] + "…" + key[-4:]) if len(key) > 12 else "",
        "model": cfg.model,
        "library_dir": cfg.library_dir,
        "whisper_model": cfg.whisper.model,
        "whisper_device": cfg.whisper.device,
        "video_codec": cfg.render.video_codec,
        "font_file": cfg.render.font_file,
        "workspace": str(workspace_dir()),
    }


@app.post("/api/config")
def set_config(update: ConfigUpdate):
    cfg = AppConfig.load()
    if update.anthropic_api_key is not None:
        cfg.anthropic_api_key = update.anthropic_api_key.strip()
    if update.library_dir is not None:
        cfg.library_dir = update.library_dir.strip()
    if update.whisper_model:
        cfg.whisper.model = update.whisper_model
    if update.whisper_device:
        cfg.whisper.device = update.whisper_device  # type: ignore[assignment]
    if update.video_codec:
        cfg.render.video_codec = update.video_codec
    if update.font_file is not None:
        cfg.render.font_file = update.font_file.strip()
    cfg.save()
    return get_config()


@app.get("/api/style")
def get_default_style():
    return StyleProfile.load().model_dump()


@app.post("/api/style")
def set_default_style(data: dict):
    style = StyleProfile.model_validate({**StyleProfile.load().model_dump(), **data})
    style.save(StyleProfile.default_path())
    return style.model_dump()


@app.get("/api/chaine")
def get_bible():
    return {"text": channel_bible()}


@app.post("/api/chaine")
def set_bible(data: dict):
    (workspace_dir() / "chaine.md").write_text(data.get("text", ""), "utf-8")
    return {"ok": True}


# ------------------------------------------------------------- fichiers locaux
@app.get("/api/browse")
def browse(path: str = ""):
    """Petit explorateur pour choisir des rush déjà sur le disque (sans les copier)."""
    if not path:
        if os.name == "nt":
            roots = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
            return {"path": "", "parent": None, "dirs": roots, "files": []}
        path = str(Path.home())
    p = Path(path).expanduser()
    if not p.is_dir():
        raise HTTPException(400, "Dossier introuvable")
    dirs, files = [], []
    try:
        for child in sorted(p.iterdir(), key=lambda c: c.name.lower()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                dirs.append(child.name)
            elif child.suffix.lower() in VIDEO_EXT:
                files.append({"name": child.name, "size": child.stat().st_size})
    except PermissionError:
        pass
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "dirs": dirs, "files": files}


@app.put("/api/upload/{filename}")
async def upload(filename: str, request: Request):
    """Reçoit un fichier en flux continu (pas de double copie sur le disque)."""
    safe = Path(filename).name
    if not safe:
        raise HTTPException(400, "Nom de fichier invalide")
    dest_dir = workspace_dir() / "rush"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / safe
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as fh:
        async for chunk in request.stream():
            fh.write(chunk)
    tmp.replace(dest)
    return {"path": str(dest)}


# ------------------------------------------------------------------ projets
class NewProject(BaseModel):
    name: str
    pov_a: list[str]
    pov_b: list[str]
    name_a: str = "Krok"
    name_b: str = "Mil"
    target_min: float | None = None
    target_max: float | None = None
    start: bool = True
    pause_after_story: bool = False


@app.get("/api/projects")
def list_projects():
    return [_summary(p) for p in reversed(Project.list())]


@app.post("/api/projects")
def create_project(data: NewProject):
    if not data.pov_a or not data.pov_b:
        raise HTTPException(400, "Il faut les deux POV.")
    for f in data.pov_a + data.pov_b:
        if not Path(f).exists():
            raise HTTPException(400, f"Fichier introuvable : {f}")
    style = StyleProfile.load()
    if data.target_min:
        style.target_min_minutes = data.target_min
    if data.target_max:
        style.target_max_minutes = data.target_max
    p = Project.create(data.name, data.pov_a, data.pov_b, data.name_a, data.name_b, style)
    if data.start:
        jobs.submit(p.id, until="story" if data.pause_after_story else None)
    return _summary(p)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    p = _project(project_id)
    return {**_summary(p), "log": p.log_tail(60)}


class RunRequest(BaseModel):
    from_step: str | None = None
    until: str | None = None
    quality: str | None = None
    manual_offset: float | None = None
    clear_offset: bool = False
    use_claude: bool | None = None


@app.post("/api/projects/{project_id}/run")
def run_project(project_id: str, req: RunRequest):
    p = _project(project_id)
    if jobs.busy(project_id):
        raise HTTPException(409, "Ce projet est déjà en cours de traitement.")
    if req.quality in ("preview", "final"):
        p.state.render_quality = req.quality  # type: ignore[assignment]
    if req.manual_offset is not None:
        p.state.manual_offset = req.manual_offset
    if req.clear_offset:
        p.state.manual_offset = None
    if req.use_claude is not None:
        p.state.use_claude = req.use_claude
    p.save()
    try:
        jobs.submit(project_id, req.from_step, req.until)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _summary(p)


@app.post("/api/projects/{project_id}/cancel")
def cancel_project(project_id: str):
    jobs.cancel(project_id)
    return {"ok": True}


@app.get("/api/projects/{project_id}/style")
def get_project_style(project_id: str):
    return _project(project_id).style().model_dump()


@app.post("/api/projects/{project_id}/style")
def set_project_style(project_id: str, data: dict):
    p = _project(project_id)
    style = StyleProfile.model_validate({**p.style().model_dump(), **data})
    p.save_style(style)
    return style.model_dump()


@app.get("/api/projects/{project_id}/review")
def review(project_id: str):
    p = _project(project_id)
    return {
        "moments": (p.read_json("moments.json") or {}).get("moments", []),
        "story": p.read_json("histoire.json"),
        "names": {k: s.name for k, s in p.state.sources.items()},
        "style": p.style().model_dump(),
    }


@app.get("/api/projects/{project_id}/lines")
def get_lines(project_id: str, start: int, end: int):
    p = _project(project_id)
    lines = (p.read_json("transcription.json") or {}).get("lines", [])
    return [{k: v for k, v in l.items() if k != "words"} for l in lines if start <= l["id"] <= end]


class StoryUpdate(BaseModel):
    sequence: list[dict]
    cold_open: dict | None = None


@app.post("/api/projects/{project_id}/story")
def update_story(project_id: str, data: StoryUpdate):
    """Enregistre la sélection retouchée à la main puis relance montage + rendu."""
    p = _project(project_id)
    if jobs.busy(project_id):
        raise HTTPException(409, "Le projet est en cours de traitement.")
    moments = {m["id"]: m for m in (p.read_json("moments.json") or {}).get("moments", [])}
    story = p.read_json("histoire.json") or {}
    lines = p.read_json("transcription.json")["lines"]
    levels, style = Levels.load(p.work / "niveaux.npz"), p.style()
    sequence = []
    for item in data.sequence:
        m = moments.get(item.get("moment"))
        if not m:
            continue
        s = int(item.get("start_line", m["start_line"]))
        e = int(item.get("end_line", m["end_line"]))
        sequence.append(
            {
                "moment": m["id"],
                "title": item.get("title") or m["title"],
                "start_line": s,
                "end_line": e,
                "chapter": item.get("chapter", ""),
                "transition": item.get("transition", "cut"),
                "est_duration": round(pieces_duration(moment_pieces(lines, s, e, levels, style)), 1),
            }
        )
    story["sequence"] = sequence
    if data.cold_open is not None:
        co = data.cold_open
        story["cold_open"] = (
            {**co, "est_duration": round(pieces_duration(moment_pieces(lines, co["start_line"], co["end_line"], levels, style)), 1)}
            if co.get("moment")
            else None
        )
    story["edited"] = True
    story["total_estimate"] = round(sequence_duration(story), 1)
    p.write_json("histoire.json", story)
    p.invalidate_from("edit")
    jobs.submit(project_id)
    return {"ok": True, "total_estimate": story["total_estimate"]}


@app.get("/api/projects/{project_id}/thumb")
def thumb(project_id: str, t: float, pov: str = "A"):
    p = _project(project_id)
    src = p.state.sources.get(pov)
    if not src or not src.path:
        raise HTTPException(404)
    cache = p.work / "vignettes"
    cache.mkdir(exist_ok=True)
    out = cache / f"{pov}_{t:.1f}.jpg"
    if not out.exists() and not extract_frame(src.path, src.to_source_time(t), out, width=320):
        raise HTTPException(404)
    return FileResponse(out, media_type="image/jpeg")


@app.get("/api/projects/{project_id}/out/{filename}")
def output_file(project_id: str, filename: str):
    p = _project(project_id)
    path = p.out / Path(filename).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=path.name)


# --------------------------------------------------------------- bibliothèque
@app.get("/api/library")
def get_library():
    cfg = AppConfig.load()
    lib = Library.load(cfg.library_dir)
    return {"dir": cfg.library_dir, "assets": lib.assets, "stats": lib.stats()}


@app.post("/api/library/scan")
def scan_library(data: dict):
    cfg = AppConfig.load()
    directory = (data.get("dir") or cfg.library_dir).strip()
    if not directory:
        raise HTTPException(400, "Indique le dossier de la bibliothèque.")
    try:
        lib = Library.scan(directory)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    cfg.library_dir = directory
    cfg.save()
    return {"dir": directory, "assets": lib.assets, "stats": lib.stats()}


@app.post("/api/library/update")
def update_asset(data: dict):
    lib = Library.load(AppConfig.load().library_dir)
    if not lib.get(data.get("id", "")):
        raise HTTPException(404, "Élément introuvable")
    return lib.update(data["id"], data.get("changes", {}))


@app.get("/api/library/file")
def library_file(id: str):
    lib = Library.load(AppConfig.load().library_dir)
    asset = lib.get(id)
    if not asset:
        raise HTTPException(404)
    return FileResponse(lib.path_of(asset))


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
