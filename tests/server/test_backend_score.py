"""Tests for FakeBackend.score() — shape and values."""

from __future__ import annotations

import math

from server.backends.fake import FakeBackend


def test_score_returns_correct_structure():
    fb = FakeBackend()
    result = fb.score("hello")
    assert hasattr(result, "tokens")
    assert hasattr(result, "token_logprobs")
    assert hasattr(result, "top_logprobs")
    assert hasattr(result, "text_offsets")


def test_score_tokens_match_prompt_length():
    fb = FakeBackend()
    prompt = "abc"
    result = fb.score(prompt)
    # FakeBackend tokenizes char-by-char
    assert len(result.tokens) == len(prompt)
    assert result.tokens == list(prompt)


def test_score_first_token_logprob_is_none():
    fb = FakeBackend()
    result = fb.score("xyz")
    assert result.token_logprobs[0] is None


def test_score_subsequent_logprobs_are_negative():
    fb = FakeBackend()
    result = fb.score("abcd")
    for lp in result.token_logprobs[1:]:
        assert lp is not None
        assert lp < 0.0


def test_score_logprob_values_match_spec():
    fb = FakeBackend()
    result = fb.score("abcd")
    # spec: -1.0 * (i+1) for i in range(n-1)
    for i, lp in enumerate(result.token_logprobs[1:]):
        assert lp == -1.0 * (i + 1)


def test_score_text_offsets_are_byte_offsets():
    fb = FakeBackend()
    prompt = "abc"
    result = fb.score(prompt)
    # Each char is one byte offset apart in FakeBackend
    assert result.text_offsets == [0, 1, 2]


def test_score_lengths_are_consistent():
    fb = FakeBackend()
    prompt = "hello world"
    result = fb.score(prompt)
    n = len(result.tokens)
    assert len(result.token_logprobs) == n
    assert len(result.text_offsets) == n


def test_score_no_top_logprobs_by_default():
    fb = FakeBackend()
    result = fb.score("hi")
    assert result.top_logprobs is None


def test_score_top_logprobs_returned_when_requested():
    fb = FakeBackend()
    result = fb.score("abc", top_logprobs=3)
    assert result.top_logprobs is not None
    assert len(result.top_logprobs) == 3  # len("abc")
    for entry in result.top_logprobs:
        assert isinstance(entry, dict)
        assert len(entry) == 3  # top_logprobs=3 → 3 entries
        for v in entry.values():
            assert isinstance(v, float)
            assert math.isfinite(v)
