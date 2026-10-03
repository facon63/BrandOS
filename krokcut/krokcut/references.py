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

from .audio import Levels, level_curve, read_pcm
from .config import AppConfig, channel_bible, workspace_dir
from .ffmpeg_utils import extract_frame, extract_pcm, probe, run_ffmpeg
from .library import Library
from .llm import BOOL, LLM, NUM, STR, arr, claude_available, obj
from .project import slugify
from .prompts import GUIDE_INSTRUCTIONS, REFERENCE_ANALYSIS_INSTRUCTIONS, REFERENCE_SYSTEM
from .sfx_detect import detect_library_sounds
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
MAX_FRAMES_FOR_CLAUDE = 24
PROMPT_BLOCK_MAX_CHARS = 12000

ESTIMATES_SCHEMA = obj(
    {
        "zooms_per_minute": NUM,
        "texts_per_minute": NUM,
        "characters_per_minute": NUM,
        "has_music": BOOL,
        "cold_open": BOOL,
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
        if guide.get("measured"):
            parts.append("#### Mesures sur vos vidéos publiées\n" + guide["measured"])
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
    top = (m.get("sfx_top") or []) if m.get("sfx_checked") else []
    if top:
        rules.append("Bruitages les plus utilisés : " + ", ".join(f"{a} ({n}×)" for a, n in top[:6]) + ".")
    if m.get("sfx_checked") and m.get("music_used"):
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
        unchecked = {"sfx_checked": False, "sfx_hits": 0, "sfx_per_min": 0.0, "sfx_top": [], "music_used": []}
        if not library.of_kind("sfx", "music"):
            self.doc.write_json("bruitages.json", {"hits": [], "music": [], "skipped": 0, "unreliable": []})
            self.doc.set_metrics(**unchecked)
            return "Bibliothèque vide : rien à reconnaître (ajoute-la puis clique sur Réanalyser)"
        if self.duration > MAX_REFERENCE_MINUTES * 60:
            self.doc.write_json("bruitages.json", {"hits": [], "music": [], "skipped": 0, "unreliable": []})
            self.doc.set_metrics(**unchecked)
            return "Vidéo trop longue : étape sautée"
        signal = read_pcm(self.pcm, 0, self.duration)
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
            sfx_hits=len(result["hits"]),
            sfx_per_min=round(len(result["hits"]) / minutes, 1),
            sfx_top=[[asset, n] for asset, n in counts.most_common(10)],
            music_used=[m["asset"] for m in result["music"]],
        )
        extra = f", {len(result['music'])} musique(s)" if result["music"] else ""
        if result["skipped"]:
            extra += f" ({result['skipped']} sons non testés : bibliothèque très grande)"
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
        if claude_available(self.cfg):
            analysis = self.analyze_with_claude(lines, sfx)
        else:
            analysis = heuristic_analysis(self.doc, lines, sfx)
        self.doc.write_json("analyse.json", analysis)
        return "par Claude" if analysis["source"] == "claude" else "mesures seules (pas de clé Claude)"

    def analyze_with_claude(self, lines: list[dict], sfx: dict) -> dict:
        m = self.doc.state.metrics
        metrics_text = "\n".join(
            [
                f"- durée : {m.get('duration_min', 0):g} min",
                f"- changements de plan : {m.get('cuts_per_min', 0):g} par minute (plan médian {m.get('median_shot', 0):g} s)",
                f"- parole : {round(100 * m.get('speech_ratio', 0))} % du temps, {m.get('words_per_min', 0)} mots/min",
                (
                    f"- bruitages de la bibliothèque reconnus : {m.get('sfx_hits', 0)} ({m.get('sfx_per_min', 0):g}/min)"
                    if m.get("sfx_checked")
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


def measured_summary(docs: list[ReferenceDoc]) -> tuple[str, dict]:
    metrics = [d.state.metrics for d in docs]
    durations = [m["duration_min"] for m in metrics if m.get("duration_min")]
    videos = [m for m in metrics if m.get("height")]  # le rythme n'a de sens que pour une vraie vidéo
    cuts = _mean([m.get("cuts_per_min", 0) for m in videos])
    shot = _mean([m.get("median_shot") for m in videos])
    ratios = [m["speech_ratio"] for m in metrics if m.get("speech_ratio") is not None]
    speech = round(statistics.mean(ratios), 2) if ratios else None  # une part : pas d'arrondi au dixième
    checked = [m for m in metrics if m.get("sfx_checked")]
    sfx_rate = _mean([m.get("sfx_per_min", 0) for m in checked])
    top: Counter = Counter()
    music: Counter = Counter()
    for m in checked:
        for asset, n in m.get("sfx_top") or []:
            top[asset] += n
        music.update(m.get("music_used") or [])
    lines = []
    if durations:
        lines.append(f"- Durée : {min(durations):g} à {max(durations):g} min (moyenne {statistics.mean(durations):.1f}).")
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
    return "\n".join(lines), {"durations": durations, "sfx_rate": sfx_rate, "sfx_checked": bool(checked)}


def suggested_style(analyses: list[tuple[ReferenceDoc, dict]], measured: dict, estimates: dict | None) -> dict:
    """Réglages du style de montage déduits des vidéos publiées (mesurés ou estimés)."""
    out: dict = {}
    sources: dict = {}
    durations = measured.get("durations") or []
    if durations:
        lo, hi = min(durations), max(durations)
        out["target_min_minutes"] = float(max(3, round(lo - 1)))
        out["target_max_minutes"] = float(max(out["target_min_minutes"] + 2, round(hi + 1)))
        sources["target_min_minutes"] = sources["target_max_minutes"] = "mesuré"
    # Seuls les sons de la bibliothèque, posés tels quels, sont reconnus : c'est un minimum.
    if measured.get("sfx_checked") and _round_half(measured.get("sfx_rate") or 0) >= 0.5:
        out["sfx_per_minute"] = _round_half(measured["sfx_rate"])
        sources["sfx_per_minute"] = "mesuré (au moins : seuls les sons de la bibliothèque sont reconnus)"
    per_video = [a.get("estimates") or {} for _, a in analyses]
    pooled = estimates or {}
    for field in ("zooms_per_minute", "texts_per_minute", "characters_per_minute"):
        values = [e.get(field) for e in per_video if e.get(field)]
        value = pooled.get(field) or (statistics.mean(values) if values else None)
        if value:
            out[field] = _round_half(float(value))
            sources[field] = "estimé par Claude"
    for flag, field in (("has_music", "music"), ("cold_open", "cold_open")):
        votes = [bool(e[flag]) for e in per_video if flag in e]
        if votes:
            out[field] = sum(votes) * 2 >= len(votes)
            sources[field] = "estimé par Claude"
    return {"values": out, "sources": sources}


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
    use_claude = claude_available(cfg) and any(a.get("source") == "claude" for _, a in analyses)
    if use_claude:
        blocks = []
        for doc, a in analyses[-10:]:
            m = doc.state.metrics
            blocks.append(
                f"### Vidéo « {doc.state.name} » — {m.get('duration_min', 0):g} min, {m.get('cuts_per_min', 0):g} plans/min, "
                f"{m.get('sfx_per_min', 0):g} bruitages reconnus/min\n"
                + json.dumps({k: v for k, v in a.items() if k != "source"}, ensure_ascii=False)
            )
        content = GUIDE_INSTRUCTIONS.format(count=len(blocks), analyses="\n\n".join(blocks) + "\n\nMESURES GLOBALES :\n" + measured_text)
        bible = channel_bible().strip()
        system = REFERENCE_SYSTEM + (f"\n\n## La chaîne (écrit par l'équipe)\n{bible}" if bible else "")
        llm = LLM(cfg, cache_dir=store.root / "claude_cache", log=log)
        result = llm.ask_json(system=system, content=content, schema=GUIDE_SCHEMA, effort="high", max_tokens=32000, label="guide")
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
        "examples": examples,
        "estimates": estimates,
        "measured": measured_text,
        "suggested": suggested_style(analyses, measured, estimates),
    }
    atomic_write(store.guide_md, text.strip() + "\n")
    atomic_write(store.guide_json, json.dumps(data, ensure_ascii=False, indent=1))
    return data
