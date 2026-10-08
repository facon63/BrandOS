"""Comparaison des chaînes : chiffres côte à côte, réglages proposés, faisabilité et rapport de Claude.

Tout ce qui est chiffré est calculé ici, en direct et sans Claude : le tableau des mesures, les réglages
proposés (formule ancrée sur la base, §6.4), la feuille de route « Pas encore faisable » et les manques de la
bibliothèque. Claude n'intervient que dans le job « benchmark_report » (profil de chaque chaîne, puis
comparaison) et cite les propositions par leur id, sans jamais donner de valeur.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import techniques
from .benchmark import (
    ALPHA,
    LOCAL_STEPS,
    MAX_MINUTES,
    QUALITY_LABELS,
    BenchDoc,
    BenchmarkStore,
    BenchSettings,
    VideoData,
    claude_analysed,
    claude_fp,
    current_claude_fp,
    current_local_fp,
    fmt_duration,
    fr,
    local_fp,
    nearest_tile,
    norm_text,
)
from .config import AppConfig, StyleProfile, channel_bible
from .library import Library
from .llm import LLM, PRICE_IN, PRICE_OUT, STR, LLMError, arr, claude_available, enum, obj
from .prompts import CHANNEL_INSTRUCTIONS, CHANNEL_SYSTEM, COMPARISON_INSTRUCTIONS, KROKCUT_CAPABILITIES
from .references import ReferenceStore, _rate, atomic_write, typical_docs
from .steps import Cancelled

MIN_CLAUDE_COVERAGE = 0.6
MAX_PROFILE_VIDEOS = 6
CHANNEL_MAX_TOKENS = 24000
COMPARISON_MAX_TOKENS = 48000
BIBLE_MAX_CHARS = 3000
GUIDE_MAX_CHARS = 3000
CONSIGNE_MAX_CHARS = 300
FEASIBILITY_MIN_RATE = 0.2  # techniques montrées à Claude dans le tableau de faisabilité
ROADMAP_MIN_RATE = 0.3
ROADMAP_MIN_OCCURRENCES = 3
ROADMAP_MIN_VIDEOS = 2
ROADMAP_RATIO = 2.0
CONSTANT_BOOST = 1.5
EFFORT_ORDER = {"facile": 0, "moyen": 1, "difficile": 2, "": 3}
MAX_ROADMAP_EXAMPLES = 3
GAP_MIN_RATE = 0.5
GAP_MUSIC_PCT = 25.0
# Réglages (§6.4)
RATIO_MIN_BASE = 0.2  # en dessous, formule additive (on ne divise pas par presque rien)
DENSITY_MIN_REL, DENSITY_MIN_ABS = 0.10, 0.3
STEP = {"seconds": 0.05, "scale": 0.05, "db": 1.0}
MUSIC_REF_PCT, MUSIC_BASE_PCT, MUSIC_MONTAGE_PCT, MUSIC_LEVEL_PCT = 25.0, 10.0, 50.0, 20.0
WHOOSH_REF_SHARE, WHOOSH_BASE_SHARE, WHOOSH_WINDOW_S = 0.5, 0.25, 1.0
LAYOUT_MAP = {"deux_pov_cote_a_cote": "split", "pov_en_incrustation": "pip", "alternance": "switch"}
# Estimation du rapport (§5.8) : ≈ 20 k / 6 k par chaîne, 45 k / 15 k pour la comparaison
CHANNEL_TOKENS = (20000, 6000)
COMPARISON_TOKENS = (45000, 15000)

INCOMPLETE = "comparaison incomplète"
REFUSED_MSG = (
    "Analyse d'abord au moins une vidéo de Krok et Mil (« Reprendre depuis Mes vidéos ») : la comparaison "
    "n'est juste que si vos vidéos passent exactement par les mêmes mesures."
)
NO_MODEL_MSG = "Analyse d'abord avec Claude au moins une vidéo d'une chaîne modèle (Wankil Studio, Club Pungouin…)."
SOUND_CATS = ("sature", "boum", "bip", "tonal", "glissando", "whoosh", "montee", "clic")
SOUND_CAT_LABELS = {
    "sature": "son saturé",
    "boum": "boum / impact grave",
    "bip": "bip (censure ?)",
    "tonal": "ding / jingle / notification",
    "glissando": "son cartoon (glissando, boing)",
    "whoosh": "whoosh / transition",
    "montee": "montée (riser)",
    "clic": "coup bref / clic",
}

# (id, libellé, unité, groupe, source, fiabilité, comparaison) — comparaison : ratio, diff (dB) ou info
ROWS: list[tuple[str, str, str, str, str, str, str]] = [
    ("duration_min", "Durée", "min", "Format", "mesure", "fiable", "info"),
    ("cuts_per_min", "Changements de plan", "/min", "Rythme", "mesure", "fiable", "ratio"),
    ("median_shot", "Durée médiane d'un plan", "s", "Rythme", "mesure", "fiable", "ratio"),
    ("shot_p25", "Plans courts (un quart des plans font moins de)", "s", "Rythme", "mesure", "fiable", "ratio"),
    ("shots_under_1s_pct", "Plans de moins d'1 s", "%", "Rythme", "mesure", "fiable", "ratio"),
    ("jump_cut_pct", "Jump cuts probables", "%", "Rythme", "mesure", "indicatif", "ratio"),
    ("visual_changes_per_min", "Changements visuels (coupes, zooms, flashs)", "/min", "Rythme", "mesure", "fiable", "ratio"),
    ("punch_ins_per_min", "Zooms secs mesurés", "/min", "Zooms", "mesure", "fiable", "ratio"),
    ("punch_ins", "Zooms secs mesurés (par vidéo)", "", "Zooms", "mesure", "fiable", "ratio"),
    ("zoom_scale_median", "Grossissement des zooms", "×", "Zooms", "mesure", "fiable", "ratio"),
    ("zoom_hold_median_s", "Durée d'un zoom", "s", "Zooms", "mesure", "fiable", "ratio"),
    ("zooms_confirmed_per_min", "Zooms secs confirmés par Claude", "/min", "Zooms", "mesure+claude", "fiable", "ratio"),
    ("zooms_total_per_min", "Tous les zooms (secs, lents, ciblés)", "/min", "Zooms", "mesure+claude", "fiable", "ratio"),
    ("flashes_per_min", "Flashs", "/min", "Effets image", "mesure", "fiable", "ratio"),
    ("inserts_per_min", "Images insérées brèves", "/min", "Effets image", "mesure", "fiable", "ratio"),
    ("freezes_per_min", "Images figées", "/min", "Effets image", "mesure", "indicatif", "ratio"),
    ("fades_per_min", "Fondus au noir", "/min", "Effets image", "mesure", "fiable", "ratio"),
    ("bw_per_10min", "Passages en noir et blanc", "/10 min", "Effets image", "mesure", "fiable", "ratio"),
    ("letterbox_pct", "Bandes noires « cinéma »", "%", "Effets image", "mesure", "fiable", "ratio"),
    ("sound_events_per_min", "Sons marquants (jeu compris)", "/min", "Bruitages", "mesure", "indicatif", "ratio"),
    *[
        (f"sound_by_cat.{c}", f"Sons marquants : {SOUND_CAT_LABELS[c]}", "/min", "Bruitages", "mesure", "indicatif", "ratio")
        for c in SOUND_CATS
    ],
    ("sfx_montage_per_min", "Bruitages ajoutés au montage (selon Claude)", "/min", "Bruitages", "claude", "estime", "ratio"),
    ("events_with_visual_pct", "Sons calés sur un effet ou une coupe", "%", "Bruitages", "mesure", "indicatif", "ratio"),
    ("sound_level_vs_voice_db", "Volume des sons par rapport aux voix", "dB", "Bruitages", "mesure", "indicatif", "diff"),
    ("music_pct", "Musique de fond (part du temps)", "%", "Musique", "mesure", "indicatif", "ratio"),
    ("music_bpm_median", "Tempo de la musique", "BPM", "Musique", "mesure", "indicatif", "ratio"),
    ("music_level_vs_voice_db", "Volume de la musique par rapport aux voix", "dB", "Musique", "mesure", "indicatif", "diff"),
    ("music_changes_per_10min", "Changements de musique", "/10 min", "Musique", "mesure", "indicatif", "ratio"),
    ("music_cuts_per_10min", "Musique coupée net", "/10 min", "Musique", "mesure", "indicatif", "ratio"),
    ("music_montage_pct", "Musique ajoutée au montage (selon Claude)", "%", "Musique", "claude", "estime", "ratio"),
    ("silences_per_10min", "Silences complets", "/10 min", "Silences et parole", "mesure", "fiable", "ratio"),
    ("sound_cuts_per_10min", "Son coupé net", "/10 min", "Silences et parole", "mesure", "fiable", "ratio"),
    ("dead_air_pct", "Temps morts", "%", "Silences et parole", "mesure", "fiable", "ratio"),
    ("pause_p50", "Blanc médian entre deux mots", "s", "Silences et parole", "mesure", "fiable", "ratio"),
    ("pause_p90", "Blancs longs entre deux mots (90 % font moins de)", "s", "Silences et parole", "mesure", "fiable", "ratio"),
    ("reaction_tail_median", "Respiration après la dernière phrase d'un plan", "s", "Silences et parole", "mesure", "indicatif", "ratio"),
    ("cuts_in_word_pct", "Coupes en pleine phrase", "%", "Silences et parole", "mesure", "indicatif", "ratio"),
    ("speech_ratio", "Part du temps avec de la parole", "", "Silences et parole", "mesure", "fiable", "ratio"),
    ("words_per_min", "Débit de parole", "mots/min", "Silences et parole", "mesure", "fiable", "ratio"),
    ("loudness_i", "Volume moyen", "LUFS", "Volume", "mesure", "fiable", "diff"),
    ("loudness_lra", "Écarts de volume", "LU", "Volume", "mesure", "fiable", "diff"),
    ("true_peak_db", "Crête", "dB", "Volume", "mesure", "fiable", "diff"),
    ("loudness_spikes_per_min", "Pics de volume", "/min", "Volume", "mesure", "fiable", "ratio"),
    ("claude_texts_per_min", "Textes ajoutés", "/min", "Vu par Claude", "claude", "estime", "ratio"),
    ("claude_overlays_per_min", "Incrustations (persos, memes, stickers)", "/min", "Vu par Claude", "claude", "estime", "ratio"),
    ("claude_time_effects_per_min", "Effets de temps (arrêt sur image, ralenti…)", "/min", "Vu par Claude", "claude", "estime", "ratio"),
    ("gags_per_min", "Gags", "/min", "Vu par Claude", "claude", "estime", "ratio"),
    ("gag_force_mean", "Force moyenne des gags (1 à 5)", "", "Vu par Claude", "claude", "estime", "ratio"),
    ("teaser_pct", "Vidéos avec un teaser d'ouverture", "%", "Vu par Claude", "claude", "estime", "ratio"),
    ("library_recall", "Bruitages de votre bibliothèque retrouvés par le détecteur", "", "Contrôle", "mesure", "fiable", "info"),
]
ROW_BY_ID = {r[0]: r for r in ROWS}
MUSIC_NOTE = "une nappe sans rythme sous la voix peut être manquée : 0 % veut dire « pas détectée »"
# Mesures qui n'existent que s'il y a quelque chose à mesurer : sans zoom, pas de grossissement ; sans
# musique, pas de niveau de musique. Les modules de mesure écrivent alors 0, qui veut dire « pas mesuré » et
# ne doit compter ni dans les médianes ni dans les réglages proposés (un grossissement de 0 tirerait
# punch_scale vers le bas, un niveau de musique de 0 dB le tirerait vers le haut).
DEFINED_IF = {  # métrique -> compte qui doit être non nul pour qu'elle ait un sens
    "zoom_scale_median": "punch_ins",
    "zoom_hold_median_s": "punch_ins",
    "music_bpm_median": "music_segments",
    "music_level_vs_voice_db": "music_segments",
    "sound_level_vs_voice_db": "sound_events_per_min",
}
ZERO_IS_UNKNOWN = {"zoom_scale_median", "zoom_hold_median_s", "music_bpm_median", "pause_p50", "pause_p90", "reaction_tail_median"}

# Réglages proposés : (champ, métriques par ordre de préférence, règle, bornes, arrondi, libellé)
FIELDS: list[tuple[str, tuple[str, ...], str, tuple[float, float], str, str]] = [
    ("zooms_per_minute", ("zooms_total_per_min", "punch_ins_per_min"), "ratio", (0.0, 15.0), "density", "Zooms par minute"),
    ("punch_scale", ("zoom_scale_median",), "delta", (1.05, 2.0), "scale", "Grossissement du zoom punch"),
    ("sfx_per_minute", ("sfx_montage_per_min", "sound_events_per_min"), "ratio", (0.0, 20.0), "density", "Bruitages par minute"),
    ("sfx_volume_db", ("sound_level_vs_voice_db",), "delta", (-20.0, 3.0), "db", "Volume des bruitages"),
    ("texts_per_minute", ("claude_texts_per_min",), "ratio", (0.0, 8.0), "density", "Textes par minute"),
    ("characters_per_minute", ("claude_overlays_per_min",), "ratio", (0.0, 8.0), "density", "Persos et memes par minute"),
    ("max_silence", ("pause_p90",), "delta", (0.25, 1.5), "seconds", "Blanc maximal gardé"),
    ("reaction_tail", ("reaction_tail_median",), "delta", (0.2, 1.5), "seconds", "Respiration après une chute"),
    ("min_shot", ("median_shot",), "ratio", (0.8, 6.0), "seconds", "Durée minimale d'un plan (POV)"),
    ("music_volume_db", ("music_level_vs_voice_db",), "delta", (-36.0, -12.0), "db", "Volume de la musique"),
]
VOTE_FIELDS = {
    "music": "Musique de fond",
    "transition_sfx": "Whoosh aux changements de partie",
    "cold_open": "Teaser d'ouverture",
    "layout": "Mise en page des deux POV",
}
SOURCE_LABELS = {
    "zooms_total_per_min": "mesuré + confirmé par Claude",
    "sfx_montage_per_min": "estimé (sons détectés, triés par Claude)",
    "sound_events_per_min": "estimé (sons détectés, jeu compris)",
    "claude_texts_per_min": "vu par Claude",
    "claude_overlays_per_min": "vu par Claude",
}
INTENSITY_WORDS = {1 / 3: "un peu", 0.5: "à mi-chemin", 1.0: "comme eux"}
UNIT_WORDS = {"/min": "/min", "s": " s", "×": "", "dB": " dB", "/10 min": " par 10 min"}

_REPORT_LOCK = threading.Lock()


# ------------------------------------------------------------------ éligibilité
def eligible(doc: BenchDoc, cfg: AppConfig, settings: BenchSettings) -> tuple[bool, bool, str]:
    """(comptée dans les mesures, comptée dans ce que Claude a vu, raison de l'exclusion)."""
    st = doc.state.steps
    m = doc.state.metrics
    if not all(st[s].status == "done" for s in LOCAL_STEPS):
        return False, False, "mesures pas encore terminées"
    if local_fp(doc) != current_local_fp(cfg):
        return False, False, "mesurée par une ancienne version : relance les mesures (gratuit)"
    if m.get("short"):
        return False, False, "Short"
    if (m.get("duration_min") or 0) > MAX_MINUTES:
        return False, False, "plus d'une heure (live ou rush ?)"
    if not claude_analysed(doc):
        return True, False, "pas encore analysée par Claude"
    current = current_claude_fp(cfg, settings)
    fp = claude_fp(doc)
    if fp[1] != current[1]:
        return True, False, f"analyse Claude en qualité {QUALITY_LABELS.get(fp[1], fp[1] or '?')}"
    if fp != current:
        return True, False, "analyse Claude d'une ancienne version : à refaire"
    if doc.state.coverage < MIN_CLAUDE_COVERAGE:
        return True, False, f"couverture Claude {round(100 * doc.state.coverage)} %"
    return True, True, ""


class Study:
    """Les chaînes, leurs vidéos comptées et exclues (avec la raison), la base et les cibles."""

    def __init__(self, store: BenchmarkStore, cfg: AppConfig, settings: BenchSettings | None = None):
        self.store = store
        self.cfg = cfg
        self.settings = settings or store.settings()
        self.channels = list(self.settings.channels)
        self.names = {c.id: c.name for c in self.channels}
        self.roles = {c.id: c.role for c in self.channels}
        self.docs: dict[str, list[BenchDoc]] = defaultdict(list)
        self.local: dict[str, list[BenchDoc]] = defaultdict(list)
        self.claude: dict[str, list[BenchDoc]] = defaultdict(list)
        self.excluded: dict[str, list[dict]] = defaultdict(list)
        self.claude_excluded: dict[str, list[dict]] = defaultdict(list)
        known = set(self.names)
        for doc in store.list():
            if doc.state.channel in known:
                self.docs[doc.state.channel].append(doc)
        for cid, docs in self.docs.items():
            local, claude_ok = [], set()
            for doc in docs:
                ok_local, ok_claude, reason = eligible(doc, cfg, self.settings)
                if not ok_local:
                    self.excluded[cid].append({"id": doc.id, "name": doc.state.name, "reason": reason})
                    continue
                local.append(doc)
                if ok_claude:
                    claude_ok.add(doc.id)
                else:
                    self.claude_excluded[cid].append({"id": doc.id, "name": doc.state.name, "reason": reason})
            typical = typical_docs(local) if local else []
            for doc in local:
                if doc not in typical:
                    self.excluded[cid].append({"id": doc.id, "name": doc.state.name, "reason": "durée inhabituelle pour la chaîne"})
            self.local[cid] = typical
            self.claude[cid] = [d for d in typical if d.id in claude_ok]
        own = next((c.id for c in self.channels if c.role == "nous"), "")
        krokcut = next((c.id for c in self.channels if c.role == "krokcut"), "")
        self.own = own
        self.base = krokcut if krokcut and self.local.get(krokcut) else own
        models = [c.id for c in self.channels if c.role == "modele"]
        wanted = [t for t in self.settings.targets if t in models]
        self.models = models
        self.targets = wanted or models

    def can_run(self) -> tuple[bool, str]:
        if not self.claude.get(self.own):
            return False, REFUSED_MSG
        if not any(self.claude.get(c) for c in self.models):
            return False, NO_MODEL_MSG
        return True, ""

    def sources(self) -> dict[str, float]:
        """Ce sur quoi repose la partie Claude du rapport : il est périmé dès que ça change."""
        out = {}
        for cid in sorted(self.claude):
            for doc in self.claude[cid]:
                out[doc.id] = doc.state.steps["synthesize"].finished or 0.0
        return out

    def claude_channels(self) -> dict[str, str]:
        return {d.id: cid for cid, docs in self.claude.items() for d in docs}

    def outdated(self, stored: dict) -> bool:
        """Rapport périmé : autres vidéos, analyses refaites, ou vidéo déplacée vers une autre chaîne."""
        if not stored:
            return False
        if stored.get("sources") != self.sources():
            return True
        before = {v: c["id"] for c in stored.get("channels") or [] for v in c.get("claude_videos") or []}
        return bool(before) and before != self.claude_channels()

    def profile(self, doc: BenchDoc) -> dict:
        return doc.read_json("profil.json") or {}


def base_and_targets(store: BenchmarkStore, settings: BenchSettings, cfg: AppConfig | None = None) -> tuple[str, list[str]]:
    study = Study(store, cfg or AppConfig.load(), settings)
    return study.base, study.targets


# ------------------------------------------------------------------ tableau
def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _metric(doc: BenchDoc, key: str):
    """Valeur d'une ligne du tableau pour une vidéo ; None si elle n'est pas mesurée (ou pas mesurable)."""
    m = doc.state.metrics
    if key.startswith("sound_by_cat."):
        cats = m.get("sound_by_cat")
        return None if cats is None else float(cats.get(key.split(".", 1)[1], 0.0))
    if key == "teaser_pct":
        teaser = ((doc.read_json("profil.json") or {}).get("accroche") or {}).get("teaser")
        return {"oui": 100.0, "non": 0.0}.get(teaser)
    value = _number(m.get(key))
    if value is None:
        return None
    if key in DEFINED_IF and not _number(m.get(DEFINED_IF[key])):
        return None
    if key in ZERO_IS_UNKNOWN and value <= 0:
        return None
    return value


def _summary(values: list[float]) -> dict:
    return {
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "n": len(values),
        "sum": round(sum(values), 3),
    }


def ecart_label(ref: float, base: float, n_ref: int, n_base: int, unit: str, *, ref_range=None, base_range=None) -> dict:
    """Écart d'une chaîne modèle à la base : gros_ecart, ecart, proche, ou a_confirmer (1 seule vidéo)."""
    overlap = True
    if ref_range and base_range:
        overlap = not (ref_range[1] < base_range[0] or base_range[1] < ref_range[0])
    solid = (not overlap) or (n_ref >= 3 and n_base >= 3)
    if unit in ("dB", "LUFS", "LU"):
        delta = round(ref - base, 2)
        size = abs(delta)
        label = "gros_ecart" if size >= 6 and solid else "ecart" if size >= 3 else "proche"
        out = {"ratio": None, "delta": delta, "label": label}
    else:
        if base == 0:
            r = None if ref else 1.0
        else:
            r = ref / base
        if r is None:
            label = "gros_ecart" if solid else "ecart"
        elif (r >= 1.5 or r <= 0.67) and solid:
            label = "gros_ecart"
        elif r >= 1.2 or r <= 0.83:
            label = "ecart"
        else:
            label = "proche"
        out = {"ratio": round(r, 2) if r is not None else None, "label": label}
    if min(n_ref, n_base) == 1:
        out["confirm"] = "à confirmer (1 seule vidéo)"
    return out


def _table(study: Study) -> list[dict]:
    base, own, models = study.base, study.own, study.models
    claude_base = base if study.claude.get(base) else own  # rendus KrokCut pas vus par Claude : vos vidéos
    claude_complete = bool(study.claude.get(claude_base)) and any(study.claude.get(c) for c in models)
    table = []
    for rid, label, unit, group, source, reliability, kind in ROWS:
        claude_row = source != "mesure"
        pool = study.claude if claude_row else study.local
        values = {}
        for cid in study.names:
            if rid == "library_recall" and study.roles.get(cid) != "nous":
                continue
            vals = [v for v in (_metric(d, rid) for d in pool.get(cid, [])) if v is not None]
            if rid == "library_recall":
                vals = [v for d, v in ((d, _metric(d, rid)) for d in pool.get(cid, [])) if v is not None and d.state.metrics.get("library_recall_n")]
            if vals:
                values[cid] = _summary(vals)
        note = ""
        if claude_row and not claude_complete:
            note = INCOMPLETE
        elif group == "Musique" and rid != "music_montage_pct":
            note = MUSIC_NOTE
        ecart = {}
        row_base = base if base in values else own if own in values else ""
        if kind != "info" and note != INCOMPLETE and row_base:
            b = values[row_base]
            for cid in models:
                if cid in values:
                    v = values[cid]
                    ecart[cid] = ecart_label(
                        v["median"], b["median"], v["n"], b["n"], unit, ref_range=(v["min"], v["max"]), base_range=(b["min"], b["max"])
                    )
        table.append(
            {
                "id": rid,
                "label": label,
                "unit": unit,
                "group": group,
                "source": source,
                "reliability": reliability,
                "values": values,
                "ecart": ecart,
                "base": row_base,
                "note": note,
            }
        )
    return table


def metrics_table(store: BenchmarkStore, cfg: AppConfig, settings: BenchSettings | None = None) -> list[dict]:
    """Les chiffres côte à côte (§6.2) : médiane des vidéos comptées de chaque chaîne, sans Claude."""
    return _table(Study(store, cfg, settings))


# ------------------------------------------------------------------ réglages proposés
def _round(value: float, kind: str) -> float:
    if kind == "density":
        return _rate(value)
    step = STEP[kind]
    return round(round(value / step) * step, 2)


def _too_close(current: float, proposed: float, kind: str) -> bool:
    delta = abs(proposed - current)
    if kind == "density":
        return delta < DENSITY_MIN_REL * abs(current) and delta < DENSITY_MIN_ABS
    return delta < STEP[kind] - 1e-9


def _intensity_word(alpha: float) -> str:
    return INTENSITY_WORDS[min(INTENSITY_WORDS, key=lambda a: abs(a - alpha))]


def _fmt_value(x, unit: str) -> str:
    if isinstance(x, bool):
        return "oui" if x else "non"
    if isinstance(x, str):
        return x
    nd = 2 if unit in ("s", "×") else 1
    return fr(x, nd) + UNIT_WORDS.get(unit, (" " + unit) if unit else "")


def parse_time(text: str) -> float | None:
    """« 3:14 », « 3:14.5 » ou « 1:02:03 » → secondes."""
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d{1,3}):(\d{1,2}(?:[.,]\d+)?)\s*", text or "")
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + float(s.replace(",", "."))


def vote_data(study: Study) -> dict[str, list[dict]]:
    """Par chaîne, ce que les profils Claude disent de chaque vidéo : teaser, mise en page, whooshs."""
    out: dict[str, list[dict]] = {}
    for cid, docs in study.claude.items():
        rows = []
        for doc in docs:
            profile = study.profile(doc)
            starts = sorted(t for t in (parse_time(p.get("debut", "")) for p in profile.get("structure") or []) if t)
            whooshes = [
                float(e["t"])
                for e in (doc.read_json("son_evenements.json") or {}).get("events") or []
                if e.get("cat") == "whoosh"
            ]
            with_whoosh = sum(any(abs(w - t) <= WHOOSH_WINDOW_S for w in whooshes) for t in starts)
            rows.append(
                {
                    "video": doc.id,
                    "teaser": ((profile.get("accroche") or {}).get("teaser")) or "inconnu",
                    "layout": doc.state.metrics.get("layout", "inconnue"),
                    "part_changes": len(starts),
                    "part_changes_whoosh": with_whoosh,
                }
            )
        out[cid] = rows
    return out


def propose_settings(
    table: list[dict],
    style: StyleProfile,
    alpha: float,
    base_cid: str,
    target_cids: list[str],
    profiles: dict[str, list[dict]] | None = None,
    names: dict[str, str] | None = None,
    own_cid: str | None = None,
) -> list[dict]:
    """Réglages proposés (§6.4), ancrés sur la base : S·(R/X)^α pour les densités, S + α·(R − X) sinon.

    Claude n'intervient jamais dans ces valeurs : il cite seulement leur id (p_<champ>). La base est
    base_cid (« Montages KrokCut » s'il y en a), ou own_cid (« nous ») quand la base n'a pas cette mesure.
    """
    rows = {r["id"]: r for r in table}
    names = names or {}
    profiles = profiles or {}
    out: list[dict] = []
    word = _intensity_word(alpha)

    def side(rid: str) -> tuple[dict | None, dict[str, dict]]:
        row = rows.get(rid)
        if not row or row.get("note") == INCOMPLETE:
            return None, {}
        vals = row["values"]
        base = vals.get(base_cid) or (vals.get(own_cid) if own_cid else None)
        return base, {c: vals[c] for c in target_cids if c in vals}

    def base_of(rid: str) -> str:
        vals = (rows.get(rid) or {}).get("values") or {}
        return base_cid if base_cid in vals or not own_cid else own_cid

    for field, metrics, rule, (lo, hi), kind, label in FIELDS:
        chosen = None
        for rid in metrics:
            base, refs = side(rid)
            if base is not None and refs:
                chosen = (rid, base, refs)
                break
        if not chosen:
            continue
        rid, base, refs = chosen
        if field == "music_volume_db":
            pct_base, pct_refs = side("music_pct")
            if not pct_base or pct_base["median"] < MUSIC_LEVEL_PCT or not all(
                pct_refs.get(c, {}).get("median", 0) >= MUSIC_LEVEL_PCT for c in refs
            ):
                continue
        unit = rows[rid]["unit"]
        R = statistics.mean(v["median"] for v in refs.values())
        X = base["median"]
        S = float(getattr(style, field))
        if rule == "ratio" and X >= RATIO_MIN_BASE:
            raw = S * (R / X) ** alpha
            used = "ratio"
        else:
            raw = S + alpha * (R - X)
            used = "delta" if rule == "delta" else "ratio_additif"
        proposed = min(hi, max(lo, _round(raw, kind)))
        close = _too_close(S, proposed, kind)
        checked = False
        if not close:
            if field == "zooms_per_minute":
                checked = rid == "zooms_total_per_min" and base["n"] >= 2 and all(v["n"] >= 2 for v in refs.values())
            elif field == "punch_scale":
                _, counts = side("punch_ins")
                base_count = rows.get("punch_ins", {}).get("values", {}).get(base_cid, {}).get("sum", 0)
                checked = base_count >= 10 and all(counts.get(c, {}).get("sum", 0) >= 10 for c in refs)
            elif field == "max_silence":
                checked = base["n"] >= 2 and all(v["n"] >= 2 for v in refs.values()) and abs(R - X) >= 0.1
        per_channel = {c: v["median"] for c, v in refs.items()}
        why = " · ".join(f"{names.get(c, c)} {_fmt_value(v, unit)}" for c, v in per_channel.items())
        why += f" · vous {_fmt_value(X, unit)} · réglage actuel {_fmt_value(S, '')} → {word} : {_fmt_value(proposed, '')}"
        if close:
            why += " (déjà proche)"
        out.append(
            {
                "id": f"p_{field}",
                "field": field,
                "label": label,
                "current": S,
                "proposed": proposed,
                "ref": round(R, 3),
                "base": X,
                "base_channel": base_of(rid),
                "per_channel": per_channel,
                "rule": used,
                "source": SOURCE_LABELS.get(rid, "mesuré"),
                "metric": rid,
                "checked": checked,
                "close": close,
                "why": why,
            }
        )

    # Votes : musique, whoosh de transition, teaser, mise en page (jamais cochés)
    def vote(field: str, proposed, why: str, source: str) -> None:
        current = getattr(style, field)
        out.append(
            {
                "id": f"p_{field}",
                "field": field,
                "label": VOTE_FIELDS[field],
                "current": current,
                "proposed": proposed,
                "ref": None,
                "base": None,
                "base_channel": base_cid,
                "per_channel": {},
                "rule": "vote",
                "source": source,
                "metric": "",
                "checked": False,
                "close": proposed == current,
                "why": why + (" (déjà le cas)" if proposed == current else ""),
            }
        )

    m_base, m_refs = side("music_pct")
    if m_base and m_refs:
        R = statistics.mean(v["median"] for v in m_refs.values())
        mont_base, mont_refs = side("music_montage_pct")
        montage_ok = not mont_refs or statistics.mean(v["median"] for v in mont_refs.values()) >= MUSIC_MONTAGE_PCT
        if R >= MUSIC_REF_PCT and m_base["median"] < MUSIC_BASE_PCT and montage_ok:
            vote("music", True, f"musique {fr(R, 0)} % du temps chez eux, {fr(m_base['median'], 0)} % chez vous", "mesuré")

    def share(cid: str) -> float | None:
        rows_ = profiles.get(cid) or []
        total = sum(r["part_changes"] for r in rows_)
        return sum(r["part_changes_whoosh"] for r in rows_) / total if total else None

    ref_shares = [s for s in (share(c) for c in target_cids) if s is not None]
    base_share = share(base_cid)
    if base_share is None and own_cid:
        base_share = share(own_cid)
    if ref_shares and base_share is not None:
        R = statistics.mean(ref_shares)
        if R >= WHOOSH_REF_SHARE and base_share < WHOOSH_BASE_SHARE:
            vote(
                "transition_sfx",
                True,
                f"whoosh sur {round(100 * R)} % des changements de partie chez eux, {round(100 * base_share)} % chez vous",
                "mesuré + structure vue par Claude",
            )

    teasers = Counter(r["teaser"] for c in target_cids for r in profiles.get(c) or [])
    if teasers["oui"] != teasers["non"] and (teasers["oui"] or teasers["non"]):
        yes = teasers["oui"] > teasers["non"]
        vote("cold_open", yes, f"teaser dans {teasers['oui']} de leurs vidéos, pas de teaser dans {teasers['non']}", "vu par Claude")

    layouts = Counter(r["layout"] for c in target_cids for r in profiles.get(c) or [] if r["layout"] not in ("", "inconnue"))
    if layouts:
        top, n = layouts.most_common(1)[0]
        if top in LAYOUT_MAP and list(layouts.values()).count(n) == 1:
            vote("layout", LAYOUT_MAP[top], f"mise en page la plus fréquente chez eux : {top.replace('_', ' ')}", "vu par Claude")
    return out


# ------------------------------------------------------------------ techniques et faisabilité
def _verdicts(doc: BenchDoc) -> dict[str, str]:
    return (doc.read_json("observations/agregats.json") or {}).get("verdicts") or {}


def _local_events(doc: BenchDoc, source: str, data: VideoData, claude: bool) -> list[dict] | None:
    """Événements mesurés qui comptent pour une technique (rate_source autre que « claude »)."""
    kind, _, sub = source.partition(":")
    verdicts = _verdicts(doc) if claude else {}

    def kept(e: dict) -> bool:  # avec l'avis de Claude, seulement ce qu'il juge ajouté au montage
        return not claude or verdicts.get(e["id"]) == "montage"

    if kind == "Z":
        return [e for e in data.image_events if e.get("type") == "zoom" and e.get("dir", "avant") == "avant" and kept(e)]
    if kind in ("F", "N", "B", "G"):
        return [e for e in data.image_events if e.get("type") == sub]
    if kind == "P":
        return [{"id": "", "t": c["t"], "description": "jump cut probable"} for c in data.cuts if c.get("kind") == sub]
    if kind == "S":
        events = [e for e in data.sound_events if e.get("cat") != "autre"]
        if sub != "montage":
            events = [e for e in events if e.get("cat") == sub]
        return [e for e in events if kept(e)]
    if kind == "M":
        if sub == "coupure_nette":
            return [m | {"t": m["end"]} for m in data.music if m.get("end_kind") == "coupure_nette" and kept(m)]
        if sub == "changes":
            return [{"id": m["id"], **ch} for m in data.music for ch in m.get("changes") or []]
        return [m | {"t": m["start"]} for m in data.music if kept(m)]
    if kind == "C":
        return [c for c in data.silences if c.get(sub)]
    return None


def _example(doc: BenchDoc, data: VideoData, e: dict) -> dict:
    t = float(e.get("t", 0.0))
    times = [x["t"] for x in data.tiles]
    tile = nearest_tile(data.tiles, times, t + 0.1) or {}
    desc = e.get("description") or e.get("label") or e.get("type") or e.get("cat") or ""
    return {
        "video_id": doc.id,
        "video": doc.state.name,
        "t": t,
        "tile": tile.get("id", ""),
        "sheet": tile.get("sheet"),
        "cell": tile.get("cell"),
        "description": desc,
    }


def technique_rates(store: BenchmarkStore, cfg: AppConfig | None = None, study: Study | None = None) -> dict:
    """Fréquence de chaque technique par chaîne (médiane par vidéo), avec des exemples à regarder."""
    study = study or Study(store, cfg or AppConfig.load())
    out: dict = {
        "channels": dict(study.roles),
        "names": dict(study.names),
        "base": study.base,
        "own": study.own,
        "targets": list(study.targets),
        "techniques": {},
        "sound_cats": {},
        "music_pct": {},
    }
    per_video: dict[str, dict[str, dict[str, tuple[float, int, list[dict]]]]] = defaultdict(lambda: defaultdict(dict))
    for cid in study.names:
        claude_ids = {d.id for d in study.claude.get(cid, [])}
        cats: dict[str, list[float]] = defaultdict(list)
        music: list[float] = []
        for doc in study.local.get(cid, []):
            data = VideoData(doc)
            minutes = max((doc.state.metrics.get("duration_s") or data.duration) / 60, 0.01)
            has_claude = doc.id in claude_ids
            agg = doc.read_json("observations/agregats.json") or {} if has_claude else {}
            claude_minutes = max((agg.get("analysed_s") or 0) / 60, 0.01)
            for t in techniques.TECHNIQUES:
                if t.rate_source == "claude":
                    if not has_claude:
                        continue
                    info = (agg.get("techniques") or {}).get(t.id) or {}
                    n = int(info.get("n") or 0)
                    examples = [
                        {"video_id": doc.id, "video": doc.state.name, **{k: x.get(k) for k in ("t", "tile", "sheet", "cell")}, "description": x.get("description") or x.get("texte", "")}
                        for x in info.get("examples") or []
                    ]
                    per_video[t.id][cid][doc.id] = (round(n / claude_minutes, 2), n, examples)
                elif t.rate_source in ("", "profil"):
                    continue
                else:
                    events = _local_events(doc, t.rate_source, data, has_claude)
                    if events is None:
                        continue
                    by_verdict = has_claude and bool(agg) and t.rate_source[0] in "SMZ" and t.rate_source != "M:changes"
                    span = claude_minutes if by_verdict else minutes
                    per_video[t.id][cid][doc.id] = (
                        round(len(events) / span, 2),
                        len(events),
                        [_example(doc, data, e) for e in events[:MAX_ROADMAP_EXAMPLES]],
                    )
            by_cat = doc.state.metrics.get("sfx_montage_by_cat") if has_claude else None
            if by_cat is None:
                by_cat = doc.state.metrics.get("sound_by_cat") or {}
            for c in SOUND_CATS:
                cats[c].append(float(by_cat.get(c, 0.0)))
            pct = doc.state.metrics.get("music_montage_pct") if has_claude else None
            pct = doc.state.metrics.get("music_pct") if pct is None else pct
            if pct is not None:
                music.append(float(pct))
        if cats:
            out["sound_cats"][cid] = {c: round(statistics.median(v), 2) for c, v in cats.items()}
        if music:
            out["music_pct"][cid] = round(statistics.median(music), 1)
    for tid, by_channel in per_video.items():
        info = {"rates": {}, "occurrences": {}, "videos_with": {}, "examples": {}}
        for cid, vids in by_channel.items():
            if not vids:
                continue
            info["rates"][cid] = round(statistics.median(r for r, _, _ in vids.values()), 2)
            info["occurrences"][cid] = sum(n for _, n, _ in vids.values())
            info["videos_with"][cid] = sum(1 for _, n, _ in vids.values() if n)
            info["examples"][cid] = [x for _, _, ex in vids.values() for x in ex]
        out["techniques"][tid] = info
    return out


def feasibility(rates: dict, profiles: dict, base_cid: str) -> list[dict]:
    """Feuille de route « Pas encore faisable dans KrokCut » (§6.5)."""
    models = [c for c, role in rates.get("channels", {}).items() if role == "modele"]
    constants = {
        c.get("technique")
        for p in (profiles or {}).values()
        if isinstance(p, dict)
        for c in p.get("constantes") or []
    }
    rows = []
    for tid, info in rates.get("techniques", {}).items():
        t = techniques.BY_ID.get(tid)
        if t is None or t.support == "oui":
            continue
        model_rates = {c: info["rates"][c] for c in models if c in info["rates"]}
        if not model_rates:
            continue
        top = max(model_rates.values())
        occurrences = sum(info["occurrences"].get(c, 0) for c in models)
        videos = sum(info["videos_with"].get(c, 0) for c in models)
        if not (top >= ROADMAP_MIN_RATE or (occurrences >= ROADMAP_MIN_OCCURRENCES and videos >= ROADMAP_MIN_VIDEOS)):
            continue
        base_rate = info["rates"].get(base_cid, info["rates"].get(rates.get("own", ""), 0.0))
        if base_rate > 0 and top < ROADMAP_RATIO * base_rate:
            continue
        examples = sorted(
            (x for c in models for x in info["examples"].get(c, [])), key=lambda x: (x.get("video_id", ""), x.get("t") or 0)
        )
        rows.append(
            {
                "technique": tid,
                "label": t.label,
                "support": t.support,
                "effort": t.effort,
                "rates": dict(info["rates"]),
                "base_rate": base_rate,
                "examples": examples[:MAX_ROADMAP_EXAMPLES],
                "todo": t.todo,
                "workaround": t.workaround,
                "constant": tid in constants,
                "score": round(top * (CONSTANT_BOOST if tid in constants else 1.0), 3),
            }
        )
    rows.sort(key=lambda r: (-r["score"], EFFORT_ORDER.get(r["effort"], 3), r["technique"]))
    return rows


GAP_WORDS = {
    "boum": ("boum", "boom", "impact", "bass", "basse"),
    "whoosh": ("whoosh", "swoosh", "woosh", "transition", "swish"),
    "tonal": ("ding", "cloche", "bell", "jingle", "notification"),
    "bip": ("bip", "beep", "bleep", "censure"),
    "glissando": ("boing", "cartoon", "slide"),
}
GAP_PHRASES = {
    "boum": ("des boums", "Ajoute 3 ou 4 boums secs"),
    "whoosh": ("des whooshs", "Ajoute 3 ou 4 whooshs de transition"),
    "tonal": ("des dings et jingles", "Ajoute 3 ou 4 dings ou notifications"),
    "bip": ("des bips de censure", "Ajoute un ou deux bips"),
    "glissando": ("des sons cartoon (boing, glissando)", "Ajoute 3 ou 4 sons cartoon"),
}


def library_gaps(cfg: AppConfig, rates: dict) -> list[dict]:
    """Sons qu'utilisent souvent les chaînes visées et que la bibliothèque n'a pas (« à faire à la main »)."""
    library = Library.load(cfg.library_dir) if cfg.library_dir else Library(Path("."), [])
    targets = rates.get("targets") or []
    names = rates.get("names") or {}
    gaps = []
    for cat, words in GAP_WORDS.items():
        per = {c: rates.get("sound_cats", {}).get(c, {}).get(cat) for c in targets}
        per = {c: v for c, v in per.items() if v is not None}
        if not per:
            continue
        R = statistics.mean(per.values())
        if R < GAP_MIN_RATE or library.find_by_tags(("sfx",), *words):
            continue
        who = max(per, key=per.get)
        what, todo = GAP_PHRASES[cat]
        gaps.append(
            {
                "category": cat,
                "rate": round(R, 2),
                "channel": who,
                "searched": list(words),
                "text": f"{names.get(who, who)} utilise souvent {what} (≈ {fr(per[who])}/min) : votre bibliothèque n'en a "
                f"aucun (cherché : {', '.join(words)}). {todo}, puis « Rescanner ».",
            }
        )
    per = {c: rates.get("music_pct", {}).get(c) for c in targets}
    per = {c: v for c, v in per.items() if v is not None}
    if per and statistics.mean(per.values()) >= GAP_MUSIC_PCT and not library.of_kind("music"):
        who = max(per, key=per.get)
        gaps.append(
            {
                "category": "musique",
                "rate": round(statistics.mean(per.values()), 1),
                "channel": who,
                "searched": ["musique"],
                "text": f"{names.get(who, who)} met de la musique de fond ≈ {fr(per[who], 0)} % du temps : votre "
                "bibliothèque n'a aucune musique. Ajoute quelques musiques libres de droits, puis « Rescanner ».",
            }
        )
    return gaps


# ------------------------------------------------------------------ Claude : schémas et normalisation
ALL_TECH = enum(*techniques.ALL_IDS)
CHANNEL_PROFILE_SCHEMA = obj(
    {
        "identite": STR,
        "constantes": arr(
            obj({"technique": ALL_TECH, "comment": STR, "prevalence": enum("toutes_les_videos", "la_plupart", "une_seule")})
        ),
        "recettes": arr(
            obj({"nom": STR, "quand": STR, "etapes": arr(STR), "techniques": arr(ALL_TECH), "exemples": arr(STR)})
        ),
        "humour": STR,
        "image": STR,
        "son": STR,
        "rythme": STR,
        "structure": STR,
        "differences_entre_videos": STR,
    }
)
AXES = (
    "rythme", "accroche_structure", "humour", "bruitages", "musique",
    "silences_respiration", "textes", "incrustations", "zooms_cadrage", "volume",
)
PRIORITY_ORDER = {"haute": 0, "moyenne": 1, "basse": 2}


def comparison_schema(proposal_ids: list[str]) -> dict:
    """Schéma de la comparaison, construit à la volée : Claude ne peut citer qu'une proposition calculée."""
    return obj(
        {
            "verdict": STR,
            "axes": arr(
                obj(
                    {
                        "axe": enum(*AXES),
                        "references": STR,
                        "vous": STR,
                        "ecart": enum("gros_ecart", "ecart", "proche", "vous_plus"),
                        "preuves": STR,
                    }
                )
            ),
            "recommandations": arr(
                obj(
                    {
                        "titre": STR,
                        "pourquoi": STR,
                        "preuves": STR,
                        "exemple": STR,
                        "priorite": enum("haute", "moyenne", "basse"),
                        "type": enum("reglage", "consigne", "pas_encore_faisable", "a_la_main"),
                        "proposition": enum("", *proposal_ids),
                        "technique": enum("", *techniques.ALL_IDS),
                        "consigne": STR,
                    }
                )
            ),
            "a_garder": arr(STR),
            "resume_equipe": STR,
        }
    )


def normalize_recommendations(recs: list[dict], proposals: list[dict]) -> list[dict]:
    """Remet les recommandations de Claude dans les clous (§6.7), puis les numérote r01, r02…"""
    usable = {p["id"] for p in proposals if not p.get("close")}
    out, seen = [], set()
    for rec in recs or []:
        r = dict(rec)
        kind = r.get("type", "consigne")
        tech = r.get("technique", "") or ""
        prop = r.get("proposition", "") or ""
        consigne = (r.get("consigne") or "").strip()[:CONSIGNE_MAX_CHARS]
        if kind == "reglage" and prop not in usable:
            if not consigne:
                continue
            kind, prop = "consigne", ""
        if kind != "reglage":
            prop = "" if prop not in usable else prop
        if kind == "consigne" and tech and techniques.support(tech) == "non":
            kind = "pas_encore_faisable"
        elif kind == "pas_encore_faisable" and tech and techniques.support(tech) == "oui":
            kind = "consigne"
        if kind == "consigne" and not consigne:
            consigne = (r.get("titre") or "").strip()[:CONSIGNE_MAX_CHARS]
        key = (kind, tech, prop) if (tech or prop) else (kind, norm_text(consigne or r.get("titre", "")))
        if key in seen:
            continue
        seen.add(key)
        r.update(type=kind, technique=tech, proposition=prop, consigne=consigne)
        out.append(r)
    out.sort(key=lambda r: PRIORITY_ORDER.get(r.get("priorite"), 1))
    for i, r in enumerate(out, 1):
        r["id"] = f"r{i:02d}"
    return out


# ------------------------------------------------------------------ textes envoyés à Claude
def _values_text(row: dict, names: dict[str, str]) -> str:
    unit = row["unit"]
    parts = []
    for cid, v in row["values"].items():
        rng = f" ({_fmt_value(v['min'], unit)} – {_fmt_value(v['max'], unit)}, {v['n']} vidéo{'s' if v['n'] > 1 else ''})"
        parts.append(f"{names.get(cid, cid)} {_fmt_value(v['median'], unit)}{rng if v['n'] > 1 else ' (1 vidéo)'}")
    return " · ".join(parts)


def table_text(table: list[dict], names: dict[str, str], channels: list[str] | None = None) -> str:
    lines = []
    for row in table:
        if channels is not None:
            row = {**row, "values": {c: v for c, v in row["values"].items() if c in channels}}
        if not row["values"]:
            continue
        line = f"- {row['label']} [{row['group']}, {row['reliability']}] : {_values_text(row, names)}"
        if row.get("note"):
            line += f" — {row['note']}"
        lines.append(line)
    return "\n".join(lines)


def _channel_content(study: Study, cid: str, table: list[dict]) -> str:
    channel = next(c for c in study.channels if c.id == cid)
    docs = sorted(study.claude.get(cid, []), key=lambda d: d.state.added, reverse=True)[:MAX_PROFILE_VIDEOS]
    blocks = []
    for doc in sorted(docs, key=lambda d: d.state.added):
        profile = {k: v for k, v in study.profile(doc).items() if k not in ("source", "coverage", "failed_chunks", "claude_error")}
        blocks.append(
            f"### {doc.state.blind_id} — {fmt_duration(doc.state.metrics.get('duration_s') or 0)}, couverture "
            f"{round(100 * doc.state.coverage)} %\n" + json.dumps(profile, ensure_ascii=False)
        )
    members = f" (dans les vidéos : {channel.members})" if channel.members else ""
    body = "\n\n".join(blocks) + "\n\nCHIFFRES DE LA CHAÎNE :\n" + table_text(table, study.names, [cid])
    return CHANNEL_INSTRUCTIONS.format(name=channel.name, members=members, count=len(docs), body=body)


def _content_fp(content: str, cfg: AppConfig) -> str:
    return hashlib.sha256(json.dumps([cfg.model, CHANNEL_SYSTEM, content], ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def _cached_profile(store: BenchmarkStore, cid: str, fp: str) -> dict | None:
    try:
        data = json.loads((store.root / "profils" / f"{cid}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("profile") if data.get("fp") == fp else None


def _comparison_content(study: Study, table: list[dict], proposals: list[dict], rates: dict, gaps: list[dict], profiles: dict) -> str:
    names = study.names
    own = names.get(study.own, "Krok et Mil")
    parts = []
    for c in study.channels:
        p = profiles.get(c.id)
        if not p:
            continue
        who = f" — dans les vidéos : {c.members}" if c.members else ""
        parts.append(f"### {c.name} ({ROLE_WORDS.get(c.role, c.role)}{who})\n" + json.dumps(p, ensure_ascii=False))
    base_name = names.get(study.base, own)
    props = [
        f"- {p['id']} ({p['label']}) : {p['why']}" + (" — déjà proche, rien à changer" if p.get("close") else "")
        for p in proposals
    ]
    feas = []
    for tid, info in rates.get("techniques", {}).items():
        if not info["rates"] or max(info["rates"].values()) < FEASIBILITY_MIN_RATE:
            continue
        t = techniques.BY_ID[tid]
        detail = t.how if t.support != "non" else f"manque : {t.todo}"
        rate_txt = " · ".join(f"{names.get(c, c)} {fr(r, 2)}/min" for c, r in info["rates"].items())
        feas.append(f"- {tid} ({t.label}) : support « {t.support} » ({detail}) ; {rate_txt}")
    style = StyleProfile.load()
    bible = channel_bible().strip()[:BIBLE_MAX_CHARS]
    guide = ReferenceStore().prompt_block()[:GUIDE_MAX_CHARS]
    body = "\n\n".join(
        [
            "## Profils des chaînes\n" + ("\n\n".join(parts) or "(aucun)"),
            f"## Les chiffres (médiane par chaîne ; la base de comparaison est « {base_name} »)\n" + table_text(table, names),
            "## Réglages proposés (calculés par le programme ; cite leur id)\n" + ("\n".join(props) or "(aucun)"),
            "## Faisabilité dans KrokCut (techniques vues au moins 0,2 fois par minute quelque part)\n" + ("\n".join(feas) or "(aucune)"),
            "## " + KROKCUT_CAPABILITIES,
            "## Réglages actuels du style de montage\n" + json.dumps(style.model_dump(), ensure_ascii=False),
            "## Bible de la chaîne (écrite par l'équipe)\n" + (bible or "(vide)"),
            "## Extrait du guide tiré de vos vidéos publiées\n" + (guide or "(pas de guide)"),
            "## Manques de la bibliothèque\n" + ("\n".join(f"- {g['text']}" for g in gaps) or "(aucun)"),
        ]
    )
    return COMPARISON_INSTRUCTIONS.format(own=own, body=body)


ROLE_WORDS = {"modele": "chaîne de référence", "nous": "vos vidéos", "krokcut": "montages faits par KrokCut"}


# ------------------------------------------------------------------ rapport
def _live(study: Study, cfg: AppConfig, alpha: float, stored_profiles: dict | None = None) -> dict:
    table = _table(study)
    proposals = propose_settings(
        table, StyleProfile.load(), alpha, study.base, study.targets, vote_data(study), names=study.names, own_cid=study.own
    )
    rates = technique_rates(study.store, cfg, study=study)
    feas = feasibility(rates, stored_profiles or {}, study.base)
    gaps = library_gaps(cfg, rates)
    tech_rows = [
        {
            "id": t.id,
            "label": t.label,
            "support": t.support,
            "rates": (rates["techniques"].get(t.id) or {}).get("rates", {}),
            "base_rate": (lambda r: r.get(study.base, r.get(study.own, 0.0)))((rates["techniques"].get(t.id) or {}).get("rates", {})),
        }
        for t in techniques.TECHNIQUES
        if (rates["techniques"].get(t.id) or {}).get("rates")
    ]
    return {"table": table, "proposals": proposals, "rates": rates, "feasibility": feas, "library_gaps": gaps, "techniques": tech_rows}


def _channels_out(study: Study) -> list[dict]:
    return [
        {
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "videos": [d.id for d in study.local.get(c.id, [])],
            "claude_videos": [d.id for d in study.claude.get(c.id, [])],
            "excluded": study.excluded.get(c.id, []),
            "claude_excluded": study.claude_excluded.get(c.id, []),
        }
        for c in study.channels
    ]


def _guarantee(study: Study) -> str:
    n = sum(len(v) for v in study.local.values())
    if not n:
        return ""
    quality = QUALITY_LABELS.get(study.settings.quality, study.settings.quality)
    return f"✓ Les {n} vidéo{'s ont' if n > 1 else ' a'} été mesurée{'s' if n > 1 else ''} exactement de la même façon ({quality})"


def build_benchmark_report(
    store: BenchmarkStore,
    cfg: AppConfig,
    cancel_event: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Job « benchmark_report » : profil Claude de chaque chaîne (mis en cache), puis comparaison."""
    (store.root / "rapport_erreur.txt").unlink(missing_ok=True)
    study = Study(store, cfg)
    ok, why = study.can_run()
    if not ok:
        raise ValueError(why)
    alpha = ALPHA[study.settings.intensity]
    live = _live(study, cfg, alpha)
    profiles: dict[str, dict | None] = {c.id: None for c in study.channels}
    comparison, claude_error, usd, calls = None, "", 0.0, 0

    def check_cancel() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise Cancelled()

    if claude_available(cfg):
        llm = LLM(cfg, cache_dir=store.root / "claude_cache", log=log)
        try:
            (store.root / "profils").mkdir(exist_ok=True)
            for c in study.channels:
                if not study.claude.get(c.id):
                    continue
                check_cancel()
                content = _channel_content(study, c.id, live["table"])
                fp = _content_fp(content, cfg)
                profile = _cached_profile(store, c.id, fp)
                if profile is None:
                    profile = llm.ask_json(
                        system=CHANNEL_SYSTEM,
                        content=content,
                        schema=CHANNEL_PROFILE_SCHEMA,
                        effort="high",
                        max_tokens=CHANNEL_MAX_TOKENS,
                        label=f"chaine_{c.id}",
                    )
                    atomic_write(
                        store.root / "profils" / f"{c.id}.json",
                        json.dumps({"fp": fp, "updated": _now(), "profile": profile}, ensure_ascii=False, indent=1),
                    )
                profiles[c.id] = profile
            check_cancel()
            live["feasibility"] = feasibility(live["rates"], profiles, study.base)
            content = _comparison_content(study, live["table"], live["proposals"], live["rates"], live["library_gaps"], profiles)
            ids = [p["id"] for p in live["proposals"] if not p.get("close")]
            comparison = llm.ask_json(
                system=CHANNEL_SYSTEM,
                content=content,
                schema=comparison_schema(ids),
                effort="high",
                max_tokens=COMPARISON_MAX_TOKENS,
                label="comparaison",
            )
        except LLMError as exc:  # le rapport garde les chiffres ; Claude sera relancé plus tard
            claude_error = str(exc)
            if log:
                log(f"Claude indisponible pour le rapport : {exc}")
        finally:
            usd, calls = llm.cost(), llm.usage["calls"]
    else:
        claude_error = "Pas de clé Claude : seuls les chiffres sont comparés."
    recommendations = normalize_recommendations((comparison or {}).get("recommandations") or [], live["proposals"])
    report = {
        "updated": _now(),
        "instrument": {"local": list(current_local_fp(cfg)), "claude": list(current_claude_fp(cfg, study.settings))},
        "quality": study.settings.quality,
        "channels": _channels_out(study),
        "base_channel": study.base,
        "sources": study.sources(),
        "table": live["table"],
        "techniques": live["techniques"],
        "feasibility": live["feasibility"],
        "library_gaps": live["library_gaps"],
        "profiles": profiles,
        "claude": comparison,
        "recommendations": recommendations,
        "claude_error": claude_error,
        "cost": {"usd": round(usd, 4), "calls": calls},
        "warnings": [],
    }
    with _REPORT_LOCK:
        atomic_write(store.root / "rapport.json", json.dumps(report, ensure_ascii=False, indent=1))
        atomic_write(store.root / "rapport.md", report_markdown({**report, "proposals": live["proposals"]}, study.names))
        if calls:
            s = store.settings()
            s.report_cost = {
                "usd": round(float(s.report_cost.get("usd", 0.0)) + usd, 4),
                "calls": int(s.report_cost.get("calls", 0)) + calls,
            }
            store.save_settings(s)
    return report


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stored_report(store: BenchmarkStore) -> dict:
    try:
        data = json.loads((store.root / "rapport.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def report_estimate_usd(study: Study) -> float:
    """≈ 1,10 $ pour 3 chaînes : profils (sauf ceux déjà à jour) + comparaison."""
    table = _table(study)
    per_channel = (CHANNEL_TOKENS[0] * PRICE_IN + CHANNEL_TOKENS[1] * PRICE_OUT) / 1e6
    usd = (COMPARISON_TOKENS[0] * PRICE_IN + COMPARISON_TOKENS[1] * PRICE_OUT) / 1e6
    for c in study.channels:
        if study.claude.get(c.id):
            fp = _content_fp(_channel_content(study, c.id, table), study.cfg)
            if _cached_profile(study.store, c.id, fp) is None:
                usd += per_channel
    return round(usd, 2)


def report_status(store: BenchmarkStore, cfg: AppConfig, busy=None) -> dict:
    """Pour l'interface : rapport présent, périmé, en cours, possible (et sinon pourquoi), coût estimé."""
    study = Study(store, cfg)
    stored = stored_report(store)
    ok, why = study.can_run()
    error_file = store.root / "rapport_erreur.txt"
    return {
        "exists": bool(stored),
        "outdated": study.outdated(stored),
        "busy": bool(busy),
        "error": error_file.read_text("utf-8") if error_file.exists() else "",
        "updated": stored.get("updated", ""),
        "estimate_usd": report_estimate_usd(study) if ok else 0.0,
        "can_run": ok,
        "why_not": why,
    }


def _settings_with(store: BenchmarkStore, intensity: str | None, targets: list[str] | None) -> BenchSettings:
    s = store.settings()
    if intensity in ALPHA:
        s.intensity = intensity
    if targets is not None:
        s.targets = [t for t in targets if t]
    return s


def live_report(store: BenchmarkStore, cfg: AppConfig, intensity: str | None = None, targets: list[str] | None = None) -> dict:
    """Rapport stocké + tableau, propositions, faisabilité et manques recalculés en direct. Jamais Claude."""
    settings = _settings_with(store, intensity, targets)
    study = Study(store, cfg, settings)
    stored = stored_report(store)
    live = _live(study, cfg, ALPHA[settings.intensity], stored.get("profiles") or {})
    recall = [d.state.metrics for d in study.local.get(study.own, []) if d.state.metrics.get("library_recall_n")]
    return {
        **stored,
        "table": live["table"],
        "proposals": live["proposals"],
        "feasibility": live["feasibility"],
        "library_gaps": live["library_gaps"],
        "techniques": live["techniques"],
        "channels": _channels_out(study),
        "base_channel": study.base,
        "targets": study.targets,
        "intensity": settings.intensity,
        "guarantee": _guarantee(study),
        "library_recall": {
            "recall": round(statistics.mean(m["library_recall"] for m in recall), 2),
            "n": int(sum(m["library_recall_n"] for m in recall)),
        }
        if recall
        else None,
        "outdated": study.outdated(stored),
    }


def apply_proposals(
    store: BenchmarkStore, cfg: AppConfig, fields: list[str], intensity: str | None = None, targets: list[str] | None = None
) -> tuple[StyleProfile, list[str]]:
    """Fusionne les réglages cochés dans le style par défaut (les épisodes existants gardent le leur)."""
    if not fields:
        raise ValueError("Aucun réglage choisi.")
    settings = _settings_with(store, intensity, targets)
    study = Study(store, cfg, settings)
    style = StyleProfile.load()
    proposals = propose_settings(
        _table(study), style, ALPHA[settings.intensity], study.base, study.targets, vote_data(study), names=study.names,
        own_cid=study.own,
    )
    data = style.model_dump()
    applied = []
    for p in proposals:
        if p["field"] in fields and not p.get("close"):
            data[p["field"]] = p["proposed"]
            applied.append(p["field"])
    new = StyleProfile.model_validate(data)
    new.save(StyleProfile.default_path())
    return new, applied


def save_inspirations(store: BenchmarkStore, enabled: bool, items: list | None = None, text: str | None = None) -> dict:
    """Consignes cochées pour le monteur automatique (inspirations.json et .md)."""
    from .benchmark import INSPIRATION_MAX_CHARS

    path = store.root / "inspirations.json"
    try:
        current = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        current = {"enabled": False, "items": [], "text": ""}
    report = stored_report(store)
    recs = {r["id"]: r for r in report.get("recommendations") or []}
    if items is not None:
        chosen = []
        for item in items:
            if isinstance(item, str):
                rec = recs.get(item)
                if rec is None:
                    raise ValueError(f"Recommandation inconnue : {item}")
                entry = {
                    "id": item,
                    "text": (rec.get("consigne") or rec.get("titre") or "").strip(),
                    "technique": rec.get("technique", ""),
                    "report": report.get("updated", ""),
                }
            else:
                entry = {
                    "id": item.get("id", ""),
                    "text": (item.get("text") or "").strip(),
                    "technique": item.get("technique", ""),
                    "report": item.get("report", report.get("updated", "")),
                }
            if entry["technique"] and techniques.support(entry["technique"]) == "non":
                raise ValueError(
                    f"« {techniques.label(entry['technique'])} » : KrokCut ne sait pas encore le faire, ce ne peut pas "
                    "être une consigne pour le monteur automatique."
                )
            chosen.append(entry)
        current["items"] = chosen
        if text is None:
            text = "\n".join(f"- {e['text']}" for e in chosen if e["text"])
    if text is not None:
        current["text"] = text.strip()[:INSPIRATION_MAX_CHARS]
    current["enabled"] = bool(enabled)
    current["updated"] = _now()
    atomic_write(path, json.dumps(current, ensure_ascii=False, indent=1))
    atomic_write(store.root / "inspirations.md", (current.get("text") or "").strip() + "\n")
    return current


# ------------------------------------------------------------------ Markdown
def report_markdown(report: dict, names: dict[str, str] | None = None) -> str:
    """Le rapport complet en Markdown (« Exporter le rapport »)."""
    names = names or {c["id"]: c["name"] for c in report.get("channels") or []}
    claude = report.get("claude") or {}
    out = [f"# Comparaison du montage — {report.get('updated', '')}", ""]
    if claude.get("verdict"):
        out += ["## En bref", claude["verdict"], ""]
    if claude.get("axes"):
        out.append("## Ce qui vous sépare")
        for a in claude["axes"]:
            out.append(f"- **{a['axe'].replace('_', ' ')}** ({a['ecart'].replace('_', ' ')}) — références : {a['references']} ; vous : {a['vous']}")
        out.append("")
    profiles = report.get("profiles") or {}
    if any(profiles.values()):
        out.append("## Leur recette")
        for cid, p in profiles.items():
            if not p:
                continue
            out += [f"### {names.get(cid, cid)}", p.get("identite", "")]
            for r in p.get("recettes") or []:
                out.append(f"- **{r['nom']}** ({r['quand']}) : " + " → ".join(r.get("etapes") or []))
            out.append("")
    recs = report.get("recommendations") or []
    if recs:
        out.append("## Recommandations")
        for r in recs:
            line = f"- [{r.get('priorite', '')}] **{r.get('titre', '')}** — {r.get('pourquoi', '')}"
            if r.get("consigne"):
                line += f" Consigne : « {r['consigne']} »"
            out.append(line)
        out.append("")
    props = [p for p in report.get("proposals") or [] if not p.get("close")]
    if props:
        out.append("## Réglages suggérés")
        out += [f"- {p['label']} : {_fmt_value(p['current'], '')} → {_fmt_value(p['proposed'], '')} ({p['why']})" for p in props]
        out.append("")
    feas = report.get("feasibility") or []
    if feas:
        out.append("## Pas encore faisable dans KrokCut")
        for f in feas:
            rates = " · ".join(f"{names.get(c, c)} {fr(r, 2)}/min" for c, r in f["rates"].items())
            out.append(f"- **{f['label']}** ({f['effort'] or '?'}) — {rates}. À ajouter : {f['todo']}. En attendant : {f['workaround']}.")
        out.append("")
    manual = [g["text"] for g in report.get("library_gaps") or []] + [
        r.get("consigne") or r.get("titre", "") for r in recs if r.get("type") == "a_la_main"
    ]
    if manual:
        out += ["## À faire à la main", *[f"- {m}" for m in manual], ""]
    if claude.get("a_garder"):
        out += ["## Ce que vous faites déjà bien (à garder)", *[f"- {k}" for k in claude["a_garder"]], ""]
    table = report.get("table") or []
    if table:
        out += ["## Les chiffres", table_text(table, names), ""]
    if report.get("claude_error"):
        out += [f"_Claude : {report['claude_error']}_", ""]
    return "\n".join(out).strip() + "\n"

