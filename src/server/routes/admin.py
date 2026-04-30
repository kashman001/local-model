"""Admin routes — model load/unload and stats."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from server.state import AppState

router = APIRouter()


class LoadRequest(BaseModel):
    model_id: str


@router.post("/admin/models/load")
def load(req: LoadRequest, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    info = state.registry.load(req.model_id)
    return {
        "id": info.id,
        "display_name": info.display_name,
        "context_length": info.context_length,
        "backend_kind": info.backend_kind,
    }


@router.post("/admin/models/unload")
def unload(req: LoadRequest, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    state.registry.unload(req.model_id)
    return {"ok": True}


@router.get("/admin/stats")
def stats(request: Request) -> dict:
    state: AppState = request.app.state.app_state
    return {
        "current_model": state.registry.current(),
        "loaded_count": len(state.registry.loaded_ids()),
        "loaded": [info.id for info in state.registry.backend.loaded_models()],
    }
