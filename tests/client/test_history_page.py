import respx
from fastapi.testclient import TestClient
from httpx import Response

from client.app import create_app


@respx.mock
def test_history_page_lists_conversations():
    upstream = "http://127.0.0.1:8080"
    respx.get(f"{upstream}/history/conversations").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": "c1",
                    "title": "first chat",
                    "model_id": "m",
                    "preset_id": None,
                    "created_at": "2026-04-28",
                    "updated_at": "2026-04-28",
                }
            ],
        )
    )
    app = create_app(server_url=upstream)
    client = TestClient(app)
    r = client.get("/history")
    assert r.status_code == 200
    assert "first chat" in r.text
