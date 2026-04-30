"""Backend protocol and shared dataclasses."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class Token:
    text: str
    token_id: int
    logprob: float
    elapsed_ms: float


@dataclass(slots=True)
class ModelInfo:
    id: str
    display_name: str
    context_length: int
    memory_mb: int
    backend_kind: str


@dataclass
class ScoreResult:
    """Per-token logprob data for a prompt — matches OpenAI's logprobs shape."""

    tokens: list[str]
    token_logprobs: list[float | None]
    top_logprobs: list[dict[str, float]] | None
    text_offsets: list[int]


@runtime_checkable
class Backend(Protocol):
    def load(self, model_id: str) -> ModelInfo: ...

    def unload(self, model_id: str) -> None: ...

    def generate(
        self,
        messages: list[dict],
        params: dict,
    ) -> Iterator[Token]: ...

    def score(self, prompt: str, *, top_logprobs: int = 0) -> ScoreResult: ...

    def model_info(self, model_id: str) -> ModelInfo: ...

    def loaded_models(self) -> list[ModelInfo]: ...
