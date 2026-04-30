import respx
from fastapi.testclient import TestClient
from httpx import Response

from client.app import create_app


@respx.mock
def test_stats_page_renders_swap_form():
    upstream = "http://127.0.0.1:8080"
    respx.get(f"{upstream}/admin/stats").mock(
        return_value=Response(
            200, json={"current_model": "m1", "loaded_count": 1, "loaded": ["m1"]}
        )
    )
    respx.get(f"{upstream}/v1/models").mock(
        return_value=Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "m1", "object": "model", "owned_by": "fake", "context_length": 2048}
                ],
            },
        )
    )
    app = create_app(server_url=upstream)
    client = TestClient(app)
    r = client.get("/stats")
    assert r.status_code == 200
    assert "m1" in r.text
    assert "/swap" in r.text


@respx.mock
def test_swap_posts_to_admin_load():
    upstream = "http://127.0.0.1:8080"
    respx.post(f"{upstream}/admin/models/load").mock(
        return_value=Response(
            200,
            json={"id": "m2", "display_name": "m2", "context_length": 4096, "backend_kind": "fake"},
        )
    )
    app = create_app(server_url=upstream)
    client = TestClient(app)
    r = client.post("/swap", data={"model_id": "m2"})
    assert r.status_code == 200
    assert "m2" in r.text
