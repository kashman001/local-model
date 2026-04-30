from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_create_list_delete_preset():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.post(
            "/presets",
            json={
                "name": "coder",
                "system_prompt": "You are a coding assistant.",
                "default_params": {"temperature": 0.2},
            },
        )
        assert r.status_code == 200
        pid = r.json()["id"]
        r2 = client.get("/presets")
        assert any(p["id"] == pid for p in r2.json())
        r3 = client.delete(f"/presets/{pid}")
        assert r3.status_code == 200
        assert all(p["id"] != pid for p in client.get("/presets").json())
