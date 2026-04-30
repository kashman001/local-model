"""Preset routes — saved system prompts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from server.state import AppState
from server.store.presets import create_preset, delete_preset, list_presets

router = APIRouter()


class CreatePreset(BaseModel):
    name: str
    system_prompt: str
    default_params: dict[str, Any] = {}


def _to_json(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "system_prompt": p.system_prompt,
        "default_params": p.default_params,
        "created_at": str(p.created_at),
    }


@router.get("/presets")
def list_p(request: Request) -> list[dict]:
    state: AppState = request.app.state.app_state
    return [_to_json(p) for p in list_presets(state.db)]


@router.post("/presets")
def create_p(req: CreatePreset, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    p = create_preset(
        state.db,
        name=req.name,
        system_prompt=req.system_prompt,
        default_params=req.default_params,
    )
    return _to_json(p)


@router.delete("/presets/{pid}")
def delete_p(pid: str, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    delete_preset(state.db, pid)
    return {"ok": True}
