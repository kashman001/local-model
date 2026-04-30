from fastapi.testclient import TestClient

from client.app import create_app


def test_index_renders():
    app = create_app(server_url="http://127.0.0.1:8080")
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "local-model" in r.text
    assert "hx-" in r.text  # HTMX attributes are present
