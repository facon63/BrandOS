"""ffmpeg introuvable : recherche robuste, message clair, réparation depuis l'interface."""

from __future__ import annotations

import os
import shutil
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from krokcut import ffmpeg_install, ffmpeg_utils
from krokcut.ffmpeg_utils import (
    FFmpegError,
    FFmpegUnavailable,
    binary,
    ffmpeg_status,
    is_missing_error,
    probe,
    run_ffmpeg,
)

REAL = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}


def fake_tool(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Aucun ffmpeg visible : ni variable, ni ~/KrokCut/bin, ni PATH, ni Homebrew."""
    app_dir = tmp_path / "KrokCut"
    (app_dir / "bin").mkdir(parents=True)
    monkeypatch.setattr(ffmpeg_utils, "APP_DIR", app_dir)
    monkeypatch.setattr(ffmpeg_utils, "EXTRA_DIRS", [str(tmp_path / "homebrew")])
    monkeypatch.delenv("KROKCUT_FFMPEG_DIR", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "vide"))
    return app_dir


def test_ffprobe_seul_dans_le_dossier_indique(isolated, tmp_path, monkeypatch):
    """Le cas de l'utilisateur : ffprobe trouvé (la lecture du fichier passe) mais pas ffmpeg."""
    only_probe = tmp_path / "seulement-ffprobe"
    (only_probe).mkdir()
    os.symlink(REAL["ffprobe"], only_probe / "ffprobe")
    monkeypatch.setenv("KROKCUT_FFMPEG_DIR", str(only_probe))
    assert binary("ffprobe") == str(only_probe / "ffprobe")
    with pytest.raises(FFmpegError) as err:
        binary("ffmpeg")
    assert is_missing_error(str(err.value)) and "ffmpeg" in str(err.value)
    status = ffmpeg_status()
    assert status["ok"] is False and status["ffprobe"] and not status["ffmpeg"] and status["error"]

    # ffmpeg présent dans ~/KrokCut/bin : trouvé même si la variable pointe ailleurs
    os.symlink(REAL["ffmpeg"], isolated / "bin" / "ffmpeg")
    assert binary("ffmpeg") == str(isolated / "bin" / "ffmpeg")
    assert ffmpeg_status()["ok"] is True


def test_app_lancee_sans_path_trouve_bin_et_homebrew(isolated, tmp_path, monkeypatch):
    # PATH minimal du Finder, pas de variable : ~/KrokCut/bin d'abord
    for name in ("ffmpeg", "ffprobe"):
        os.symlink(REAL[name], isolated / "bin" / name)
    assert binary("ffmpeg") == str(isolated / "bin" / "ffmpeg")
    # Rien dans bin : Homebrew (absent du PATH des apps lancées depuis le Finder)
    for name in ("ffmpeg", "ffprobe"):
        (isolated / "bin" / name).unlink()
        os.symlink(REAL[name], fake_tool(tmp_path / "homebrew" / "x").parent / name)
    assert binary("ffprobe") == str(tmp_path / "homebrew" / "ffprobe")


def test_liens_casses_et_fichiers_non_executables_ignores(isolated, tmp_path):
    os.symlink(tmp_path / "desinstalle" / "ffmpeg", isolated / "bin" / "ffmpeg")  # ffmpeg de Homebrew supprimé
    (tmp_path / "homebrew").mkdir()
    (tmp_path / "homebrew" / "ffmpeg").write_text("pas un programme")  # pas exécutable
    assert ffmpeg_utils.find_binary("ffmpeg") is None
    fake_tool(tmp_path / "homebrew" / "ffmpeg")
    assert binary("ffmpeg") == str(tmp_path / "homebrew" / "ffmpeg")


def test_programme_qui_ne_se_lance_pas(isolated, tmp_path, monkeypatch):
    """Mauvais processeur, fichier abîmé : on le signale (bandeau + Réparer) et on passe au suivant."""
    for name in ("ffmpeg", "ffprobe"):
        bad = isolated / "bin" / name
        bad.write_bytes(b"\x00\x01binaire pour un autre processeur")
        bad.chmod(0o755)
    status = ffmpeg_status()
    assert status["ok"] is False and "ne se lance pas" in status["error"] and is_missing_error(status["error"])
    with pytest.raises(FFmpegUnavailable) as err:
        probe(tmp_path / "x.mp4")
    assert "ne se lance pas" in str(err.value) and str(isolated / "bin" / "ffprobe") in str(err.value)
    with pytest.raises(FFmpegUnavailable):
        run_ffmpeg(["-version"])
    # Un ffmpeg qui marche plus loin (Homebrew) est utilisé à la place du binaire cassé
    for name in ("ffmpeg", "ffprobe"):
        os.symlink(REAL[name], fake_tool(tmp_path / "homebrew" / "x").parent / name)
    assert binary("ffmpeg") == str(tmp_path / "homebrew" / "ffmpeg") and ffmpeg_status()["ok"] is True


def test_programme_qui_cesse_de_se_lancer(isolated, monkeypatch):
    """Vérifié au premier appel, abîmé ensuite : erreur claire, reconnue pour la reprise automatique."""
    for name in ("ffmpeg", "ffprobe"):
        (isolated / "bin" / name).write_bytes(b"\x00\x01")
        (isolated / "bin" / name).chmod(0o755)
    monkeypatch.setattr(ffmpeg_utils, "launch_problem", lambda path: "")
    for call in (lambda: run_ffmpeg(["-version"]), lambda: run_ffmpeg(["-version"], duration=1.0, on_progress=lambda f: None)):
        with pytest.raises(FFmpegUnavailable) as err:
            call()
        assert is_missing_error(str(err.value)) and "ne se lance pas" in str(err.value)


def test_dossier_du_path_illisible(isolated, tmp_path, monkeypatch):
    """Un dossier du PATH qu'on n'a pas le droit de lire est sauté (pas de plantage de /api/config)."""
    forbidden = tmp_path / "interdit"
    real_stat = os.stat

    def stat(path, *args, **kwargs):
        if str(path).startswith(str(forbidden)):
            raise PermissionError(13, "Permission denied", str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", stat)
    later = tmp_path / "plus-loin"
    later.mkdir()
    for name in ("ffmpeg", "ffprobe"):
        os.symlink(REAL[name], later / name)
    monkeypatch.setenv("PATH", f"{forbidden}{os.pathsep}{later}")
    assert binary("ffmpeg") == str(later / "ffmpeg") and ffmpeg_status()["ok"] is True


def test_windows_cherche_aussi_le_dossier_de_krokcut(isolated, monkeypatch):
    dirs = ffmpeg_utils.search_dirs(windows=True)
    assert isolated in dirs and Path.cwd() in dirs
    assert dirs.index(isolated / "bin") < dirs.index(isolated)


def test_scan_sans_ffprobe_ne_vide_pas_la_bibliotheque(workspace, library_dir, monkeypatch, tmp_path):
    from krokcut import server
    from krokcut.library import Library

    lib = Library.scan(library_dir)
    asset = lib.assets[0]
    Library.load(library_dir).update(asset["id"], {"tags": ["perso"], "description": "mon boing"})
    monkeypatch.setattr(ffmpeg_utils, "search_dirs", lambda: [tmp_path / "vide"])
    with pytest.raises(FFmpegUnavailable):
        Library.scan(library_dir)
    kept = {a["id"]: a for a in Library.load(library_dir).assets}
    assert len(kept) == len(lib.assets) and kept[asset["id"]]["description"] == "mon boing"
    res = TestClient(server.app).post("/api/library/scan", json={"dir": str(library_dir)})
    assert res.status_code == 503 and is_missing_error(res.json()["detail"])
    assert len(Library.load(library_dir).assets) == len(lib.assets)


def test_anciens_messages_reconnus():
    old = "audio : 'ffmpeg' est introuvable. Installe ffmpeg (https://ffmpeg.org/download.html) et ajoute-le au PATH"
    assert is_missing_error(old)
    assert is_missing_error(ffmpeg_utils.missing_message("ffprobe"))
    assert not is_missing_error("audio : ffmpeg a échoué : Invalid data found")
    assert not is_missing_error("")


# ------------------------------------------------------------------ réparation
def zip_of(tmp_path: Path, prog: str, body: str) -> str:
    src = fake_tool(tmp_path / "src" / prog, body)
    archive = tmp_path / f"{prog}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(src, prog)
        zf.writestr(f"__MACOSX/._{prog}", "métadonnées")
    return archive.as_uri()


GOOD = {
    "ffmpeg": 'case "$*" in *-encoders*) echo " V....D libx264 H.264";; esac',
    "ffprobe": "echo ffprobe version 9",
}


def test_reparation_installe_les_deux_et_remplace_un_lien_casse(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(tmp_path / "parti" / "ffmpeg", bin_dir / "ffmpeg")
    urls = {p: ["file:///introuvable.zip", zip_of(tmp_path, p, GOOD[p])] for p in ffmpeg_install.PROGRAMS}
    seen = []
    ffmpeg_install.install(bin_dir, urls=urls, on_progress=seen.append)
    assert ffmpeg_install.works(bin_dir)
    assert not (bin_dir / "ffmpeg").is_symlink() and os.access(bin_dir / "ffmpeg", os.X_OK)
    assert seen and max(seen) <= 1.0
    assert not [p for p in bin_dir.iterdir() if p.name.startswith(".ffmpeg-")]  # pas de dossier temporaire oublié


def test_reparation_ratee_ne_touche_a_rien(tmp_path):
    bin_dir = tmp_path / "bin"
    keep = fake_tool(bin_dir / "ffprobe", "echo ancien")
    urls = {"ffmpeg": ["file:///introuvable.zip"], "ffprobe": [zip_of(tmp_path, "ffprobe", GOOD["ffprobe"])]}
    with pytest.raises(FFmpegError, match="Téléchargement de ffmpeg impossible"):
        ffmpeg_install.install(bin_dir, urls=urls)
    assert keep.read_text().endswith("echo ancien\n") and not (bin_dir / "ffmpeg").exists()
    # ffmpeg téléchargé mais inutilisable (pas d'encodeur H.264) : rien n'est remplacé non plus
    urls = {p: [zip_of(tmp_path, p, "echo rien")] for p in ffmpeg_install.PROGRAMS}
    with pytest.raises(FFmpegError, match="ne fonctionne pas"):
        ffmpeg_install.install(bin_dir, urls=urls)
    assert keep.read_text().endswith("echo ancien\n") and not (bin_dir / "ffmpeg").exists()


def test_sources_selon_le_processeur():
    arm = ffmpeg_install.sources("ffmpeg", "arm64")
    intel = ffmpeg_install.sources("ffprobe", "x86_64")
    assert arm[0] == "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
    assert "evermeet" in arm[1]  # version Intel en secours (Rosetta), refusée par works() si elle ne tourne pas
    assert intel[0].endswith("/macos/amd64/release/ffprobe.zip") and "evermeet" in intel[1]


def test_reparation_coupee_puis_reprise(tmp_path, monkeypatch):
    """Coupure en plein téléchargement (IncompleteRead) : la source de secours prend le relais ;
    les restes d'une réparation interrompue par « Quitter » sont nettoyés."""
    import http.client

    bin_dir = tmp_path / "bin"
    stale = bin_dir / ".ffmpeg-abc123"
    stale.mkdir(parents=True)
    (stale / "ffmpeg.zip").write_bytes(b"x" * 1000)
    real_download = ffmpeg_install._download

    def flaky(url, dest, on_progress=None):
        if url.startswith("https://exemple.invalid/"):
            raise http.client.IncompleteRead(b"")
        return real_download(url, dest, on_progress)

    monkeypatch.setattr(ffmpeg_install, "_download", flaky)
    urls = {p: ["https://exemple.invalid/coupe.zip", zip_of(tmp_path, p, GOOD[p])] for p in ffmpeg_install.PROGRAMS}
    ffmpeg_install.install(bin_dir, urls=urls)
    assert ffmpeg_install.works(bin_dir)
    assert not list(bin_dir.glob(".ffmpeg-*"))
    (bin_dir / ".ffmpeg-telechargement").mkdir()
    ffmpeg_install.clean_repair_leftovers(bin_dir)
    assert not list(bin_dir.glob(".ffmpeg-*"))


# ------------------------------------------------------------------ serveur
def test_serveur_refuse_les_envois_sans_ffmpeg_puis_reprend(workspace, rushes, monkeypatch, tmp_path):
    from krokcut import server
    from krokcut.references import ReferenceStore

    client = TestClient(server.app)
    assert client.get("/api/config").json()["ffmpeg"]["ok"] is True

    monkeypatch.setattr(ffmpeg_utils, "search_dirs", lambda: [tmp_path / "vide"])
    cfg = client.get("/api/config").json()["ffmpeg"]
    assert cfg["ok"] is False and is_missing_error(cfg["error"]) and "supported" in cfg["repair"]
    up = client.put("/api/upload/wankil.mp4?folder=references", content=b"0" * 1000)
    assert up.status_code == 503 and is_missing_error(up.json()["detail"])
    assert not list(ReferenceStore().files_dir.glob("wankil*"))  # rien copié pour rien
    assert client.post("/api/references", json={"paths": [str(rushes["a"])]}).status_code == 503
    new = {"name": "x", "pov_a": [str(rushes["a"])], "pov_b": [str(rushes["b"])]}
    assert client.post("/api/projects", json=new).status_code == 503
    assert client.post("/api/projects", json={**new, "start": False}).status_code == 200  # créer sans lancer reste possible

    # Une vidéo arrêtée faute de ffmpeg repart toute seule quand il revient
    store = ReferenceStore()
    doc, _ = store.add_or_get(str(rushes["a"]))
    doc.set_step("probe", status="done")
    doc.set_step("audio", status="error", message="'ffmpeg' est introuvable.")
    doc.state.last_error = "audio : 'ffmpeg' est introuvable. Installe ffmpeg"
    doc.save()
    submitted = []
    monkeypatch.setattr(server.jobs, "submit", lambda target, *a, **k: submitted.append((target, k.get("kind"))))
    assert server.resume_missing_ffmpeg() == 0  # toujours absent : on ne relance rien
    monkeypatch.setattr(ffmpeg_utils, "search_dirs", lambda: [Path(REAL["ffmpeg"]).parent])
    assert server.resume_missing_ffmpeg() == 1 and submitted == [(doc.id, "reference")]


def test_bouton_reparer(workspace, monkeypatch):
    from krokcut import server

    client = TestClient(server.app)
    monkeypatch.setattr(server, "repair_supported", lambda: False)
    assert client.post("/api/ffmpeg/repair").status_code == 400
    monkeypatch.setattr(server, "repair_supported", lambda: True)
    started = []
    monkeypatch.setattr(server.ffmpeg_repair, "start", lambda: started.append(1) or True)
    assert client.post("/api/ffmpeg/repair").status_code == 200 and started


def test_reparation_en_arriere_plan_puis_reprise():
    done = []
    repair = ffmpeg_install.Repair(on_done=lambda: done.append(1))

    def ok(on_progress):
        on_progress(0.5)
        return Path(".")

    assert repair.start(ok)
    for _ in range(200):
        if not repair.running:
            break
        time.sleep(0.01)
    assert done == [1] and repair.state()["error"] == ""

    def fails(on_progress):
        raise FFmpegError("Téléchargement de ffmpeg impossible (connexion internet ?).")

    assert repair.start(fails)
    for _ in range(200):
        if not repair.running:
            break
        time.sleep(0.01)
    assert "connexion" in repair.state()["error"] and done == [1]
