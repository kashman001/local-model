# 0005 — POST /v1/completions and Backend.score(): Protocol extension for logprob scoring

- **Status:** Accepted
- **Date:** 2026-04-30
- **Deciders:** project owner

## Context

`lm_eval`'s `local-completions` adapter drives evaluations (MMLU, ARC, HellaSwag, etc.)
via the OpenAI legacy completions endpoint (`POST /v1/completions`). The critical usage
pattern is *loglikelihood scoring*: lm_eval sends `max_tokens=0, echo=True, logprobs=0`
and reads `choices[0].logprobs.token_logprobs` to rank candidate continuations without
generating any new tokens. This is distinct from chat/generation and requires a dedicated
forward-pass-only codepath.

## Decisions

### 1. Extend `Backend` Protocol with `score()` rather than a separate `Scorer` interface

**Option A (chosen):** Add `score(prompt, *, top_logprobs=0) -> ScoreResult` directly to
the `Backend` Protocol.

**Option B (rejected):** Introduce a parallel `Scorer` protocol; backends opt-in.

Option A is correct here because:
- Scoring requires the **same model weights** loaded for generation. A separate interface
  would force a second load or a cross-protocol dependency — worse ergonomics for the same
  threading budget.
- The thread-affinity rule from ADR 0004 already makes `Backend` the right coordination
  point. Both `generate` and `score` must run on the same `_MLXWorkerThread`.
- The protocol surface stays small (one extra method); callers that only need generation
  can ignore `score`.

### 2. MLX scoring dispatches through `_MLXWorkerThread`

`MLXBackend.score(prompt)` enqueues a `"score"` task exactly like `"generate"` and
`"load"`. The worker thread:

1. Encodes `prompt` with `tokenizer.encode` (raw text, not chat-templated — lm_eval sends
   raw prompts).
2. Runs a single forward pass: `logits = model(mx.array([input_ids]))`.
3. Applies `mlx.nn.log_softmax(logits[0], axis=-1)` — note: `mx.core` has no
   `log_softmax`; the function lives in `mlx.nn`.
4. Extracts `token_logprobs[i] = log_probs[i-1, input_ids[i]]` for each position > 0
   (position 0 has no prior context → `None`).
5. Optionally computes top-k per position via `mx.argpartition(-row, kth=k-1)[:k]` then
   sorts the slice — avoids a full vocab sort.
6. Casts all `mx.array` scalars to Python `float` before returning (arrays are bound to
   the worker stream and are not JSON-serialisable).

This is a direct continuation of ADR 0004's rule: any MLX op must run on the worker
thread that called `mx.new_thread_local_stream`.

### 3. Streaming deferred for `/v1/completions`

The route returns HTTP 400 if `stream=true`. Reasons:
- lm_eval's `local-completions` adapter never sets `stream=true` for loglikelihood
  requests (the whole point is to get logprobs in one response).
- Modern LLM tooling uses `/v1/chat/completions` for interactive streaming; legacy
  completions streaming is rare.
- SSE streaming of logprobs-with-echo would require buffering the entire scored prefix
  then streaming generated tokens — non-trivial and not needed in v1.

### 4. V2 implication: `VLLMBackend.score`

vLLM's native API supports `prompt_logprobs: int` on the generate request, which returns
per-token log-probabilities for the prompt without any generation overhead. The V2
implementation should use `AsyncLLMEngine.generate(prompt, sampling_params=SamplingParams(prompt_logprobs=k, max_tokens=0))` rather than re-implementing a forward pass.
`VLLMBackend.score` currently raises `NotImplementedError` with this note.

## Consequences

- All three `/v1/completions` modes (pure generation, pure scoring, combined) are covered
  by unit tests with `FakeBackend` and by a mac-only smoke test with the real MLX backend.
- The `ScoreResult` dataclass is part of the public `backend.base` module; future backends
  must implement `score`.
- `lm_eval --model local-completions` now works end-to-end against this server.
- `mlx.nn.log_softmax` (not `mx.log_softmax`) must be used — documented here so future
  maintainers don't reintroduce the API drift.

## Cross-references

- [ADR 0003](./0003-server-architecture.md) — Backend Protocol definition
- [ADR 0004](./0004-streaming-thread-affinity.md) — `_MLXWorkerThread` pattern
- `src/server/backends/base.py` — `ScoreResult` dataclass + `Backend.score` Protocol method
- `src/server/routes/completions.py` — three-mode route implementation
- `tests/server/test_backend_score.py` — FakeBackend score unit tests
- `tests/server/test_routes_completions.py` — route tests (all three modes)
- `tests/smoke/test_mac_completions.py` — real-MLX smoke test
