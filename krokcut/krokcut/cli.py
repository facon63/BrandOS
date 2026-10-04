"""Ligne de commande : `python -m krokcut serve` ouvre l'interface web."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from .config import AppConfig
from .pipeline import Pipeline
from .project import STEP_IDS, Project


def cmd_serve(args) -> None:
    import uvicorn

    url = f"http://{args.host}:{args.port}"
    print(f"KrokCut tourne sur {url}  (Ctrl+C pour arrêter)")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("krokcut.server:app", host=args.host, port=args.port, log_level="warning")


def cmd_run(args) -> None:
    project = Project.create(args.name, args.a, args.b, args.name_a, args.name_b)
    print(f"Projet créé : {project.root}")
    _run(project, None, args.until)


def cmd_resume(args) -> None:
    project = Project.open(args.project)
    if args.quality:
        project.state.render_quality = args.quality
        project.save()
    _run(project, args.from_step, args.until)


def _run(project: Project, from_step, until) -> None:

    pipeline = Pipeline(project, AppConfig.load())
    done = threading.Event()
    result = {}

    def work():
        result["ok"] = pipeline.run(from_step, until)
        done.set()

    threading.Thread(target=work, daemon=True).start()
    last = ""
    while not done.wait(1.0):
        project.reload()
        running = [(s, project.state.steps[s]) for s in STEP_IDS if project.state.steps[s].status == "running"]
        if running:
            step, st = running[0]
            line = f"{step:<11} {st.progress * 100:5.1f} %  {st.message}"
            if line != last:
                print("\r" + line[:110].ljust(110), end="", flush=True)
                last = line
    print()
    project.reload()
    for step in STEP_IDS:
        st = project.state.steps[step]
        print(f"  {'✔' if st.status == 'done' else '✖' if st.status == 'error' else '·'} {step:<11} {st.message}")
    if not result.get("ok"):
        print(f"\nErreur : {project.state.last_error}")
        sys.exit(1)
    print(f"\nRésultats dans : {project.out}")


def cmd_library(args) -> None:
    from .library import Library

    cfg = AppConfig.load()
    lib = Library.scan(args.dir, on_progress=lambda f, name: print(f"\r{f * 100:5.1f} % {name[:60]:<60}", end=""))
    print()
    cfg.library_dir = args.dir
    cfg.save()
    print("Bibliothèque :", ", ".join(f"{v} {k}" for k, v in lib.stats().items()))


def cmd_style(args) -> None:
    """Ajoute des vidéos déjà montées, les analyse et met à jour le guide de style."""
    from .llm import claude_available
    from .references import REF_STEP_IDS, ReferenceAnalyzer, ReferenceStore, build_guide, needs_claude, sfx_outdated

    cfg = AppConfig.load()
    store = ReferenceStore()
    for video in args.videos:
        doc = store.add(video)
        print(f"Analyse de {doc.state.name}…")
        if sfx_outdated(doc.state.metrics):  # mesurée par l'ancienne détection des bruitages
            doc.invalidate(["sfx", "analyze"])
        analysis = doc.read_json("analyse.json")
        redo = "analyze" if analysis and claude_available(cfg) and needs_claude(doc, analysis) else None
        ok = ReferenceAnalyzer(doc, cfg, store).run(redo)  # relancer la commande réessaie Claude
        doc.reload()
        for step in REF_STEP_IDS:
            st = doc.state.steps[step]
            print(f"  {'✔' if st.status == 'done' else '✖' if st.status == 'error' else '·'} {step:<11} {st.message}")
        if not ok:
            print(f"  Erreur : {doc.state.last_error}")
    build_guide(store, cfg)
    print("\n" + (store.guide_md.read_text("utf-8") if store.guide_md.exists() else "(pas de guide)"))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="krokcut", description="Dérush et montage automatiques — Krok et Mil")
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="ouvre l'interface web")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    s.set_defaults(func=cmd_serve)

    r = sub.add_parser("run", help="traite un épisode en ligne de commande")
    r.add_argument("--name", required=True)
    r.add_argument("--a", nargs="+", required=True, help="fichier(s) du POV A")
    r.add_argument("--b", nargs="+", required=True, help="fichier(s) du POV B")
    r.add_argument("--name-a", default="Krok")
    r.add_argument("--name-b", default="Mil")
    r.add_argument("--until", choices=STEP_IDS)
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("resume", help="reprend / relance un épisode existant")
    c.add_argument("project", help="identifiant du projet (nom du dossier)")
    c.add_argument("--from-step", choices=STEP_IDS)
    c.add_argument("--until", choices=STEP_IDS)
    c.add_argument("--quality", choices=["preview", "final"])
    c.set_defaults(func=cmd_resume)

    lib = sub.add_parser("library", help="scanne le dossier de sons / persos")
    lib.add_argument("dir")
    lib.set_defaults(func=cmd_library)

    st = sub.add_parser("style", help="apprend le style de vidéos déjà montées (onglet « Mes vidéos »)")
    st.add_argument("videos", nargs="+")
    st.set_defaults(func=cmd_style)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["serve"])
    args.func(args)
