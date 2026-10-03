from fastapi.testclient import TestClient

from krokcut.server import app


def test_api_smoke(workspace, rushes, library_dir):
    client = TestClient(app)
    assert "KrokCut" in client.get("/").text
    cfg = client.get("/api/config").json()
    assert cfg["claude"] is False and cfg["model"] == "claude-opus-5-5"

    # Enregistrement d'une clé : seule une version masquée est renvoyée
    cfg = client.post("/api/config", json={"anthropic_api_key": "sk-ant-api03-abcdefghijklmnop"}).json()
    assert cfg["claude"] is True and "abcdefghijk" not in cfg["api_key_hint"]

    # Bibliothèque
    lib = client.post("/api/library/scan", json={"dir": str(library_dir)}).json()
    assert lib["stats"]["sfx"] == 3
    upd = client.post("/api/library/update", json={"id": "sfx/boing_cartoon", "changes": {"tags": ["fail"]}}).json()
    assert upd["tags"] == ["fail"]
    assert client.get("/api/library/file", params={"id": "sfx/boing_cartoon"}).status_code == 200

    # Envoi d'un fichier en flux
    up = client.put("/api/upload/essai.mp4", content=rushes["a"].read_bytes()).json()
    assert up["path"].endswith("essai.mp4")

    # Explorateur
    listing = client.get("/api/browse", params={"path": str(rushes["root"])}).json()
    assert {f["name"] for f in listing["files"]} >= {"pov_A.mp4", "pov_B.mp4"}

    # Projet
    bad = client.post("/api/projects", json={"name": "x", "pov_a": ["/nope.mp4"], "pov_b": ["/nope2.mp4"], "start": False})
    assert bad.status_code == 400
    p = client.post(
        "/api/projects",
        json={"name": "Épisode 12", "pov_a": [up["path"]], "pov_b": [str(rushes["b"])], "target_min": 8, "target_max": 12, "start": False},
    ).json()
    assert p["id"] == "episode-12" and len(p["steps"]) == 10
    assert client.get(f"/api/projects/{p['id']}/style").json()["target_max_minutes"] == 12
    assert client.get("/api/projects").json()[0]["id"] == "episode-12"
    detail = client.get(f"/api/projects/{p['id']}").json()
    assert detail["busy"] is None and detail["outputs"] == []
    assert client.get("/api/projects/inconnu").status_code == 404
    assert client.get("/api/chaine").json()["text"].startswith("# Krok et Mil")
