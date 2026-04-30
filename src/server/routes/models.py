"""GET /v1/models — list loaded models."""

from __future__ import annotations

from fastapi import APIRouter, Request

from server.state import AppState

router = APIRouter()


@router.get("/v1/models")
def list_models(request: Request) -> dict:
    state: AppState = request.app.state.app_state
    return {
        "object": "list",
        "data": [
            {
                "id": info.id,
                "object": "model",
                "owned_by": info.backend_kind,
                "context_length": info.context_length,
            }
            for info in state.registry.backend.loaded_models()
        ],
    }
