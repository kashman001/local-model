"""In-memory fake backend used by tests."""

from __future__ import annotations

import time
from collections.abc import Iterator

from server.backends.base import ModelInfo, Token


class FakeBackend:
    """Yields a canned token stream. Useful for end-to-end tests without a model."""

    def __init__(self, canned_text: str = "ok") -> None:
        self.canned_text = canned_text
        self._loaded: dict[str, ModelInfo] = {}

    def load(self, model_id: str) -> ModelInfo:
        info = ModelInfo(
            id=model_id,
            display_name=model_id,
            context_length=2048,
            memory_mb=0,
            backend_kind="fake",
        )
        self._loaded[model_id] = info
        return info

    def unload(self, model_id: str) -> None:
        self._loaded.pop(model_id, None)

    def generate(self, messages: list[dict], params: dict) -> Iterator[Token]:
        """Yield one Token per char. Arguments required by Protocol but ignored."""
        start = time.perf_counter()
        for i, ch in enumerate(self.canned_text):
            yield Token(
                text=ch,
                token_id=i,
                logprob=0.0,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
            )

    def model_info(self, model_id: str) -> ModelInfo:
        return self._loaded[model_id]

    def loaded_models(self) -> list[ModelInfo]:
        return list(self._loaded.values())
