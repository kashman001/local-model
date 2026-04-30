"""Wrap a backend Token iterator into Server-Sent Events matching OpenAI's shape."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterable, Iterator

from server.backends.base import Token
from server.timing import StreamTimer


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def sse_chat_stream(tokens: Iterable[Token], *, model_id: str) -> Iterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    timer = StreamTimer()
    timer.start()
    for tok in tokens:
        timer.token()
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": {"content": tok.text}, "finish_reason": None}],
        }
        yield _sse(chunk)
    summary = timer.finish()
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "x_local_model_stats": {
            "ttft_ms": summary.ttft_ms,
            "tps": summary.tps,
            "token_count": summary.token_count,
            "total_ms": summary.total_ms,
        },
    }
    yield _sse(final)
    yield "data: [DONE]\n\n"
