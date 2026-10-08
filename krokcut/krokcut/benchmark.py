"""Onglet « Comparer » : le montage de chaînes de référence mesuré comme le vôtre.

Chaque vidéo (Wankil Studio, Club Pungouin… et quelques vidéos de Krok et Mil) passe par exactement les
mêmes étapes : mesures locales gratuites (image, son, transcription), planches d'images, puis — après
validation du coût — Claude regarde les planches extrait par extrait, à l'aveugle (« Vidéo V3 »), et
décrit comment la vidéo est montée. Le programme compte ; Claude ne donne jamais de chiffres.

Les modules de mesure (vision, soundscan, sheets) sont importés au premier usage, par leur nom complet :
les tests les remplacent dans sys.modules.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import re
import shutil
import statistics
import threading
import unicodedata
from bisect import bisect_left
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from . import techniques
from .audio import Levels, level_curve
from .config import AppConfig, workspace_dir
from .ffmpeg_utils import FFmpegError, extract_pcm, probe, run_ffmpeg
from .llm import (
    INT,
    LLM,
    NUM,
    PRICE_CACHE_READ,
    PRICE_CACHE_WRITE,
    PRICE_IN,
    PRICE_OUT,
    STR,
    LLMError,
    arr,
    claude_available,
    enum,
    obj,
)
from .project import slugify
from .prompts import BENCH_SYSTEM, INSPIRATION_HEADER, OBSERVE_INSTRUCTIONS, VIDEO_INSTRUCTIONS
from .references import (
    ReferenceDoc,
    ReferenceStore,
    WordsProvider,
    atomic_write,
    file_signature,
    sfx_measured,
    speech_ratio,
)
from .steps import Cancelled, Skipped, StepDoc, StepRunner, StepStatus
from .transcribe import build_lines, transcribe_mix

BENCH_STEPS: list[tuple[str, str]] = [
    ("probe", "Lecture du fichier"),
    ("audio", "Extraction du son et du volume"),
    ("image", "Analyse de l'image (plans, zooms, flashs)"),
    ("transcribe", "Transcription"),
    ("sound", "Analyse du son (bruitages, musique, silences)"),
    ("sheets", "Planches d'images pour Claude"),
    ("observe", "Claude regarde la vidéo"),
    ("synthesize", "Synthèse de la vidéo"),
]
BENCH_STEP_IDS = [s for s, _ in BENCH_STEPS]
LOCAL_STEPS = BENCH_STEP_IDS[:6]
CLAUDE_STEPS = ["observe", "synthesize"]
OBSERVE_VERSION = 1  # change si les consignes ou le schéma de la lecture par Claude changent

Quality = Literal["eco", "standard", "detaille"]
Role = Literal["modele", "nous", "krokcut"]
Intensity = Literal["un_peu", "mi_chemin", "comme_eux"]
ALPHA = {"un_peu": 1 / 3, "mi_chemin": 0.5, "comme_eux": 1.0}
QUALITY_LABELS = {"eco": "Économique", "standard": "Standard", "detaille": "Détaillée"}
ROLE_LABELS = {"modele": "chaîne modèle", "nous": "nos vidéos", "krokcut": "montages KrokCut"}
DEFAULT_CHANNELS = (
    ("wankil-studio", "Wankil Studio", "modele", ""),
    ("club-pungouin", "Club Pungouin", "modele", ""),
    ("krok-et-mil", "Krok et Mil", "nous", "Krok, Mil"),
)
KROKCUT_CHANNEL_NAME = "Montages KrokCut"

MAX_MINUTES = 60  # au-delà, sûrement un live ou un rush
SHORT_MINUTES = 3  # en dessous, un Short : exclu des chiffres et de Claude par défaut

# Passes Claude
OBSERVE_EFFORT = {"eco": "low", "standard": "medium", "detaille": "medium"}  # si sheets.PRESETS ne le dit pas
OBSERVE_MAX_TOKENS = 32000
VIDEO_MAX_TOKENS = 32000
SPLIT_KINDS = ("tronque", "json", "refus")  # erreurs qui se règlent en coupant l'extrait en deux
BUDGET_FACTOR = 1.5  # pause si la dépense dépasse 1,5 × le coût approuvé
CONTEXT_S = 20.0  # transcription donnée en contexte avant chaque extrait
MAX_SOUND_LINES = 120  # sons listés par extrait (les plus marquants) ; le reste est résumé
MAX_SHEETS_PER_CALL = 14
MAX_REQUEST_B64 = 24 * 1024 * 1024  # au-delà, planches réencodées plus compressées
SHRINK_JPEG_Q = 6
SYNTH_OCCURRENCES_PER_CHUNK = 80
SYNTH_TOP_GAGS = 10
SYNTH_INTRO_S = 60.0
SYNTH_MEASURES = (  # mesures données à la synthèse, en clair
    ("cuts_per_min", "changements de plan", "/min"),
    ("median_shot", "durée médiane d'un plan", " s"),
    ("shots_under_1s_pct", "plans de moins d'1 s", " %"),
    ("jump_cut_pct", "jump cuts probables", " %"),
    ("punch_ins_per_min", "zooms secs mesurés", "/min"),
    ("zoom_scale_median", "grossissement médian des zooms", "×"),
    ("flashes_per_min", "flashs", "/min"),
    ("freezes_per_min", "images figées", "/min"),
    ("sound_events_per_min", "sons marquants (jeu compris)", "/min"),
    ("music_pct", "musique détectée", " % du temps"),
    ("silences_per_10min", "silences complets", " par 10 min"),
    ("pause_p90", "blancs entre les mots (90 % font moins de)", " s"),
    ("reaction_tail_median", "respiration après la dernière phrase d'un plan", " s"),
    ("speech_ratio", "part du temps avec de la parole", ""),
    ("words_per_min", "débit de parole", " mots/min"),
    ("loudness_i", "volume moyen", " LUFS"),
    ("loudness_lra", "écarts de volume", " LU"),
)

# Estimation du coût (§5.8)
CHARS_PER_TOKEN = 3.2
SYSTEM_TOKENS = 4000
SYNTH_INPUT_TOKENS = {"eco": 25000, "standard": 35000, "detaille": 45000}
SYNTH_OUTPUT_TOKENS = {"eco": 8000, "standard": 10000, "detaille": 12000}
DEFAULT_OUTPUT_PER_CHUNK = {"eco": 6000.0, "standard": 10000.0, "detaille": 11000.0}
CALIB_WEIGHT = 0.3  # moyenne glissante des tokens de sortie réellement observés
ESTIMATE_LOW, ESTIMATE_HIGH = 0.7, 1.4
QUALITY_USD_PER_MIN = {"eco": 0.075, "standard": 0.15, "detaille": 0.285}  # avant les planches (≈ 1,5 / 3 / 5,7 $ pour 20 min)

# Comptes déterministes (§5.4)
DEDUP_TEXT_S = 2.0  # même technique et même texte à l'écran
DEDUP_PLAIN_S = 0.5  # même technique sans texte
ZOOM_MATCH_S = 0.35  # une occurrence de zoom à côté d'un Z confirmé est ce même zoom
MAX_EXAMPLES = 6
FORCE_RANGE = (1, 5)

INSPIRATION_MAX_CHARS = 5000
HALLUCINATIONS = re.compile(r"amara\.org|sous-titr(?:es|age) (?:réalisés|par)", re.I)
ID_RE = re.compile(r"^(?:T\d{4,}|[LPZFGNBSMC]\d+)$")
VERDICT_PREFIXES = ("S", "M", "Z")

_SETTINGS_LOCK = threading.RLock()
_DEFAULT_VAD = object()  # « détecteur de parole par défaut de soundscan »


def _media(name: str):
    """vision, soundscan ou sheets, importés au premier usage (remplaçables dans sys.modules par les tests)."""
    return importlib.import_module(f"{__package__}.{name}")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ modèles
class BenchChannel(BaseModel):
    id: str
    name: str
    role: Role = "modele"
    members: str = ""  # « Laink, Terracid » : donné seulement aux passes chaîne et comparaison
    added: str


class BenchSettings(BaseModel):
    quality: Quality = "standard"
    intensity: Intensity = "mi_chemin"
    targets: list[str] = []  # chaînes modèles visées par les réglages ([] = toutes)
    auto_claude: bool = False  # True : Claude démarre sans validation après les mesures
    channels: list[BenchChannel] = []
    calib_output: dict[str, float] = {}  # qualité -> tokens de sortie moyens par extrait
    report_cost: dict = Field(default_factory=lambda: {"usd": 0.0, "calls": 0})
    next_blind: int = 1  # compteur des « V<n> », jamais réutilisé


class BenchState(BaseModel):
    id: str
    name: str
    channel: str
    path: str
    added: str
    copied: bool = False  # fichier (ou lien dur) dans comparaison/fichiers : supprimé avec la vidéo
    signature: str = ""
    origin: Literal["depot", "disque", "mes_videos"] = "depot"
    origin_id: str = ""  # id « Mes vidéos »
    blind_id: str = ""  # « V7 », seul nom donné à Claude dans les passes vidéo
    steps: dict[str, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in BENCH_STEP_IDS})
    metrics: dict = Field(default_factory=dict)
    instrument: dict = Field(default_factory=dict)
    claude_ok: bool = False  # coût approuvé (ou auto_claude)
    approved_usd: float = 0.0  # fourchette haute au moment de l'approbation
    approved_at_usd: float = 0.0  # déjà dépensé au moment de l'approbation (le garde-fou compte à partir de là)
    estimate: dict = Field(default_factory=dict)
    claude: dict = Field(
        default_factory=lambda: {"usd": 0.0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}
    )
    coverage: float = 0.0  # part de la durée réellement regardée par Claude
    failed_chunks: list[int] = []
    last_error: str = ""
    edits: int = 0  # changements faits depuis l'interface (chaîne…) : un traitement en cours ne les écrase pas


# Champs changés depuis l'interface, éventuellement pendant qu'un traitement tourne sur la vidéo (« Déplacer
# vers… » pendant les mesures) : le traitement, qui garde son propre état en mémoire, les reprend du disque.
EDITABLE_FIELDS = ("channel", "copied")


class BenchDoc(StepDoc):
    STATE_FILE = "video.json"
    INTERRUPTED_MSG = "Interrompu (KrokCut a été fermé) : clique sur Reprendre"
    state_model = BenchState
    step_ids = BENCH_STEP_IDS
    state: BenchState

    @property
    def id(self) -> str:
        return self.state.id

    def save(self) -> None:
        with self._lock:
            try:
                disk = json.loads((self.root / self.STATE_FILE).read_text("utf-8"))
            except (OSError, ValueError):
                disk = {}
            if int(disk.get("edits") or 0) > self.state.edits:  # modifiée ailleurs depuis notre lecture
                for key in EDITABLE_FIELDS:
                    if key in disk:
                        setattr(self.state, key, disk[key])
                self.state.edits = int(disk["edits"])
            super().save()

    def edit(self, **fields) -> None:
        """Changement venu de l'interface : relu depuis le disque, appliqué, et jamais écrasé ensuite par un
        traitement qui tournerait sur la vidéo."""
        unknown = set(fields) - set(EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"Champs non modifiables : {', '.join(sorted(unknown))}")
        with self._lock:
            self.reload()
            for key, value in fields.items():
                setattr(self.state, key, value)
            self.state.edits += 1
            super().save()

    def set_metrics(self, **values) -> None:
        with self._lock:
            self.state.metrics.update(values)
            self.save()

    def set_instrument(self, **values) -> None:
        with self._lock:
            self.state.instrument.update(values)
            self.save()


# ------------------------------------------------------------------ stockage
def _default_settings() -> BenchSettings:
    added = now_iso()
    return BenchSettings(
        channels=[BenchChannel(id=c, name=n, role=r, members=m, added=added) for c, n, r, m in DEFAULT_CHANNELS]
    )


class BenchmarkStore:
    def __init__(self, root: Path | None = None):
        self.root = root or (workspace_dir() / "comparaison")
        self.root.mkdir(parents=True, exist_ok=True)
        with _SETTINGS_LOCK:
            if not self.settings_path.exists():
                self.save_settings(_default_settings())

    @property
    def settings_path(self) -> Path:
        return self.root / "etude.json"

    @property
    def files_dir(self) -> Path:
        path = self.root / "fichiers"
        path.mkdir(exist_ok=True)
        return path

    @property
    def videos_dir(self) -> Path:
        path = self.root / "videos"
        path.mkdir(exist_ok=True)
        return path

    # ------------------------------------------------------------ réglages
    def settings(self) -> BenchSettings:
        try:
            return BenchSettings.model_validate_json(self.settings_path.read_text("utf-8"))
        except (OSError, ValueError):  # fichier abîmé : on repart des valeurs par défaut (sans l'écraser)
            return _default_settings()

    def save_settings(self, s: BenchSettings) -> None:
        with _SETTINGS_LOCK:
            atomic_write(self.settings_path, s.model_dump_json(indent=2))

    # ------------------------------------------------------------- chaînes
    def channel(self, cid: str) -> BenchChannel:
        for c in self.settings().channels:
            if c.id == cid:
                return c
        raise KeyError(f"Chaîne inconnue : {cid}")

    def own_channel(self) -> BenchChannel:
        s = self.settings()
        own = next((c for c in s.channels if c.role == "nous"), None)
        if own is None:  # ne devrait jamais arriver : on la recrée
            own = self.add_channel("Krok et Mil", "nous", "Krok, Mil")
        return own

    def add_channel(self, name: str, role: Role = "modele", members: str = "") -> BenchChannel:
        name = (name or "").strip() or (KROKCUT_CHANNEL_NAME if role == "krokcut" else "Nouvelle chaîne")
        with _SETTINGS_LOCK:
            s = self.settings()
            if role in ("nous", "krokcut") and any(c.role == role for c in s.channels):
                what = "« nos vidéos »" if role == "nous" else "« Montages KrokCut »"
                raise ValueError(f"Il y a déjà une colonne {what}.")
            base = slugify(name)[:40]
            cid, i = base, 2
            while any(c.id == cid for c in s.channels):
                cid, i = f"{base}-{i}", i + 1
            channel = BenchChannel(id=cid, name=name, role=role, members=members.strip(), added=now_iso())
            s.channels.append(channel)
            self.save_settings(s)
        return channel

    def update_channel(self, cid: str, *, name: str | None = None, members: str | None = None) -> BenchChannel:
        with _SETTINGS_LOCK:
            s = self.settings()
            channel = next((c for c in s.channels if c.id == cid), None)
            if channel is None:
                raise KeyError(f"Chaîne inconnue : {cid}")
            if name is not None and name.strip():
                channel.name = name.strip()
            if members is not None:
                channel.members = members.strip()
            self.save_settings(s)
        return channel

    def remove_channel(self, cid: str, with_videos: bool = False) -> None:
        channel = self.channel(cid)
        if channel.role == "nous":
            raise ValueError("La colonne de vos vidéos ne se supprime pas (tu peux la renommer).")
        videos = self.videos_of(cid)
        if videos and not with_videos:
            raise ValueError(f"« {channel.name} » contient {len(videos)} vidéo(s) : retire-les d'abord.")
        for doc in videos:
            self.remove(doc.id)
        with _SETTINGS_LOCK:
            s = self.settings()
            s.channels = [c for c in s.channels if c.id != cid]
            s.targets = [t for t in s.targets if t != cid]
            self.save_settings(s)
        (self.root / "profils" / f"{cid}.json").unlink(missing_ok=True)

    # -------------------------------------------------------------- vidéos
    def list(self) -> list[BenchDoc]:
        docs = []
        for path in sorted(self.videos_dir.iterdir()):
            if (path / BenchDoc.STATE_FILE).exists():
                try:
                    docs.append(BenchDoc(path))
                except Exception:  # vidéo abîmée : ignorée
                    continue
        docs.sort(key=lambda d: (d.state.added, d.id))
        return docs

    def videos_of(self, cid: str) -> list[BenchDoc]:
        return [d for d in self.list() if d.state.channel == cid]

    def open(self, vid: str) -> BenchDoc:
        root = self.videos_dir / Path(vid).name
        if not (root / BenchDoc.STATE_FILE).exists():
            raise FileNotFoundError(f"Vidéo de comparaison introuvable : {vid}")
        return BenchDoc(root)

    def find_duplicate(self, path: Path, signature: str) -> BenchDoc | None:
        """Même fichier ou même contenu, toutes chaînes confondues."""
        for doc in self.list():
            known = Path(doc.state.path)
            if known == path:
                return doc
            other = doc.state.signature
            if not other and known.is_file():
                other = file_signature(known)
                doc.state.signature = other
                doc.save()
            if other and other == signature:
                return doc
        return None

    def _create(self, path: Path, channel: str, *, name: str, origin: str, copied: bool, signature: str, origin_id: str = "") -> BenchDoc:
        with _SETTINGS_LOCK:
            s = self.settings()
            blind = f"V{s.next_blind}"
            s.next_blind += 1
            self.save_settings(s)
        base = slugify(name)[:60]
        vid, i = base, 2
        while (self.videos_dir / vid).exists():
            vid, i = f"{base}-{i}", i + 1
        root = self.videos_dir / vid
        root.mkdir(parents=True)
        state = BenchState(
            id=vid,
            name=name,
            channel=channel,
            path=str(path),
            added=now_iso(),
            copied=copied,
            signature=signature,
            origin=origin,
            origin_id=origin_id,
            blind_id=blind,
        )
        (root / BenchDoc.STATE_FILE).write_text(state.model_dump_json(indent=2), "utf-8")
        return BenchDoc(root)

    def add_or_get(self, path: str | Path, channel: str, origin: str = "depot") -> tuple[BenchDoc, bool]:
        """Ajoute une vidéo ; (vidéo, nouvelle ?). Déjà présente (toutes chaînes) : la vidéo existante."""
        self.channel(channel)  # KeyError si la chaîne n'existe pas
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {path}")
        signature = file_signature(path)
        in_workspace = self.files_dir.resolve() in path.parents
        existing = self.find_duplicate(path, signature)
        if existing:
            if in_workspace and Path(existing.state.path) != path:  # copie déposée une 2e fois : inutile
                path.unlink(missing_ok=True)
            return existing, False
        doc = self._create(path, channel, name=path.stem, origin=origin, copied=in_workspace, signature=signature)
        return doc, True

    def _free_name(self, name: str) -> Path:
        dst = self.files_dir / name
        stem, suffix, i = dst.stem, dst.suffix, 2
        while dst.exists():
            dst = self.files_dir / f"{stem}-{i}{suffix}"
            i += 1
        return dst

    def import_reference(
        self, ref: ReferenceDoc, cfg: AppConfig, channel: str | None = None, move: bool = False
    ) -> tuple[BenchDoc, bool]:
        """Reprend une vidéo de « Mes vidéos » : même instrument, son et transcription réutilisés (§1.5).

        move=True la retire ensuite de « Mes vidéos » (une vidéo d'une autre chaîne n'a rien à faire dans
        le guide de VOTRE style) ; le fichier est gardé par un lien dur ou une copie.
        """
        cid = channel or self.own_channel().id
        self.channel(cid)
        src = Path(ref.state.path)
        existing = next((d for d in self.list() if d.state.origin == "mes_videos" and d.state.origin_id == ref.id), None)
        if existing is None and src.is_file():
            existing = self.find_duplicate(src.resolve(), ref.state.signature or file_signature(src))
        if existing is not None:
            if move:
                self._detach_reference(ref, existing)
            return existing, False
        if not src.is_file():
            raise FileNotFoundError(f"Fichier d'origine introuvable (déplacé ou supprimé ?) : {src}")
        dst = self._free_name(src.name)
        try:
            os.link(src, dst)
            path, copied = dst, True
        except OSError:
            if move and ref.state.copied:  # la copie de « Mes vidéos » va disparaître avec elle : on la garde
                shutil.copy2(src, dst)
                path, copied = dst, True
            else:
                path, copied = src.resolve(), False
        doc = self._create(
            path,
            cid,
            name=ref.state.name,
            origin="mes_videos",
            copied=copied,
            signature=ref.state.signature or file_signature(path),
            origin_id=ref.id,
        )
        for name in ("audio.pcm", "niveaux.npy"):  # l'étape « audio » voit qu'ils existent
            _link_or_copy(ref.root / name, doc.root / name)
        model = whisper_model(cfg)
        transcript = ref.read_json("transcription.json") or {}
        if ref.state.metrics.get("whisper_model") == model and transcript.get("lines") is not None:
            doc.write_json("transcription.json", {"lines": transcript["lines"], "whisper_model": model, "reused_from": ref.id})
        if sfx_measured(ref.state.metrics):  # sert seulement à mesurer le rappel du détecteur sur vos bruitages
            hits = (ref.read_json("bruitages.json") or {}).get("hits") or []
            doc.write_json(
                "bibliotheque.json",
                {
                    "hits": [{"t": h["t"], "asset": h.get("asset", "")} for h in hits],
                    "sfx_per_min": ref.state.metrics.get("sfx_per_min", 0.0),
                },
            )
        if move:
            self._detach_reference(ref, doc)
        return doc, True

    def _detach_reference(self, ref: ReferenceDoc, doc: BenchDoc) -> None:
        """Retire la vidéo de « Mes vidéos », sans perdre le fichier dont dépend la comparaison."""
        if ref.state.copied and Path(doc.state.path).resolve() == Path(ref.state.path).resolve():
            # La comparaison lit la copie faite par « Mes vidéos » (lien dur impossible à l'import) : elle en
            # devient propriétaire (effacée avec la vidéo de comparaison), « Mes vidéos » ne l'efface pas.
            ref.state.copied = False
            ref.save()
            doc.edit(copied=True)
        ReferenceStore(ref.root.parent).remove(ref.id)

    def move(self, vid: str, channel: str) -> None:
        """Vers une autre chaîne : rien à remesurer (le rapport devient seulement périmé)."""
        self.channel(channel)
        self.open(vid).edit(channel=channel)

    @property
    def owned_dirs(self) -> tuple[Path, ...]:
        """Dossiers dont KrokCut peut effacer les fichiers : ses copies, jamais les fichiers de l'utilisateur."""
        return (self.files_dir.resolve(), (self.root.parent / "references" / "fichiers").resolve())

    def remove(self, vid: str) -> None:
        doc = self.open(vid)
        if doc.state.copied:
            path = Path(doc.state.path).resolve()
            mine, refs = self.owned_dirs
            if mine in path.parents or (refs in path.parents and not self._used_by_reference(path)):
                path.unlink(missing_ok=True)
        shutil.rmtree(doc.root, ignore_errors=True)

    def _used_by_reference(self, path: Path) -> bool:
        refs = self.root.parent / "references"
        if not refs.is_dir():
            return False
        return any(Path(r.state.path).resolve() == path for r in ReferenceStore(refs).list())


def _link_or_copy(src: Path, dst: Path) -> bool:
    if not src.is_file() or dst.exists():
        return False
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return True


def duplicate_info(store: BenchmarkStore, doc: BenchDoc) -> dict:
    """Pour l'interface : « Déjà présente dans « Wankil Studio » »."""
    try:
        channel_name = store.channel(doc.state.channel).name
    except KeyError:
        channel_name = doc.state.channel
    return {"id": doc.id, "name": doc.state.name, "channel": doc.state.channel, "channel_name": channel_name}


# ------------------------------------------------------------ empreintes
def whisper_model(cfg: AppConfig) -> str:
    return cfg.references_whisper_model or cfg.whisper.model


def local_fp(doc: BenchDoc) -> tuple:
    i = doc.state.instrument
    return (i.get("image"), i.get("sound"), i.get("whisper"))


def current_local_fp(cfg: AppConfig) -> tuple:
    return (_media("vision").IMAGE_VERSION, _media("soundscan").SOUND_VERSION, whisper_model(cfg))


def claude_fp(doc: BenchDoc) -> tuple:
    i = doc.state.instrument
    return (i.get("sheets"), i.get("quality"), i.get("observe"), i.get("model"))


def current_claude_fp(cfg: AppConfig, settings: BenchSettings) -> tuple:
    return (_media("sheets").SHEETS_VERSION, settings.quality, OBSERVE_VERSION, cfg.model)


def _store_of(doc: BenchDoc) -> BenchmarkStore:
    return BenchmarkStore(doc.root.parent.parent)


def outdated_local(doc: BenchDoc, cfg: AppConfig, settings: BenchSettings | None = None) -> list[str]:
    """Étapes à refaire parce que l'instrument a changé (version des mesures, modèle, qualité, fichier)."""
    st, ins = doc.state.steps, doc.state.instrument

    def done(step: str) -> bool:
        return st[step].status in ("done", "skipped")

    src = Path(doc.state.path)
    if doc.state.signature and done("probe") and src.is_file():
        try:
            if file_signature(src) != doc.state.signature:  # autre fichier au même endroit : tout est à refaire
                return list(BENCH_STEP_IDS)
        except OSError:
            pass
    image_v, sound_v, whisper = current_local_fp(cfg)
    reset: set[str] = set()
    if done("image") and ins.get("image") != image_v:
        reset |= {"image", "sound", "sheets", "observe", "synthesize"}
    if done("sound") and ins.get("sound") != sound_v:
        reset |= {"sound", "sheets", "observe", "synthesize"}
    if done("transcribe") and ins.get("whisper") != whisper:
        reset |= {"transcribe", "sound", "sheets", "observe", "synthesize"}
    settings = settings or _store_of(doc).settings()
    sheets_v, quality, observe_v, model = current_claude_fp(cfg, settings)
    if done("sheets") and (ins.get("sheets") != sheets_v or ins.get("quality") != quality):
        reset |= {"sheets", "observe", "synthesize"}
    if st["observe"].status == "done" and (ins.get("observe") != observe_v or ins.get("model") != model):
        reset |= {"observe", "synthesize"}
    if "sheets" in reset and "image" not in reset and not (doc.root / "images4").is_dir():
        reset.add("image")  # les images candidates ont été supprimées après la synthèse
    return [s for s in BENCH_STEP_IDS if s in reset]


def invalidate_outdated(doc: BenchDoc, cfg: AppConfig, settings: BenchSettings | None = None) -> list[str]:
    """Applique outdated_local : remet ces étapes à zéro. Une analyse Claude faite avec l'ancien instrument
    est à refaire, mais seulement après une nouvelle validation du coût."""
    steps = outdated_local(doc, cfg, settings)
    if not steps:
        return []
    claude_done = any(doc.state.steps[s].status == "done" for s in CLAUDE_STEPS if s in steps)
    if "probe" in steps:  # autre fichier : le son et la transcription de l'ancien ne valent plus rien
        for name in ("audio.pcm", "niveaux.npy", "transcription.json", "bibliotheque.json"):
            (doc.root / name).unlink(missing_ok=True)
        try:
            doc.state.signature = file_signature(Path(doc.state.path))
        except OSError:
            pass
    if "observe" in steps:  # lu par Claude avec l'ancien instrument : à refaire (le cache LLM évite de repayer l'identique)
        shutil.rmtree(doc.root / "observations", ignore_errors=True)
        (doc.root / "profil.json").unlink(missing_ok=True)
    doc.invalidate(steps)
    if claude_done:
        with doc._lock:
            doc.state.claude_ok = False
            doc.save()
    doc.log(f"Mesures à refaire (instrument changé) : {', '.join(steps)}")
    return steps


def approve_claude(doc: BenchDoc) -> None:
    """« Analyser avec Claude » : coût validé (fourchette haute) ; le garde-fou compte à partir d'ici."""
    with doc._lock:
        doc.state.claude_ok = True
        doc.state.approved_usd = float(doc.state.estimate.get("high") or 0.0)
        doc.state.approved_at_usd = float(doc.state.claude.get("usd") or 0.0)
        doc.save()


def reset_claude(doc: BenchDoc) -> None:
    """« Refaire l'analyse Claude » : observe et synthesize à refaire, extraits déjà lus oubliés.

    (Sur des planches et des textes identiques, le cache de LLM.ask_json rend la relecture gratuite.)
    """
    shutil.rmtree(doc.root / "observations", ignore_errors=True)
    (doc.root / "profil.json").unlink(missing_ok=True)
    doc.invalidate(CLAUDE_STEPS)
    with doc._lock:
        doc.state.failed_chunks = []
        doc.state.coverage = 0.0
        doc.save()


def claude_analysed(doc: BenchDoc) -> bool:
    if doc.state.steps["synthesize"].status != "done":
        return False
    return (doc.read_json("profil.json") or {}).get("source") == "claude"


def quality_change_usd(store: BenchmarkStore, quality: str) -> float:
    """Coût approximatif de la nouvelle analyse Claude de toutes les vidéos déjà analysées."""
    rate = QUALITY_USD_PER_MIN.get(quality, QUALITY_USD_PER_MIN["standard"])
    return round(sum((d.state.metrics.get("duration_min") or 0) * rate for d in store.list() if claude_analysed(d)), 2)


def set_quality(store: BenchmarkStore, cfg: AppConfig, quality: str) -> list[BenchDoc]:
    """Change la précision de toute l'étude (c'est l'instrument) ; renvoie les vidéos remises à zéro."""
    with _SETTINGS_LOCK:
        s = store.settings()
        s.quality = quality
        store.save_settings(s)
    touched = []
    for doc in store.list():
        if invalidate_outdated(doc, cfg, s):
            touched.append(doc)
    return touched


def startup_plan(store: BenchmarkStore, cfg: AppConfig) -> list[tuple[str, str | None]]:
    """Au démarrage : traitements coupés remis en attente, instrument vérifié, puis ce qu'il faut relancer.

    Renvoie [(id, until)] : until="sheets" pour les mesures locales (gratuites) ; None pour finir une
    analyse Claude déjà validée.
    """
    plan: list[tuple[str, str | None]] = []
    for doc in store.list():
        doc.recover_interrupted()
        try:
            invalidate_outdated(doc, cfg)
        except Exception as exc:  # module de mesure absent ou fichier illisible : on n'empêche pas le démarrage
            doc.log(f"Vérification de l'instrument impossible : {exc}")
        st = doc.state.steps
        if any(s.status == "error" for s in st.values()):
            continue
        if any(st[s].status == "pending" for s in LOCAL_STEPS):
            plan.append((doc.id, "sheets"))
        elif doc.state.claude_ok and claude_todo(doc, cfg):
            plan.append((doc.id, None))
    return plan


# ------------------------------------------------------------ mise en forme
def fmt_t(t: float) -> str:
    """9:12.4 (ou 1:02:03.4)."""
    t = max(0.0, float(t))
    tenths = int(round(t * 10))
    s10 = tenths % 600
    minutes = tenths // 600
    h, m = divmod(minutes, 60)
    sec = f"{s10 // 10:02d}.{s10 % 10}"
    return f"{h}:{m:02d}:{sec}" if h else f"{m}:{sec}"


def fmt_duration(t: float) -> str:
    """19:42 (ou 1:02:03)."""
    t = int(round(max(0.0, float(t))))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fr(x: float, nd: int = 1) -> str:
    """Nombre à la française : 1,25 ; −14,1."""
    text = f"{float(x):.{nd}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",").replace("-", "−")


def signed_db(x: float) -> str:
    return ("+" if x >= 0 else "") + fr(x, 0)


def norm_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def drop_hallucinations(lines: list[dict]) -> list[dict]:
    """Whisper invente parfois des crédits de sous-titrage sur les blancs ou la musique."""
    return [l for l in lines if not HALLUCINATIONS.search(l.get("text") or "")]


def _windows(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("windows") or data.get("fenetres") or []
    return []


def _line_words(lines: list[dict]) -> list[dict]:
    return [{"w": w, "s": s, "e": e} for l in lines for w, s, e in (l.get("words") or [])]


def _union_length(spans: list[tuple[float, float]], t0: float, t1: float) -> float:
    spans = sorted((max(t0, s), min(t1, e)) for s, e in spans if e > t0 and s < t1)
    total, cur_s, cur_e = 0.0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


# ------------------------------------------------------------ données d'une vidéo
class VideoData:
    """Tout ce qu'ont écrit les étapes locales, chargé une fois."""

    def __init__(self, doc: BenchDoc):
        r = doc.read_json
        self.duration = float(doc.state.metrics.get("duration_s") or 0.0)
        plans = r("plans.json") or {}
        self.plans: list[dict] = plans.get("plans") or []
        self.cuts: list[dict] = plans.get("cuts") or []
        self.image_events: list[dict] = (r("image_evenements.json") or {}).get("events") or []
        self.sound_events: list[dict] = (r("son_evenements.json") or {}).get("events") or []
        music = r("musique.json") or {}
        self.music: list[dict] = music.get("segments") or []
        self.silences: list[dict] = (r("silences.json") or {}).get("silences") or []
        self.rhythm: list[dict] = _windows(r("rythme.json"))
        self.lines: list[dict] = (r("transcription.json") or {}).get("lines") or []
        self.planches: dict = r("planches.json") or {}
        self.tiles: list[dict] = self.planches.get("tiles") or []
        self.sheets: list[dict] = self.planches.get("sheets") or []
        self.chunks: list[dict] = self.planches.get("chunks") or []
        self.tiles_by_id = {t["id"]: t for t in self.tiles}
        self.tiles_by_sheet: dict[int, list[dict]] = defaultdict(list)
        for t in self.tiles:
            self.tiles_by_sheet[t.get("sheet", -1)].append(t)
        self.sheets_by_n = {s["n"]: s for s in self.sheets}
        self.root = doc.root

    def sheet_tiles(self, sheet_ns: list[int]) -> list[dict]:
        return sorted((t for n in sheet_ns for t in self.tiles_by_sheet.get(n, [])), key=lambda t: (t["t"], t["id"]))

    def plans_between(self, t0: float, t1: float) -> list[dict]:
        return [p for p in self.plans if p["end"] > t0 and p["start"] < t1]


def nearest_tile(tiles: list[dict], times: list[float], t: float) -> dict | None:
    if not tiles:
        return None
    i = bisect_left(times, t)
    best = min((j for j in (i - 1, i) if 0 <= j < len(tiles)), key=lambda j: abs(times[j] - t))
    return tiles[best]


# ------------------------------------------------------------ requêtes « observe »
def chunk_parts(chunk: dict, data: VideoData) -> list[dict] | None:
    """Les deux moitiés (en planches) d'un extrait, chacune avec son intervalle de temps."""
    sheets = list(chunk.get("sheets") or [])
    if len(sheets) < 2:
        return None
    half = len(sheets) // 2
    first = data.sheets_by_n.get(sheets[half], {})
    tb = float(first.get("t0", (chunk["t0"] + chunk["t1"]) / 2))
    tiles_b = data.sheet_tiles(sheets[half:])
    if tiles_b:
        tb = min(tb, tiles_b[0]["t"])
    return [
        {**chunk, "t0": chunk["t0"], "t1": tb, "sheets": sheets[:half], "part": "a"},
        {**chunk, "t0": tb, "t1": chunk["t1"], "sheets": sheets[half:], "part": "b"},
    ]


def _sheet_image(path: Path, shrink: bool) -> bytes:
    if not shrink:
        return path.read_bytes()
    small = path.parent / "compressees" / path.name
    if not small.exists():
        small.parent.mkdir(exist_ok=True)
        try:
            run_ffmpeg(["-i", str(path), "-q:v", str(SHRINK_JPEG_Q), str(small)])
        except FFmpegError:
            return path.read_bytes()
    return small.read_bytes()


def _sound_line(e: dict, tile: str) -> str:
    db = e.get("peak_vs_voice_db")
    level = ""
    if db is not None:
        if db >= 6:
            level = f"fort ({signed_db(db)} dB sur les voix)"
        elif db >= -6:
            level = f"au niveau des voix ({signed_db(db)} dB)"
        else:
            level = f"discret ({signed_db(db)} dB sous les voix)"
    parts = [f"[{fmt_t(e['t'])}] {e['id']} {e.get('label') or e.get('cat', 'son')}"]
    if level:
        parts.append(level)
    parts.append("pendant la parole" if (e.get("in_speech") or 0) >= 0.5 else "hors parole")
    vis = e.get("with_visual") or ""
    if vis.startswith("P"):
        parts.append(f"sur une coupe ({vis})")
    elif vis:
        parts.append(f"même instant que {vis}")
    if tile:
        parts.append(f"≈{tile}")
    return " · ".join(parts)


ZOOM_ZONE = "centre"
IMAGE_EVENT_LABELS = {
    "flash_blanc": "flash blanc",
    "noir_bref": "image noire brève",
    "image_inseree": "image insérée brève",
    "fige": "image figée",
    "fondu_noir": "fondu au noir",
    "fondu_depuis_noir": "ouverture depuis le noir",
    "noir": "écran noir",
    "noir_et_blanc": "passage en noir et blanc",
    "bandes_cinema": "bandes noires haut et bas",
}
MUSIC_KIND = {"rythmee": "rythmée", "nappe": "nappe sans rythme"}
MUSIC_END = {"coupure_nette": "coupure nette", "fondu": "en fondu", "normale": "fin normale"}
MUSIC_CHANGE = {"tempo": "tempo", "harmonie": "harmonie", "accords": "harmonie", "niveau": "niveau"}


def _image_event_line(e: dict, tile: str) -> str:
    kind = e.get("type", "")
    tail = f" · ≈{tile}" if tile else ""
    if kind == "zoom":
        word = "zoom sec" if e.get("dir", "avant") == "avant" else "dézoom sec"
        text = f"[{fmt_t(e['t'])}] {e['id']} {word} ×{fr(e.get('scale', 1.0), 2)} ({e.get('zone') or ZOOM_ZONE})"
        if e.get("end"):
            text += f" jusqu'à {fmt_t(e['end'])}"
        text += " · tout le cadre" if e.get("whole_frame", True) else " · un seul calque bouge (le reste du cadre est fixe)"
        return text + tail
    dur = e.get("dur")
    if dur is None and e.get("end") is not None:
        dur = float(e["end"]) - float(e["t"])
    length = f" {fr(dur, 2)} s" if dur else ""
    return f"[{fmt_t(e['t'])}] {e['id']} {IMAGE_EVENT_LABELS.get(kind, kind)}{length}{tail}"


def _music_desc(m: dict) -> str:
    bits = [MUSIC_KIND.get(m.get("kind", ""), "musique")]
    if m.get("kind") == "rythmee" and m.get("bpm"):
        bits[0] += f" ≈{fr(m['bpm'], 0)} BPM"
    level = m.get("level_vs_voice_db")
    if level is not None:
        bits.append(f"≈ {fr(abs(level), 0)} dB sous les voix" if level < 0 else f"≈ {signed_db(level)} dB sur les voix")
    return ", ".join(bits)


def chunk_view(data: VideoData, chunk: dict) -> tuple[str, str, str, set[str], list[dict]]:
    """(contexte, mesures, chronologie, ids valides, cases) d'un extrait ou d'une moitié d'extrait."""
    t0, t1 = float(chunk["t0"]), float(chunk["t1"])
    tiles = data.sheet_tiles(list(chunk.get("sheets") or []))
    times = [t["t"] for t in tiles]
    ids: set[str] = {t["id"] for t in tiles}

    def tile_near(t: float) -> str:
        found = nearest_tile(tiles, times, t)
        return found["id"] if found else ""

    def inside(t) -> bool:
        return t is not None and t0 <= float(t) < t1

    rows: list[tuple[float, int, str]] = []
    # Transcription : toutes les lignes de l'extrait
    for line in data.lines:
        if not inside(line.get("start")):
            continue
        lid = f"L{line['id']:03d}"
        ids.add(lid)
        if line.get("kind") == "event":
            text = f"[{fmt_t(line['start'])}] {lid} {line.get('text', '')}"
        else:
            text = f"[{fmt_t(line['start'])}] {lid} « {line.get('text', '')} »"
        text += " [FORT]" if line.get("loud") else ""
        text += " [RIRE]" if line.get("laugh") else ""
        rows.append((float(line["start"]), 0, text))
    # Repères image
    for e in data.image_events:
        if inside(e.get("t")):
            ids.add(e["id"])
            rows.append((float(e["t"]), 2, _image_event_line(e, tile_near(float(e["t"]) + 0.1))))
    # Sons marquants : les plus saillants d'abord, le reste résumé
    sounds = [e for e in data.sound_events if inside(e.get("t"))]
    sounds.sort(key=lambda e: (-(e.get("salience") or 0.0), e["t"]))
    listed, rest = sounds[:MAX_SOUND_LINES], sounds[MAX_SOUND_LINES:]
    for e in listed:
        ids.add(e["id"])
        rows.append((float(e["t"]), 1, _sound_line(e, tile_near(float(e["t"]) + 0.15))))
    # Musique : début, fin, changements ; « en cours » si elle a commencé avant l'extrait
    music_ids = []
    for m in data.music:
        start, end = float(m["start"]), float(m["end"])
        if end <= t0 or start >= t1:
            continue
        ids.add(m["id"])
        music_ids.append(m["id"])
        if start < t0:
            rows.append((t0, 3, f"[{fmt_t(t0)}] {m['id']} musique en cours depuis {fmt_t(start)} ({_music_desc(m)})"))
        else:
            rows.append((start, 3, f"[{fmt_t(start)}] {m['id']} début de musique ({_music_desc(m)}) · ≈{tile_near(start + 0.2)}"))
        for ch in m.get("changes") or []:
            if inside(ch.get("t")):
                why = MUSIC_CHANGE.get(ch.get("why", ""), ch.get("why", ""))
                rows.append((float(ch["t"]), 3, f"[{fmt_t(ch['t'])}] {m['id']} changement dans la musique ({why})"))
        if inside(end):
            end_kind = MUSIC_END.get(m.get("end_kind", ""), "fin")
            rows.append((end, 3, f"[{fmt_t(end)}] {m['id']} fin de musique ({end_kind}) · ≈{tile_near(end)}"))
    # Silences
    for c in data.silences:
        if inside(c.get("t")):
            ids.add(c["id"])
            text = f"[{fmt_t(c['t'])}] {c['id']} silence complet {fr(c.get('dur', 0), 2)} s"
            text += " (coupure nette)" if c.get("abrupt") else ""
            rows.append((float(c["t"]), 4, text + f" · ≈{tile_near(float(c['t']) + 0.1)}"))
    for p in data.plans_between(t0, t1):
        ids.add(p["id"])
    rows.sort(key=lambda r: (r[0], r[1]))
    chronology = "\n".join(text for _, _, text in rows)
    if rest:
        cats = Counter(e.get("cat", "autre") for e in rest).most_common(2)
        chronology += f"\n+ {len(rest)} sons brefs moins marqués, surtout " + " et ".join(c for c, _ in cats)

    # Contexte : la transcription des 20 s précédentes, texte seul
    before = [l.get("text", "") for l in data.lines if l.get("kind") != "event" and t0 - CONTEXT_S <= l.get("start", -1) < t0]
    context = " ".join(f"« {t} »" for t in before) if before else ("(début de la vidéo)" if t0 < 1 else "(personne ne parle)")

    measures = _chunk_measures(data, t0, t1, sounds, music_ids)
    return context, measures, chronology, ids, tiles


def _chunk_measures(data: VideoData, t0: float, t1: float, sounds: list[dict], music_ids: list[str]) -> str:
    span = max(t1 - t0, 0.01)
    plans = data.plans_between(t0, t1)
    lengths = [p["end"] - p["start"] for p in plans]
    cuts = [c for c in data.cuts if t0 <= c["t"] < t1]
    jump = round(100 * sum(c.get("kind") == "meme_decor" for c in cuts) / len(cuts)) if cuts else 0
    parts = [f"{len(plans)} plans (médiane {fr(statistics.median(lengths)) if lengths else '0'} s, {jump} % de jump cuts probables)"]
    zooms = [e for e in data.image_events if e.get("type") == "zoom" and e.get("dir", "avant") == "avant" and t0 <= e["t"] < t1]
    parts.append(f"{len(zooms)} zoom{'s' if len(zooms) > 1 else ''} sec{'s' if len(zooms) > 1 else ''}")
    editorial = [e for e in sounds if e.get("cat") != "autre"]
    cats = Counter(e.get("cat", "autre") for e in editorial).most_common(4)
    detail = f" ({', '.join(f'{c} {n}' for c, n in cats)}{'…' if len(cats) == 4 else ''})" if cats else ""
    parts.append(f"{len(editorial)} sons marquants{detail}")
    covered = _union_length([(m["start"], m["end"]) for m in data.music], t0, t1)
    if music_ids:
        parts.append(f"musique {round(100 * covered / span)} % ({', '.join(music_ids)})")
    else:
        parts.append("pas de musique détectée")
    n_sil = sum(1 for c in data.silences if t0 <= c["t"] < t1)
    parts.append(f"{n_sil} silence{'s' if n_sil > 1 else ''}")
    speech = _union_length([(w["s"], w["e"]) for w in _line_words(data.lines)], t0, t1)
    parts.append(f"parole {round(100 * speech / span)} %")
    rates = [w.get("cuts_per_min") for w in data.rhythm if t0 <= float(w.get("t0", -1)) < t1 and w.get("cuts_per_min") is not None]
    if rates:
        parts.append("rythme par 30 s : coupes/min " + " ".join(fr(r, 0) for r in rates))
    return " · ".join(parts)


def build_chunk_request(
    doc: BenchDoc,
    chunk: dict,
    planches: dict | None = None,
    settings: BenchSettings | None = None,
    *,
    data: VideoData | None = None,
    images: bool = True,
) -> tuple[list[dict], set[str]]:
    """Contenu d'un appel « observe » (texte et planches, à l'aveugle) et ids que Claude peut citer."""
    data = data or VideoData(doc)  # planches et settings : acceptés pour le contrat, relus depuis le disque
    context, measures, chronology, ids, tiles = chunk_view(data, chunk)
    total = len(data.chunks) or 1
    part = {"a": " (première moitié)", "b": " (seconde moitié)"}.get(chunk.get("part", ""), "")
    sheet_ns = list(chunk.get("sheets") or [])
    plan_ids = sorted({t.get("plan", "") for t in tiles if t.get("plan")})
    header = (
        f"Vidéo {doc.state.blind_id or 'V?'} — extrait {chunk['n'] + 1}/{total}{part}, de {fmt_t(chunk['t0'])} "
        f"à {fmt_t(chunk['t1'])} (vidéo de {fmt_duration(data.duration)}). "
    )
    if tiles:
        header += f"Cases {tiles[0]['id']} à {tiles[-1]['id']} sur {len(sheet_ns)} planche{'s' if len(sheet_ns) > 1 else ''}"
        header += f", plans {plan_ids[0]} à {plan_ids[-1]}." if plan_ids else "."
    content: list[dict] = [{"type": "text", "text": header}]
    blobs: list[tuple[str, Path]] = []
    for k, n in enumerate(sheet_ns):
        sheet = data.sheets_by_n.get(n)
        if not sheet:
            continue
        legend = (
            f"Planche {k + 1}/{len(sheet_ns)} — {sheet.get('first', '')} à {sheet.get('last', '')} — de "
            f"{fmt_t(sheet.get('t0', 0))} à {fmt_t(sheet.get('t1', 0))} (cases de gauche à droite, puis de haut en bas)"
        )
        content.append({"type": "text", "text": legend})
        blobs.append((legend, doc.root / sheet["file"]))
        if images:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ""}})
    if images:
        raw = [p.read_bytes() for _, p in blobs]
        shrink = sum(len(b) * 4 // 3 for b in raw) > MAX_REQUEST_B64
        datas = iter(base64.b64encode(_sheet_image(p, True) if shrink else b).decode() for (_, p), b in zip(blobs, raw))
        for block in content:
            if block["type"] == "image":
                block["source"]["data"] = next(datas)
    content.append(
        {
            "type": "text",
            "text": f"CONTEXTE (transcription des {fr(CONTEXT_S, 0)} s précédentes) : {context}\n\n"
            f"MESURES DE L'EXTRAIT : {measures}\n\n"
            f"CHRONOLOGIE (temps de la vidéo) :\n{chronology or '(rien de mesuré)'}",
        }
    )
    content.append({"type": "text", "text": OBSERVE_INSTRUCTIONS})
    return content, ids


def request_text_chars(content: list[dict]) -> int:
    return sum(len(b.get("text", "")) for b in content if b["type"] == "text")


# ------------------------------------------------------------ schémas
VIS = enum(*techniques.VISUAL_IDS)
POSITIONS = ("plein_ecran", "centre", "haut", "bas", "gauche", "droite", "coin", "sur_visage", "inconnue")
ORIGINS = ("montage", "jeu_ou_joueurs", "incertain")
ROLES = (
    "ponctue_vanne", "souligne_fail", "transition", "censure", "tension", "rupture",
    "ambiance", "bruit_du_jeu", "voix_ou_rire", "inconnu",
)
LAYOUTS = (
    "jeu_plein_ecran", "jeu_et_facecams", "facecam_plein_ecran",
    "deux_pov_cote_a_cote", "pov_en_incrustation", "alternance", "inconnue",
)
OBSERVE_SCHEMA = obj(
    {
        "resume": STR,
        "occurrences": arr(
            obj(
                {
                    "technique": VIS,
                    "tuile_debut": STR,
                    "tuile_fin": STR,
                    "texte_ecran": STR,
                    "description": STR,
                    "position": enum(*POSITIONS),
                    "lie_a": arr(STR),
                    "certitude": enum("vu", "probable"),
                }
            )
        ),
        "verdicts": arr(obj({"id": STR, "origine": enum(*ORIGINS), "role": enum(*ROLES)})),
        "gags": arr(
            obj(
                {
                    "ligne": STR,
                    "tuile": STR,
                    "citation": STR,
                    "mise_en_place": STR,
                    "chute": STR,
                    "mecaniques": arr(enum(*techniques.HUMOR_IDS)),
                    "techniques": arr(VIS),
                    "sons": arr(STR),
                    "pourquoi": STR,
                    "force": INT,
                }
            )
        ),
        "rythme": STR,
        "style_textes": STR,
        "mise_en_page": enum(*LAYOUTS),
        "doutes": STR,
    }
)
ALL_TECH = enum(*techniques.ALL_IDS)
VIDEO_PROFILE_SCHEMA = obj(
    {
        "resume": STR,
        "accroche": obj({"teaser": enum("oui", "non", "inconnu"), "duree_s": NUM, "description": STR}),
        "structure": arr(
            obj(
                {
                    "debut": STR,
                    "fin": STR,
                    "role": enum("teaser", "intro", "partie", "transition", "sponsor", "conclusion", "outro", "autre"),
                    "titre": STR,
                }
            )
        ),
        "signatures": arr(
            obj(
                {
                    "technique": ALL_TECH,
                    "comment": STR,
                    "quand": STR,
                    "frequence": enum("tout_le_temps", "souvent", "parfois", "rare"),
                    "exemple": STR,
                }
            )
        ),
        "mecaniques_dominantes": arr(enum(*techniques.HUMOR_IDS)),
        "humour": STR,
        "image": STR,
        "textes": STR,
        "son": STR,
        "rythme": STR,
        "meilleurs_exemples": arr(
            obj({"temps": STR, "tuile": STR, "quoi": STR, "pourquoi": STR, "techniques": arr(ALL_TECH)})
        ),
        "regles": arr(STR),
    }
)


# ------------------------------------------------------------ validation (code, jamais Claude)
def _valid(ref: str, ids: set[str]) -> bool:
    return bool(ref) and bool(ID_RE.match(ref)) and ref in ids


def validate_observation(result: dict, ids: set[str], tiles: dict[str, dict]) -> tuple[dict, int]:
    """Retire les références inventées (comptées), recale les temps sur les cases, complète les verdicts."""
    invalid = 0
    occurrences = []
    for occ in result.get("occurrences") or []:
        a, b = occ.get("tuile_debut", ""), occ.get("tuile_fin", "")
        ok_a, ok_b = _valid(a, ids) and a in tiles, _valid(b, ids) and b in tiles
        invalid += (not ok_a) + (not ok_b)
        if not ok_a and not ok_b:
            continue
        a, b = (a if ok_a else b), (b if ok_b else a)
        if tiles[b]["t"] < tiles[a]["t"]:
            a, b = b, a
        links = []
        for ref in occ.get("lie_a") or []:
            if _valid(ref, ids):
                links.append(ref)
            else:
                invalid += 1
        tech = occ.get("technique", "autre")
        occurrences.append(
            {
                "technique": tech if tech in techniques.VISUAL_IDS else "autre",
                "tuile_debut": a,
                "tuile_fin": b,
                "t": tiles[a]["t"],
                "end": tiles[b]["t"],
                "sheet": tiles[a].get("sheet"),
                "cell": tiles[a].get("cell"),
                "texte_ecran": (occ.get("texte_ecran") or "").strip(),
                "description": (occ.get("description") or "").strip(),
                "position": occ.get("position", "inconnue"),
                "lie_a": links,
                "certitude": occ.get("certitude", "probable"),
            }
        )
    verdicts, seen = [], set()
    for v in result.get("verdicts") or []:
        vid = v.get("id", "")
        if not _valid(vid, ids) or not vid.startswith(VERDICT_PREFIXES):
            invalid += 1
            continue
        if vid in seen:
            continue
        seen.add(vid)
        verdicts.append({"id": vid, "origine": v.get("origine", "incertain"), "role": v.get("role", "inconnu")})
    for vid in sorted(i for i in ids if i.startswith(VERDICT_PREFIXES) and i not in seen):
        verdicts.append({"id": vid, "origine": "incertain", "role": "inconnu", "auto": True})
    gags = []
    for g in result.get("gags") or []:
        line, tile = g.get("ligne", ""), g.get("tuile", "")
        if line and not _valid(line, ids):
            invalid += 1
            line = ""
        if tile and not (_valid(tile, ids) and tile in tiles):
            invalid += 1
            tile = ""
        sounds = []
        for ref in g.get("sons") or []:
            if _valid(ref, ids):
                sounds.append(ref)
            else:
                invalid += 1
        gags.append(
            {
                "ligne": line,
                "tuile": tile,
                "t": tiles[tile]["t"] if tile else None,
                "sheet": tiles[tile].get("sheet") if tile else None,
                "cell": tiles[tile].get("cell") if tile else None,
                "citation": (g.get("citation") or "").strip(),
                "mise_en_place": g.get("mise_en_place", ""),
                "chute": g.get("chute", ""),
                "mecaniques": list(dict.fromkeys(g.get("mecaniques") or [])),
                "techniques": list(dict.fromkeys(g.get("techniques") or [])),
                "sons": sounds,
                "pourquoi": g.get("pourquoi", ""),
                "force": max(FORCE_RANGE[0], min(FORCE_RANGE[1], int(g.get("force") or FORCE_RANGE[0]))),
            }
        )
    validated = {
        "resume": result.get("resume", ""),
        "occurrences": occurrences,
        "verdicts": verdicts,
        "gags": gags,
        "rythme": result.get("rythme", ""),
        "style_textes": result.get("style_textes", ""),
        "mise_en_page": result.get("mise_en_page", "inconnue"),
        "doutes": result.get("doutes", ""),
    }
    return validated, invalid


def merge_observations(parts: list[dict]) -> dict:
    """Résultats des deux moitiés d'un extrait, fusionnés."""
    if len(parts) == 1:
        return parts[0]
    verdicts: dict[str, dict] = {}
    for p in parts:
        for v in p["verdicts"]:
            old = verdicts.get(v["id"])
            if old is None or (old.get("auto") and not v.get("auto")):
                verdicts[v["id"]] = v
    join = lambda key: "\n".join(p[key] for p in parts if p.get(key))  # noqa: E731
    layout = next((p["mise_en_page"] for p in parts if p.get("mise_en_page") not in ("", "inconnue")), "inconnue")
    return {
        "resume": join("resume"),
        "occurrences": sorted((o for p in parts for o in p["occurrences"]), key=lambda o: (o["t"], o["technique"])),
        "verdicts": [verdicts[k] for k in sorted(verdicts)],
        "gags": [g for p in parts for g in p["gags"]],
        "rythme": join("rythme"),
        "style_textes": join("style_textes"),
        "mise_en_page": layout,
        "doutes": join("doutes"),
    }


# ------------------------------------------------------------ comptes
def chunk_records(doc: BenchDoc) -> list[dict]:
    """Extraits déjà lus par Claude avec l'instrument actuel (les autres sont ignorés)."""
    folder = doc.root / "observations"
    if not folder.is_dir():
        return []
    fp = observe_fp(doc)
    records = []
    for path in sorted(folder.glob("morceau_*.json")):
        try:
            rec = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if rec.get("fp") == fp:
            records.append(rec)
    records.sort(key=lambda r: r["chunk"])
    return records


def observe_fp(doc: BenchDoc) -> list:
    planches = doc.root / "planches.json"
    digest = hashlib.sha1(planches.read_bytes()).hexdigest()[:16] if planches.exists() else ""
    i = doc.state.instrument
    return [*local_fp(doc), i.get("sheets"), i.get("quality"), OBSERVE_VERSION, i.get("model"), digest]


def _inside(t: float, ranges: list[list[float]]) -> bool:
    return any(a <= t < b for a, b in ranges)


def _per_min(n: float, minutes: float) -> float:
    return round(n / minutes, 2) if minutes > 0 else 0.0


def dedup_occurrences(occurrences: list[dict]) -> list[dict]:
    """Même effet vu deux fois (deux extraits voisins, deux moitiés) : compté une fois."""
    kept: list[dict] = []
    for occ in sorted(occurrences, key=lambda o: (o["t"], o["technique"], o.get("tuile_debut", ""))):
        text = norm_text(occ.get("texte_ecran", ""))
        dup = None
        for prev in reversed(kept):
            if occ["t"] - prev["t"] > DEDUP_TEXT_S:
                break
            if prev["technique"] != occ["technique"]:
                continue
            prev_text = norm_text(prev.get("texte_ecran", ""))
            if text and prev_text == text:
                dup = prev
                break
            if not text and not prev_text and occ["t"] - prev["t"] <= DEDUP_PLAIN_S:
                dup = prev
                break
        if dup is not None:
            if occ.get("certitude") == "vu":
                dup["certitude"] = "vu"
            dup["end"] = max(dup.get("end", dup["t"]), occ.get("end", occ["t"]))
            continue
        kept.append(dict(occ))
    return kept


def merged_verdicts(records: list[dict]) -> dict[str, str]:
    """Origine retenue pour chaque S, M et Z (une musique à cheval sur deux extraits : avis majoritaire)."""
    votes: dict[str, list[str]] = defaultdict(list)
    for rec in records:
        for v in rec["result"].get("verdicts") or []:
            votes[v["id"]].append(v.get("origine", "incertain"))
    out = {}
    for vid, vs in votes.items():
        known = Counter(v for v in vs if v != "incertain").most_common()
        if not known or (len(known) > 1 and known[0][1] == known[1][1]):
            out[vid] = "incertain"
        else:
            out[vid] = known[0][0]
    return out


def aggregate_observations(doc: BenchDoc) -> dict:
    """Comptes déterministes à partir des extraits lus par Claude (§5.4) ; écrit agregats.json."""
    records = chunk_records(doc)
    data = VideoData(doc)
    analysed = sorted(([float(a), float(b)] for rec in records for a, b in rec.get("analysed") or []), key=lambda r: r[0])
    analysed_s = sum(b - a for a, b in analysed)
    minutes = analysed_s / 60
    coverage = round(min(1.0, analysed_s / data.duration), 3) if data.duration else 0.0
    occurrences = dedup_occurrences([o for rec in records for o in rec["result"].get("occurrences") or []])
    verdicts = merged_verdicts(records)

    per_tech: dict[str, dict] = {}
    for tid in sorted({o["technique"] for o in occurrences}):
        occs = [o for o in occurrences if o["technique"] == tid]
        ranked = sorted(occs, key=lambda o: (o.get("certitude") != "vu", o["t"]))[:MAX_EXAMPLES]
        per_tech[tid] = {
            "n": len(occs),
            "per_min": _per_min(len(occs), minutes),
            "vu": sum(o.get("certitude") == "vu" for o in occs),
            "probable": sum(o.get("certitude") != "vu" for o in occs),
            "examples": [
                {
                    "t": o["t"],
                    "tile": o["tuile_debut"],
                    "sheet": o.get("sheet"),
                    "cell": o.get("cell"),
                    "texte": o.get("texte_ecran", ""),
                    "description": o.get("description", ""),
                }
                for o in sorted(ranked, key=lambda o: o["t"])
            ],
        }

    def group(ids) -> float:
        return _per_min(sum(per_tech.get(t, {}).get("n", 0) for t in ids), minutes)

    # Zooms : Z mesurés que Claude confirme, plus les zooms qu'il voit sans mesure (lents, ciblés…)
    zoom_events = [e for e in data.image_events if e.get("type") == "zoom" and _inside(float(e["t"]), analysed)]
    confirmed = [e for e in zoom_events if verdicts.get(e["id"]) == "montage"]
    confirmed_t = [float(e["t"]) for e in confirmed]
    zoom_ids = {e["id"] for e in zoom_events}
    extra = [
        o
        for o in occurrences
        if o["technique"] in techniques.ZOOM_IDS
        and not (set(o.get("lie_a") or []) & zoom_ids)
        and not any(abs(o["t"] - t) <= ZOOM_MATCH_S for t in confirmed_t)
    ]
    # Sons : seulement les catégories « éditoriales » (pas « autre »), selon le verdict de Claude
    sounds = [e for e in data.sound_events if e.get("cat") != "autre" and _inside(float(e["t"]), analysed)]
    origin = {e["id"]: verdicts.get(e["id"], "incertain") for e in sounds}
    montage_cats = Counter(e.get("cat", "autre") for e in sounds if origin[e["id"]] == "montage")
    # Musique : part (en durée) des M jugées « montage »
    music_montage = sum(
        sum(max(0.0, min(b, float(m["end"])) - max(a, float(m["start"]))) for a, b in analysed)
        for m in data.music
        if verdicts.get(m["id"]) == "montage"
    )
    gags = [g for rec in records for g in rec["result"].get("gags") or []]
    mechanics = Counter(m for g in gags for m in g.get("mecaniques") or [])
    total_mech = sum(mechanics.values())
    layouts = Counter(
        rec["result"].get("mise_en_page") for rec in records if rec["result"].get("mise_en_page") not in (None, "", "inconnue")
    )
    agg = {
        "analysed_s": round(analysed_s, 1),
        "coverage": coverage,
        "analysed": analysed,
        "techniques": per_tech,
        "groups": {
            "texts_per_min": group(techniques.TEXT_IDS),
            "overlays_per_min": group(techniques.OVERLAY_IDS),
            "time_effects_per_min": group(techniques.TIME_EFFECT_IDS),
        },
        "zooms": {
            "confirmed_per_min": _per_min(len(confirmed), minutes),
            "total_per_min": _per_min(len(confirmed) + len(extra), minutes),
            "measured": len(zoom_events),
            "confirmed": len(confirmed),
        },
        "sounds": {
            "raw_per_min": _per_min(len(sounds), minutes),
            "montage_per_min": _per_min(sum(v == "montage" for v in origin.values()), minutes),
            "jeu_per_min": _per_min(sum(v == "jeu_ou_joueurs" for v in origin.values()), minutes),
            "incertain_per_min": _per_min(sum(v == "incertain" for v in origin.values()), minutes),
            "montage_by_cat": {c: _per_min(n, minutes) for c, n in sorted(montage_cats.items())},
        },
        "music": {"montage_pct": round(100 * music_montage / analysed_s, 1) if analysed_s else 0.0},
        "gags": {
            "n": len(gags),
            "per_min": _per_min(len(gags), minutes),
            "force_mean": round(statistics.mean(g["force"] for g in gags), 2) if gags else 0.0,
            "mechanics": {m: round(n / total_mech, 2) for m, n in sorted(mechanics.items())} if total_mech else {},
        },
        "layout_votes": dict(sorted(layouts.items())),
        "verdicts": dict(sorted(verdicts.items())),
        "invalid_refs": sum(int(rec.get("invalid_refs") or 0) for rec in records),
    }
    (doc.root / "observations").mkdir(exist_ok=True)
    doc.write_json("observations/agregats.json", agg)
    doc.set_metrics(
        claude_texts_per_min=agg["groups"]["texts_per_min"],
        claude_overlays_per_min=agg["groups"]["overlays_per_min"],
        claude_time_effects_per_min=agg["groups"]["time_effects_per_min"],
        zooms_confirmed_per_min=agg["zooms"]["confirmed_per_min"],
        zooms_total_per_min=agg["zooms"]["total_per_min"],
        sfx_montage_per_min=agg["sounds"]["montage_per_min"],
        sfx_jeu_per_min=agg["sounds"]["jeu_per_min"],
        sfx_incertain_per_min=agg["sounds"]["incertain_per_min"],
        sfx_montage_by_cat=agg["sounds"]["montage_by_cat"],
        music_montage_pct=agg["music"]["montage_pct"],
        gags_per_min=agg["gags"]["per_min"],
        gag_force_mean=agg["gags"]["force_mean"],
        gag_mechanics=agg["gags"]["mechanics"],
        layout=layouts.most_common(1)[0][0] if layouts else "inconnue",
        claude_coverage=coverage,
    )
    with doc._lock:
        doc.state.coverage = coverage
        doc.save()
    return agg


# ------------------------------------------------------------ coût
def sheet_tokens(w: int, h: int) -> int:
    return -(-int(w) * int(h) // 750)


def estimate(doc: BenchDoc, settings: BenchSettings) -> dict:
    """Coût estimé de l'analyse Claude d'une vidéo, une fois ses planches faites (§5.8)."""
    data = VideoData(doc)
    quality = doc.state.instrument.get("quality") or settings.quality
    chunks = data.chunks
    image_tokens = sum(sheet_tokens(s.get("w", 0), s.get("h", 0)) for s in data.sheets)
    chars = 0
    for chunk in chunks:
        content, _ = build_chunk_request(doc, chunk, data=data, images=False)
        chars += request_text_chars(content)
    text_tokens = int(chars / CHARS_PER_TOKEN)
    n = len(chunks)
    out_per_chunk = settings.calib_output.get(quality) or DEFAULT_OUTPUT_PER_CHUNK.get(quality, 10000.0)
    synth_in = SYNTH_INPUT_TOKENS.get(quality, 35000)
    tokens_in = image_tokens + text_tokens + SYSTEM_TOKENS * (n + 1) + synth_in
    tokens_out = int(out_per_chunk * n + SYNTH_OUTPUT_TOKENS.get(quality, 10000))
    usd = (
        (image_tokens + text_tokens + synth_in) * PRICE_IN
        + SYSTEM_TOKENS * PRICE_CACHE_WRITE  # le système, identique partout, n'est payé plein tarif qu'une fois
        + SYSTEM_TOKENS * n * PRICE_CACHE_READ
        + tokens_out * PRICE_OUT
    ) / 1e6
    return {
        "tokens_in": int(tokens_in),
        "tokens_out": tokens_out,
        "image_tokens": image_tokens,
        "usd": round(usd, 2),
        "low": round(usd * ESTIMATE_LOW, 2),
        "high": round(usd * ESTIMATE_HIGH, 2),
        "chunks": n,
    }


# ------------------------------------------------------------ profil sans Claude
def measures_profile(doc: BenchDoc) -> dict:
    """Profil « mesures seules » : des règles tirées des mesures, sur le modèle de heuristic_analysis."""
    m = doc.state.metrics
    rules = []
    if m.get("cuts_per_min") is not None:
        rules.append(
            f"Rythme : {fr(m['cuts_per_min'])} changements de plan par minute (plan médian {fr(m.get('median_shot', 0), 2)} s"
            f", {fr(m.get('jump_cut_pct', 0), 0)} % de jump cuts probables)."
        )
    if m.get("punch_ins_per_min"):
        rules.append(f"Zooms secs : {fr(m['punch_ins_per_min'])} par minute (×{fr(m.get('zoom_scale_median') or 1, 2)} en médiane).")
    if m.get("sound_events_per_min"):
        cats = sorted((m.get("sound_by_cat") or {}).items(), key=lambda kv: -kv[1])[:3]
        detail = f" (surtout : {', '.join(c for c, _ in cats)})" if cats else ""
        rules.append(f"Sons marquants (jeu compris) : {fr(m['sound_events_per_min'])} par minute{detail}.")
    if m.get("music_pct"):
        rules.append(f"Musique de fond détectée {fr(m['music_pct'], 0)} % du temps.")
    if m.get("flashes_per_min"):
        rules.append(f"Flashs : {fr(m['flashes_per_min'])} par minute.")
    if m.get("pause_p90") is not None:
        rules.append(f"Blancs entre les mots : 90 % font moins de {fr(m['pause_p90'], 2)} s.")
    if m.get("loudness_i") is not None:
        rules.append(f"Volume : {fr(m['loudness_i'])} LUFS.")
    return {"source": "mesures", "resume": "", "regles": rules}


# ------------------------------------------------------------ inspirations
def inspirations_path() -> Path:
    return workspace_dir(create=False) / "comparaison" / "inspirations.json"


def inspiration_block() -> str:
    """Pistes cochées dans « Comparer », pour les prompts de montage ; "" si désactivées ou en cas de souci.

    Ne crée jamais de fichier ni de dossier (appelé à chaque montage).
    """
    try:
        path = inspirations_path()
        if not path.is_file():
            return ""
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, dict) or not data.get("enabled"):
            return ""
        text = (data.get("text") or "").strip()
        if not text:
            text = "\n".join(f"- {i['text']}" for i in data.get("items") or [] if (i.get("text") or "").strip())
        if not text:
            return ""
        return INSPIRATION_HEADER + "\n\n" + text[:INSPIRATION_MAX_CHARS]
    except Exception:
        return ""


# ------------------------------------------------------------ résumé pour l'interface
def claude_todo(doc: BenchDoc, cfg: AppConfig | None = None) -> bool:
    """Une étape Claude reste à faire : en attente, en erreur, ou sautée faute de clé alors qu'il y en a une
    maintenant (la vidéo, mesurée sans clé, peut être analysée par Claude sans rien remesurer)."""
    st = doc.state.steps
    if any(st[s].status in ("pending", "error") for s in CLAUDE_STEPS):
        return True
    return st["observe"].status == "skipped" and claude_available(cfg or AppConfig.load())


def waiting_for_claude(doc: BenchDoc, cfg: AppConfig | None = None) -> bool:
    """Mesures prêtes, analyse Claude à lancer (ni faite, ni déjà validée, ni un Short)."""
    st = doc.state.steps
    return (
        all(st[s].status == "done" for s in LOCAL_STEPS)
        and not doc.state.claude_ok
        and not doc.state.metrics.get("short")
        and claude_todo(doc, cfg)
    )


def pending_claude(store: BenchmarkStore, cfg: AppConfig | None = None) -> dict:
    """Barre « Claude » : vidéos mesurées qui attendent Claude, et le coût estimé (avec la fourchette)."""
    cfg = cfg or AppConfig.load()
    docs = [d for d in store.list() if waiting_for_claude(d, cfg) and d.state.estimate]
    total = lambda key: round(sum(float(d.state.estimate.get(key) or 0.0) for d in docs), 2)  # noqa: E731
    return {"count": len(docs), "usd": total("usd"), "low": total("low"), "high": total("high"), "ids": [d.id for d in docs]}


def spent_usd(store: BenchmarkStore, channel: str | None = None) -> float:
    """Dépense Claude de l'étude (vidéos, et rapport si aucune chaîne n'est précisée)."""
    usd = sum(float(d.state.claude.get("usd", 0.0)) for d in store.list() if channel is None or d.state.channel == channel)
    if channel is None:
        usd += float(store.settings().report_cost.get("usd", 0.0))
    return round(usd, 2)


STATUS_LABELS = {
    "en_file": "en file d'attente",
    "pret_claude": "Mesures prêtes — analyse Claude",
    "mesures_seules": "mesures seules (pas de clé Claude)",
    "analysee": "analysée",
    "partielle": "analysée en partie",
    "a_mettre_a_jour": "Mesures mises à jour : analyse Claude à refaire",
    "erreur": "erreur",
    "interrompue": "interrompue",
}


def video_status(doc: BenchDoc, busy: str | None, cfg: AppConfig) -> str:
    st = doc.state.steps
    if busy == "running":
        return "en_cours"
    if busy == "queued":
        return "en_file"
    if any(s.status == "error" for s in st.values()):
        return "erreur"
    if not all(st[s].status == "done" for s in LOCAL_STEPS):
        return "interrompue"
    if st["synthesize"].status == "done":
        if claude_analysed(doc):
            return "partielle" if doc.state.failed_chunks or doc.state.coverage < 0.999 else "analysee"
        if st["observe"].status == "done":  # Claude a regardé, mais tout refusé ou synthèse impossible
            return "partielle"
        if not (st["observe"].status == "skipped" and claude_available(cfg)):
            return "mesures_seules"
        return "pret_claude"  # mesurée sans clé ; une clé a été ajoutée depuis
    if not claude_available(cfg):
        return "mesures_seules"
    if doc.state.claude.get("calls") and not chunk_records(doc):
        return "a_mettre_a_jour"
    return "pret_claude"


def headline(m: dict) -> str:
    parts = []
    if m.get("cuts_per_min") is not None:
        parts.append(f"{fr(m['cuts_per_min'])} plans/min")
    zooms = m.get("zooms_total_per_min", m.get("punch_ins_per_min"))
    if zooms is not None:
        parts.append(f"{fr(zooms)} zooms secs/min")
    sounds = m.get("sfx_montage_per_min", m.get("sound_events_per_min"))
    if sounds is not None:
        parts.append(f"{fr(sounds, 0)} sons/min")
    if m.get("music_pct") is not None:
        parts.append(f"musique {fr(m['music_pct'], 0)} %")
    if m.get("loudness_i") is not None:
        parts.append(f"{fr(m['loudness_i'])} LUFS")
    return " · ".join(parts)


BRIEF_KEYS = (
    "duration_min", "cuts_per_min", "median_shot", "punch_ins_per_min", "zooms_total_per_min", "sound_events_per_min",
    "sfx_montage_per_min", "music_pct", "loudness_i", "speech_ratio", "claude_texts_per_min", "claude_overlays_per_min",
    "gags_per_min",
)


def video_summary(doc: BenchDoc, busy: str | None, queue_note: str, settings: BenchSettings, cfg: AppConfig) -> dict:
    """Forme « VideoSummary » de l'API (§8)."""
    m = doc.state.metrics
    labels = dict(BENCH_STEPS)
    warnings = []
    if m.get("short"):
        warnings.append(f"Short (moins de {SHORT_MINUTES} min) : non compté")
    if (m.get("duration_min") or 0) > MAX_MINUTES:
        warnings.append("Plus d'une heure : c'est sûrement un live ou un rush, pas une vidéo montée.")
    if not Path(doc.state.path).is_file():
        warnings.append("Fichier d'origine introuvable : redépose la vidéo pour remesurer")
    est = doc.state.estimate or {}
    return {
        "id": doc.id,
        "name": doc.state.name,
        "channel": doc.state.channel,
        "origin": doc.state.origin,
        "added": doc.state.added,
        "duration_min": m.get("duration_min"),
        "short": bool(m.get("short")),
        "steps": [
            {
                "id": s,
                "label": labels[s],
                "status": doc.state.steps[s].status,
                "progress": doc.state.steps[s].progress,
                "message": doc.state.steps[s].message,
                "started": doc.state.steps[s].started,
                "finished": doc.state.steps[s].finished,
            }
            for s in BENCH_STEP_IDS
        ],
        "headline": headline(m),
        "metrics_brief": {k: m[k] for k in BRIEF_KEYS if k in m},
        "busy": busy,
        "queue_note": queue_note,
        "status": video_status(doc, busy, cfg),
        "claude_ok": doc.state.claude_ok,
        "estimate": {"usd": est.get("usd"), "low": est.get("low"), "high": est.get("high")},
        "claude": {"usd": round(doc.state.claude.get("usd", 0.0), 2), "calls": doc.state.claude.get("calls", 0)},
        "coverage": doc.state.coverage,
        "failed_chunks": list(doc.state.failed_chunks),
        "warnings": warnings,
        "has_thumb": (doc.root / "vignette.jpg").exists(),
        "last_error": doc.state.last_error,
    }


# ------------------------------------------------------------ traitement
class _Stop(Exception):
    """Plus d'envoi à Claude (annulation, garde-fou de budget ou erreur d'un autre extrait)."""


class BenchAnalyzer(StepRunner):
    step_ids = BENCH_STEP_IDS

    def __init__(
        self,
        doc: BenchDoc,
        cfg: AppConfig,
        store: BenchmarkStore | None = None,
        *,
        words_provider: WordsProvider | None = None,
        speech_provider=_DEFAULT_VAD,
        cancel_event: threading.Event | None = None,
    ):
        super().__init__(doc, cancel_event)
        self.doc = doc
        self.cfg = cfg
        self.store = store or _store_of(doc)
        self.words_provider = words_provider
        self.speech_provider = speech_provider
        self._llms: list[LLM] = []
        self._llm_lock = threading.Lock()
        self._stop = threading.Event()
        self._over_budget = threading.Event()

    def run(self, from_step: str | None = None, until: str | None = None) -> bool:
        invalidate_outdated(self.doc, self.cfg)  # l'instrument a pu changer depuis la dernière fois
        return super().run(from_step, until)

    # ------------------------------------------------------------ outils
    @property
    def root(self) -> Path:
        return self.doc.root

    @property
    def pcm(self) -> Path:
        return self.root / "audio.pcm"

    @property
    def duration(self) -> float:
        return float(self.doc.state.metrics.get("duration_s") or 0.0)

    def source(self) -> Path:
        path = Path(self.doc.state.path)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier d'origine introuvable : redépose la vidéo pour remesurer ({path})")
        return path

    def levels(self) -> Levels:
        curve = np.load(self.root / "niveaux.npy")
        return Levels.compute_thresholds(curve, curve)

    def _progress_cb(self, step: str, lo: float = 0.0, hi: float = 1.0):
        def cb(fraction: float, message: str = "") -> None:
            self.progress(step, lo + (hi - lo) * max(0.0, min(1.0, float(fraction))), message)

        return cb

    def lines(self) -> list[dict]:
        return (self.doc.read_json("transcription.json") or {}).get("lines") or []

    # ------------------------------------------------------------ étapes locales
    def step_probe(self) -> str:
        info = probe(self.source())
        if not info.has_video or not info.width:
            raise ValueError("Cette analyse a besoin de l'image : dépose la vidéo, pas seulement le son.")
        if not info.has_audio:
            raise ValueError("Cette vidéo n'a pas de son : impossible de mesurer bruitages, musique et silences.")
        if info.duration > MAX_MINUTES * 60:
            raise ValueError("Plus d'une heure : c'est sûrement un live ou un rush, pas une vidéo montée.")
        short = info.duration < SHORT_MINUTES * 60
        self.doc.set_metrics(
            duration_s=round(info.duration, 2),
            duration_min=round(info.duration / 60, 1),
            width=info.width,
            height=info.height,
            fps=round(info.fps, 3),
            video_codec=info.video_codec,
            short=short,
        )
        return f"{fmt_duration(info.duration)}, {info.width}×{info.height}" + (" — Short : non compté" if short else "")

    def step_audio(self) -> str:
        if not self.pcm.exists():  # déjà là si la vidéo vient de « Mes vidéos »
            extract_pcm(self.source(), self.pcm, duration=self.duration, on_progress=self._progress_cb("audio", 0.0, 0.5))
        levels_path = self.root / "niveaux.npy"
        if not levels_path.exists():
            np.save(levels_path, level_curve(self.pcm))
        loud = _media("soundscan").measure_loudness(self.source(), self.root, self.duration, self._progress_cb("audio", 0.5, 1.0))
        self.doc.set_metrics(**loud)
        return f"{fr(loud['loudness_i'])} LUFS" if loud.get("loudness_i") is not None else ""

    def step_image(self) -> str:
        vision = _media("vision")
        info = probe(self.source())
        metrics = vision.analyze_image(self.source(), self.root, info, progress=self._progress_cb("image"))
        self.doc.set_metrics(**metrics)
        self.doc.set_instrument(image=vision.IMAGE_VERSION)
        return f"{fr(metrics.get('cuts_per_min', 0))} plans/min, {metrics.get('punch_ins', 0)} zooms secs"

    def step_transcribe(self) -> str:
        model = whisper_model(self.cfg)
        existing = self.doc.read_json("transcription.json") or {}
        if existing.get("whisper_model") == model and existing.get("lines") is not None:
            lines = existing["lines"]
            note = " (reprise de « Mes vidéos »)" if existing.get("reused_from") else " (reprise)"
        else:
            levels = self.levels()
            if self.words_provider:
                words = self.words_provider(self.pcm, levels)
            else:
                settings = self.cfg.whisper.model_copy(update={"model": model})
                words = transcribe_mix(
                    self.pcm,
                    levels,
                    settings,
                    self.root / "transcription_morceaux",
                    on_progress=self._progress_cb("transcribe"),
                    log=self.doc.log,
                )
            lines = drop_hallucinations(build_lines(words, levels))
            self.doc.write_json("transcription.json", {"lines": lines, "whisper_model": model, "reused_from": ""})
            note = ""
        words = _line_words(lines)
        self.doc.set_metrics(
            words=len(words),
            words_per_min=round(len(words) / max(self.duration / 60, 0.01)),
            speech_ratio=round(speech_ratio(words, self.duration), 2),
            whisper_model=model,
        )
        self.doc.set_instrument(whisper=model)
        return f"{len(words)} mots{note}"

    def step_sound(self) -> str:
        soundscan = _media("soundscan")
        data = VideoData(self.doc)
        library = self.doc.read_json("bibliotheque.json")
        kwargs = {} if self.speech_provider is _DEFAULT_VAD else {"speech_provider": self.speech_provider}
        metrics = soundscan.analyze_sound(
            self.pcm,
            self.root,
            duration=self.duration,
            words=[(w["s"], w["e"]) for w in _line_words(data.lines)],
            cuts=[float(c["t"]) for c in data.cuts],
            visual_events=data.image_events,
            library_hits=[float(h["t"]) for h in library.get("hits") or []] if library else None,
            progress=self._progress_cb("sound"),
            **kwargs,
        )
        self.doc.set_metrics(**metrics)
        self.doc.set_instrument(sound=soundscan.SOUND_VERSION)
        music = f", musique {fr(metrics['music_pct'], 0)} %" if metrics.get("music_pct") is not None else ""
        return f"{fr(metrics.get('sound_events_per_min', 0))} sons marquants/min{music}"

    def step_sheets(self) -> str:
        sheets = _media("sheets")
        settings = self.store.settings()
        data = VideoData(self.doc)
        r = self.doc.read_json
        sheets.build_sheets(
            self.source(),
            self.root,
            quality=settings.quality,
            duration=self.duration,
            plans=r("plans.json") or {},
            image_events=r("image_evenements.json") or {},
            sound_events=r("son_evenements.json") or {},
            music=r("musique.json") or {},
            silences=r("silences.json") or {},
            words=[(w["s"], w["e"]) for w in _line_words(data.lines)],
            progress=self._progress_cb("sheets", 0.0, 0.95),
        )
        self.doc.set_instrument(sheets=sheets.SHEETS_VERSION, quality=settings.quality)
        est = estimate(self.doc, settings)
        with self.doc._lock:
            self.doc.state.estimate = est
            self.doc.save()
        data = VideoData(self.doc)
        return (
            f"{len(data.tiles)} cases, {len(data.sheets)} planches, {est['chunks']} extraits — analyse Claude "
            f"≈ {fr(est['usd'], 2)} $ (entre {fr(est['low'], 2)} et {fr(est['high'], 2)} $)"
        )

    # ------------------------------------------------------------ Claude
    def _observe_effort(self, quality: str) -> str:
        try:
            effort = getattr(_media("sheets").PRESETS[quality], "observe_effort", "")
        except Exception:
            effort = ""
        return effort or OBSERVE_EFFORT.get(quality, "medium")

    def _new_llm(self) -> LLM:
        llm = LLM(self.cfg, cache_dir=self.root / "claude_cache", log=self.doc.log)
        with self._llm_lock:
            self._llms.append(llm)
        return llm

    def _step_cost(self) -> float:
        with self._llm_lock:
            return sum(llm.cost() for llm in self._llms)

    def _approved(self) -> float:
        return self.doc.state.approved_usd or float(self.doc.state.estimate.get("high") or 0.0)

    def _before_send(self) -> None:
        """Garde-fou, avant chaque envoi : annulation, ou dépense > 1,5 × le coût approuvé."""
        if self._stop.is_set() or self.cancel.is_set():
            raise _Stop()
        spent = self.doc.state.claude.get("usd", 0.0) + self._step_cost() - self.doc.state.approved_at_usd
        if spent > BUDGET_FACTOR * self._approved():
            self._over_budget.set()
            self._stop.set()
            raise _Stop()

    def _account(self) -> None:
        """Ajoute la dépense de l'étape à celle de la vidéo (appelé même en cas d'arrêt)."""
        with self._llm_lock:
            llms, self._llms = self._llms, []
        if not llms:
            return
        with self.doc._lock:
            c = self.doc.state.claude
            for key in ("input", "output", "cache_read", "cache_write", "calls"):
                c[key] = int(c.get(key, 0)) + sum(int(llm.usage.get(key, 0)) for llm in llms)
            c["usd"] = round(float(c.get("usd", 0.0)) + sum(llm.cost() for llm in llms), 4)
            self.doc.save()

    def _pause_for_budget(self) -> None:
        with self.doc._lock:
            self.doc.state.claude_ok = False
            self.doc.save()
        spent = self.doc.state.claude.get("usd", 0.0)
        raise Cancelled(
            f"Coût plus élevé que prévu : analyse en pause ({fr(spent, 2)} $ dépensés). "
            "Clique sur « Continuer l'analyse Claude » pour poursuivre."
        )

    def _ask_part(self, llm: LLM, chunk: dict, data: VideoData, effort: str) -> tuple[dict, int]:
        self._before_send()
        content, ids = build_chunk_request(self.doc, chunk, data=data)
        label = f"observe_{chunk['n']:02d}{chunk.get('part', '')}"
        result = llm.ask_json(
            system=BENCH_SYSTEM, content=content, schema=OBSERVE_SCHEMA, effort=effort, max_tokens=OBSERVE_MAX_TOKENS, label=label
        )
        return validate_observation(result, ids, data.tiles_by_id)

    def _observe_chunk(self, chunk: dict, data: VideoData, effort: str, fp: list) -> dict:
        """Un extrait : un appel, ou deux moitiés si Claude tronque, renvoie un JSON illisible ou refuse."""
        llm = self._new_llm()
        parts: list[tuple[dict, dict, int]] = []
        failed: list[str] = []
        try:
            if len(chunk.get("sheets") or []) > MAX_SHEETS_PER_CALL:  # trop d'images pour une requête
                raise LLMError(f"plus de {MAX_SHEETS_PER_CALL} planches", kind="tronque")
            result, invalid = self._ask_part(llm, chunk, data, effort)
            parts.append((chunk, result, invalid))
        except LLMError as exc:
            if exc.kind not in SPLIT_KINDS:
                raise
            halves = chunk_parts(chunk, data)
            self.doc.log(f"Extrait {chunk['n'] + 1} : {exc} — " + ("coupé en deux" if halves else "abandonné"))
            for half in halves or []:
                try:
                    result, invalid = self._ask_part(llm, half, data, effort)
                    parts.append((half, result, invalid))
                except LLMError as exc2:
                    if exc2.kind not in SPLIT_KINDS:
                        raise
                    self.doc.log(f"Extrait {chunk['n'] + 1}{half['part']} abandonné : {exc2}")
                    failed.append(half["part"])
            if not halves:
                failed.append("tout")
        merged = merge_observations([r for _, r, _ in parts]) if parts else merge_observations([validate_observation({}, set(), {})[0]])
        record = {
            "chunk": chunk["n"],
            "t0": chunk["t0"],
            "t1": chunk["t1"],
            "observe_version": OBSERVE_VERSION,
            "fp": fp,
            "result": merged,
            "invalid_refs": sum(i for _, _, i in parts),
            "analysed": [[p["t0"], p["t1"]] for p, _, _ in parts],
            "failed": failed,
            "usage": {"input": llm.usage["input"], "output": llm.usage["output"], "calls": llm.usage["calls"]},
        }
        self.doc.write_json(f"observations/morceau_{chunk['n']:02d}.json", record)
        return record

    def step_observe(self) -> str:
        if not claude_available(self.cfg):
            raise Skipped("Pas de clé Claude : mesures seules")
        settings = self.store.settings()
        if not self.doc.state.claude_ok:
            if settings.auto_claude and not self.doc.state.metrics.get("short"):
                approve_claude(self.doc)
            else:
                usd = self.doc.state.estimate.get("usd")
                cost = f" (≈ {fr(usd, 2)} $)" if usd is not None else ""
                raise Cancelled(f"En attente de ta validation : « Analyser avec Claude »{cost}")
        data = VideoData(self.doc)
        if not data.chunks:
            raise ValueError("Pas de planches : relance les mesures.")
        quality = self.doc.state.instrument.get("quality") or settings.quality
        effort = self._observe_effort(quality)
        self.doc.set_instrument(observe=OBSERVE_VERSION, model=self.cfg.model)
        (self.root / "observations").mkdir(exist_ok=True)
        fp = observe_fp(self.doc)
        done_ids = {rec["chunk"] for rec in chunk_records(self.doc)}
        todo = [c for c in data.chunks if c["n"] not in done_ids]
        total = len(data.chunks)
        self._stop.clear()
        self._over_budget.clear()
        error: BaseException | None = None
        new_records: list[dict] = []
        pool = ThreadPoolExecutor(max_workers=max(1, int(self.cfg.llm_parallel_requests)))
        try:
            futures = [pool.submit(self._observe_chunk, c, data, effort, fp) for c in todo]
            finished = len(done_ids)
            for future in as_completed(futures):
                try:
                    new_records.append(future.result())
                except _Stop:
                    pass
                except Exception as exc:  # erreur d'API : les extraits finis restent acquis
                    error = error or exc
                    self._stop.set()
                finished += 1
                spent = self.doc.state.claude.get("usd", 0.0) + self._step_cost()
                self.progress("observe", finished / max(total, 1), f"Claude : passage {finished}/{total} · {fr(spent, 2)} $ dépensés")
        except Cancelled:
            self._stop.set()
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)  # les appels partis vont au bout (et sont mis en cache)
            calls = [rec["usage"] for rec in new_records if rec["usage"].get("calls")]
            self._account()
            if calls:
                with _SETTINGS_LOCK:
                    s = self.store.settings()
                    old = s.calib_output.get(quality) or DEFAULT_OUTPUT_PER_CHUNK.get(quality, 10000.0)
                    mean_out = sum(u["output"] for u in calls) / len(calls)
                    s.calib_output[quality] = round((1 - CALIB_WEIGHT) * old + CALIB_WEIGHT * mean_out, 1)
                    self.store.save_settings(s)
        if self._over_budget.is_set():
            self._pause_for_budget()
        if self.cancel.is_set():
            raise Cancelled()
        if error is not None:
            raise error
        records = chunk_records(self.doc)
        failed = sorted(rec["chunk"] for rec in records if rec.get("failed"))
        with self.doc._lock:
            self.doc.state.failed_chunks = failed
            self.doc.save()
        agg = aggregate_observations(self.doc)
        if self.doc.state.steps["synthesize"].status != "pending":  # « mesures seules » faite avant : à refaire
            self.doc.invalidate(["synthesize"])
        refused = f" ({len(failed)} passage{'s' if len(failed) > 1 else ''} refusé{'s' if len(failed) > 1 else ''})" if failed else ""
        return (
            f"{len(records)} extraits regardés, couverture {round(100 * agg['coverage'])} %{refused} · "
            f"{fr(self.doc.state.claude.get('usd', 0.0), 2)} $"
        )

    def _video_content(self, data: VideoData, agg: dict, records: list[dict]) -> str:
        m = self.doc.state.metrics
        failed = [rec for rec in records if rec.get("failed")]
        coverage = f"COUVERTURE : {round(100 * agg['coverage'])} % de la vidéo regardée."
        if failed:
            coverage += " Passages refusés par Claude (non regardés) : " + ", ".join(
                f"extrait {rec['chunk'] + 1} ({fmt_t(rec['t0'])}–{fmt_t(rec['t1'])})" for rec in failed
            ) + "."
        counts = [
            f"- textes ajoutés : {fr(agg['groups']['texts_per_min'], 2)}/min ; incrustations : "
            f"{fr(agg['groups']['overlays_per_min'], 2)}/min ; effets de temps : {fr(agg['groups']['time_effects_per_min'], 2)}/min",
            f"- zooms confirmés : {fr(agg['zooms']['confirmed_per_min'], 2)}/min ; avec ceux vus sans mesure : "
            f"{fr(agg['zooms']['total_per_min'], 2)}/min",
            f"- sons marquants : {fr(agg['sounds']['raw_per_min'], 2)}/min, dont ajoutés au montage "
            f"{fr(agg['sounds']['montage_per_min'], 2)}/min et du jeu ou des joueurs {fr(agg['sounds']['jeu_per_min'], 2)}/min",
            f"- musique ajoutée au montage : {fr(agg['music']['montage_pct'], 0)} % du temps regardé",
            f"- gags : {agg['gags']['n']} ({fr(agg['gags']['per_min'], 2)}/min), force moyenne {fr(agg['gags']['force_mean'], 1)}/5",
        ]
        for tid, t in sorted(agg["techniques"].items(), key=lambda kv: -kv[1]["n"]):
            counts.append(f"- {tid} : {t['n']} ({fr(t['per_min'], 2)}/min)")
        measured = [f"- {label} : {fr(m[k], 2)}{unit}" for k, label, unit in SYNTH_MEASURES if isinstance(m.get(k), (int, float))]
        rhythm = " ".join(fr(w.get("cuts_per_min", 0), 0) for w in data.rhythm)
        intro = " ".join(
            f"[{fmt_t(l['start'])}] {l.get('text', '')}" for l in data.lines if l.get("start", 0) < SYNTH_INTRO_S
        )
        gags = sorted((g for rec in records for g in rec["result"].get("gags") or []), key=lambda g: (-g["force"], g.get("t") or 0))
        top = [
            f"- [{fmt_t(g['t']) if g.get('t') is not None else '?'} {g.get('tuile', '')}] force {g['force']} : « {g['citation']} » — "
            f"{g.get('chute', '')} ({', '.join(g.get('mecaniques') or [])} ; {', '.join(g.get('techniques') or [])})"
            for g in gags[:SYNTH_TOP_GAGS]
        ]
        blocks = []
        for rec in records:
            res = rec["result"]
            head = f"### Extrait {rec['chunk'] + 1}/{len(data.chunks)} ({fmt_t(rec['t0'])}–{fmt_t(rec['t1'])})"
            if rec.get("failed"):
                head += " — en partie non regardé (refus)"
            occ = [
                f"[{fmt_t(o['t'])} {o['tuile_debut']}] {o['technique']}"
                + (f" « {o['texte_ecran']} »" if o.get("texte_ecran") else "")
                + (f" — {o['description']}" if o.get("description") else "")
                for o in (res.get("occurrences") or [])[:SYNTH_OCCURRENCES_PER_CHUNK]
            ]
            blocks.append(
                "\n".join(
                    [
                        head,
                        f"Résumé : {res.get('resume', '')}",
                        f"Rythme : {res.get('rythme', '')}",
                        f"Textes : {res.get('style_textes', '')}",
                        f"Mise en page : {res.get('mise_en_page', '')}",
                        "Effets vus :",
                        *(occ or ["(aucun)"]),
                    ]
                )
            )
        return "\n\n".join(
            [
                coverage,
                "COMPTES DU PROGRAMME :\n" + "\n".join(counts),
                "MESURES AUTOMATIQUES :\n" + ("\n".join(measured) or "(aucune)"),
                f"RYTHME PAR 30 S (coupes/min) : {rhythm or '(non mesuré)'}",
                f"DÉBUT DE LA VIDÉO ({fr(SYNTH_INTRO_S, 0)} premières secondes) : {intro or '(pas de parole)'}",
                "GAGS LES PLUS FORTS :\n" + ("\n".join(top) or "(aucun)"),
                "EXTRAITS :\n\n" + "\n\n".join(blocks),
            ]
        )

    def step_synthesize(self) -> str:
        records = chunk_records(self.doc)
        observe = self.doc.state.steps["observe"].status
        if not claude_available(self.cfg) or observe == "skipped" or not records:
            self.doc.write_json("profil.json", measures_profile(self.doc))
            return "mesures seules"
        data = VideoData(self.doc)
        agg = self.doc.read_json("observations/agregats.json") or aggregate_observations(self.doc)
        if not agg.get("analysed_s"):
            profile = {**measures_profile(self.doc), "claude_error": "Claude a refusé tous les passages de la vidéo."}
            self.doc.write_json("profil.json", profile)
            return "mesures seules : Claude a refusé tous les passages"
        content = VIDEO_INSTRUCTIONS.format(
            blind=self.doc.state.blind_id or "V?",
            duration=fmt_duration(data.duration),
            body=self._video_content(data, agg, records),
        )
        self.progress("synthesize", 0.05, "Synthèse de la vidéo par Claude…")
        claude_error = ""
        try:
            self._before_send()
            llm = self._new_llm()
            result = llm.ask_json(
                system=BENCH_SYSTEM, content=content, schema=VIDEO_PROFILE_SCHEMA, effort="high", max_tokens=VIDEO_MAX_TOKENS, label="video"
            )
        except _Stop:
            self._account()
            if self._over_budget.is_set():
                self._pause_for_budget()
            raise Cancelled()
        except LLMError as exc:
            self._account()
            if exc.kind not in SPLIT_KINDS:
                raise
            result, claude_error = None, str(exc)
        else:
            self._account()
        if result is None:
            profile = {**measures_profile(self.doc), "claude_error": claude_error}
            self.doc.write_json("profil.json", profile)
            return f"mesures seules : Claude n'a pas pu faire la synthèse ({claude_error})"
        profile = {"source": "claude", **result, "coverage": agg["coverage"], "failed_chunks": self.doc.state.failed_chunks}
        self.doc.write_json("profil.json", profile)
        shutil.rmtree(self.root / "images4", ignore_errors=True)  # 150 à 250 Mo, inutiles désormais
        cost = fr(self.doc.state.claude.get("usd", 0.0), 2)
        return f"profil de la vidéo prêt · analyse complète {cost} $"


def video_detail(doc: BenchDoc, busy: str | None, queue_note: str, settings: BenchSettings, cfg: AppConfig) -> dict:
    """Détail d'une vidéo (§8) : mesures, planches et cases, observations de Claude, profil, journal."""
    data = VideoData(doc)
    records = chunk_records(doc)
    occurrences = dedup_occurrences([o for rec in records for o in rec["result"].get("occurrences") or []])
    gags = sorted((g for rec in records for g in rec["result"].get("gags") or []), key=lambda g: (g.get("t") is None, g.get("t") or 0))
    return {
        **video_summary(doc, busy, queue_note, settings, cfg),
        "metrics": doc.state.metrics,
        "sheets": [{k: s.get(k) for k in ("n", "t0", "t1", "chunk", "w", "h", "first", "last")} for s in data.sheets],
        "tiles": [{k: t.get(k) for k in ("id", "t", "sheet", "cell", "plan")} for t in data.tiles],
        "layout": {k: data.planches.get(k) for k in ("quality", "tile_w", "tile_h", "cols", "rows")},
        "observations": {
            "occurrences": [
                {
                    "t": o["t"],
                    "technique": o["technique"],
                    "label": techniques.label(o["technique"]),
                    "texte": o.get("texte_ecran", ""),
                    "description": o.get("description", ""),
                    "tile": o.get("tuile_debut", ""),
                    "sheet": o.get("sheet"),
                    "cell": o.get("cell"),
                    "certitude": o.get("certitude", ""),
                }
                for o in occurrences
            ],
            "gags": gags,
        },
        "agregats": doc.read_json("observations/agregats.json") or {},
        "profile": doc.read_json("profil.json") or {},
        "log": doc.log_tail(),
    }
