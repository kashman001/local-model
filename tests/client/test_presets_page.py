import respx
from fastapi.testclient import TestClient
from httpx import Response

from client.app import create_app


@respx.mock
def test_presets_page_lists_and_create():
    upstream = "http://127.0.0.1:8080"
    respx.get(f"{upstream}/presets").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": "p1",
                    "name": "coder",
                    "system_prompt": "code",
                    "default_params": {},
                    "created_at": "x",
                }
            ],
        )
    )
    respx.post(f"{upstream}/presets").mock(
        return_value=Response(
            200,
            json={
                "id": "p2",
                "name": "editor",
                "system_prompt": "edit",
                "default_params": {},
                "created_at": "x",
            },
        )
    )
    app = create_app(server_url=upstream)
    with TestClient(app) as client:
        r = client.get("/presets")
        assert r.status_code == 200
        assert "coder" in r.text
        # List page should expose a delete control per preset.
        assert 'hx-delete="/presets/p1"' in r.text
        r2 = client.post("/presets/new", data={"name": "editor", "system_prompt": "edit"})
        assert r2.status_code == 200
        # New-preset response is the <li> partial — must include its own delete button.
        assert 'hx-delete="/presets/p2"' in r2.text


@respx.mock
def test_presets_delete_proxies_to_upstream():
    upstream = "http://127.0.0.1:8080"
    respx.delete(f"{upstream}/presets/p1").mock(return_value=Response(204))
    app = create_app(server_url=upstream)
    with TestClient(app) as client:
        r = client.delete("/presets/p1")
        assert r.status_code == 200
        # HTMX outerHTML swap with empty body removes the <li>.
        assert r.text == ""
