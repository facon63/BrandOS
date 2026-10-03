"""Transcription (Whisper en local) et attribution des répliques à Krok ou à Mil."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import Levels, pcm_duration, read_pcm
from .config import WhisperSettings

LAUGH_RE = re.compile(r"\b(?:a?h(?:a|ah|ahah)+h?|mdr+|ptdr+|xptdr+|hihi+|héhé+|lol)\b", re.I)


# --------------------------------------------------------------------- Whisper
def resolve_device(settings: WhisperSettings) -> str:
    if settings.device != "auto":
        return settings.device
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def load_whisper(settings: WhisperSettings, device: str):
    from faster_whisper import WhisperModel  # import tardif : dépendance lourde

    compute = settings.compute_type
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return WhisperModel(settings.model, device=device, compute_type=compute)


def chunk_bounds(levels: Levels, duration: float, chunk_s: float, search_s: float = 30.0) -> list[tuple[float, float]]:
    """Découpe en morceaux de ~chunk_s, en coupant dans un silence pour ne pas hacher un mot."""
    activity = np.maximum(levels.a - levels.floor_a, levels.b - levels.floor_b)
    bounds = [0.0]
    t = chunk_s
    while t < duration - search_s:
        i0 = int(max(0, t - search_s) / levels.hop)
        i1 = int(min(duration, t + search_s) / levels.hop)
        window = activity[i0:i1]
        # le point le plus calme, en préférant rester près de la cible
        distance = np.abs(np.arange(i0, i1) * levels.hop - t)
        cut = (i0 + int(np.argmin(window + 0.05 * distance))) * levels.hop if len(window) else t
        bounds.append(cut)
        t = cut + chunk_s
    bounds.append(duration)
    return list(zip(bounds[:-1], bounds[1:]))


def _transcribe_chunk(model, audio, t0, t1, duration, settings, label, on_progress) -> list[dict]:
    segments, _info = model.transcribe(
        audio,
        language=settings.language or None,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=settings.beam_size,
        condition_on_previous_text=False,  # évite les boucles d'hallucination sur les longs rush
    )
    out = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                out.append({"w": text, "s": round(t0 + w.start, 3), "e": round(t0 + w.end, 3), "p": round(w.probability, 3)})
        if on_progress:
            on_progress((t0 + min(seg.end, t1 - t0)) / duration, label)
    return out


def transcribe_mix(
    mix_pcm: Path,
    levels: Levels,
    settings: WhisperSettings,
    cache_dir: Path,
    on_progress: Callable[[float, str], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Transcrit le mix maître morceau par morceau (reprise possible après coupure)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    duration = pcm_duration(mix_pcm)
    chunks = chunk_bounds(levels, duration, settings.chunk_minutes * 60)
    model = None
    device = resolve_device(settings)
    words: list[dict] = []
    for index, (t0, t1) in enumerate(chunks):
        cache = cache_dir / f"{index:03d}_{t0:.1f}.json"
        if cache.exists():
            words += json.loads(cache.read_text("utf-8"))
            continue
        if model is None:
            if on_progress:
                on_progress(t0 / duration, f"Chargement du modèle Whisper ({settings.model}, {device})…")
            model = load_whisper(settings, device)
        audio = read_pcm(mix_pcm, t0, t1 - t0)
        label = f"Transcription {index + 1}/{len(chunks)}"
        try:
            chunk_words = _transcribe_chunk(model, audio, t0, t1, duration, settings, label, on_progress)
        except (RuntimeError, OSError) as exc:
            if device != "cuda" or settings.device != "auto":
                raise
            # Carte NVIDIA détectée mais CUDA/cuDNN mal installés : on continue sur le processeur
            if log:
                log(f"GPU inutilisable ({exc}) : transcription sur le processeur.")
            device = "cpu"
            model = load_whisper(settings, device)
            chunk_words = _transcribe_chunk(model, audio, t0, t1, duration, settings, label, on_progress)
        cache.write_text(json.dumps(chunk_words, ensure_ascii=False), "utf-8")
        words += chunk_words
    words.sort(key=lambda w: w["s"])
    return words


# ----------------------------------------------------------- qui parle ? / lignes
def attribute_speakers(words: list[dict], levels: Levels, margin_db: float = 3.0) -> list[str | None]:
    """Compare les niveaux des deux micros pendant chaque mot."""
    raw: list[str | None] = []
    for w in words:
        da = levels.mean_db("A", w["s"], w["e"]) - levels.floor_a
        db = levels.mean_db("B", w["s"], w["e"]) - levels.floor_b
        diff = da - db
        raw.append("A" if diff > margin_db else "B" if diff < -margin_db else None)

    # Comble les mots indécis avec le voisinage
    filled = list(raw)
    last = None
    for i, spk in enumerate(filled):
        if spk is None:
            filled[i] = last
        else:
            last = spk
    nxt = None
    for i in range(len(filled) - 1, -1, -1):
        if filled[i] is None:
            filled[i] = nxt
        else:
            nxt = filled[i]

    # Supprime les micro-changements (1 mot isolé au milieu de l'autre)
    for i in range(1, len(filled) - 1):
        if filled[i - 1] == filled[i + 1] != filled[i] and raw[i] is None:
            filled[i] = filled[i - 1]
    return filled


def build_lines(words: list[dict], levels: Levels, *, max_gap: float = 1.2, max_words: int = 28) -> list[dict]:
    speakers = attribute_speakers(words, levels)
    lines: list[dict] = []
    current: list[tuple[dict, str | None]] = []

    def flush():
        if not current:
            return
        ws = [w for w, _ in current]
        spk_votes = [s for _, s in current if s]
        speaker = max(set(spk_votes), key=spk_votes.count) if spk_votes else None
        text = " ".join(w["w"] for w in ws)
        start, end = ws[0]["s"], ws[-1]["e"]
        key_loud = levels.loud_a if speaker == "A" else levels.loud_b
        loud = speaker is not None and levels.mean_db(speaker, start, end) >= key_loud - 3
        lines.append(
            {
                "start": start,
                "end": end,
                "speaker": speaker,
                "text": text,
                "words": [[w["w"], w["s"], w["e"]] for w in ws],
                "kind": "speech",
                "loud": bool(loud),
                "laugh": bool(LAUGH_RE.search(text)),
            }
        )
        current.clear()

    for w, spk in zip(words, speakers):
        if current:
            prev_w, prev_spk = current[-1]
            sentence_end = prev_w["w"].endswith((".", "?", "!", "…")) and len(current) >= 12
            if spk != prev_spk or w["s"] - prev_w["e"] > max_gap or len(current) >= max_words or sentence_end:
                flush()
        current.append((w, spk))
    flush()

    lines += detect_events(lines, levels)
    lines.sort(key=lambda l: l["start"])
    for i, line in enumerate(lines):
        line["id"] = i
    return lines


def detect_events(lines: list[dict], levels: Levels, *, min_len: float = 0.7) -> list[dict]:
    """Repère les moments bruyants sans parole : rires, cris, grosse action en jeu…"""
    hop = levels.hop
    n = len(levels.a)
    covered = np.zeros(n, dtype=bool)
    for line in lines:
        for _, s, e in line["words"]:
            covered[max(0, int((s - 0.15) / hop)) : int((e + 0.15) / hop) + 1] = True
    strong = (levels.a >= levels.floor_a + 18) | (levels.b >= levels.floor_b + 18)
    loud = levels.loud_mask()
    candidate = strong & ~covered

    events = []
    i = 0
    while i < n:
        if not candidate[i]:
            i += 1
            continue
        j = i
        gap = 0
        while j < n and gap <= 3:  # tolère 0,3 s de creux
            gap = 0 if candidate[j] else gap + 1
            j += 1
        j -= gap
        start, end = i * hop, j * hop
        is_loud = bool(loud[i:j].any())
        if end - start >= min_len and (is_loud or end - start >= 1.5):
            da = levels.mean_db("A", start, end) - levels.floor_a
            db = levels.mean_db("B", start, end) - levels.floor_b
            events.append(
                {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "speaker": "A" if da > db + 3 else "B" if db > da + 3 else None,
                    "text": f"(son fort sans parole {end - start:.1f}s : rires, cris ou action ?)",
                    "words": [],
                    "kind": "event",
                    "loud": is_loud,
                    "laugh": False,
                }
            )
        i = max(j, i + 1)
    return events


# --------------------------------------------------------------- mise en forme
def fmt_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def format_line(line: dict, names: dict[str, str]) -> str:
    marks = ""
    if line.get("loud"):
        marks += " [FORT]"
    if line.get("laugh"):
        marks += " [RIRE]"
    if line["kind"] == "event":
        who = f" côté {names[line['speaker']]}" if line.get("speaker") in names else ""
        return f"#{line['id']} [{fmt_time(line['start'])}] {line['text']}{who}{marks}"
    who = names.get(line.get("speaker") or "", "?")
    return f"#{line['id']} [{fmt_time(line['start'])}] {who} : {line['text']}{marks}"


def format_lines(lines: list[dict], names: dict[str, str]) -> str:
    return "\n".join(format_line(line, names) for line in lines)
