from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_admin_load_swap():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.post("/admin/models/load", json={"model_id": "m2"})
        assert r.status_code == 200
        assert r.json()["id"] == "m2"
        r2 = client.get("/v1/models")
        assert "m2" in [m["id"] for m in r2.json()["data"]]


def test_admin_stats():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.get("/admin/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["current_model"] == "m1"
        assert data["loaded_count"] == 1


def test_admin_unload():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.post("/admin/models/unload", json={"model_id": "m1"})
        assert r.status_code == 200
        assert client.get("/admin/stats").json()["current_model"] is None
