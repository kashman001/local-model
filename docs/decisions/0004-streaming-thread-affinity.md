# 0004 — Backend generate contract: thread-safe iterators for Starlette streaming

- **Status:** Accepted
- **Date:** 2026-04-30
- **Deciders:** project owner

## Context

FastAPI uses Starlette's `StreamingResponse` for SSE. When the response body is a
*synchronous* iterator, Starlette wraps it via `iterate_in_threadpool`, which calls
each `next()` through `anyio.to_thread.run_sync`. At realistic concurrency, successive
`next()` calls can land on **different** OS threads from the default anyio worker pool.

MLX has a deeper thread constraint than just "stream per thread". `mlx_lm.generate`
declares a module-level `generation_stream = mx.new_thread_local_stream(...)` at import
time. All `stream_generate` internals run inside `with mx.stream(generation_stream):`.
Because `ThreadLocalStream` is OS-thread-local, the stream it resolves to differs per
thread — but tensors (including `prompt_cache.state`) are bound to the stream they were
first computed on. When `generate_step` runs `mx.eval([c.state for c in prompt_cache])`
on a thread whose stream differs from the one that created those tensors, MLX raises:

```
RuntimeError: There is no Stream(gpu, N) in current thread.
```

Critically, this affects **both** `load` and `generate`: the model weights loaded via
`mlx_lm.load` are lazy tensors bound to the calling thread's stream. Any subsequent
`stream_generate` call that lands on a different thread will fail on the first
`prompt_cache` eval, regardless of whether a new stream was initialized on that thread.

This was invisible with small models (SmolLM-135M) because they complete before anyio
cycles its threadpool. It surfaces reliably with Llama-3.1-8B-Instruct at ~125 tok/s.

## Decision

**`Backend.generate(messages, params)` returns a sync `Iterator[Token]` that is safe
to consume from any thread.** Implementations whose engine has thread affinity own the
responsibility of ensuring all engine operations execute on a single dedicated thread.

`MLXBackend` now owns a single persistent `_MLXWorkerThread` per instance. This thread
calls `mx.new_thread_local_stream(mx.gpu)` once at startup and then handles all `load`,
`unload`, and `generate` dispatches for the backend's lifetime via a `queue.Queue`.
`MLXBackend.generate(...)` enqueues the work and returns a generator that drains a
per-request `token_q`; callers can consume it from any thread. The public signature is
unchanged; no route or middleware changes are required.

## Why both load and generate must share the same thread

A naïve per-request worker thread (one thread per `generate` call) does not fix the
problem: the model weights are lazy tensors bound to the stream of whichever thread
called `mlx_load`. Any new thread gets a different stream number, and the first
`mx.eval` on the cache state fails. The model must be loaded on the same thread that
will run all generation.

## Why this lives in the backend, not the route

The `Backend` Protocol is the abstraction boundary. Routes only see `Iterator[Token]`.
If thread pinning lived in the route layer, every route would need to know each
backend's threading quirks — exactly the coupling the Protocol is meant to prevent.
Keeping the responsibility inside the backend means `VLLMBackend` can handle its own
threading model differently without touching the route.

## Consequences

- `MLXBackend` adds one persistent daemon thread per backend instance. Requests are
  serialised through it; `queue.Queue(maxsize=128)` provides token backpressure.
- `VLLMBackend` (Phase 2) faces the analogous problem differently: `AsyncLLMEngine`
  exposes an `AsyncGenerator`. Options are (a) keep the sync `Backend` Protocol and
  wrap async→sync at the boundary using `asyncio.run_coroutine_threadsafe` against a
  dedicated event loop, or (b) extend the Protocol to support async backends natively.
  **Decide this in the V2 plan, not at impl time.**
- Future raw-CUDA-via-PyTorch backends would need `torch.cuda.set_device()` inside the
  worker thread plus explicit stream synchronization.
- Generic rule: any `Backend.generate` whose engine touches GPU state directly should
  assume Starlette will call `next()` from arbitrary threads, and either pin generation
  internally (MLX pattern) or use an async-native bridge (vLLM pattern).

## Cross-references

- [ADR 0003](./0003-server-architecture.md) — defines the `Backend` Protocol
- `src/server/backends/mlx_backend.py` — `_MLXWorkerThread` persistent-thread implementation
- `tests/smoke/test_mac_streaming.py` — regression test (1B model, 64 tokens)
