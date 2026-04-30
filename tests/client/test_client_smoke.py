import respx
from fastapi.testclient import TestClient
from httpx import Response

from client.app import create_app


def test_index_renders():
    app = create_app(server_url="http://127.0.0.1:8080")
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "local-model" in r.text


@respx.mock
def test_chat_send_creates_conversation_and_returns_assistant_shell():
    upstream = "http://127.0.0.1:8080"
    # Mock the upstream history API
    respx.post(f"{upstream}/history/conversations").mock(
        return_value=Response(200, json={"id": "conv1", "title": "t", "model_id": "m"})
    )
    respx.post(f"{upstream}/history/messages").mock(return_value=Response(200, json={"id": "msg1"}))
    respx.get(f"{upstream}/admin/stats").mock(
        return_value=Response(200, json={"current_model": "m", "loaded_count": 1})
    )

    app = create_app(server_url=upstream)
    client = TestClient(app)
    r = client.post("/chat/send", data={"prompt": "hi", "conversation_id": ""})
    assert r.status_code == 200
    # Returned HTML should include both the user bubble and an assistant shell that streams
    assert "msg user" in r.text
    assert 'hx-ext="sse"' in r.text
    assert "/chat/stream" in r.text


def test_current_model_partial():
    upstream = "http://127.0.0.1:8080"
    with respx.mock:
        respx.get(f"{upstream}/admin/stats").mock(
            return_value=Response(200, json={"current_model": "m1", "loaded_count": 1})
        )
        app = create_app(server_url=upstream)
        client = TestClient(app)
        r = client.get("/_partials/current-model")
        assert r.status_code == 200
        assert "m1" in r.text
