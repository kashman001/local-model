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
        stats = data["x_local_model_stats"]
        assert all(k in stats for k in ("ttft_ms", "tps", "token_count", "total_ms"))
        assert all(isinstance(stats[k], (int, float)) for k in stats)


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
            stats_chunks = [c for c in chunks if "x_local_model_stats" in c]
            assert len(stats_chunks) == 1
            stats = stats_chunks[0]["x_local_model_stats"]
            assert all(k in stats for k in ("ttft_ms", "tps", "token_count", "total_ms"))
            assert all(isinstance(stats[k], (int, float)) for k in stats)


def test_chat_model_not_loaded_returns_503():
    app = create_app(backend=FakeBackend(), default_model="m")
    with TestClient(app) as client:
        # Manually unload after lifespan startup to simulate no-model state.
        state = app.state.app_state
        state.registry.unload("m")
        r = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "model_not_loaded"
    assert isinstance(body["error"]["message"], str)
