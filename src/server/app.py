"""FastAPI app factory. Wires together registry, store, and routes."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.backends.base import Backend
from server.config import ServerSettings
from server.registry import ModelRegistry
from server.state import AppState
from server.store.db import connect, migrate


def create_app(
    *,
    backend: Backend,
    default_model: str,
    db_path: str = ":memory:",
) -> FastAPI:
    registry = ModelRegistry(backend=backend)
    db = connect(db_path)
    migrate(db)
    state = AppState(registry=registry, db=db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry.load(default_model)
        try:
            yield
        finally:
            current = registry.current()
            if current:
                registry.unload(current)
            db.close()

    app = FastAPI(title="local-model server", version="0.1.0", lifespan=lifespan)
    from server.routes.chat import router as chat_router

    app.include_router(chat_router)
    app.state.app_state = state

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def build_app_from_env() -> FastAPI:
    """Entry point for `uvicorn server.app:build_app_from_env --factory`."""
    settings = ServerSettings()
    logging.basicConfig(level=settings.log_level)
    backend = _resolve_backend(settings.backend)
    return create_app(
        backend=backend,
        default_model=settings.default_model,
        db_path=settings.db_path,
    )


def _resolve_backend(name: str) -> Backend:
    if name == "mlx":
        from server.backends.mlx_backend import MLXBackend
        from server.capability import check_mlx

        check_mlx()
        return MLXBackend()
    if name == "vllm":
        from server.backends.vllm_backend import VLLMBackend
        from server.capability import check_vllm

        check_vllm()
        return VLLMBackend()
    raise ValueError(f"Unknown backend: {name}")
