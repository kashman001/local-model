from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_list_models_includes_loaded():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.get("/v1/models")
        assert r.status_code == 200
        data = r.json()
        ids = [m["id"] for m in data["data"]]
        assert "m1" in ids
        assert data["object"] == "list"
