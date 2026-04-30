"""Streaming regression test against a real MLX backend.

Verifies that the worker-thread fix prevents RuntimeError from MLX's
thread-local GPU stream when Starlette dispatches next() calls across
threads.  Uses Llama-3.2-1B — slow enough (~250-300 tok/s on M5 Max)
to reliably expose the bug pre-fix.

Marked mac_only — skipped on non-Apple-Silicon.
"""

from __future__ import annotations

import json
import platform

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.mac_only

MODEL = "mlx-community/Llama-3.2-1B-Instruct-4bit"


def _on_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


@pytest.mark.skipif(not _on_apple_silicon(), reason="needs Apple Silicon")
def test_streaming_thread_affinity():
    """SSE stream must deliver tokens without RuntimeError across worker threads."""
    from server.app import create_app
    from server.backends.mlx_backend import MLXBackend

    app = create_app(backend=MLXBackend(), default_model=MODEL)

    with TestClient(app) as client:
        chunks_with_content: list[dict] = []
        final_chunk: dict | None = None

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Count slowly: 1, 2, 3"}],
                "stream": True,
                "max_tokens": 64,
            },
        ) as resp:
            assert resp.status_code == 200
            for raw_line in resp.iter_lines():
                line = raw_line.strip()
                if not line or line == "data: [DONE]":
                    continue
                assert line.startswith("data: "), f"unexpected SSE line: {line!r}"
                payload = json.loads(line[len("data: ") :])
                delta = payload["choices"][0]["delta"]
                if delta.get("content"):
                    chunks_with_content.append(payload)
                if "x_local_model_stats" in payload:
                    final_chunk = payload

        # At least 5 content chunks (the 1B model with max_tokens=64 easily exceeds this)
        assert len(chunks_with_content) >= 5, (
            f"expected ≥5 content chunks, got {len(chunks_with_content)}"
        )

        # Final stats chunk must be present and well-formed
        assert final_chunk is not None, "missing final chunk with x_local_model_stats"
        stats = final_chunk["x_local_model_stats"]
        for field in ("ttft_ms", "tps", "token_count", "total_ms"):
            assert isinstance(stats[field], (int, float)), (
                f"x_local_model_stats.{field} is not numeric: {stats[field]!r}"
            )
