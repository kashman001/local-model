from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_create_list_get_delete_conversation():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.post(
            "/history/conversations",
            json={"title": "first", "model_id": "m1"},
        )
        assert r.status_code == 200
        cid = r.json()["id"]
        r2 = client.get("/history/conversations")
        assert any(c["id"] == cid for c in r2.json())
        r3 = client.get(f"/history/conversations/{cid}")
        assert r3.json()["id"] == cid
        r4 = client.delete(f"/history/conversations/{cid}")
        assert r4.status_code == 200
        assert client.get(f"/history/conversations/{cid}").status_code == 404


def test_append_message_and_list():
    app = create_app(backend=FakeBackend(), default_model="m1")
    with TestClient(app) as client:
        r = client.post("/history/conversations", json={"title": "t", "model_id": "m1"})
        cid = r.json()["id"]
        r2 = client.post(
            "/history/messages",
            json={"conversation_id": cid, "role": "user", "content": "hi"},
        )
        assert r2.status_code == 200
        r3 = client.get(f"/history/conversations/{cid}/messages")
        msgs = r3.json()
        assert msgs[0]["content"] == "hi"
