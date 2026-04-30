"""End-to-end smoke against a real MLX backend. Marked mac_only — skipped on non-Apple-Silicon.

Loads the smallest MLX model the project trusts and runs one chat completion.
"""

from __future__ import annotations

import platform

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.mac_only


def _on_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


@pytest.mark.skipif(not _on_apple_silicon(), reason="needs Apple Silicon")
def test_real_chat_completion_streams():
    from server.app import create_app
    from server.backends.mlx_backend import MLXBackend

    app = create_app(
        backend=MLXBackend(),
        default_model="mlx-community/SmolLM-135M-Instruct-4bit",
    )
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={
                "model": "mlx-community/SmolLM-135M-Instruct-4bit",
                "messages": [{"role": "user", "content": "Say hi in one word."}],
                "stream": False,
                "max_tokens": 8,
            },
        )
        assert r.status_code == 200
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        assert isinstance(text, str)
        assert len(text) > 0
        assert data["x_local_model_stats"]["token_count"] > 0
