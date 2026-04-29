"""Single-model registry. Enforces 'one model loaded at a time' for v1."""

from __future__ import annotations

import threading

from server.backends.base import Backend, ModelInfo


class ModelNotLoaded(RuntimeError):
    """Raised when an operation needs a loaded model but none is."""


class ModelRegistry:
    def __init__(self, backend: Backend) -> None:
        self._backend = backend
        self._current: str | None = None
        self._lock = threading.Lock()

    def load(self, model_id: str) -> ModelInfo:
        with self._lock:
            if self._current and self._current != model_id:
                self._backend.unload(self._current)
                self._current = None
            info = self._backend.load(model_id)
            self._current = model_id
            return info

    def unload(self, model_id: str) -> None:
        with self._lock:
            if self._current == model_id:
                self._backend.unload(model_id)
                self._current = None

    def current(self) -> str | None:
        return self._current

    def loaded_ids(self) -> list[str]:
        return [self._current] if self._current else []

    def require_current(self) -> str:
        if not self._current:
            raise ModelNotLoaded("No model is currently loaded")
        return self._current

    @property
    def backend(self) -> Backend:
        return self._backend
