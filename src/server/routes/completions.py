"""POST /v1/completions — OpenAI-compatible legacy text completions.

Supports three modes:
- Pure generation  (max_tokens > 0, echo=False, logprobs=None)
- Pure scoring     (max_tokens == 0, echo=True,  logprobs >= 0)
- Combined         (max_tokens > 0, echo=True,   logprobs >= 0)

Streaming is not implemented in v1 (lm_eval doesn't need it). Requests with
stream=True return HTTP 400.
"""

from __future__ import annotations

import math
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from server.state import AppState

router = APIRouter()


class CompletionRequest(BaseModel):
    model: str | None = None
    prompt: str | list[str] = ""
    max_tokens: int = Field(default=16, ge=0)
    temperature: float = 0.0
    top_p: float = 1.0
    echo: bool = False
    logprobs: int | None = Field(default=None, ge=0, le=5)
    stream: bool = False
    stop: str | list[str] | None = None


def _logprobs_object(
    tokens: list[str],
    token_logprobs: list[float | None],
    top_logprobs: list[dict[str, float]] | None,
    text_offsets: list[int],
) -> dict:
    return {
        "tokens": tokens,
        "token_logprobs": token_logprobs,
        "top_logprobs": top_logprobs if top_logprobs is not None else [None] * len(tokens),
        "text_offset": text_offsets,
    }


def _build_response(
    model_id: str,
    text: str,
    logprobs_obj: dict | None,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict:
    return {
        "id": f"cmpl-{uuid.uuid4().hex[:24]}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [
            {
                "text": text,
                "index": 0,
                "logprobs": logprobs_obj,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@router.post("/v1/completions")
async def completions(req: CompletionRequest, request: Request):
    if req.stream:
        raise HTTPException(
            status_code=400,
            detail="stream=true is not supported for /v1/completions in v1",
        )

    state: AppState = request.app.state.app_state
    model_id = req.model or state.registry.require_current()
    if state.registry.current() != model_id:
        state.registry.load(model_id)

    backend = state.registry.backend

    # Normalise prompt to a single string (lm_eval sends str, not list).
    prompt = req.prompt if isinstance(req.prompt, str) else "\n".join(req.prompt)

    top_k = req.logprobs if req.logprobs is not None else 0
    do_score = req.echo or (req.logprobs is not None)
    do_generate = req.max_tokens > 0

    # ------------------------------------------------------------------ #
    # Mode 1: pure generation — no logprobs needed.                        #
    # ------------------------------------------------------------------ #
    if do_generate and not do_score:
        params: dict = {
            "model": model_id,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "top_p": req.top_p,
        }
        messages = [{"role": "user", "content": prompt}]
        parts: list[str] = []
        for tok in backend.generate(messages, params):
            parts.append(tok.text)
        gen_text = "".join(parts)
        # Rough token estimate: len(prompt.split()) for prompt, len(parts) for completion.
        return _build_response(
            model_id=model_id,
            text=gen_text,
            logprobs_obj=None,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(parts),
        )

    # ------------------------------------------------------------------ #
    # Mode 2: pure scoring — echo prompt with logprobs, no new tokens.    #
    # ------------------------------------------------------------------ #
    if not do_generate and do_score:
        score = backend.score(prompt, top_logprobs=top_k)
        lp_obj = _logprobs_object(
            score.tokens,
            score.token_logprobs,
            score.top_logprobs,
            score.text_offsets,
        )
        return _build_response(
            model_id=model_id,
            text=prompt if req.echo else "",
            logprobs_obj=lp_obj,
            prompt_tokens=len(score.tokens),
            completion_tokens=0,
        )

    # ------------------------------------------------------------------ #
    # Mode 3: combined — score prompt + generate continuation.            #
    # ------------------------------------------------------------------ #
    # Score the prompt first.
    score = backend.score(prompt, top_logprobs=top_k)
    prompt_tokens_count = len(score.tokens)

    # Generate continuation.
    params = {
        "model": model_id,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
        "top_p": req.top_p,
    }
    messages = [{"role": "user", "content": prompt}]
    gen_tokens: list = []
    for tok in backend.generate(messages, params):
        gen_tokens.append(tok)

    gen_text = "".join(t.text for t in gen_tokens)

    # Build combined logprobs: prompt logprobs + generated-token logprobs.
    all_tokens = score.tokens + [t.text for t in gen_tokens]
    all_token_logprobs: list[float | None] = list(score.token_logprobs) + [
        t.logprob if (t.logprob is not None and math.isfinite(t.logprob)) else None
        for t in gen_tokens
    ]
    all_text_offsets = list(score.text_offsets)
    # Continuation offsets start from end of prompt.
    prompt_char_len = score.text_offsets[-1] + len(score.tokens[-1]) if score.tokens else 0
    gen_offset = prompt_char_len
    for t in gen_tokens:
        all_text_offsets.append(gen_offset)
        gen_offset += len(t.text)

    # top_logprobs for generated positions: None entries (not available from stream_generate).
    if score.top_logprobs is not None:
        all_top_logprobs: list[dict[str, float]] | None = list(score.top_logprobs) + [
            {} for _ in gen_tokens
        ]
    else:
        all_top_logprobs = None

    lp_obj = _logprobs_object(
        all_tokens,
        all_token_logprobs,
        all_top_logprobs,
        all_text_offsets,
    )

    full_text = (prompt if req.echo else "") + gen_text
    return _build_response(
        model_id=model_id,
        text=full_text,
        logprobs_obj=lp_obj,
        prompt_tokens=prompt_tokens_count,
        completion_tokens=len(gen_tokens),
    )
