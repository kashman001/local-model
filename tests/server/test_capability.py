import platform

import pytest

from server.capability import CapabilityError, check_mlx, check_vllm


def test_check_mlx_on_apple_silicon_or_skips():
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import mlx  # noqa: F401
        except ImportError:
            pytest.skip("mlx not installed")
        check_mlx()  # must not raise
    else:
        with pytest.raises(CapabilityError):
            check_mlx()


def test_check_vllm_raises_when_unavailable(monkeypatch):
    # Force the import to fail to simulate missing vLLM.
    import sys

    monkeypatch.setitem(sys.modules, "vllm", None)
    with pytest.raises(CapabilityError):
        check_vllm()
