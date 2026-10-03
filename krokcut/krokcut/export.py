"""Exports : timeline XML (Premiere Pro / DaVinci Resolve), sous-titres, chapitres, récap."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .ffmpeg_utils import probe
from .timeline import Timeline
from .transcribe import fmt_time


# ------------------------------------------------------------------ XML FCP7
def _rate(parent: ET.Element, fps: float) -> None:
    rate = ET.SubElement(parent, "rate")
    ntsc = abs(fps * 1.001 - round(fps * 1.001)) < 0.01 and abs(fps - round(fps)) > 0.01
    ET.SubElement(rate, "timebase").text = str(int(round(fps * 1.001)) if ntsc else int(round(fps)))
    ET.SubElement(rate, "ntsc").text = "TRUE" if ntsc else "FALSE"


def _sub(parent: ET.Element, tag: str, text) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = str(text)
    return el


def _pathurl(path: str) -> str:
    uri = Path(path).resolve().as_uri()
    return uri.replace("file:///", "file://localhost/", 1)


def _motion(parent: ET.Element, scale: float, horiz: float = 0.0, vert: float = 0.0) -> None:
    flt = ET.SubElement(parent, "filter")
    eff = ET.SubElement(flt, "effect")
    _sub(eff, "name", "Basic Motion")
    _sub(eff, "effectid", "basic")
    _sub(eff, "effectcategory", "motion")
    _sub(eff, "effecttype", "motion")
    _sub(eff, "mediatype", "video")
    p = ET.SubElement(eff, "parameter")
    _sub(p, "parameterid", "scale")
    _sub(p, "name", "Scale")
    _sub(p, "valuemin", 0)
    _sub(p, "valuemax", 1000)
    _sub(p, "value", f"{scale:.2f}")
    c = ET.SubElement(eff, "parameter")
    _sub(c, "parameterid", "center")
    _sub(c, "name", "Center")
    v = ET.SubElement(c, "value")
    _sub(v, "horiz", f"{horiz:.5f}")
    _sub(v, "vert", f"{vert:.5f}")


def _audio_level(parent: ET.Element, db: float) -> None:
    flt = ET.SubElement(parent, "filter")
    eff = ET.SubElement(flt, "effect")
    _sub(eff, "name", "Audio Levels")
    _sub(eff, "effectid", "audiolevels")
    _sub(eff, "effectcategory", "audiolevels")
    _sub(eff, "effecttype", "audiolevels")
    _sub(eff, "mediatype", "audio")
    p = ET.SubElement(eff, "parameter")
    _sub(p, "parameterid", "level")
    _sub(p, "name", "Level")
    _sub(p, "valuemin", 0)
    _sub(p, "valuemax", 3.98109)
    _sub(p, "value", f"{10 ** (db / 20):.5f}")


class _XmlBuilder:
    def __init__(self, tl: Timeline):
        self.tl = tl
        self.fps = tl.fps
        self.files: dict[str, str] = {}
        self.file_info: dict[str, dict] = {}
        self.n = 0

    def frames(self, seconds: float) -> int:
        return int(round(seconds * self.fps))

    def file_ref(self, parent: ET.Element, path: str, info: dict | None = None) -> None:
        """Ajoute une référence ; la définition complète est posée plus tard sur la 1re occurrence."""
        if path not in self.files:
            self.files[path] = f"file-{len(self.files) + 1}"
            if info is None:
                try:
                    info = probe(path).to_dict()
                except Exception:
                    info = {"duration": 0, "has_video": False, "has_audio": True}
            self.file_info[path] = info
        ET.SubElement(parent, "file", id=self.files[path])

    def define_files(self, root: ET.Element) -> None:
        """Premiere exige que chaque fichier soit décrit à sa première apparition dans le document."""
        by_id = {file_id: path for path, file_id in self.files.items()}
        seen: set[str] = set()
        for f in root.iter("file"):
            file_id = f.get("id")
            if file_id in seen or file_id not in by_id:
                continue
            seen.add(file_id)
            path = by_id[file_id]
            info = self.file_info[path]
            _sub(f, "name", Path(path).name)
            _sub(f, "pathurl", _pathurl(path))
            _rate(f, info.get("fps") or self.fps)
            _sub(f, "duration", self.frames(info.get("duration") or 0))
            media = ET.SubElement(f, "media")
            if info.get("has_video"):
                vid = ET.SubElement(media, "video")
                sc = ET.SubElement(vid, "samplecharacteristics")
                _rate(sc, info.get("fps") or self.fps)
                _sub(sc, "width", info.get("width") or self.tl.width)
                _sub(sc, "height", info.get("height") or self.tl.height)
            if info.get("has_audio"):
                aud = ET.SubElement(media, "audio")
                sc = ET.SubElement(aud, "samplecharacteristics")
                _sub(sc, "depth", 16)
                _sub(sc, "samplerate", 48000)
                _sub(aud, "channelcount", 2)

    def clipitem(self, track: ET.Element, name: str, path: str, start_f: int, frames: int, in_f: int, info=None, audio=False) -> ET.Element:
        self.n += 1
        item = ET.SubElement(track, "clipitem", id=f"clipitem-{self.n}")
        _sub(item, "name", name)
        _sub(item, "enabled", "TRUE")
        dur = (info or {}).get("duration") or 0
        _sub(item, "duration", max(self.frames(dur), in_f + frames))
        _rate(item, self.fps)
        _sub(item, "start", start_f)
        _sub(item, "end", start_f + frames)
        _sub(item, "in", in_f)
        _sub(item, "out", in_f + frames)
        self.file_ref(item, path, info)
        if audio:
            st = ET.SubElement(item, "sourcetrack")
            _sub(st, "mediatype", "audio")
            _sub(st, "trackindex", 1)
        return item


def _alloc(tracks: list[list[tuple[int, int]]], start: int, end: int) -> int:
    for i, used in enumerate(tracks):
        if all(end <= s or start >= e for s, e in used):
            used.append((start, end))
            return i
    tracks.append([(start, end)])
    return len(tracks) - 1


def export_xml(tl: Timeline, out: Path, name: str) -> Path:
    b = _XmlBuilder(tl)
    W, H = tl.width, tl.height
    root = ET.Element("xmeml", version="5")
    seq = ET.SubElement(root, "sequence", id="sequence-1")
    _sub(seq, "name", name)
    _sub(seq, "duration", tl.total_frames)
    _rate(seq, tl.fps)
    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    fmt = ET.SubElement(video, "format")
    sc = ET.SubElement(fmt, "samplecharacteristics")
    _rate(sc, tl.fps)
    _sub(sc, "width", W)
    _sub(sc, "height", H)
    _sub(sc, "pixelaspectratio", "square")
    _sub(sc, "fielddominance", "none")

    v1, v2 = ET.SubElement(video, "track"), ET.SubElement(video, "track")
    audio = ET.SubElement(media, "audio")
    _sub(audio, "numOutputChannels", 2)
    a1, a2 = ET.SubElement(audio, "track"), ET.SubElement(audio, "track")

    infos = {k: s.info for k, s in tl.sources.items()}
    for clip in tl.clips:
        keys = ["A", "B"] if clip.pov == "both" else [clip.pov]
        # Découpe aux bornes des zooms : chaque morceau a une échelle fixe (facile à retoucher)
        cuts = {0, clip.frames}
        for z in clip.zooms:
            cuts.update({min(clip.frames, max(0, b.frames(z.t0))), min(clip.frames, max(0, b.frames(z.t1)))})
        cuts = sorted(cuts)
        for f0, f1 in zip(cuts[:-1], cuts[1:]):
            if f1 <= f0:
                continue
            mid = (f0 + f1) / 2 / tl.fps
            zoom = next((z for z in clip.zooms if z.t0 <= mid < z.t1), None)
            scale = {"punch": z_scale(zoom), "slow": 108.0, "shake": 110.0}[zoom.kind] if zoom else 100.0
            for j, key in enumerate(keys):
                src = tl.sources[key]
                in_f = b.frames(src.to_source_time(clip.src_in) + f0 / tl.fps)
                track = v1 if j == 0 else v2
                item = b.clipitem(track, f"POV {src.name}", src.path, clip.start_f + f0, f1 - f0, in_f, infos[key])
                if clip.pov == "both":  # écran partagé : deux images réduites côte à côte
                    _motion(item, scale * 0.5, horiz=-0.25 if j == 0 else 0.25)
                elif scale != 100.0:
                    _motion(item, scale)
            if tl.layout == "pip" and clip.pov in ("A", "B"):
                other = tl.sources["B" if clip.pov == "A" else "A"]
                if other.covers(clip.src_in, clip.src_out):
                    in_f = b.frames(other.to_source_time(clip.src_in) + f0 / tl.fps)
                    item = b.clipitem(v2, f"PiP {other.name}", other.path, clip.start_f + f0, f1 - f0, in_f, infos[other.key])
                    _motion(item, 30.0, horiz=0.5 - 0.02 - 0.15, vert=-0.5 + 0.02 * W / H + 0.15)
        # Son : A1 = POV affiché (ou A), A2 = l'autre en mode mix
        audio_keys = keys if tl.audio_mode == "follow" else (["A", "B"] if tl.audio_mode == "mix" else [tl.audio_mode])
        for j, key in enumerate(audio_keys[:2]):
            src = tl.sources[key]
            if not src.covers(clip.src_in, clip.src_out) or not src.info.get("has_audio"):
                continue
            in_f = b.frames(src.to_source_time(clip.src_in))
            b.clipitem(a1 if j == 0 else a2, f"Son {src.name}", src.path, clip.start_f, clip.frames, in_f, infos[key], audio=True)

    # Personnages / memes sur des pistes vidéo au-dessus
    overlay_tracks: list[list[tuple[int, int]]] = []
    overlay_elements: list[ET.Element] = []
    for o in tl.overlays:
        start, frames = b.frames(o.start), max(1, b.frames(o.duration))
        idx = _alloc(overlay_tracks, start, start + frames)
        while len(overlay_elements) <= idx:
            overlay_elements.append(ET.SubElement(video, "track"))
        info = None
        try:
            info = probe(o.path).to_dict()
        except Exception:
            pass
        asset_h = (info or {}).get("height") or H
        scale = (H * o.scale) / asset_h * 100 if o.position != "center" else 100.0
        horiz, vert = _overlay_center(o.position, o.scale, (info or {}).get("width") or H, asset_h, W, H)
        item = b.clipitem(overlay_elements[idx], o.asset_id, o.path, start, frames, 0, info)
        _motion(item, scale, horiz, vert)

    # Bruitages et musique sur des pistes audio dédiées
    for items, label in ((tl.sfx, "sfx"), (tl.music, "music")):
        tracks: list[list[tuple[int, int]]] = []
        elements: list[ET.Element] = []
        for s in items:
            start = b.frames(s.start)
            length = (s.end - s.start) if label == "music" else (s.duration or 1.0)
            frames = max(1, b.frames(length))
            idx = _alloc(tracks, start, start + frames)
            while len(elements) <= idx:
                elements.append(ET.SubElement(audio, "track"))
            item = b.clipitem(elements[idx], s.asset_id, s.path, start, frames, 0, None, audio=True)
            _audio_level(item, s.volume_db)

    for m in tl.markers:
        mk = ET.SubElement(seq, "marker")
        _sub(mk, "name", m.name)
        _sub(mk, "comment", "chapitre")
        _sub(mk, "in", b.frames(m.start))
        _sub(mk, "out", -1)
    for t in tl.texts:
        mk = ET.SubElement(seq, "marker")
        _sub(mk, "name", f"TEXTE : {t.text}")
        _sub(mk, "comment", f"texte à l'écran ({t.style})")
        _sub(mk, "in", b.frames(t.start))
        _sub(mk, "out", b.frames(t.start + t.duration))

    b.define_files(root)
    ET.indent(root)
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
    out.write_text(xml, "utf-8")
    return out


def z_scale(zoom) -> float:
    return round(zoom.scale * 100, 1)


def _overlay_center(position: str, scale: float, aw: int, ah: int, W: int, H: int) -> tuple[float, float]:
    h = H * scale
    w = aw * h / ah if ah else h
    m = W * 0.03
    cx = {"left": m + w / 2, "bottom_left": m + w / 2, "top_left": m + w / 2,
          "right": W - m - w / 2, "bottom_right": W - m - w / 2, "top_right": W - m - w / 2}.get(position, W / 2)
    cy = {"top_left": m + h / 2, "top_right": m + h / 2,
          "bottom_left": H - h / 2, "bottom_right": H - h / 2}.get(position, H / 2)
    return (cx - W / 2) / W, (cy - H / 2) / H


# ---------------------------------------------------------------- sous-titres
def _srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def timeline_words(tl: Timeline, lines: list[dict]) -> list[tuple[str, float, float]]:
    words = [(w, s, e) for line in lines for w, s, e in line.get("words", [])]
    words.sort(key=lambda x: x[1])
    out = []
    import bisect

    starts = [w[1] for w in words]
    for clip in tl.clips:
        t0 = clip.start_f / tl.fps
        i = bisect.bisect_left(starts, clip.src_in)
        while i < len(words) and words[i][1] < clip.src_out:
            w, s, e = words[i]
            out.append((w, t0 + s - clip.src_in, t0 + min(e, clip.src_out) - clip.src_in))
            i += 1
    return out


def export_srt(tl: Timeline, lines: list[dict], out: Path, max_chars: int = 42) -> Path:
    words = timeline_words(tl, lines)
    cues: list[tuple[float, float, str]] = []
    current: list[tuple[str, float, float]] = []

    def flush():
        if current:
            cues.append((current[0][1], max(current[-1][2], current[0][1] + 0.6), " ".join(w for w, _, _ in current)))
            current.clear()

    for w in words:
        if current:
            text_len = len(" ".join(x[0] for x in current)) + len(w[0]) + 1
            if text_len > max_chars or w[1] - current[-1][2] > 0.6 or w[1] - current[0][1] > 3.5:
                flush()
        current.append(w)
    flush()
    with open(out, "w", encoding="utf-8") as fh:
        for i, (s, e, text) in enumerate(cues, start=1):
            nxt = cues[i][0] if i < len(cues) else e
            fh.write(f"{i}\n{_srt_time(s)} --> {_srt_time(min(e, nxt))}\n{text}\n\n")
    return out


def export_chapters(tl: Timeline, out: Path) -> Path:
    """Chapitres au format YouTube : premier à 0:00, 10 s minimum chacun, 3 au moins."""
    chapters: list[tuple[float, str]] = []
    for m in sorted(tl.markers, key=lambda m: m.start):
        start = 0.0 if not chapters and m.start < 10 else m.start
        if not chapters and start > 0:
            chapters.append((0.0, "Intro"))
        if chapters and start - chapters[-1][0] < 10:
            continue
        if tl.duration - start < 10:
            break
        chapters.append((start, m.name))
    if not chapters:
        chapters = [(0.0, "Intro")]
    text = "\n".join(f"{_yt_time(t)} {name}" for t, name in chapters) + "\n"
    if len(chapters) < 3:
        text += "\n(YouTube n'affiche les chapitres qu'à partir de 3 : ajoute des titres de chapitre dans la sélection.)\n"
    out.write_text(text, "utf-8")
    return out


def _yt_time(t: float) -> str:
    t = int(t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def export_report(tl: Timeline, story: dict, out: Path, name: str, cost: float | None = None) -> Path:
    lines = [f"# {name}", ""]
    lines.append(f"Durée finale : **{_yt_time(tl.duration)}** — {len(tl.clips)} plans, {len(tl.sfx)} bruitages, "
                 f"{len(tl.overlays)} incrustations, {len(tl.texts)} textes, {sum(1 for c in tl.clips for _ in c.zooms)} zooms.")
    if cost:
        lines.append(f"Coût Claude estimé pour cet épisode : {cost:.2f} $")
    lines.append(f"Dérush réalisé par : {'Claude' if story.get('source') == 'claude' else 'mode hors ligne (heuristique)'}")
    if story.get("summary"):
        lines += ["", "## Résumé", story["summary"]]
    if story.get("title_ideas"):
        lines += ["", "## Idées de titres"] + [f"- {t}" for t in story["title_ideas"]]
    if story.get("thumbnail_ideas"):
        lines += ["", "## Idées de miniature"] + [f"- {t}" for t in story["thumbnail_ideas"]]
    lines += ["", "## Déroulé", "", "| Timeline | Rush (temps maître) | Moment |", "|---|---|---|"]
    for seg in tl.segments:
        clips = [c for c in tl.clips if c.segment == seg.index]
        src = f"{fmt_time(clips[0].src_in)} → {fmt_time(clips[-1].src_out)}" if clips else ""
        lines.append(f"| {_yt_time(seg.start)} | {src} | {seg.title or seg.moment_id} |")
    if story.get("notes"):
        lines += ["", "## Notes du monteur", story["notes"]]
    out.write_text("\n".join(lines) + "\n", "utf-8")
    return out
