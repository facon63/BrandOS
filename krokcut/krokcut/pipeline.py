"""Enchaînement des étapes, avec reprise : une étape terminée n'est pas refaite."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable

from . import audio as audio_mod
from .config import AppConfig, channel_bible, workspace_dir
from .derush import build_story_claude, build_story_heuristic, find_moments_claude, find_moments_heuristic
from .editing import build_plan, edit_heuristic, edit_with_claude
from .export import export_chapters, export_report, export_srt, export_xml
from .ffmpeg_utils import concat_files, extract_pcm, probe
from .library import Library
from .llm import LLM, claude_available
from .project import STEP_IDS, Project
from .prompts import EDIT_SYSTEM_EXTRA, base_system
from .references import ReferenceStore
from .render import render
from .steps import Cancelled, StepRunner
from .timeline import Timeline, build_timeline
from .transcribe import build_lines, transcribe_mix

WordsProvider = Callable[[Path, audio_mod.Levels], list[dict]]


__all__ = ["Cancelled", "Pipeline", "standard_fps"]

STANDARD_FPS = (24000 / 1001, 24.0, 25.0, 30000 / 1001, 30.0, 50.0, 60000 / 1001, 60.0)


def standard_fps(fps: float) -> float:
    """OBS et les téléphones donnent parfois 59,87 i/s (fréquence variable) : on se cale sur la norme."""
    best = min(STANDARD_FPS, key=lambda f: abs(f - fps))
    return best if abs(best - fps) / best < 0.02 else round(fps, 3)


class Pipeline(StepRunner):
    step_ids = STEP_IDS

    def __init__(
        self,
        project: Project,
        cfg: AppConfig,
        *,
        words_provider: WordsProvider | None = None,
        cancel_event: threading.Event | None = None,
    ):
        super().__init__(project, cancel_event)
        self.p = project
        self.cfg = cfg
        self.words_provider = words_provider
        self._llm: LLM | None = None

    # ------------------------------------------------------------ outils
    @property
    def names(self) -> dict[str, str]:
        return {k: s.name for k, s in self.p.state.sources.items()}

    def use_claude(self) -> bool:
        return self.p.state.use_claude and claude_available(self.cfg)

    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = LLM(self.cfg, cache_dir=self.p.work / "claude_cache", log=self.p.log)
        return self._llm

    def levels(self) -> audio_mod.Levels:
        return audio_mod.Levels.load(self.p.work / "niveaux.npz")

    def lines(self) -> list[dict]:
        return self.p.read_json("transcription.json", {"lines": []})["lines"]

    def library(self) -> Library:
        return Library.load(self.cfg.library_dir) if self.cfg.library_dir else Library(Path("."), [])

    def reference_notes(self) -> str:
        """Ce que l'équipe attend, appris des vidéos déjà montées (onglet « Mes vidéos »)."""
        notes = ReferenceStore().prompt_block()
        legacy = workspace_dir() / "references.md"  # ancienne analyse en ligne de commande
        if legacy.exists():
            notes = (notes + "\n\n" + legacy.read_text("utf-8")).strip()
        return notes

    def system_prompt(self) -> str:
        return base_system(channel_bible(), self.p.style(), self.names, self.reference_notes())

    # ------------------------------------------------------------ étapes
    def step_probe(self) -> str:
        for key, src in self.p.state.sources.items():
            files = [Path(f) for f in src.files]
            for f in files:
                if not f.exists():
                    raise FileNotFoundError(f"Fichier introuvable : {f}")
            if len(files) > 1:
                joined = self.p.work / f"pov_{key}{files[0].suffix}"
                if not joined.exists():
                    self.p.log(f"Assemblage des {len(files)} fichiers du POV {key}…")
                    concat_files(files, joined)
                src.path = str(joined)
            else:
                src.path = str(files[0].resolve())
            info = probe(src.path)
            if not info.has_video:
                raise ValueError(f"{src.path} ne contient pas de vidéo.")
            src.info = info.to_dict()
        self.p.save()
        a, b = self.p.source("A"), self.p.source("B")
        return f"A {a.duration / 60:.0f} min, B {b.duration / 60:.0f} min"

    def step_audio(self) -> str:
        total = sum(s.duration for s in self.p.state.sources.values()) or 1
        done = 0.0
        for key, src in self.p.state.sources.items():
            dst = self.p.work / f"audio_{key}.pcm"
            if not dst.exists():
                if not src.info.get("has_audio"):
                    raise ValueError(f"Le POV {key} n'a pas de son : impossible de synchroniser.")
                track = src.audio_track if src.audio_track < src.info.get("audio_streams", 1) else 0
                base = done
                extract_pcm(
                    src.path,
                    dst,
                    audio_track=track,
                    duration=src.duration,
                    on_progress=lambda f, base=base, d=src.duration: self.progress("audio", (base + f * d) / total, f"POV {key}"),
                )
            done += src.duration
        return ""

    def step_sync(self) -> str:
        a, b = self.p.work / "audio_A.pcm", self.p.work / "audio_B.pcm"
        if self.p.state.manual_offset is not None:
            result = audio_mod.SyncResult(lag=float(self.p.state.manual_offset), confidence=99, warning="décalage manuel")
        else:
            self.progress("sync", 0.1, "Recherche du décalage…")
            result = audio_mod.synchronize(a, b)
        offsets = audio_mod.sources_offsets(result.lag, result.drift)
        for key, (offset, rate) in offsets.items():
            self.p.state.sources[key].offset = offset
            self.p.state.sources[key].rate = rate
        self.p.save()
        self.p.write_json("synchro.json", result.__dict__)
        if result.warning:
            self.p.log("⚠ " + result.warning)
        extra = " (écho Discord détecté)" if result.double_peak else ""
        return f"B {'en avance' if result.lag > 0 else 'en retard'} de {abs(result.lag):.2f} s{extra}" + (
            f" — {result.warning}" if result.warning else ""
        )

    def step_features(self) -> str:
        hop = audio_mod.HOP
        frames = int(self.p.master_duration() / hop) + 1
        curves = {}
        for i, key in enumerate(("A", "B")):
            self.progress("features", 0.1 + 0.4 * i, f"Niveaux POV {key}")
            src = self.p.source(key)
            curve = audio_mod.level_curve(self.p.work / f"audio_{key}.pcm", hop)
            curves[key] = audio_mod.to_master_curve(curve, src.offset, src.rate, frames, hop)
        levels = audio_mod.Levels.compute_thresholds(curves["A"], curves["B"], hop)
        levels.save(self.p.work / "niveaux.npz")
        loud = levels.loud_mask().mean() * 100
        return f"{loud:.1f} % du temps avec pics sonores"

    def step_transcribe(self) -> str:
        levels = self.levels()
        mix = self.p.work / "mix.pcm"
        if not mix.exists():
            offsets = {k: (s.offset, s.rate) for k, s in self.p.state.sources.items()}
            audio_mod.write_master_mix(
                self.p.work / "audio_A.pcm",
                self.p.work / "audio_B.pcm",
                offsets,
                self.p.master_duration(),
                mix,
                on_progress=lambda f: self.progress("transcribe", 0.05 * f, "Mixage des deux POV"),
            )
        if self.words_provider:
            words = self.words_provider(mix, levels)
        else:
            words = transcribe_mix(
                mix,
                levels,
                self.cfg.whisper,
                self.p.work / "transcription_morceaux",
                on_progress=lambda f, msg: self.progress("transcribe", 0.05 + 0.95 * f, msg),
                log=self.p.log,
            )
        lines = build_lines(words, levels)
        self.p.write_json("transcription.json", {"language": self.cfg.whisper.language, "lines": lines})
        return f"{len(words)} mots, {len(lines)} répliques"

    def step_derush(self) -> str:
        lines, levels, style = self.lines(), self.levels(), self.p.style()
        if not lines:
            raise ValueError("La transcription est vide : vérifie le son des rush.")
        if self.use_claude():
            moments, summaries = find_moments_claude(
                self.llm(),
                self.system_prompt(),
                lines,
                self.names,
                levels,
                style,
                self.cfg.effort.derush,
                parallel=self.cfg.llm_parallel_requests,
                on_progress=lambda f, msg: self.progress("derush", f, msg),
            )
            source = "claude"
        else:
            self.p.log("Pas de clé API Claude : dérush en mode hors ligne (pics sonores).")
            moments, summaries = find_moments_heuristic(lines, levels, style, self.names)
            source = "heuristic"
        self.p.write_json("moments.json", {"source": source, "moments": moments, "summaries": summaries})
        total = sum(m["est_duration"] for m in moments) / 60
        return f"{len(moments)} moments repérés ({total:.0f} min au total)"

    def step_story(self) -> str:
        data = self.p.read_json("moments.json")
        lines, levels, style = self.lines(), self.levels(), self.p.style()
        if self.use_claude() and data["source"] == "claude":
            story = build_story_claude(
                self.llm(), self.system_prompt(), data["moments"], data["summaries"], lines, levels, style, self.cfg.effort.story
            )
        else:
            story = build_story_heuristic(data["moments"], lines, levels, style)
        self.p.write_json("histoire.json", story)
        return f"{len(story['sequence'])} moments retenus, ≈ {story['total_estimate'] / 60:.1f} min"

    def step_edit(self) -> str:
        story = self.p.read_json("histoire.json")
        lines, levels, style = self.lines(), self.levels(), self.p.style()
        library = self.library()
        previous = self.p.read_json("decisions.json", {"moments": {}, "music": []})
        # On ne redemande à Claude que les moments nouveaux ou recoupés
        reusable = {
            mid: d
            for mid, d in previous.get("moments", {}).items()
            if any(i["moment"] == mid and d.get("_lines") == [i["start_line"], i["end_line"]] for i in story["sequence"])
        }
        todo = [i for i in story["sequence"] if i["moment"] not in reusable]
        if todo and self.use_claude():
            system = self.system_prompt() + "\n\n" + EDIT_SYSTEM_EXTRA.format(
                catalog=library.catalog(), name_a=self.names["A"], name_b=self.names["B"]
            )
            fresh = edit_with_claude(
                self.llm(),
                system,
                {**story, "sequence": todo},
                lines,
                self.names,
                self.p.state.sources,
                self.cfg.effort.edit,
                use_frames=True,
                on_progress=lambda f, msg: self.progress("edit", 0.9 * f, msg),
            )
        elif todo:
            fresh = edit_heuristic({**story, "sequence": todo}, lines, library, style, self.names)
        else:
            fresh = {"moments": {}, "music": []}
        for item in todo:
            if item["moment"] in fresh["moments"]:
                fresh["moments"][item["moment"]]["_lines"] = [item["start_line"], item["end_line"]]
        kept_ids = {i["moment"] for i in story["sequence"]}
        decisions = {
            "moments": {**reusable, **fresh["moments"]},
            "music": [m for m in previous.get("music", []) if m["from_moment"] in kept_ids and m["from_moment"] in reusable]
            + fresh["music"],
        }
        self.p.write_json("decisions.json", decisions)

        plan = build_plan(story, decisions, style)
        self.p.write_json("plan.json", plan)
        fps = standard_fps(self.cfg.render.fps or self.p.source("A").info.get("fps") or 30.0)
        tl = build_timeline(
            plan, lines, levels, style, self.p.state.sources, library, fps, self.cfg.render.width, self.cfg.render.height
        )
        self.p.write_json("timeline.json", json.loads(tl.model_dump_json()))
        return (
            f"{tl.duration / 60:.1f} min, {len(tl.clips)} plans, {sum(len(c.zooms) for c in tl.clips)} zooms, "
            f"{len(tl.sfx)} sons, {len(tl.overlays)} persos"
        )

    def timeline(self) -> Timeline:
        return Timeline.model_validate(self.p.read_json("timeline.json"))

    def step_render(self) -> str:
        tl = self.timeline()
        style = self.p.style()
        quality = self.p.state.render_quality
        out = self.p.out / f"montage_{quality}.mp4"
        render(
            tl,
            self.p.work,
            out,
            self.cfg.render,
            quality,
            on_progress=lambda f, msg: self.progress("render", f, msg),
            sfx_volume_db=style.sfx_volume_db,
            voice_polish=style.voice_polish,
            denoise=style.denoise,
        )
        return out.name

    def step_export(self) -> str:
        tl = self.timeline()
        story = self.p.read_json("histoire.json", {})
        name = self.p.state.name
        export_xml(tl, self.p.out / "timeline_premiere_davinci.xml", name)
        export_srt(tl, self.lines(), self.p.out / "sous_titres.srt")
        export_chapters(tl, self.p.out / "chapitres_youtube.txt")
        cost = self._llm.cost() if self._llm else None
        export_report(tl, story, self.p.out / "recap.md", name, cost)
        return "XML, SRT, chapitres et récap prêts"
