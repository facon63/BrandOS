"""Bibliothèque de la chaîne : bruitages, musiques, actions des personnages, images/memes.

Le dossier est scanné, chaque fichier reçoit un identifiant court et des tags
(tirés des noms de dossiers et de fichiers). Les modifications faites à la main
dans `krokcut_library.json` (tags, description, désactivation…) sont conservées
à chaque nouveau scan.
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path

from .ffmpeg_utils import FFmpegError, FFmpegUnavailable, binary, probe

LIBRARY_FILE = "krokcut_library.json"

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".aif", ".aiff"}
VIDEO_EXT = {".mov", ".webm", ".mp4", ".mkv", ".avi", ".m4v"}
IMAGE_EXT = {".png", ".gif", ".jpg", ".jpeg", ".webp", ".apng"}

KIND_HINTS = {
    "music": {"musique", "musiques", "music", "musics", "bgm", "ost", "ambiance", "ambiances"},
    "sfx": {"sfx", "son", "sons", "bruitage", "bruitages", "sound", "sounds", "fx", "effets", "soundesign", "sounddesign"},
    "character": {"perso", "persos", "personnage", "personnages", "character", "characters", "mascotte", "mascottes", "actions", "avatars"},
    "image": {"image", "images", "meme", "memes", "sticker", "stickers", "emoji", "emojis", "overlay", "overlays"},
    "skip": {"videos", "video", "references", "reference", "publiees", "inspiration", "rush", "rushs", "exports", "projets"},
}

ALL_HINTS = set().union(*KIND_HINTS.values())

STOPWORDS = {"de", "du", "la", "le", "les", "des", "et", "a", "au", "aux", "un", "une", "the", "of", "final", "v1", "v2", "copy", "copie", "new"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower()


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    parts = re.split(r"[^a-zA-Z0-9]+", normalize(text))
    return [p for p in parts if p and not p.isdigit() and p not in STOPWORDS and len(p) > 1]


def make_id(rel: Path, kind: str) -> str:
    prefix = {"sfx": "sfx", "music": "music", "character": "perso", "image": "img", "video": "clip"}[kind]
    stem_parts = [p for p in rel.with_suffix("").parts]
    # retire le dossier racine type "sfx" / "personnages" déjà porté par le préfixe
    if stem_parts and normalize(stem_parts[0]).replace(" ", "") in ALL_HINTS:
        stem_parts = stem_parts[1:] or stem_parts
    slug = "/".join(re.sub(r"[^a-z0-9]+", "_", normalize(p)).strip("_") for p in stem_parts)
    return f"{prefix}/{slug}"


def guess_kind(rel: Path, ext: str, info) -> str | None:
    folder_words = {normalize(p).replace(" ", "") for p in rel.parts[:-1]}
    folder_tokens = set()
    for part in rel.parts[:-1]:
        folder_tokens.update(tokens(part))
    words = folder_words | folder_tokens
    if words & KIND_HINTS["skip"]:
        return None
    if ext in AUDIO_EXT:
        if words & KIND_HINTS["music"]:
            return "music"
        if words & KIND_HINTS["sfx"]:
            return "sfx"
        return "music" if info.duration >= 45 else "sfx"
    if ext in IMAGE_EXT:
        if words & KIND_HINTS["character"]:
            return "character"
        return "image"
    if ext in VIDEO_EXT:
        if words & KIND_HINTS["character"]:
            return "character"
        if words & KIND_HINTS["image"]:
            return "video"
        if info.alpha:
            return "character"
        if info.duration > 120:  # longue vidéo : sûrement une référence, pas un asset
            return None
        return "video"
    return None


def detect_green_screen(path: Path) -> bool:
    """Regarde les coins d'une image : vert vif = fond vert à incruster."""
    try:
        proc = subprocess.run(
            [
                binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", "0.1", "-i", str(path),
                "-frames:v", "1", "-vf", "scale=32:18", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
            ],
            capture_output=True,
            timeout=30,
        )
    except (FFmpegError, OSError, subprocess.TimeoutExpired):
        return False
    raw = proc.stdout
    if len(raw) < 32 * 18 * 3:
        return False

    def px(x, y):
        i = (y * 32 + x) * 3
        return raw[i], raw[i + 1], raw[i + 2]

    corners = [px(0, 0), px(31, 0), px(0, 17), px(31, 17)]
    return sum(1 for r, g, b in corners if g > 140 and r < 120 and b < 120) >= 3


def character_name(rel: Path, kind: str) -> str:
    if kind != "character":
        return ""
    parts = list(rel.parts[:-1])
    for i, part in enumerate(parts):
        if set(tokens(part)) & KIND_HINTS["character"] and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else ""


class Library:
    def __init__(self, root: Path, assets: list[dict]):
        self.root = root
        self.assets = assets
        self._by_id = {a["id"]: a for a in assets}

    # -------------------------------------------------------------- chargement
    @classmethod
    def load(cls, root: str | Path | None) -> "Library":
        if not root:
            return cls(Path("."), [])
        root = Path(root).expanduser().resolve()
        path = root / LIBRARY_FILE
        if path.exists():
            data = json.loads(path.read_text("utf-8"))
            return cls(root, data.get("assets", []))
        return cls(root, [])

    def save(self) -> None:
        (self.root / LIBRARY_FILE).write_text(
            json.dumps({"version": 1, "assets": self.assets}, ensure_ascii=False, indent=1),
            "utf-8",
        )

    @classmethod
    def scan(cls, root: str | Path, on_progress=None) -> "Library":
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Dossier bibliothèque introuvable : {root}")
        binary("ffprobe")  # absent ou cassé : on s'arrête ici, sinon chaque fichier serait sauté et la
        # bibliothèque enregistrée vide (tags et descriptions perdus)
        previous = {a["path"]: a for a in cls.load(root).assets}
        files = [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix.lower() in AUDIO_EXT | VIDEO_EXT | IMAGE_EXT and not p.name.startswith(".")
        ]
        assets: list[dict] = []
        used_ids: set[str] = set()
        for i, path in enumerate(files):
            if on_progress:
                on_progress(i / max(1, len(files)), path.name)
            rel = path.relative_to(root)
            rel_str = rel.as_posix()
            old = previous.get(rel_str)
            try:
                info = probe(path)
            except FFmpegUnavailable:
                raise
            except FFmpegError:
                continue
            kind = old["kind"] if old and old.get("edited") else guess_kind(rel, path.suffix.lower(), info)
            if kind is None:
                continue
            asset_id = old["id"] if old else make_id(rel, kind)
            base_id, n = asset_id, 2
            while asset_id in used_ids:
                asset_id = f"{base_id}_{n}"
                n += 1
            used_ids.add(asset_id)

            tags = []
            for part in rel.with_suffix("").parts:
                for tok in tokens(part):
                    if tok not in tags and tok not in ALL_HINTS:
                        tags.append(tok)
            key = "none"
            if kind in ("character", "image", "video"):
                if info.alpha or path.suffix.lower() in (".png", ".gif", ".webp", ".apng"):
                    key = "alpha"
                elif info.has_video and detect_green_screen(path):
                    key = "green"
            asset = {
                "id": asset_id,
                "path": rel_str,
                "kind": kind,
                "name": path.stem,
                "character": character_name(rel, kind),
                "tags": tags,
                "description": "",
                "duration": round(info.duration, 3) if info.duration else 0.0,
                "width": info.width,
                "height": info.height,
                "has_audio": info.has_audio,
                "key": key,
                "enabled": True,
                "edited": False,
            }
            if old:  # garde les retouches manuelles
                for field in ("tags", "description", "enabled", "key", "character", "edited", "kind"):
                    if old.get("edited") or field in ("description", "enabled"):
                        asset[field] = old.get(field, asset[field])
            assets.append(asset)
        lib = cls(root, assets)
        lib.save()
        return lib

    # --------------------------------------------------------------- accès
    def get(self, asset_id: str) -> dict | None:
        return self._by_id.get(asset_id)

    def path_of(self, asset: dict) -> Path:
        return self.root / asset["path"]

    def of_kind(self, *kinds: str) -> list[dict]:
        return [a for a in self.assets if a["kind"] in kinds and a.get("enabled", True)]

    def resolve(self, asset_id: str, kinds: tuple[str, ...]) -> dict | None:
        """Retrouve un asset même si Claude a légèrement déformé l'identifiant."""
        asset = self._by_id.get(asset_id)
        if asset and asset["kind"] in kinds and asset.get("enabled", True):
            return asset
        import difflib

        pool = [a["id"] for a in self.of_kind(*kinds)]
        match = difflib.get_close_matches(asset_id, pool, n=1, cutoff=0.75)
        return self._by_id[match[0]] if match else None

    def find_by_tags(self, kinds: tuple[str, ...], *words: str) -> list[dict]:
        wanted = {normalize(w) for w in words}
        found = []
        for a in self.of_kind(*kinds):
            hay = set(a["tags"]) | set(tokens(a["name"])) | set(tokens(a.get("description", "")))
            if hay & wanted:
                found.append(a)
        return found

    def update(self, asset_id: str, changes: dict) -> dict:
        asset = self._by_id[asset_id]
        for field in ("tags", "description", "enabled", "key", "character", "kind"):
            if field in changes:
                asset[field] = changes[field]
        asset["edited"] = True
        self.save()
        return asset

    # --------------------------------------------------------------- prompts
    def catalog(self) -> str:
        """Catalogue compact lu par Claude pour choisir les sons et les persos."""
        sections = []
        groups = [
            ("sfx", "BRUITAGES (sfx)"),
            ("character", "ACTIONS DES PERSONNAGES (à incruster)"),
            ("image", "IMAGES / MEMES (à incruster)"),
            ("video", "CLIPS / MEMES VIDÉO (à incruster)"),
            ("music", "MUSIQUES DE FOND"),
        ]
        for kind, title in groups:
            items = self.of_kind(kind)
            if not items:
                continue
            lines = [f"## {title} — {len(items)} éléments", "id | tags | durée | description"]
            for a in items:
                who = f"{a['character']} — " if a.get("character") else ""
                desc = a.get("description") or ""
                lines.append(f"{a['id']} | {who}{', '.join(a['tags'][:8])} | {a['duration']:.1f}s | {desc}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections) if sections else "(bibliothèque vide : aucun son ni personnage disponible)"

    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for a in self.assets:
            counts[a["kind"]] = counts.get(a["kind"], 0) + 1
        return counts
