from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_health_endpoint():
    app = create_app(backend=FakeBackend(), default_model="fake-model")
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_default_model_is_loaded_on_startup():
    fb = FakeBackend()
    app = create_app(backend=fb, default_model="m1")
    with TestClient(app):  # triggers lifespan
        assert "m1" in {info.id for info in fb.loaded_models()}
