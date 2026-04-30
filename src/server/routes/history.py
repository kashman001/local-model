"""History routes — conversations and messages."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from server.state import AppState
from server.store.history import (
    create_conversation,
    delete_conversation,
    get_conversation,
    insert_message,
    list_conversations,
    list_messages,
)

router = APIRouter()


class CreateConv(BaseModel):
    title: str
    model_id: str
    preset_id: str | None = None


class AppendMessage(BaseModel):
    conversation_id: str
    role: str
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tps: float | None = None
    ttft_ms: float | None = None


def _conv_to_json(c) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "model_id": c.model_id,
        "preset_id": c.preset_id,
        "created_at": str(c.created_at),
        "updated_at": str(c.updated_at),
    }


def _msg_to_json(m) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "role": m.role,
        "content": m.content,
        "prompt_tokens": m.prompt_tokens,
        "completion_tokens": m.completion_tokens,
        "tps": m.tps,
        "ttft_ms": m.ttft_ms,
        "created_at": str(m.created_at),
    }


@router.post("/history/conversations")
def create_conv(req: CreateConv, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    c = create_conversation(
        state.db, title=req.title, model_id=req.model_id, preset_id=req.preset_id
    )
    return _conv_to_json(c)


@router.get("/history/conversations")
def list_convs(request: Request) -> list[dict]:
    state: AppState = request.app.state.app_state
    return [_conv_to_json(c) for c in list_conversations(state.db)]


@router.get("/history/conversations/{cid}")
def get_conv(cid: str, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    c = get_conversation(state.db, cid)
    if not c:
        raise HTTPException(status_code=404, detail="conversation not found")
    return _conv_to_json(c)


@router.delete("/history/conversations/{cid}")
def del_conv(cid: str, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    delete_conversation(state.db, cid)
    return {"ok": True}


@router.get("/history/conversations/{cid}/messages")
def list_msgs(cid: str, request: Request) -> list[dict]:
    state: AppState = request.app.state.app_state
    if not get_conversation(state.db, cid):
        raise HTTPException(status_code=404, detail="conversation not found")
    return [_msg_to_json(m) for m in list_messages(state.db, cid)]


@router.post("/history/messages")
def append_msg(req: AppendMessage, request: Request) -> dict:
    state: AppState = request.app.state.app_state
    if not get_conversation(state.db, req.conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    m = insert_message(
        state.db,
        conversation_id=req.conversation_id,
        role=req.role,
        content=req.content,
        prompt_tokens=req.prompt_tokens,
        completion_tokens=req.completion_tokens,
        tps=req.tps,
        ttft_ms=req.ttft_ms,
    )
    return _msg_to_json(m)
