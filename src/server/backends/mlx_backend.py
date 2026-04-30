"""MLX backend — wraps `mlx_lm.load` and `mlx_lm.stream_generate`.

MLX has a thread-local GPU stream (Stream(gpu, N)).  All tensors produced
by a given computation are bound to the stream that was active when they
were created.  Starlette's iterate_in_threadpool dispatches each next()
call from a StreamingResponse to an arbitrary anyio worker thread, and each
such thread has a *different* stream number.  Tensor evals that cross thread
boundaries fail with:

    RuntimeError: There is no Stream(gpu, N) in current thread.

Fix (see ADR 0004): all MLX operations — both load and generate — run on a
single persistent worker thread (_MLXWorkerThread) created when this backend
is instantiated.  Callers communicate via queues; the public interface is
unchanged (sync Iterator[Token]).
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterator
from typing import Any

from server.backends.base import ModelInfo, Token

# Sentinel objects used in inter-thread communication.
_STOP = object()  # worker loop shutdown
_DONE = object()  # end of one generation stream


class _MLXWorkerThread:
    """Single OS thread that owns the MLX GPU stream for this backend."""

    def __init__(self) -> None:
        self._q: queue.Queue[Any] = queue.Queue()
        self._loaded: dict[str, dict[str, Any]] = {}
        self._t = threading.Thread(target=self._loop, daemon=True, name="mlx-worker")
        self._t.start()

    def _loop(self) -> None:
        """Main loop — runs entirely on the dedicated worker thread."""
        import mlx.core as mx
        from mlx_lm import load as mlx_load
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        # Own a fresh GPU stream for this thread's lifetime.  All MLX ops
        # (including mlx_load and stream_generate) will run on this stream.
        mx.new_thread_local_stream(mx.gpu)

        while True:
            task = self._q.get()
            if task is _STOP:
                break

            kind, args, result_q = task

            if kind == "load":
                (model_id,) = args
                try:
                    model, tokenizer = mlx_load(model_id)
                    ctx = getattr(model, "max_position_embeddings", None) or getattr(
                        getattr(model, "args", None), "max_position_embeddings", 4096
                    )
                    info = ModelInfo(
                        id=model_id,
                        display_name=model_id,
                        context_length=int(ctx),
                        memory_mb=0,
                        backend_kind="mlx",
                    )
                    self._loaded[model_id] = {
                        "model": model,
                        "tokenizer": tokenizer,
                        "info": info,
                    }
                    result_q.put(("ok", info))
                except Exception as exc:
                    result_q.put(("err", exc))

            elif kind == "unload":
                (model_id,) = args
                self._loaded.pop(model_id, None)
                result_q.put(("ok", None))

            elif kind == "generate":
                model_id, prompt, max_tokens, temp, top_p, token_q = args
                bundle = self._loaded.get(model_id)
                if bundle is None:
                    token_q.put(("error", KeyError(f"model not loaded: {model_id}")))
                    continue
                try:
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
                        token_q.put(
                            Token(
                                text=response.text,
                                token_id=int(response.token),
                                logprob=float(response.logprobs[response.token])
                                if response.logprobs is not None
                                else 0.0,
                                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                            )
                        )
                        if i + 1 >= max_tokens:
                            break
                except Exception as exc:
                    token_q.put(("error", exc))
                    continue
                token_q.put(_DONE)

    def _call(self, kind: str, *args: Any) -> Any:
        """Dispatch a synchronous call to the worker thread; block until done."""
        result_q: queue.Queue[Any] = queue.Queue()
        self._q.put((kind, args, result_q))
        status, val = result_q.get()
        if status == "err":
            raise val
        return val


class MLXBackend:
    """Loads MLX models from the HuggingFace cache and streams tokens.

    All MLX operations (load, generate) are serialised onto a single
    background thread to avoid MLX's thread-local GPU-stream constraint.
    """

    def __init__(self) -> None:
        self._worker = _MLXWorkerThread()

    def load(self, model_id: str) -> ModelInfo:
        return self._worker._call("load", model_id)

    def unload(self, model_id: str) -> None:
        self._worker._call("unload", model_id)

    def generate(self, messages: list[dict], params: dict) -> Iterator[Token]:
        # Resolve model_id before dispatching (need tokenizer for prompt render).
        model_id = params.get("model") or next(reversed(self._worker._loaded), None)
        if model_id is None:
            raise RuntimeError("No model loaded")
        bundle = self._worker._loaded.get(model_id)
        if bundle is None:
            raise KeyError(f"model not loaded: {model_id}")

        prompt = self._render_chat_prompt(bundle["tokenizer"], messages)
        max_tokens = int(params.get("max_tokens", 512))
        temp = float(params.get("temperature", 0.0))
        top_p = float(params.get("top_p", 0.0))

        # The worker owns the GPU stream; it pushes Token objects into this
        # queue.  We consume them here (from any thread) — safe because queue
        # is thread-safe and no MLX ops happen outside the worker thread.
        token_q: queue.Queue[Any] = queue.Queue(maxsize=128)
        result_q: queue.Queue[Any] = queue.Queue()
        self._worker._q.put(
            ("generate", (model_id, prompt, max_tokens, temp, top_p, token_q), result_q)
        )

        while True:
            item = token_q.get()
            if item is _DONE:
                break
            if isinstance(item, tuple) and item[0] == "error":
                raise item[1]
            yield item  # type: ignore[misc]

    def model_info(self, model_id: str) -> ModelInfo:
        return self._worker._loaded[model_id]["info"]

    def loaded_models(self) -> list[ModelInfo]:
        return [b["info"] for b in self._worker._loaded.values()]

    @staticmethod
    def _render_chat_prompt(tokenizer: Any, messages: list[dict]) -> str:
        if hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
