"""Interface web locale (http://localhost:8765) : déposer les rush, suivre, valider, télécharger."""

from __future__ import annotations

import hashlib
import os
import string
import tempfile
import threading
from contextlib import asynccontextmanager
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
from .ffmpeg_install import Repair, clean_repair_leftovers, repair_supported
from .ffmpeg_utils import FFmpegUnavailable, extract_frame, ffmpeg_status, is_missing_error
from .jobs import JobManager
from .library import Library
from .llm import claude_available
from .project import STEPS, Project
from .references import (
    REF_STEP_IDS,
    REF_STEPS,
    ReferenceDoc,
    ReferenceStore,
    guide_outdated,
    needs_claude,
    refresh_suggestions,
    remeasure_outdated_sfx,
    sfx_outdated,
    too_long,
)

WEB = Path(__file__).parent / "web"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".ts", ".flv"}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    for project in Project.list():  # un traitement coupé par une fermeture de l'app reprendra proprement
        project.recover_interrupted()
    store = ReferenceStore()
    for ref in store.list():
        ref.recover_interrupted()
    try:
        clean_repair_leftovers()  # réparation coupée par « Quitter » ou une mise à jour
        resume_missing_ffmpeg()  # ffmpeg réinstallé depuis : les vidéos bloquées repartent toutes seules
    except Exception:
        pass
    try:
        refresh_suggestions(store)  # guide d'une version précédente : réglages suggérés recalculés
        for doc in remeasure_outdated_sfx(store):  # bruitages mesurés par l'ancienne détection
            if not jobs.busy(doc.id, "reference"):
                jobs.submit(doc.id, kind="reference")
        if guide_outdated(store):  # mise à jour du guide interrompue : on la refait
            jobs.submit_guide()
    except Exception:  # le guide ne doit jamais empêcher KrokCut de démarrer
        pass
    yield


app = FastAPI(title="KrokCut", version=__version__, lifespan=lifespan)
jobs = JobManager()


def resume_missing_ffmpeg() -> int:
    """Relance les analyses de « Mes vidéos » arrêtées parce que ffmpeg manquait, s'il est là maintenant."""
    if not ffmpeg_status()["ok"]:
        return 0
    resumed = 0
    for doc in ReferenceStore().list():
        failed = any(st.status == "error" for st in doc.state.steps.values())
        if failed and is_missing_error(doc.state.last_error) and not jobs.busy(doc.id, "reference"):
            jobs.submit(doc.id, kind="reference")
            resumed += 1
    return resumed


ffmpeg_repair = Repair(on_done=resume_missing_ffmpeg)


def require_ffmpeg() -> None:
    """Refuse tout de suite (avant de copier des Go de vidéo) si ffmpeg manque."""
    status = ffmpeg_status()
    if not status["ok"]:
        raise HTTPException(503, status["error"])
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.middleware("http")
async def always_fresh_interface(request: Request, call_next):
    """Après une mise à jour, le navigateur ne doit jamais garder l'ancienne interface en cache."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _project(project_id: str) -> Project:
    try:
        return Project.open(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


def _queue_note(target: str, kind: str) -> str:
    """Ce qu'attend un traitement en file d'attente, en clair (« après l'analyse de 2 vidéos… »)."""
    ahead = jobs.waiting_for(target, kind)
    if not ahead:
        return ""
    refs = sum(j.kind == "reference" for j in ahead)
    parts = []
    if refs:
        other = "autre " if kind == "reference" else ""
        count = "d'une" if refs == 1 else f"de {refs}"
        parts.append(f"l'analyse {count} {other}vidéo{'s' if refs > 1 else ''} de « Mes vidéos »")
    elif any(j.kind == "guide" for j in ahead):
        parts.append("la mise à jour du guide de style")
    episodes = [j.target for j in ahead if j.kind == "project"]
    if len(episodes) == 1:
        try:
            parts.append(f"l'épisode « {Project.open(episodes[0]).state.name} »")
        except FileNotFoundError:
            parts.append("un autre épisode")
    elif episodes:
        parts.append(f"{len(episodes)} autres épisodes")
    note = "après " + " et ".join(parts)
    if kind == "project" and (refs or any(j.kind == "guide" for j in ahead)):
        note += " : le guide de style à jour servira à ce montage"
    return note


def _summary(p: Project) -> dict:
    state = p.state
    return {
        "id": state.id,
        "name": state.name,
        "created": state.created,
        "sources": {k: {"name": s.name, "files": s.files, "duration": s.duration} for k, s in state.sources.items()},
        "steps": [{"id": sid, "label": label, **state.steps[sid].model_dump()} for sid, label in STEPS],
        "busy": jobs.busy(state.id),
        "queue_note": _queue_note(state.id, "project"),
        "last_error": state.last_error,
        "render_quality": state.render_quality,
        "use_claude": state.use_claude,
        "manual_offset": state.manual_offset,
        "outputs": sorted(f.name for f in p.out.iterdir() if f.is_file() and ".part" not in f.name) if p.out.exists() else [],
    }


def code_fingerprint() -> str:
    """Empreinte du code installé (Python + interface), relue sur le disque à chaque appel."""
    digest = hashlib.sha1()
    package = Path(__file__).parent
    for path in sorted([*package.glob("*.py"), *WEB.glob("*")]):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


RUNNING_BUILD = code_fingerprint()  # le code avec lequel ce serveur a démarré


@app.get("/api/version")
def version():
    """« current » est faux si KrokCut a été mis à jour pendant qu'il tournait : il faut le relancer."""
    return {"version": __version__, "build": RUNNING_BUILD, "current": RUNNING_BUILD == code_fingerprint()}


def _assets_version() -> str:
    digest = hashlib.sha1()
    for name in ("app.js", "style.css"):
        digest.update((WEB / name).read_bytes())
    return digest.hexdigest()[:12]


@app.get("/", response_class=HTMLResponse)
def index():
    # Le numéro de version dans l'adresse oblige le navigateur à recharger script et styles
    # quand ils changent (sinon il peut garder ceux d'avant la mise à jour).
    version = _assets_version()
    html = (WEB / "index.html").read_text("utf-8")
    for name in ("app.js", "style.css"):
        html = html.replace(f'"/static/{name}"', f'"/static/{name}?v={version}"')
    return html


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
        "ffmpeg": {**ffmpeg_status(), "repair": ffmpeg_repair.state()},
    }


@app.post("/api/ffmpeg/repair")
def repair_ffmpeg():
    """Bouton « Réparer ffmpeg » : retélécharge ffmpeg dans ~/KrokCut/bin (Mac)."""
    if not repair_supported():
        raise HTTPException(400, "La réparation automatique n'existe que sur Mac : relance l'installation de KrokCut.")
    ffmpeg_repair.start()
    return ffmpeg_repair.state()


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
async def upload(filename: str, request: Request, folder: str = "rush"):
    """Reçoit un fichier en flux continu (pas de double copie sur le disque)."""
    safe = Path(filename).name
    if not safe or safe.startswith("."):
        raise HTTPException(400, "Nom de fichier invalide")
    require_ffmpeg()
    if folder == "references":
        dest_dir = ReferenceStore().files_dir
    else:
        dest_dir = workspace_dir() / "rush"
        dest_dir.mkdir(exist_ok=True)
    # Réserve le nom de façon atomique : deux envois simultanés du même nom ne se mélangent jamais,
    # et un fichier déjà utilisé par un épisode n'est jamais écrasé.
    dest, n = dest_dir / safe, 2
    while True:
        try:
            os.close(os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            dest = dest_dir / f"{Path(safe).stem}-{n}{Path(safe).suffix}"
            n += 1
    fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".envoi-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            async for chunk in request.stream():
                fh.write(chunk)
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise
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
    if data.start:
        require_ffmpeg()
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
    require_ffmpeg()
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
    require_ffmpeg()
    try:
        lib = Library.scan(directory)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FFmpegUnavailable as exc:  # bibliothèque laissée intacte
        raise HTTPException(503, str(exc)) from exc
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


# ------------------------------------------------------- vidéos de référence
def _reference_summary(doc: ReferenceDoc) -> dict:
    state = doc.state
    analysis = doc.read_json("analyse.json")
    return {
        "id": state.id,
        "name": state.name,
        "path": state.path,
        "added": state.added,
        "steps": [{"id": sid, "label": label, **state.steps[sid].model_dump()} for sid, label in REF_STEPS],
        "metrics": state.metrics,
        "busy": jobs.busy(state.id, "reference"),
        "queue_note": _queue_note(state.id, "reference"),
        "last_error": state.last_error,
        "analysis_source": analysis.get("source") if analysis else None,
        "claude_error": (analysis or {}).get("claude_error", ""),
        "has_thumb": (doc.root / "vignette.jpg").exists(),
    }


@app.get("/api/references")
def list_references():
    store = ReferenceStore()
    error_file = store.root / "guide_erreur.txt"
    return {
        "references": [_reference_summary(d) for d in store.list()],
        "guide": store.guide(),
        "guide_busy": jobs.any_busy("guide"),
        "guide_error": error_file.read_text("utf-8") if error_file.exists() else "",
        "claude": claude_available(AppConfig.load()),
    }


class AddReferences(BaseModel):
    paths: list[str]


@app.post("/api/references")
def add_references(data: AddReferences):
    store = ReferenceStore()
    added, duplicates = [], []
    for path in data.paths:
        if not Path(path).is_file():
            raise HTTPException(400, f"Fichier introuvable : {path}")
    require_ffmpeg()
    for path in data.paths:
        doc, created = store.add_or_get(path)
        if not created:
            duplicates.append(doc.state.name)
        if doc.state.steps["analyze"].status != "done" and not jobs.busy(doc.id, "reference"):
            jobs.submit(doc.id, kind="reference")
        added.append(_reference_summary(doc))
    return {"added": added, "duplicates": duplicates}


def _reference(ref_id: str) -> ReferenceDoc:
    try:
        return ReferenceStore().open(ref_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/references/{ref_id}")
def get_reference(ref_id: str):
    doc = _reference(ref_id)
    return {
        **_reference_summary(doc),
        "analysis": doc.read_json("analyse.json"),
        "log": doc.log_tail(30),
    }


@app.post("/api/references/{ref_id}/run")
def rerun_reference(ref_id: str, data: dict | None = None):
    """Analyse terminée : refait seulement les bruitages et le style (bibliothèque ou bible changée).
    Analyse incomplète : reprend là où elle s'est arrêtée. `from_step` force une relance plus large."""
    doc = _reference(ref_id)
    from_step = (data or {}).get("from_step")
    if from_step and from_step not in REF_STEP_IDS:
        raise HTTPException(400, "Étape inconnue")
    if jobs.busy(doc.id, "reference"):
        raise HTTPException(409, "Déjà en cours de traitement.")
    require_ffmpeg()
    if not from_step and all(st.status == "done" for st in doc.state.steps.values()):
        doc.invalidate(["sfx", "analyze"])
    try:
        jobs.submit(doc.id, from_step=from_step, kind="reference")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _reference_summary(doc)


@app.delete("/api/references/{ref_id}")
def delete_reference(ref_id: str):
    doc = _reference(ref_id)
    if jobs.busy(doc.id, "reference") == "running":
        raise HTTPException(409, "Analyse en cours : annule-la d'abord.")
    jobs.cancel(doc.id, "reference")
    ReferenceStore().remove(doc.id)
    jobs.submit_guide()
    return {"ok": True}


@app.post("/api/references/{ref_id}/cancel")
def cancel_reference(ref_id: str):
    jobs.cancel(_reference(ref_id).id, "reference")
    return {"ok": True}


@app.get("/api/references/{ref_id}/thumb")
def reference_thumb(ref_id: str):
    path = _reference(ref_id).root / "vignette.jpg"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")


@app.post("/api/guide/rebuild")
def rebuild_guide():
    """Met à jour le guide. Avec une clé Claude, les vidéos analysées sans Claude (pas de clé à
    l'époque, Claude indisponible) ou sur d'anciennes mesures de bruitages sont d'abord relues par
    Claude ; le guide suit tout seul."""
    store = ReferenceStore()
    reanalysing = 0
    if claude_available(AppConfig.load()):
        for doc, analysis in store.analyses():
            if needs_claude(doc, analysis) and not too_long(doc) and not jobs.busy(doc.id, "reference"):
                if sfx_outdated(doc.state.metrics):  # bruitages à remesurer d'abord (sans refaire images ni transcription)
                    doc.invalidate(["sfx", "analyze"])
                    jobs.submit(doc.id, kind="reference")
                else:
                    jobs.submit(doc.id, from_step="analyze", kind="reference")
                reanalysing += 1
    if not reanalysing:
        jobs.submit_guide()
    return {"ok": True, "reanalysing": reanalysing}


class ApplyGuide(BaseModel):
    fields: list[str] | None = None  # réglages cochés ; par défaut, ceux qui sont mesurés


@app.post("/api/guide/apply")
def apply_guide_style(data: ApplyGuide | None = None):
    """Reporte les réglages suggérés par les vidéos publiées dans le style par défaut."""
    guide = ReferenceStore().guide()
    suggested = (guide or {}).get("suggested") or {}
    values = suggested.get("values") or {}
    default = suggested.get("checked")
    if default is None:  # ancien guide : seulement ce qui est mesuré
        default = [k for k, src in (suggested.get("sources") or {}).items() if str(src).startswith("mesuré")]
    fields = data.fields if data and data.fields is not None else default
    values = {k: v for k, v in values.items() if k in fields}
    if not values:
        raise HTTPException(400, "Aucun réglage choisi.")
    style = StyleProfile.model_validate({**StyleProfile.load().model_dump(), **values})
    style.save(StyleProfile.default_path())
    return style.model_dump()


@app.post("/api/quit")
def quit_app():
    """Ferme KrokCut (bouton « Quitter » de l'interface)."""
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"ok": True, "interrupted": bool(jobs.current)}


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
