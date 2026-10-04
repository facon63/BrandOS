"""Vidéos déjà montées : KrokCut les étudie pour apprendre ce que l'équipe attend.

Pour chaque vidéo publiée : rythme des coupes, part de parole, bruitages de la bibliothèque
reconnus dans le son, images clés, transcription, puis analyse du style par Claude. Le tout est
résumé dans un « guide de style » injecté dans les prompts de chaque dérush.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
from pydantic import BaseModel, Field

from .audio import Levels, level_curve
from .config import AppConfig, channel_bible, workspace_dir
from .ffmpeg_utils import extract_frame, extract_pcm, probe, run_ffmpeg
from .library import Library
from .llm import LLM, NUM, STR, LLMError, arr, claude_available, enum, obj
from .project import slugify
from .prompts import GUIDE_INSTRUCTIONS, REFERENCE_ANALYSIS_INSTRUCTIONS, REFERENCE_SYSTEM
from .sfx_detect import SFX_DETECTOR_VERSION, detect_library_sounds, load_detect_signal
from .steps import StepDoc, StepRunner, StepStatus
from .transcribe import build_lines, fmt_time, transcribe_mix

REF_STEPS: list[tuple[str, str]] = [
    ("probe", "Lecture du fichier"),
    ("audio", "Extraction du son"),
    ("rhythm", "Rythme du montage"),
    ("sfx", "Bruitages de la bibliothèque reconnus"),
    ("frames", "Images clés"),
    ("transcribe", "Transcription"),
    ("analyze", "Analyse du style"),
]
REF_STEP_IDS = [s for s, _ in REF_STEPS]
MAX_REFERENCE_MINUTES = 60  # au-delà, c'est sûrement un rush, pas une vidéo montée
SHORT_REFERENCE_MINUTES = 3  # en dessous, sûrement un Short : autre format, pas compté dans les moyennes
EMPTY_SFX = {"hits": [], "music": [], "skipped": 0, "skipped_music": [], "unreliable": [], "too_short": [], "tested": 0}
MAX_FRAMES_FOR_CLAUDE = 24
PROMPT_BLOCK_MAX_CHARS = 12000
GUIDE_INPUT_MAX_CHARS = 150000  # analyses relues par Claude pour écrire le guide (~40 000 tokens)

ESTIMATES_SCHEMA = obj(
    {
        "zooms_per_minute": NUM,
        "texts_per_minute": NUM,
        "characters_per_minute": NUM,
        "has_music": enum("oui", "non", "inconnu"),
        "cold_open": enum("oui", "non", "inconnu"),
    }
)
EXAMPLE_FIELDS = {"time": STR, "quote": STR, "why_kept": STR, "effects": STR}
ANALYSIS_SCHEMA = obj(
    {
        "summary": STR,
        "structure": STR,
        "humor": STR,
        "editing": STR,
        "sound_design": STR,
        "rules": arr(STR),
        "examples": arr(obj(EXAMPLE_FIELDS)),
        "estimates": ESTIMATES_SCHEMA,
    }
)
GUIDE_SCHEMA = obj(
    {
        "guide": STR,
        "examples": arr(obj({"video": STR, **EXAMPLE_FIELDS})),
        "estimates": ESTIMATES_SCHEMA,
    }
)


# ------------------------------------------------------------------ stockage
def file_signature(path: Path, chunk: int = 1 << 20) -> str:
    """Taille + empreinte du début et de la fin : rapide même sur une vidéo de plusieurs Go."""
    size = path.stat().st_size
    digest = hashlib.sha1(str(size).encode())
    with open(path, "rb") as fh:
        digest.update(fh.read(chunk))
        if size > 2 * chunk:
            fh.seek(-chunk, os.SEEK_END)
            digest.update(fh.read(chunk))
    return digest.hexdigest()


def atomic_write(path: Path, text: str) -> None:
    """Écrit via un fichier temporaire : un arrêt brutal ne laisse jamais un fichier tronqué."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def too_long(doc: "ReferenceDoc") -> bool:
    return (doc.state.metrics.get("duration_min") or 0) > MAX_REFERENCE_MINUTES


def is_short(doc: "ReferenceDoc") -> bool:
    return 0 < (doc.state.metrics.get("duration_min") or 0) < SHORT_REFERENCE_MINUTES


def sfx_measured(metrics: dict) -> bool:
    """Bruitages cherchés, avec la détection actuelle (celle d'avant donnait trop de fausses alertes)."""
    return bool(metrics.get("sfx_checked")) and metrics.get("sfx_detector") == SFX_DETECTOR_VERSION


def sfx_outdated(metrics: dict) -> bool:
    return bool(metrics.get("sfx_checked")) and metrics.get("sfx_detector") != SFX_DETECTOR_VERSION


def flag(value) -> bool | None:
    """Oui / non / inconnu. Les anciennes analyses disaient « false » aussi quand elles ne savaient pas."""
    if value is True or value == "oui":
        return True
    if value == "non":
        return False
    return None


class ReferenceState(BaseModel):
    id: str
    name: str
    path: str
    added: str
    copied: bool = False  # fichier copié dans l'espace de travail (supprimé avec la référence)
    signature: str = ""  # empreinte du contenu : repère une même vidéo déposée deux fois
    steps: dict[str, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in REF_STEP_IDS})
    metrics: dict = Field(default_factory=dict)
    last_error: str = ""


class ReferenceDoc(StepDoc):
    STATE_FILE = "reference.json"
    INTERRUPTED_MSG = "Interrompu (KrokCut a été fermé) : clique sur Reprendre l'analyse"
    state_model = ReferenceState
    step_ids = REF_STEP_IDS
    state: ReferenceState

    @property
    def id(self) -> str:
        return self.state.id

    def set_metrics(self, **values) -> None:
        with self._lock:
            self.state.metrics.update(values)
            self.save()


class ReferenceStore:
    def __init__(self, root: Path | None = None):
        self.root = root or (workspace_dir() / "references")
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def files_dir(self) -> Path:
        path = self.root / "fichiers"
        path.mkdir(exist_ok=True)
        return path

    @property
    def sounds_cache(self) -> Path:
        return self.root / "_sons_cache"

    def list(self) -> list[ReferenceDoc]:
        docs = []
        for path in sorted(self.root.iterdir()):
            if (path / ReferenceDoc.STATE_FILE).exists():
                try:
                    docs.append(ReferenceDoc(path))
                except Exception:  # référence abîmée : ignorée
                    continue
        docs.sort(key=lambda d: d.state.added)
        return docs

    def open(self, ref_id: str) -> ReferenceDoc:
        root = self.root / Path(ref_id).name
        if not (root / ReferenceDoc.STATE_FILE).exists():
            raise FileNotFoundError(f"Vidéo de référence introuvable : {ref_id}")
        return ReferenceDoc(root)

    def add(self, path: str | Path, name: str | None = None) -> ReferenceDoc:
        return self.add_or_get(path, name)[0]

    def add_or_get(self, path: str | Path, name: str | None = None) -> tuple[ReferenceDoc, bool]:
        """Ajoute une vidéo ; renvoie (référence, nouvelle ?). Une vidéo déjà présente n'est pas dupliquée."""
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {path}")
        signature = file_signature(path)
        in_workspace = self.files_dir.resolve() in path.parents
        for doc in self.list():
            known = Path(doc.state.path)
            if known == path:
                return doc, False
            other = doc.state.signature
            if not other and known.is_file():
                other = file_signature(known)
                doc.state.signature = other
                doc.save()
            if other == signature:
                if in_workspace:  # même vidéo déposée une 2e fois : inutile de garder la copie
                    path.unlink(missing_ok=True)
                return doc, False
        base = slugify(name or path.stem)[:60]
        ref_id, i = base, 2
        while (self.root / ref_id).exists():
            ref_id, i = f"{base}-{i}", i + 1
        root = self.root / ref_id
        root.mkdir(parents=True)
        state = ReferenceState(
            id=ref_id,
            name=name or path.stem,
            path=str(path),
            added=datetime.now().isoformat(timespec="seconds"),
            copied=in_workspace,
            signature=signature,
        )
        (root / ReferenceDoc.STATE_FILE).write_text(state.model_dump_json(indent=2), "utf-8")
        return ReferenceDoc(root), True

    def remove(self, ref_id: str) -> None:
        doc = self.open(ref_id)
        if doc.state.copied:
            Path(doc.state.path).unlink(missing_ok=True)
        shutil.rmtree(doc.root, ignore_errors=True)

    # ---------------------------------------------------------------- guide
    @property
    def guide_md(self) -> Path:
        return self.root / "guide.md"

    @property
    def guide_json(self) -> Path:
        return self.root / "guide.json"

    def guide(self) -> dict | None:
        """Le guide courant, ou None (absent ou illisible : il ne doit jamais bloquer un dérush)."""
        try:
            data = json.loads(self.guide_json.read_text("utf-8"))
            data["text"] = self.guide_md.read_text("utf-8") if self.guide_md.exists() else ""
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def analyses(self) -> list[tuple[ReferenceDoc, dict]]:
        out = []
        for doc in self.list():
            analysis = doc.read_json("analyse.json")
            if analysis and doc.state.steps["analyze"].status == "done":
                out.append((doc, analysis))
        return out

    def prompt_block(self) -> str:
        """Texte injecté dans les prompts de dérush et de montage."""
        guide = self.guide()
        if not guide or not guide.get("text", "").strip():
            return ""
        # Les titres du guide descendent de deux niveaux pour rester sous la section « Repères »
        text = re.sub(r"(?m)^(#{1,4}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", guide["text"].strip())
        parts = [text]
        examples = guide.get("examples") or []
        if examples:
            rows = [
                f"- [{e.get('video', '')} {e.get('time', '')}] « {e.get('quote', '')} » — {e.get('why_kept', '')}"
                + (f" (effets : {e['effects']})" if e.get("effects") else "")
                for e in examples[:12]
            ]
            parts.append("#### Exemples de moments gardés dans vos vidéos publiées\n" + "\n".join(rows))
        if guide.get("measured") and guide.get("source") == "claude":  # le guide « mesures seules » les contient déjà
            parts.append("#### Mesures sur vos vidéos publiées (pour information)\n" + guide["measured"])
        text = "\n\n".join(parts)
        if len(text) > PROMPT_BLOCK_MAX_CHARS:
            text = text[:PROMPT_BLOCK_MAX_CHARS].rsplit("\n", 1)[0] + "\n(…)"
        return text


# --------------------------------------------------------------- mesures
def scene_cuts(path: str | Path, work: Path, duration: float, threshold: float = 0.32, on_progress=None) -> list[float]:
    """Instants des changements de plan (détection de scène de ffmpeg, en basse résolution)."""
    listing = work / "coupes.txt"
    listing.unlink(missing_ok=True)
    run_ffmpeg(
        [
            "-i", str(Path(path).resolve()), "-an",
            "-vf", f"scale=320:-2,select='gt(scene,{threshold})',metadata=print:file=coupes.txt",
            "-f", "null", "-",
        ],
        duration=duration,
        on_progress=on_progress,
        cwd=work,
    )
    text = listing.read_text("utf-8", errors="replace") if listing.exists() else ""
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", text)]


def rhythm_metrics(cuts: list[float], duration: float) -> dict:
    minutes = max(duration / 60, 0.01)
    edges = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    shots = [b - a for a, b in zip(edges[:-1], edges[1:]) if b - a > 0.04]
    q = statistics.quantiles(shots, n=4) if len(shots) >= 4 else [0, 0, 0]
    return {
        "cuts": len(edges) - 2,
        "cuts_per_min": round((len(edges) - 2) / minutes, 1),
        "median_shot": round(statistics.median(shots), 2) if shots else round(duration, 2),
        "shot_p25": round(q[0], 2),
        "shot_p75": round(q[2], 2),
    }


def speech_ratio(words: list[dict], duration: float, join_gap: float = 0.3) -> float:
    """Part du temps où quelqu'un parle, d'après les mots transcrits (blancs < 0,3 s comptés)."""
    if duration <= 0 or not words:
        return 0.0
    spans = sorted((w["s"], min(w["e"], w["s"] + 1.5)) for w in words)
    total, cur_s, cur_e = 0.0, spans[0][0], spans[0][1]
    for s, e in spans[1:]:
        if s <= cur_e + join_gap:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return min(1.0, total / duration)


def timeline_text(lines: list[dict], hits: list[dict]) -> str:
    """Transcription de la vidéo finale entremêlée des bruitages reconnus."""
    events = [(l["start"], f"[{fmt_time(l['start'])}] {l['text']}") for l in lines]
    events += [(h["t"], f"[{fmt_time(h['t'])}] 🔊 {h['asset']}") for h in hits]
    events.sort(key=lambda e: e[0])
    return "\n".join(text for _, text in events)


def heuristic_analysis(doc: ReferenceDoc, lines: list[dict], sfx: dict) -> dict:
    """Sans Claude : des règles et exemples tirés des seules mesures."""
    m = doc.state.metrics
    rules = []
    if m.get("cuts_per_min"):
        rules.append(
            f"Rythme d'environ {m['cuts_per_min']:g} changements de plan par minute "
            f"(un plan dure {m.get('median_shot', 0):g} s en médiane)."
        )
    top = (m.get("sfx_top") or []) if sfx_measured(m) else []
    if top:
        rules.append("Bruitages les plus utilisés : " + ", ".join(f"{a} ({n}×)" for a, n in top[:6]) + ".")
    if sfx_measured(m) and m.get("music_used"):
        rules.append("Musique de fond utilisée : " + ", ".join(m["music_used"]) + ".")
    examples = []
    for h in (sfx.get("hits") or [])[:40]:
        before = [l for l in lines if l["kind"] == "speech" and l["end"] <= h["t"] + 0.3 and l["end"] >= h["t"] - 4]
        if before:
            line = before[-1]
            examples.append(
                {"time": fmt_time(line["start"]), "quote": line["text"][:160], "why_kept": "phrase ponctuée d'un bruitage", "effects": h["asset"]}
            )
        if len(examples) >= 6:
            break
    return {
        "source": "heuristic",
        "summary": "",
        "structure": f"{m.get('duration_min', 0):g} min, {m.get('cuts_per_min', 0):g} changements de plan par minute.",
        "humor": "",
        "editing": "",
        "sound_design": "",
        "rules": rules,
        "examples": examples,
        "estimates": {},
    }


# -------------------------------------------------------------- analyse
WordsProvider = Callable[[Path, Levels], list[dict]]


class ReferenceAnalyzer(StepRunner):
    step_ids = REF_STEP_IDS

    def __init__(
        self,
        doc: ReferenceDoc,
        cfg: AppConfig,
        store: ReferenceStore | None = None,
        *,
        words_provider: WordsProvider | None = None,
        cancel_event: threading.Event | None = None,
    ):
        super().__init__(doc, cancel_event)
        self.doc = doc
        self.cfg = cfg
        self.store = store or ReferenceStore(doc.root.parent)
        self.words_provider = words_provider

    @property
    def pcm(self) -> Path:
        return self.doc.root / "audio.pcm"

    @property
    def duration(self) -> float:
        return float(self.doc.state.metrics.get("duration_s") or 0.0)

    def levels(self) -> Levels:
        curve = np.load(self.doc.root / "niveaux.npy")
        return Levels.compute_thresholds(curve, curve)

    def source(self) -> Path:
        path = Path(self.doc.state.path)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier d'origine introuvable (déplacé ou supprimé ?) : {path}")
        return path

    # ----------------------------------------------------------------- étapes
    def step_probe(self) -> str:
        info = probe(self.source())
        if not info.has_audio:
            raise ValueError("Cette vidéo n'a pas de son : impossible d'en tirer le style.")
        self.doc.set_metrics(
            duration_s=round(info.duration, 2),
            duration_min=round(info.duration / 60, 1),
            width=info.width,
            height=info.height,
        )
        warning = ""
        if info.duration > MAX_REFERENCE_MINUTES * 60:
            warning = " — attention : très longue pour une vidéo montée (c'est un rush ?)"
        return f"{info.duration / 60:.1f} min{warning}"

    def step_audio(self) -> str:
        if not self.pcm.exists():
            extract_pcm(
                self.source(),
                self.pcm,
                duration=self.duration,
                on_progress=lambda f: self.progress("audio", f),
            )
        return ""

    def step_rhythm(self) -> str:
        cuts = []
        if self.doc.state.metrics.get("height"):
            cuts = scene_cuts(
                self.source(),
                self.doc.root,
                self.duration,
                on_progress=lambda f: self.progress("rhythm", 0.9 * f, "Détection des changements de plan"),
            )
        self.doc.write_json("coupes.json", cuts)
        curve = level_curve(self.pcm)
        np.save(self.doc.root / "niveaux.npy", curve)
        metrics = rhythm_metrics(cuts, self.duration)
        self.doc.set_metrics(**metrics)
        return f"{metrics['cuts_per_min']:g} changements de plan / min, plan médian {metrics['median_shot']:g} s"

    def step_sfx(self) -> str:
        library = Library.load(self.cfg.library_dir) if self.cfg.library_dir else Library(Path("."), [])
        unchecked = {"sfx_checked": False, "sfx_hits": 0, "sfx_per_min": 0.0, "sfx_top": [], "music_used": [], "sfx_detector": SFX_DETECTOR_VERSION}
        if not library.of_kind("sfx", "music"):
            self.doc.write_json("bruitages.json", EMPTY_SFX)
            self.doc.set_metrics(**unchecked)
            return "Bibliothèque vide : rien à reconnaître (ajoute-la puis clique sur Réanalyser)"
        if self.duration > MAX_REFERENCE_MINUTES * 60:
            self.doc.write_json("bruitages.json", EMPTY_SFX)
            self.doc.set_metrics(**unchecked)
            return "Vidéo trop longue : étape sautée"
        signal = load_detect_signal(self.pcm, self.doc.root / "audio8k.pcm")
        result = detect_library_sounds(
            signal,
            library,
            self.store.sounds_cache,
            on_progress=lambda f, name: self.progress("sfx", f, f"Recherche : {name}"),
        )
        self.doc.write_json("bruitages.json", result)
        counts = Counter(h["asset"] for h in result["hits"])
        minutes = max(self.duration / 60, 0.01)
        self.doc.set_metrics(
            sfx_checked=True,
            sfx_detector=SFX_DETECTOR_VERSION,
            sfx_hits=len(result["hits"]),
            sfx_per_min=round(len(result["hits"]) / minutes, 1),
            sfx_top=[[asset, n] for asset, n in counts.most_common(10)],
            music_used=[m["asset"] for m in result["music"]],
        )
        extra = f", {len(result['music'])} musique(s)" if result["music"] else ""
        notes = []
        if result["unreliable"]:
            notes.append(f"{len(result['unreliable'])} son(s) ignoré(s) car ils ressemblent à tout")
        if result["too_short"]:
            notes.append(f"{len(result['too_short'])} son(s) trop bref(s) ou muet(s) pour être reconnus")
        if result["skipped"]:
            notes.append(f"{result['skipped']} son(s) non testé(s) : bibliothèque très grande")
        if result.get("skipped_music"):
            notes.append(f"{len(result['skipped_music'])} musique(s) non testée(s) : bibliothèque très grande")
        if notes:
            extra += " — " + " ; ".join(notes)
        return f"{len(result['hits'])} bruitages reconnus{extra}"

    def step_frames(self) -> str:
        frames_dir = self.doc.root / "images"
        existing = sorted(frames_dir.glob("img_*.jpg")) if frames_dir.exists() else []
        if not self.doc.state.metrics.get("height"):
            shutil.rmtree(frames_dir, ignore_errors=True)
            return "Pas d'image (fichier audio)"
        if not Path(self.doc.state.path).is_file():
            if existing:
                return f"Fichier d'origine introuvable : les {len(existing)} images précédentes sont conservées"
            self.source()  # lève une erreur explicite
        tmp_dir = self.doc.root / "images.tmp"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir()
        count = int(min(40, max(8, self.duration / 15)))
        done = 0
        for i in range(count):
            t = self.duration * (0.03 + 0.94 * i / max(1, count - 1))
            if extract_frame(self.doc.state.path, t, tmp_dir / f"img_{i:03d}_{t:08.1f}.jpg", width=480):
                done += 1
            self.progress("frames", (i + 1) / count)
        if not done:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            if existing:
                return f"Extraction impossible : les {len(existing)} images précédentes sont conservées"
            raise RuntimeError("Impossible d'extraire des images de cette vidéo.")
        shutil.rmtree(frames_dir, ignore_errors=True)
        tmp_dir.rename(frames_dir)
        thumb_tmp = self.doc.root / "vignette.tmp.jpg"
        if extract_frame(self.doc.state.path, self.duration * 0.1, thumb_tmp, width=320):
            thumb_tmp.replace(self.doc.root / "vignette.jpg")
        return f"{done} images"

    def step_transcribe(self) -> str:
        levels = self.levels()
        if self.words_provider:
            words = self.words_provider(self.pcm, levels)
        else:
            settings = self.cfg.whisper.model_copy(update={"model": self.cfg.references_whisper_model or self.cfg.whisper.model})
            words = transcribe_mix(
                self.pcm,
                levels,
                settings,
                self.doc.root / "transcription_morceaux",
                on_progress=lambda f, msg: self.progress("transcribe", f, msg),
                log=self.doc.log,
            )
        lines = build_lines(words, levels)
        self.doc.write_json("transcription.json", {"lines": lines})
        self.doc.set_metrics(
            words_per_min=round(len(words) / max(self.duration / 60, 0.01)),
            speech_ratio=round(speech_ratio(words, self.duration), 2),
        )
        return f"{len(words)} mots"

    def step_analyze(self) -> str:
        lines = self.doc.read_json("transcription.json", {"lines": []})["lines"]
        sfx = self.doc.read_json("bruitages.json", {"hits": []})
        self.progress("analyze", 0.05, "Analyse du style…")
        message = "mesures seules (pas de clé Claude)"
        if claude_available(self.cfg):
            try:
                analysis = self.analyze_with_claude(lines, sfx)
                message = "par Claude"
            except LLMError as exc:  # la vidéo compte quand même, avec ses mesures
                self.doc.log(f"Claude indisponible, analyse par les mesures seules : {exc}")
                analysis = {**heuristic_analysis(self.doc, lines, sfx), "claude_error": str(exc)}
                message = f"mesures seules : Claude n'a pas répondu ({exc}). Relance l'analyse (Réanalyser) pour réessayer."
        else:
            analysis = heuristic_analysis(self.doc, lines, sfx)
        analysis["sfx_detector"] = self.doc.state.metrics.get("sfx_detector")
        self.doc.write_json("analyse.json", analysis)
        return message

    def analyze_with_claude(self, lines: list[dict], sfx: dict) -> dict:
        m = self.doc.state.metrics
        metrics_text = "\n".join(
            [
                f"- durée : {m.get('duration_min', 0):g} min",
                f"- changements de plan : {m.get('cuts_per_min', 0):g} par minute (plan médian {m.get('median_shot', 0):g} s)",
                f"- parole : {round(100 * m.get('speech_ratio', 0))} % du temps, {m.get('words_per_min', 0)} mots/min",
                (
                    f"- bruitages de la bibliothèque reconnus : {m.get('sfx_hits', 0)} ({m.get('sfx_per_min', 0):g}/min)"
                    if sfx_measured(m)
                    else "- bruitages : non vérifiés (bibliothèque absente)"
                ),
                f"- musiques reconnues : {', '.join(m.get('music_used') or []) or 'aucune'}",
            ]
        )
        library = Library.load(self.cfg.library_dir) if self.cfg.library_dir else None
        library_note = ""
        if library and library.of_kind("character", "image", "video"):
            items = library.of_kind("character", "image", "video")[:150]
            library_note = (
                "\nPersonnages et memes de la bibliothèque (si tu en reconnais à l'image, cite leur id) :\n"
                + "\n".join(f"- {a['id']} ({a.get('character') or a['kind']}) : {', '.join(a['tags'][:6])}" for a in items)
                + "\n"
            )
        content: list[dict] = []
        frames = sorted((self.doc.root / "images").glob("img_*.jpg"))
        step = max(1, len(frames) // MAX_FRAMES_FOR_CLAUDE + (1 if len(frames) % MAX_FRAMES_FOR_CLAUDE else 0))
        for frame in frames[::step][:MAX_FRAMES_FOR_CLAUDE]:
            t = float(frame.stem.split("_")[-1])
            content.append({"type": "text", "text": f"Image à {fmt_time(t)} :"})
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(frame.read_bytes()).decode()}}
            )
        content.append(
            {
                "type": "text",
                "text": REFERENCE_ANALYSIS_INSTRUCTIONS.format(
                    name=self.doc.state.name,
                    duration=fmt_time(self.duration),
                    metrics=metrics_text,
                    library_note=library_note,
                    timeline=timeline_text(lines, sfx.get("hits") or []) or "(pas de parole transcrite)",
                ),
            }
        )
        bible = channel_bible().strip()
        system = REFERENCE_SYSTEM + (f"\n\n## La chaîne (écrit par l'équipe)\n{bible}" if bible else "")
        llm = LLM(self.cfg, cache_dir=self.doc.root / "claude_cache", log=self.doc.log)
        result = llm.ask_json(system=system, content=content, schema=ANALYSIS_SCHEMA, effort="medium", max_tokens=32000, label="reference")
        return {"source": "claude", **result}


# ---------------------------------------------------------------- guide
def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 1) if values else None


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def _rate(x: float) -> float:
    """Arrondi d'une densité par minute : une estimation non nulle ne devient jamais 0."""
    if x <= 0:
        return 0.0
    return max(0.1, round(x, 1)) if x < 1 else _round_half(x)


def usual_length(durations: list[float]) -> tuple[float, float] | None:
    """Durées « habituelles » : autour de la médiane (à 1,5× près) dès 3 vidéos.

    Un épisode spécial deux fois plus long (ou un extrait deux fois plus court) n'en fait pas partie.
    Avec 1 ou 2 vidéos, impossible de dire laquelle est à part : toutes comptent.
    """
    d = sorted(x for x in durations if x)
    if not d:
        return None
    if len(d) < 3:
        return d[0], d[-1]
    m = statistics.median(d)
    return m / 1.5, m * 1.5


def typical_docs(docs: list[ReferenceDoc]) -> list[ReferenceDoc]:
    """Vidéos au format habituel de la chaîne : ni Short, ni rush, ni durée hors norme.

    Elles seules comptent dans les durées et rythmes mesurés (toutes, si aucune n'est habituelle).
    """
    usual = [d for d in docs if not is_short(d) and not too_long(d)] or docs
    bounds = usual_length([d.state.metrics.get("duration_min") or 0 for d in usual])
    if bounds:
        lo, hi = bounds
        usual = [d for d in usual if lo <= (d.state.metrics.get("duration_min") or 0) <= hi] or usual
    return usual


def duration_targets(durations: list[float]) -> tuple[float, float]:
    """Fourchette de durée : le cœur des vidéos publiées (une vidéo hors norme ne l'étire pas)."""
    lo_ok, hi_ok = usual_length(durations) or (0, float("inf"))
    d = sorted(x for x in durations if lo_ok <= x <= hi_ok) or sorted(durations)
    if len(d) >= 4:
        q = statistics.quantiles(d, n=4, method="inclusive")
        lo, hi = q[0], q[2]
    else:
        lo, hi = d[0], d[-1]
    target_min = float(max(3, round(lo - 1)))
    target_max = float(min(MAX_REFERENCE_MINUTES, max(target_min + 2, round(hi + 1))))
    return target_min, target_max


def measured_summary(docs: list[ReferenceDoc]) -> tuple[str, dict]:
    typical = typical_docs(docs)
    shorts = [d.state.name for d in docs if d not in typical and is_short(d)]
    unusual = [d.state.name for d in docs if d not in typical and not is_short(d)]
    metrics = [d.state.metrics for d in typical]
    durations = [m["duration_min"] for m in metrics if m.get("duration_min")]
    videos = [m for m in metrics if m.get("height")]  # le rythme n'a de sens que pour une vraie vidéo
    cuts = _mean([m.get("cuts_per_min", 0) for m in videos])
    shot = _mean([m.get("median_shot") for m in videos])
    ratios = [m["speech_ratio"] for m in metrics if m.get("speech_ratio") is not None]
    speech = round(statistics.mean(ratios), 2) if ratios else None  # une part : pas d'arrondi au dixième
    checked = [m for m in metrics if sfx_measured(m)]
    sfx_rate = _mean([m.get("sfx_per_min", 0) for m in checked])
    top: Counter = Counter()
    for m in checked:
        for asset, n in m.get("sfx_top") or []:
            top[asset] += n
    music: Counter = Counter()  # une musique reconnue, même dans un Short, prouve qu'elle est utilisée
    for d in docs:
        if sfx_measured(d.state.metrics):
            music.update(d.state.metrics.get("music_used") or [])
    lines = []
    if len(set(durations)) > 1:
        lines.append(
            f"- Durée : {statistics.median(durations):g} min en médiane (de {min(durations):g} à {max(durations):g} min)."
        )
    elif durations:
        lines.append(f"- Durée : {durations[0]:g} min.")
    if videos:
        lines.append(f"- Rythme : {cuts:g} changements de plan par minute, plan médian {shot:g} s.")
    if speech is not None:
        lines.append(f"- Parole : {round(speech * 100)} % du temps.")
    if checked:
        lines.append(f"- Bruitages de la bibliothèque reconnus : au moins {sfx_rate or 0:g} par minute.")
        if top:
            lines.append("- Les plus utilisés : " + ", ".join(f"{a} ({n}×)" for a, n in top.most_common(8)) + ".")
    if music:
        lines.append("- Musiques reconnues : " + ", ".join(a for a, _ in music.most_common(5)) + ".")
    if shorts:
        lines.append(
            f"- Non comptées dans ces chiffres (moins de {SHORT_REFERENCE_MINUTES} min, sûrement des Shorts) : "
            + ", ".join(shorts) + "."
        )
    if unusual:
        lines.append("- Non comptées non plus (durée inhabituelle, épisode spécial ?) : " + ", ".join(unusual) + ".")
    return "\n".join(lines), {
        "durations": durations,
        "sfx_rate": sfx_rate,
        "sfx_checked": bool(checked),
        "music": [a for a, _ in music.most_common()],
        "shorts": shorts,
        "unusual": unusual,
    }


def _majority(votes: list[bool | None]) -> bool | None:
    known = [v for v in votes if v is not None]
    yes = sum(known)
    if not known or yes * 2 == len(known):
        return None
    return yes * 2 > len(known)


def suggested_style(analyses: list[tuple[ReferenceDoc, dict]], measured: dict, estimates: dict | None) -> dict:
    """Réglages du style de montage déduits des vidéos publiées.

    Ce qui est mesuré est proposé (case cochée) ; ce que Claude estime à partir de quelques images,
    sans entendre le son, est seulement indiqué (case à cocher soi-même).
    """
    out: dict = {}
    sources: dict = {}
    checked: list[str] = []
    durations = measured.get("durations") or []
    if durations:
        out["target_min_minutes"], out["target_max_minutes"] = duration_targets(durations)
        sources["target_min_minutes"] = sources["target_max_minutes"] = "mesuré"
        if max(durations) <= 1.5 * min(durations):  # durées trop dispersées : à décider soi-même
            checked += ["target_min_minutes", "target_max_minutes"]
        else:
            sources["target_min_minutes"] = sources["target_max_minutes"] = "mesuré (durées très différentes)"
    # Seuls les sons de la bibliothèque, posés tels quels, sont reconnus : c'est un minimum.
    if measured.get("sfx_checked") and _round_half(measured.get("sfx_rate") or 0) >= 0.5:
        out["sfx_per_minute"] = _round_half(measured["sfx_rate"])
        sources["sfx_per_minute"] = "mesuré (minimum : sons de la bibliothèque)"
        checked.append("sfx_per_minute")
    typical = {d.id for d in typical_docs([d for d, _ in analyses])}
    per_video = [a.get("estimates") or {} for d, a in analyses if d.id in typical and a.get("source") == "claude"]
    pooled = estimates or {}
    for field in ("zooms_per_minute", "texts_per_minute", "characters_per_minute"):
        values = [float(e[field]) for e in per_video if e.get(field)]
        value = pooled.get(field) or (statistics.mean(values) if values else None)
        if value:
            out[field] = _rate(float(value))
            sources[field] = "estimé par Claude (peu fiable)"
    if measured.get("music"):
        out["music"] = True
        sources["music"] = "mesuré (musique reconnue)"
        checked.append("music")
    else:
        votes = [flag(e.get("has_music")) for e in per_video] or [flag(pooled.get("has_music"))]
        if _majority(votes):  # jamais « non » : Claude n'entend pas le son
            out["music"] = True
            sources["music"] = "estimé par Claude (sans le son)"
    votes = [flag(e.get("cold_open")) for e in per_video] or [flag(pooled.get("cold_open"))]
    teaser = _majority(votes)
    if teaser is not None:
        out["cold_open"] = teaser
        sources["cold_open"] = "estimé par Claude"
    return {"values": out, "sources": sources, "checked": checked}


def _guide_block(doc: ReferenceDoc, analysis: dict) -> str:
    """Analyse d'une vidéo, résumée pour la rédaction du guide."""
    m = doc.state.metrics
    sfx = f"{m.get('sfx_per_min', 0):g} bruitages reconnus/min" if sfx_measured(m) else "bruitages non vérifiés"
    header = f"### Vidéo « {doc.state.name} » — {m.get('duration_min', 0):g} min, {m.get('cuts_per_min', 0):g} plans/min, {sfx}"
    if is_short(doc):
        header += " (format court, sûrement un Short)"
    compact = {k: (v[:900] if isinstance(v, str) else v) for k, v in analysis.items() if k not in ("source", "claude_error", "sfx_detector")}
    compact["rules"] = (analysis.get("rules") or [])[:12]
    compact["examples"] = (analysis.get("examples") or [])[:6]
    return header + "\n" + json.dumps(compact, ensure_ascii=False)


def build_guide(store: ReferenceStore, cfg: AppConfig, log: Callable[[str], None] | None = None) -> dict:
    """(Re)construit le guide de style à partir de toutes les vidéos analysées."""
    (store.root / "guide_erreur.txt").unlink(missing_ok=True)
    everything = store.analyses()
    analyses = [(d, a) for d, a in everything if not too_long(d)]  # une vidéo de plus d'1 h est un rush
    ignored = [d.state.name for d, _ in everything if too_long(d)]
    if not analyses:
        store.guide_md.unlink(missing_ok=True)
        store.guide_json.unlink(missing_ok=True)
        return {}
    measured_text, measured = measured_summary([d for d, _ in analyses])
    result, claude_error, left_out = None, "", []
    if claude_available(cfg) and any(a.get("source") == "claude" for _, a in analyses):
        blocks: list[str] = []
        budget = GUIDE_INPUT_MAX_CHARS
        for doc, a in reversed(analyses):  # si tout ne tient pas, les plus récentes d'abord
            block = _guide_block(doc, a)
            if blocks and len(block) > budget:
                left_out.append(doc.state.name)
                continue
            budget -= len(block)
            blocks.append(block)
        blocks.reverse()
        content = GUIDE_INSTRUCTIONS.format(count=len(blocks), analyses="\n\n".join(blocks) + "\n\nMESURES GLOBALES :\n" + measured_text)
        bible = channel_bible().strip()
        system = REFERENCE_SYSTEM + (f"\n\n## La chaîne (écrit par l'équipe)\n{bible}" if bible else "")
        llm = LLM(cfg, cache_dir=store.root / "claude_cache", log=log)
        try:
            result = llm.ask_json(system=system, content=content, schema=GUIDE_SCHEMA, effort="high", max_tokens=32000, label="guide")
        except LLMError as exc:  # jamais de guide périmé : on retombe sur les mesures des vidéos actuelles
            claude_error, left_out = str(exc), []
            if log:
                log(f"Claude indisponible pour le guide, guide tiré des mesures seules : {exc}")
    if result:
        text, examples, estimates, source = result["guide"], result["examples"], result["estimates"], "claude"
    else:
        rules: list[str] = []
        for _, a in analyses:
            for rule in a.get("rules") or []:
                if rule not in rules:
                    rules.append(rule)
        text = "## Format et rythme\n" + (measured_text or "- (pas de mesure)")
        if rules:
            text += "\n\n## Règles relevées\n" + "\n".join(f"- {r}" for r in rules[:20])
        examples = [{"video": d.state.name, **e} for d, a in analyses for e in (a.get("examples") or [])][:12]
        estimates, source = {}, "heuristic"
    data = {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "sources": [d.id for d, _ in analyses],
        "ignored": ignored,
        "shorts": measured["shorts"],
        "unusual": measured["unusual"],
        "claude_left_out": left_out,
        "claude_error": claude_error,
        "examples": examples,
        "estimates": estimates,
        "measured": measured_text,
        "suggested": suggested_style(analyses, measured, estimates),
    }
    atomic_write(store.guide_md, text.strip() + "\n")
    atomic_write(store.guide_json, json.dumps(data, ensure_ascii=False, indent=1))
    return data


def refresh_suggestions(store: ReferenceStore) -> bool:
    """Guide écrit par une version précédente : recalcule ses réglages suggérés (sans appeler Claude).

    Les anciens guides cochaient tout, y compris « musique : non » deviné par Claude.
    """
    guide = store.guide()
    if not guide or "checked" in (guide.get("suggested") or {}):
        return False
    analyses = [(d, a) for d, a in store.analyses() if not too_long(d)]
    if not analyses:
        return False
    measured_text, measured = measured_summary([d for d, _ in analyses])
    guide.pop("text", None)
    guide.update(
        measured=measured_text,
        shorts=measured["shorts"],
        unusual=measured["unusual"],
        suggested=suggested_style(analyses, measured, guide.get("estimates") or {}),
    )
    atomic_write(store.guide_json, json.dumps(guide, ensure_ascii=False, indent=1))
    return True


def guide_outdated(store: ReferenceStore) -> bool:
    """Une analyse s'est terminée après le guide (mise à jour du guide interrompue, par exemple)."""
    guide = store.guide()
    analyses = store.analyses()
    if not analyses:
        return guide is not None
    if not guide:
        return True
    try:
        updated = datetime.fromisoformat(guide.get("updated", "")).timestamp()
    except ValueError:
        return True
    return any((d.state.steps["analyze"].finished or 0) > updated + 1 for d, _ in analyses)


def needs_claude(doc: ReferenceDoc, analysis: dict) -> bool:
    """Analyse à refaire par Claude : faite sans lui, ou sur des bruitages mesurés par l'ancienne détection."""
    if analysis.get("source") != "claude":
        return True
    return bool(doc.state.metrics.get("sfx_checked")) and analysis.get("sfx_detector") != SFX_DETECTOR_VERSION


def remeasure_outdated_sfx(store: ReferenceStore) -> list[ReferenceDoc]:
    """Références mesurées par l'ancienne détection des bruitages : la recherche est à refaire (gratuit).

    L'analyse par Claude, elle, n'est refaite qu'à la demande (« Mettre à jour »), car elle est payante ;
    une analyse sans Claude est refaite tout de suite.
    """
    todo = []
    for doc in store.list():
        if doc.state.steps["sfx"].status == "done" and sfx_outdated(doc.state.metrics) and not too_long(doc):
            analysis = doc.read_json("analyse.json") or {}
            doc.invalidate(["sfx"] if analysis.get("source") == "claude" else ["sfx", "analyze"])
            todo.append(doc)
    return todo
