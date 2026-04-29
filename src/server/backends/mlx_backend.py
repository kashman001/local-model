"""MLX backend — wraps `mlx_lm.load` and `mlx_lm.stream_generate`."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from server.backends.base import ModelInfo, Token


class MLXBackend:
    """Loads MLX models from the HuggingFace cache and streams tokens."""

    def __init__(self) -> None:
        self._loaded: dict[str, dict[str, Any]] = {}

    def load(self, model_id: str) -> ModelInfo:
        from mlx_lm import load as mlx_load  # imported lazily to keep tests light

        model, tokenizer = mlx_load(model_id)
        ctx = getattr(model, "max_position_embeddings", None) or getattr(
            getattr(model, "args", None), "max_position_embeddings", 4096
        )
        info = ModelInfo(
            id=model_id,
            display_name=model_id,
            context_length=int(ctx),
            memory_mb=0,  # MLX uses unified memory; precise number is non-trivial
            backend_kind="mlx",
        )
        self._loaded[model_id] = {"model": model, "tokenizer": tokenizer, "info": info}
        return info

    def unload(self, model_id: str) -> None:
        self._loaded.pop(model_id, None)

    def generate(self, messages: list[dict], params: dict) -> Iterator[Token]:
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        # Pick the most-recently-loaded model if no model_id in params.
        model_id = params.get("model") or next(reversed(self._loaded))
        bundle = self._loaded[model_id]
        prompt = self._render_chat_prompt(bundle["tokenizer"], messages)
        max_tokens = int(params.get("max_tokens", 512))

        # generate_step (called internally by stream_generate) no longer accepts
        # temp=/top_p= as bare kwargs — it requires a sampler callable.
        # make_sampler(temp, top_p) is the canonical factory in mlx_lm.sample_utils.
        temp = float(params.get("temperature", 0.0))
        top_p = float(params.get("top_p", 0.0))
        sampler = make_sampler(temp=temp, top_p=top_p)

        start = time.perf_counter()
        for i, response in enumerate(
            stream_generate(
                bundle["model"],
                bundle["tokenizer"],
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=sampler,
            )
        ):
            yield Token(
                text=response.text,
                token_id=int(response.token),
                logprob=float(response.logprobs[response.token])
                if response.logprobs is not None
                else 0.0,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
            )
            if i + 1 >= max_tokens:
                break

    def model_info(self, model_id: str) -> ModelInfo:
        return self._loaded[model_id]["info"]

    def loaded_models(self) -> list[ModelInfo]:
        return [b["info"] for b in self._loaded.values()]

    @staticmethod
    def _render_chat_prompt(tokenizer: Any, messages: list[dict]) -> str:
        if hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
        # Fallback for tokenizers without a chat template — concatenate roles.
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
