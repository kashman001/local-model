from server.backends.base import Backend, ModelInfo, Token
from server.backends.fake import FakeBackend


def test_token_dataclass_fields():
    t = Token(text="hi", token_id=42, logprob=-0.5, elapsed_ms=12.3)
    assert t.text == "hi"
    assert t.token_id == 42
    assert t.logprob == -0.5
    assert t.elapsed_ms == 12.3


def test_model_info_dataclass_fields():
    info = ModelInfo(
        id="m",
        display_name="m",
        context_length=1024,
        memory_mb=128,
        backend_kind="fake",
    )
    assert info.id == "m"
    assert info.backend_kind == "fake"


def test_fake_backend_satisfies_protocol():
    fb = FakeBackend(canned_text="hello world")
    assert isinstance(fb, Backend)


def test_fake_backend_load_returns_model_info():
    fb = FakeBackend()
    info = fb.load("m")
    assert info.id == "m"
    assert info.backend_kind == "fake"


def test_fake_backend_generate_yields_tokens():
    fb = FakeBackend(canned_text="ab cd")
    fb.load("m")
    tokens = list(fb.generate(messages=[{"role": "user", "content": "hi"}], params={}))
    assert "".join(t.text for t in tokens) == "ab cd"
    assert all(isinstance(t, Token) for t in tokens)
