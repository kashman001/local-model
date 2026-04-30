"""Mac-only smoke test for /v1/completions scoring via real MLX backend.

Loads mlx-community/Llama-3.2-1B-4bit (small, fast, should be in HF cache),
scores a known prompt, and asserts logprob shape + value sanity.
"""

from __future__ import annotations

import math
import platform

import pytest

pytestmark = pytest.mark.mac_only

_MODEL = "mlx-community/Llama-3.2-1B-Instruct-4bit"


def _on_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


@pytest.mark.skipif(not _on_apple_silicon(), reason="needs Apple Silicon")
def test_real_completions_scoring():
    from fastapi.testclient import TestClient

    from server.app import create_app
    from server.backends.mlx_backend import MLXBackend

    app = create_app(backend=MLXBackend(), default_model=_MODEL)
    with TestClient(app) as client:
        prompt = "The quick brown fox"
        r = client.post(
            "/v1/completions",
            json={
                "model": _MODEL,
                "prompt": prompt,
                "max_tokens": 0,
                "echo": True,
                "logprobs": 3,
            },
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()

        assert data["object"] == "text_completion"
        assert data["choices"][0]["text"] == prompt

        lp = data["choices"][0]["logprobs"]
        assert lp is not None

        tokens = lp["tokens"]
        token_logprobs = lp["token_logprobs"]
        top_logprobs = lp["top_logprobs"]

        assert len(tokens) > 0
        assert len(token_logprobs) == len(tokens)

        # First token has no prediction context.
        assert token_logprobs[0] is None

        # All subsequent logprobs must be negative finite floats.
        for lp_val in token_logprobs[1:]:
            assert lp_val is not None, "logprob should not be None after first token"
            assert math.isfinite(lp_val), f"expected finite float, got {lp_val}"
            assert lp_val < 0.0, f"log-probability must be <= 0, got {lp_val}"

        # top_logprobs: each position should have up to k=3 entries with finite values.
        assert top_logprobs is not None
        assert len(top_logprobs) == len(tokens)
        for pos_dict in top_logprobs:
            assert isinstance(pos_dict, dict)
            assert 1 <= len(pos_dict) <= 3
            for tok_str, lp_val in pos_dict.items():
                assert isinstance(tok_str, str)
                assert math.isfinite(lp_val), f"top logprob not finite: {lp_val}"

        # Usage sanity.
        usage = data["usage"]
        assert usage["prompt_tokens"] == len(tokens)
        assert usage["completion_tokens"] == 0
