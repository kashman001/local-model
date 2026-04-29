import pytest

from server.backends.vllm_backend import VLLMBackend


def test_load_raises_not_implemented():
    b = VLLMBackend()
    with pytest.raises(NotImplementedError, match="Phase 2"):
        b.load("m")


def test_generate_raises_not_implemented():
    b = VLLMBackend()
    with pytest.raises(NotImplementedError, match="Phase 2"):
        list(b.generate(messages=[], params={}))
