"""vLLM backend — Phase 2 stub. Kept here so the layout is stable for v1."""

from __future__ import annotations

from collections.abc import Iterator

from server.backends.base import ModelInfo, Token

_MSG = "VLLMBackend is a Phase 2 stub. Not implemented in v1."


class VLLMBackend:
    def load(self, model_id: str) -> ModelInfo:
        raise NotImplementedError(_MSG)

    def unload(self, model_id: str) -> None:
        raise NotImplementedError(_MSG)

    def generate(self, messages: list[dict], params: dict) -> Iterator[Token]:
        raise NotImplementedError(_MSG)
        yield  # pragma: no cover  (keeps signature an iterator)

    def model_info(self, model_id: str) -> ModelInfo:
        raise NotImplementedError(_MSG)

    def loaded_models(self) -> list[ModelInfo]:
        raise NotImplementedError(_MSG)
