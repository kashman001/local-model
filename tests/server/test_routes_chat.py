import json

from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend


def test_chat_non_streaming():
    app = create_app(backend=FakeBackend(canned_text="hi"), default_model="m")
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={
                "model": "m",
                "messages": [{"role": "user", "content": "say hi"}],
                "stream": False,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["choices"][0]["message"]["content"] == "hi"
        assert data["choices"][0]["finish_reason"] == "stop"


def test_chat_streaming_emits_done():
    app = create_app(backend=FakeBackend(canned_text="ok"), default_model="m")
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "m",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        ) as r:
            body = "".join(chunk for chunk in r.iter_text())
            assert "[DONE]" in body
            chunks = [
                json.loads(line[len("data: ") :])
                for line in body.split("\n")
                if line.startswith("data: ") and "[DONE]" not in line
            ]
            assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "ok"
