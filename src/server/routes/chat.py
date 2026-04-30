"""POST /v1/chat/completions — OpenAI-compatible chat completions."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.state import AppState
from server.streaming import sse_chat_stream
from server.timing import StreamTimer

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = Field(default=512, ge=1, le=8192)


def _params(req: ChatRequest) -> dict[str, Any]:
    p: dict[str, Any] = {"max_tokens": req.max_tokens}
    if req.temperature is not None:
        p["temperature"] = req.temperature
    if req.top_p is not None:
        p["top_p"] = req.top_p
    if req.model is not None:
        p["model"] = req.model
    return p


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, request: Request):
    state: AppState = request.app.state.app_state
    model_id = req.model or state.registry.require_current()
    if state.registry.current() != model_id:
        state.registry.load(model_id)
    messages = [m.model_dump() for m in req.messages]
    backend = state.registry.backend
    if req.stream:
        return StreamingResponse(
            sse_chat_stream(backend.generate(messages, _params(req)), model_id=model_id),
            media_type="text/event-stream",
        )
    timer = StreamTimer()
    timer.start()
    text_parts: list[str] = []
    for tok in backend.generate(messages, _params(req)):
        timer.token()
        text_parts.append(tok.text)
    summary = timer.finish()
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "".join(text_parts)},
                "finish_reason": "stop",
            }
        ],
        "x_local_model_stats": {
            "ttft_ms": summary.ttft_ms,
            "tps": summary.tps,
            "token_count": summary.token_count,
            "total_ms": summary.total_ms,
        },
    }
