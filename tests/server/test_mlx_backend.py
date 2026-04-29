import platform

import pytest

pytestmark = pytest.mark.mac_only


@pytest.fixture(scope="module")
def small_model_id() -> str:
    return "mlx-community/SmolLM-135M-Instruct-4bit"


def _on_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


@pytest.mark.skipif(not _on_apple_silicon(), reason="needs Apple Silicon")
def test_load_returns_info(small_model_id):
    from server.backends.mlx_backend import MLXBackend

    b = MLXBackend()
    info = b.load(small_model_id)
    assert info.id == small_model_id
    assert info.backend_kind == "mlx"
    assert info.context_length > 0


@pytest.mark.skipif(not _on_apple_silicon(), reason="needs Apple Silicon")
def test_generate_yields_tokens(small_model_id):
    from server.backends.mlx_backend import MLXBackend

    b = MLXBackend()
    b.load(small_model_id)
    tokens = list(
        b.generate(
            messages=[{"role": "user", "content": "Say hi"}],
            params={"max_tokens": 4, "temperature": 0.0},
        )
    )
    assert 1 <= len(tokens) <= 4
    assert all(t.text != "" for t in tokens)
