# Post-v1 Plan — vLLM Backend on RTX 4080 PC (V2 scoping)

**Status:** scoping doc. Not yet a 32-task implementation plan; the V2
session resolves the open questions below first, *then* writes the
implementation plan in the style of
`docs/plans/2026-04-28-v1-mac-mlx.md`.

**Goal:** Bring up the same `local-model` FastAPI server on the user's
RTX 4080 PC running Linux, swapping `MLXBackend` for `VLLMBackend`. The
route surface, browser client, history/presets stores, and benchmark
harness are unchanged. Only the inference engine changes.

**Pre-read:** [`docs/V2_Catchup.md`](../V2_Catchup.md) (durable handoff
from v1) and ADRs 0003–0005.

---

## What the v1 plan got right that V2 should mimic

- **32 subagent-sized tasks**, ~1 PR each, organized into phases
- **Phase 0** = scaffold (`Backend` stub, `FakeBackend`, settings, schema)
- **Phase 1** = backend implementation (`VLLMBackend.generate`, `score`,
  capability detection)
- **Phase 2** = HTTP layer integration (mostly verifying existing routes
  work against the new backend; should be small)
- **Phase 3** = client (likely just a multi-endpoint config addition)
- **Phase 4** = benchmarks (run the same harness against vLLM, compare
  to v1 baselines in `bench/baselines/v1-mac-mlx/`)
- **Phase 5** = SC1–SC9 walkthrough on the PC, ship-it commits, push
- **Execution log appendix** in the plan, updated as the plan deviates
  from reality

## What v1 got wrong that V2 should learn from

- **The plan didn't anticipate fast-moving-library API drift.** Mlx_lm
  changed its sampler API (T1.9), and `mx.log_softmax` doesn't exist
  (T5.4d). vLLM has a faster-moving API surface than mlx_lm. **Use
  Context7** to verify every vLLM API call before writing it. Don't
  trust training data on vLLM.
- **The plan didn't anticipate threading constraints.** ADR 0004 was
  written *retroactively* after Llama-8B streaming broke. For V2, look
  at vLLM's threading model **before** writing the implementation plan.
  Specifically: `AsyncLLMEngine` is async-native; if you wrap it in a
  sync `Backend.generate()`, you're crossing a threading boundary.
- **SC7 was misspecified.** The v1 plan said "command-builder verified"
  was enough; reality required adding `/v1/completions` with logprobs
  to actually run lm_eval-based MMLU. V2's SC7 should require a real
  `mmlu_stem` JSON score from the start.
- **The plan committed code verbatim that hadn't been ruff-formatted.**
  Several `docs(plans):` follow-ups were needed for trivial style
  divergence. Run the V2 plan body through `ruff format` before
  finalizing.

## Open questions (resolve before writing the V2 task plan)

### Q1: Sync vs async `Backend` Protocol

vLLM exposes `AsyncLLMEngine.generate(...)` returning
`AsyncGenerator[RequestOutput]`. Our current `Backend.generate(...)`
returns sync `Iterator[Token]`. Three resolutions:

1. **Keep Protocol sync, bridge async→sync inside `VLLMBackend`** —
   recommended. Run a dedicated asyncio event loop in a worker thread
   (mirrors `MLXBackend._MLXWorkerThread` pattern). Use
   `asyncio.run_coroutine_threadsafe` to pull tokens off the
   `AsyncGenerator` and feed them into the sync `Iterator`. Existing
   route code unchanged.
2. **Add parallel async methods to `Backend`** (`async_generate`,
   `async_score`). Routes pick one at request time. More surface, but
   gets full async benefit on vLLM.
3. **Make `Backend` Protocol fully async** — change `MLXBackend` too.
   Biggest change.

**Decision needed:** option 1 unless there's a compelling reason
otherwise.

### Q2: Default model

vLLM reads HF transformers format, not MLX. Pick a model that fits in
~16 GB VRAM with reasonable speed:

- `meta-llama/Llama-3.1-8B-Instruct` — full FP16, ~16 GB, marginal
- `meta-llama/Llama-3.1-8B-Instruct` + AWQ quantization — ~5 GB
- `Qwen/Qwen2.5-7B-Instruct-AWQ` — pre-quantized, ~5 GB
- `mistralai/Ministral-8B-Instruct-2410` — ~16 GB FP16

vLLM's quantization support is good; AWQ models load fast. The user
explicitly wants the 4080's VRAM well-utilized — pick a model that uses
most of it (FP16 8B or larger AWQ-quantized).

### Q3: vLLM version pin

Pin a specific vLLM version in `pyproject.toml`'s `[vllm]` extras. vLLM
has fast minor-version cadence with occasional API breaks (their
`AsyncLLMEngine` constructor signature has changed across versions).
Verify with Context7 against the version we pin.

### Q4: Server topology — single endpoint or both?

Two patterns to consider:

- **Single endpoint per process** — server runs either MLX or vLLM, not
  both. `LOCAL_MODEL_BACKEND=vllm` env. Client points at one URL. v1's
  `_resolve_backend()` function already does this correctly.
- **Multi-endpoint client** — Mac runs MLX server on `:8080`, PC runs
  vLLM server on (say) `:8081`, client has a dropdown. Adds routing
  complexity but lets the user A/B-test both backends interactively.

**Recommendation:** start with single endpoint per process (simplest
delta from v1). Multi-endpoint client is a post-V2 polish item.

### Q5: Where do v1's known forward gaps land?

v1 left some polish gaps (logged in
`docs/plans/2026-04-28-v1-mac-mlx.md` Execution log appendix):

- `/stats` body has no auto-refresh after model swap
- `prompt_tokens` in `/v1/completions` generation mode is a word-split
  estimate, not a real token count
- `prompt: list[str]` in `/v1/completions` silently joins instead of
  returning multiple `choices` or rejecting with 422
- Combined-mode (`echo=True, max_tokens>0`) lacks a real-MLX smoke
- Markdown rendering in chat UI (model responses with `$$math$$` or code
  blocks show as raw source)

V2 can tackle some of these as part of polish phases, OR explicitly
defer to V3. Decide in the V2 plan.

## Constraints carried over from v1

These are non-negotiable; they're load-bearing in v1 and shape V2's
plan:

- **`Backend` Protocol contract** — `generate()` returns a sync
  `Iterator[Token]` that's thread-safe-to-consume; backends with thread
  affinity must encapsulate it. ADR 0004.
- **Route → `app.state.app_state` → `registry` → `backend`** — don't
  introduce a fourth indirection layer.
- **One model loaded at a time** — hot-swap via `/admin/models/load`,
  parallel inference deferred. vLLM technically supports
  multi-model-per-engine; we don't expose that in v1's surface and
  shouldn't in V2 either.
- **No JS framework on the client** — HTMX only.
- **No ORM** — sqlite3 stdlib only.
- **Mermaid diagrams only** — no images.

## Tasks the V2 plan should explicitly include

Mechanical/Haiku candidates (mirror v1's task shape):

- T0.x — vLLM dependency setup, capability detection, `[vllm]` extras
- T1.x — `VLLMBackend.generate` (substantive, async bridge — Sonnet)
- T1.x — `VLLMBackend.score` (mechanical, ~30 LoC via `prompt_logprobs` —
  Haiku, but verify vLLM API via Context7 first)
- T1.x — capability detection: `check_vllm()` (mechanical — Haiku)
- T2.x — verify all existing routes work against `VLLMBackend` (mostly
  test-running; Haiku)
- T3.x — multi-endpoint client config (optional, post-V2)
- T4.x — re-run benchmarks, compare to `bench/baselines/v1-mac-mlx/`
- T5.x — SC walkthrough, ship commits, push, V2_Catchup.md → V3 (or just
  delete if there's no V3 in the offing)

Substantive/Sonnet candidates:

- The async-bridge inside `VLLMBackend.generate` is the hardest piece;
  start there.
- `VLLMBackend.score` if vLLM's `prompt_logprobs` API has changed.
- Cross-platform smoke setup (some `mac_only` tests need a `linux_only`
  parallel; or just gate by capability detection).

## Definition of "V2 done"

- `VLLMBackend` passes all existing route tests (with `FakeBackend`-style
  shape compatibility) on Linux/CUDA
- `bench/throughput.py` produces a JSON for the V2 default model under
  `bench/baselines/v2-pc-vllm/`
- `bench/vibe_check.py` produces a Markdown report
- `bench/eval_harness.py` runs `mmlu_stem` end-to-end (vLLM has native
  `prompt_logprobs`, so SC7 should be Just Work, not a special closeout
  task)
- Live SC1–SC5 walkthrough on the PC against the V2 default model
- All numbers comparable to or faster than the v1 Mac MLX baseline
  (4080 should beat M5 Max on Llama-3.1-8B; if it doesn't, investigate)

## Don't expand scope here

V2 is *just* "same server, vLLM backend, RTX 4080 PC." It is **not**:

- Multi-user / authentication / TLS
- Vision / multimodal / tool calling / fine-tuning
- Distributed inference across both Mac and PC
- A V3 plan

If any of those land, they're V3+. Capture them as TODOs in
`V2_Catchup.md` only after V2 ships.
