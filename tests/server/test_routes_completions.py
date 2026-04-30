"""Tests for POST /v1/completions — all three modes with FakeBackend."""

from __future__ import annotations

from fastapi.testclient import TestClient

from server.app import create_app
from server.backends.fake import FakeBackend

_OPENAI_COMPLETION_KEYS = {"id", "object", "created", "model", "choices", "usage"}
_CHOICE_KEYS = {"text", "index", "logprobs", "finish_reason"}
_USAGE_KEYS = {"prompt_tokens", "completion_tokens", "total_tokens"}
_LOGPROBS_KEYS = {"tokens", "token_logprobs", "top_logprobs", "text_offset"}


def _make_client(canned: str = "ok") -> TestClient:
    app = create_app(backend=FakeBackend(canned_text=canned), default_model="m")
    return TestClient(app)


# ------------------------------------------------------------------ #
# Mode 1: pure generation                                              #
# ------------------------------------------------------------------ #


def test_generation_mode_response_shape():
    client = _make_client("hello")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "test", "max_tokens": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert _OPENAI_COMPLETION_KEYS.issubset(data.keys())
    assert data["object"] == "text_completion"
    assert data["id"].startswith("cmpl-")
    assert isinstance(data["created"], int)
    assert data["model"] == "m"


def test_generation_mode_choices_shape():
    client = _make_client("hi")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "ping", "max_tokens": 4},
    )
    data = r.json()
    choices = data["choices"]
    assert len(choices) == 1
    assert _CHOICE_KEYS.issubset(choices[0].keys())
    assert choices[0]["index"] == 0
    assert choices[0]["finish_reason"] == "stop"
    assert choices[0]["logprobs"] is None


def test_generation_mode_usage():
    client = _make_client("ab")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "hello world", "max_tokens": 8},
    )
    data = r.json()
    usage = data["usage"]
    assert _USAGE_KEYS.issubset(usage.keys())
    assert usage["completion_tokens"] >= 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_generation_mode_text_is_canned():
    client = _make_client("world")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "say hi", "max_tokens": 10},
    )
    data = r.json()
    # FakeBackend emits canned_text chars as tokens
    assert data["choices"][0]["text"] == "world"


# ------------------------------------------------------------------ #
# Mode 2: pure scoring                                                 #
# ------------------------------------------------------------------ #


def test_scoring_mode_response_shape():
    client = _make_client()
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "abc", "max_tokens": 0, "echo": True, "logprobs": 0},
    )
    assert r.status_code == 200
    data = r.json()
    assert _OPENAI_COMPLETION_KEYS.issubset(data.keys())
    assert data["object"] == "text_completion"


def test_scoring_mode_logprobs_shape():
    client = _make_client()
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "abc", "max_tokens": 0, "echo": True, "logprobs": 0},
    )
    data = r.json()
    lp = data["choices"][0]["logprobs"]
    assert lp is not None
    assert _LOGPROBS_KEYS.issubset(lp.keys())
    assert len(lp["tokens"]) == 3  # "abc" → 3 chars
    assert lp["token_logprobs"][0] is None  # first token always None


def test_scoring_mode_echo_text():
    client = _make_client()
    prompt = "hello"
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": prompt, "max_tokens": 0, "echo": True, "logprobs": 0},
    )
    data = r.json()
    assert data["choices"][0]["text"] == prompt


def test_scoring_mode_zero_completion_tokens():
    client = _make_client()
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "abc", "max_tokens": 0, "echo": True, "logprobs": 0},
    )
    data = r.json()
    assert data["usage"]["completion_tokens"] == 0


def test_scoring_mode_top_logprobs_returned():
    client = _make_client()
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "abc", "max_tokens": 0, "echo": True, "logprobs": 2},
    )
    data = r.json()
    top_lp = data["choices"][0]["logprobs"]["top_logprobs"]
    assert top_lp is not None
    assert len(top_lp) == 3  # one per token


# ------------------------------------------------------------------ #
# Mode 3: combined                                                      #
# ------------------------------------------------------------------ #


def test_combined_mode_response_shape():
    client = _make_client("ok")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "hi", "max_tokens": 4, "echo": True, "logprobs": 0},
    )
    assert r.status_code == 200
    data = r.json()
    assert _OPENAI_COMPLETION_KEYS.issubset(data.keys())


def test_combined_mode_text_contains_prompt_and_generation():
    client = _make_client("ok")
    prompt = "hi"
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": prompt, "max_tokens": 4, "echo": True, "logprobs": 0},
    )
    data = r.json()
    text = data["choices"][0]["text"]
    # echo=True → prompt is prepended
    assert text.startswith(prompt)
    # generation appended
    assert text == prompt + "ok"


def test_combined_mode_logprobs_length():
    client = _make_client("ok")
    prompt = "hi"  # 2 chars
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": prompt, "max_tokens": 4, "echo": True, "logprobs": 0},
    )
    data = r.json()
    lp = data["choices"][0]["logprobs"]
    # 2 prompt tokens + 2 generated tokens ("ok")
    assert len(lp["tokens"]) == 4
    assert len(lp["token_logprobs"]) == 4


def test_combined_mode_usage_counts():
    client = _make_client("ok")
    prompt = "hi"
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": prompt, "max_tokens": 4, "echo": True, "logprobs": 0},
    )
    data = r.json()
    usage = data["usage"]
    assert usage["prompt_tokens"] == 2  # len("hi")
    assert usage["completion_tokens"] == 2  # len("ok")
    assert usage["total_tokens"] == 4


# ------------------------------------------------------------------ #
# Edge / error cases                                                    #
# ------------------------------------------------------------------ #


def test_stream_true_returns_400():
    client = _make_client()
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": "hi", "stream": True},
    )
    assert r.status_code == 400


def test_prompt_as_list_joined():
    client = _make_client("ok")
    r = client.post(
        "/v1/completions",
        json={"model": "m", "prompt": ["hello", "world"], "max_tokens": 4},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["text"] == "ok"
