# V2 Catchup

> **Read this first if you're picking up `local-model` for V2 work** —
> typically a fresh Claude Code session on the user's RTX 4080 PC with no
> prior project context. This doc is the durable handoff that replaces
> the gitignored `RESUME.md` of the v1 session.

V1 (Mac MLX) is shipped. V2 brings up the **same FastAPI server** on a
different host with `VLLMBackend` instead of `MLXBackend`. The point of
this doc is to compress everything the v1 sessions discovered into a
form a fresh agent can act on without re-discovering it.

## V1 ship state

| Field | Value |
|---|---|
| Repo | <https://github.com/kashman001/local-model> |
| Branch | `main` (v1 ships here); `feature/v1-mac-mlx` is the working branch |
| Last v1 plan-task SHA on main | `1f90bf0` (T5.1–T5.4 verified) |
| Post-ship polish + SC7 closure | `feature/v1-mac-mlx` continues past `1f90bf0`; latest is the `/v1/completions` + scoring commit, follow-on `T5.4d` appendix |
| Test count | 88 passing on Mac (incl. 2 mac_only smoke) |
| Plan | [`docs/plans/2026-04-28-v1-mac-mlx.md`](./plans/2026-04-28-v1-mac-mlx.md) — 32 tasks + Execution log appendix that lists every plan-vs-reality adaptation |

## Hardware

| | v1 | V2 |
|---|---|---|
| Host | M5 Max MacBook Pro | RTX 4080 PC |
| Memory | 128 GB unified | system RAM + 16 GB VRAM |
| Backend | `MLXBackend` (uses `mlx_lm` directly) | `VLLMBackend` (uses `vllm.AsyncLLMEngine`) |
| OS | macOS 25.x (`Darwin arm64`) | Linux (assumed) |
| Default model | `mlx-community/Llama-3.1-8B-Instruct-4bit` | TBD — vLLM reads HF format, not MLX |

V1 deliberately runs *only* on Apple Silicon (`tests/smoke/test_mac_smoke.py`,
`tests/smoke/test_mac_streaming.py`, `tests/smoke/test_mac_completions.py`
are all `pytest.mark.mac_only`-skipped on non-arm64). Don't try to make
v1 cross-platform — V2 is the cross-platform answer.

## Architecture pointers (read in this order)

1. [`SPEC.md`](../SPEC.md) — what we're building, success criteria
2. [`ARCHITECTURE.md`](../ARCHITECTURE.md) — how it's built, components, diagrams
3. [`docs/decisions/0003-server-architecture.md`](./decisions/0003-server-architecture.md) — load-bearing: custom FastAPI server with `Backend` Protocol; rejects all wrapper paths (no LM Studio, Ollama, `mlx_lm.server`)
4. [`docs/decisions/0004-streaming-thread-affinity.md`](./decisions/0004-streaming-thread-affinity.md) — load-bearing for any streaming backend with thread-local GPU state
5. [`docs/decisions/0005-completions-and-scoring.md`](./decisions/0005-completions-and-scoring.md) — `Backend.score()` Protocol extension for OpenAI `/v1/completions` parity
6. [`CLAUDE.md`](../CLAUDE.md) — workflow, model routing (subagent dispatches table), tooling conventions (incl. **"Backend runtime constraints"** subsection that flags vLLM async-native concerns)

## What V2 inherits unchanged

These are the parts of v1 that V2 reuses verbatim:

- FastAPI app factory + lifespan + `AppState` (`src/server/app.py`)
- Route → `request.app.state.app_state` → `registry` → `backend` pattern
- `Backend` Protocol (`src/server/backends/base.py`) — sync `Iterator[Token]` for streaming, sync `score(prompt, top_logprobs) -> ScoreResult` for `/v1/completions`
- All 15+ HTTP endpoints (`/health`, `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/admin/models/{load,unload,stats}`, `/history/*`, `/presets/*`)
- Browser client (`src/client/`) — FastAPI + Jinja2 + HTMX, no JS framework
- SQLite history + presets stores (`src/server/store/`)
- Benchmark harness (`bench/throughput.py`, `bench/vibe_check.py`, `bench/eval_harness.py`)
- Test infrastructure (`pytest`, `respx`, `mac_only` marker)
- ADRs 0001–0005

## What V2 changes

These are the parts that get a vLLM-shaped rewrite:

### `VLLMBackend`

Currently a stub at `src/server/backends/vllm_backend.py`. v1 deferred its
implementation to V2.

vLLM exposes `AsyncLLMEngine.generate(...)` which returns an
`AsyncGenerator[RequestOutput]`. Our `Backend` Protocol is currently sync
(`def generate(...) -> Iterator[Token]`). **Resolve this in the V2 plan,
not at impl time.** Three options:

1. **Wrap async→sync in `VLLMBackend`** — use `asyncio.run_coroutine_threadsafe`
   against a dedicated event loop running in a worker thread. Same shape
   as `MLXBackend`'s `_MLXWorkerThread`, just with an asyncio loop
   inside. Keeps the `Backend` Protocol uniform.
2. **Extend `Backend` Protocol to support both sync and async** — add a
   parallel `async_generate(...) -> AsyncIterator[Token]`. Routes pick
   one based on backend introspection.
3. **Make `Backend` Protocol async-native** — change `MLXBackend` too,
   add a sync→async adapter. Bigger change.

**Recommendation:** option 1 is the smallest delta. It keeps the route
code exactly as it is today and pushes the async→sync bridge into a
single backend implementation.

### Capability detection on Linux/CUDA

`src/server/capability.py` currently has `check_mlx()` and `check_vllm()`.
The vLLM path needs:

- `import vllm` succeeds
- `torch.cuda.is_available()` returns True
- `torch.cuda.device_count() >= 1`

The `[vllm]` extras group in `pyproject.toml` is already gated on
`platform_system == 'Linux'`.

### Default model

vLLM reads HuggingFace transformers format, not MLX. Pick a reasonable
default for the 4080 (16 GB VRAM):

- `meta-llama/Llama-3.1-8B-Instruct` — full FP16, ~16 GB, tight fit
- `meta-llama/Llama-3.1-8B-Instruct` with AWQ/GPTQ quantization — ~5 GB
- `Qwen/Qwen2.5-7B-Instruct-AWQ` — AWQ-quantized, ~5 GB

Decide in the V2 plan. The user wants 16 GB VRAM well-utilized, not a
tiny demo model.

### `score()` for vLLM

vLLM has native `prompt_logprobs` support. `VLLMBackend.score()` is a
~30-line adapter — request `prompt_logprobs=top_k` and read the response.
**Much simpler than MLX scoring** (which needed manual forward-pass
extraction).

### Multi-endpoint client config (post-MVP V2)

The client's `ClientSettings.endpoints` is already a list, but the UI
only talks to the first entry. V2 lets the user route the same chat to
either the Mac or the PC. Optional second-pass work after the basic
vLLM bring-up.

## Things that v1 caught and you should NOT re-discover

These are durable lessons, codified in ADRs + CLAUDE.md. Don't repeat
them on V2:

1. **MLX has thread-local GPU streams.** ADR 0004. The fix pattern
   (single persistent worker thread per backend instance) is in
   `MLXBackend._MLXWorkerThread`. **CUDA contexts have a similar
   per-thread quirk.** If you see `RuntimeError: ... no Stream(gpu, N) in
   current thread`-shaped errors against vLLM (or anything with PyTorch
   underneath), that's the same class. PyTorch tooling (`torch.cuda.set_device`,
   `torch.cuda.synchronize`, `Stream`) handles it differently than MLX,
   but the constraint exists.

2. **Starlette dispatches sync streaming iterators across worker
   threads.** If `VLLMBackend.generate(...)` returns a sync iterator
   that touches GPU state, it must be safe to call from arbitrary
   threads. Either pin to a worker (MLX pattern) or use vLLM's
   async-native API (recommended).

3. **`mx.log_softmax` does not exist.** Use `mx.nn.log_softmax`. Same
   lesson generalizes: any LLM inference engine (MLX, vLLM, transformers)
   has a fast-moving API surface — verify with Context7
   (`mcp__plugin_context7_context7__query-docs`) before quoting training
   data.

4. **EventSource auto-reconnects.** SSE streams from `/v1/chat/completions`
   need an explicit close mechanism on the client. v1 uses an
   `event: done\ndata: end\n\n` sentinel + htmx-ext-sse's `sse-close="done"`
   attribute. If you change the streaming response shape, keep the
   sentinel.

5. **`/stats` body is render-on-load.** No HTMX poll on the body; the
   nav pill polls every 5 s. After a model swap, the body shows stale
   info. Cosmetic for v1, worth fixing in V2 polish.

6. **Per-request `MLXBackend()` is wrong.** The persistent worker thread
   is per-instance. Tests must reuse instances or accept startup cost.

## Future work — speeding up Mac MLX evaluation (post-V2 / V3 horizon)

V1's `mmlu_stem` baseline takes ~14 hours on M5 Max. V2 (vLLM on RTX
4080) will be 5-10× faster purely from vLLM's continuous batching
+ PagedAttention prefix sharing — **not** because the GPU is dramatically
better, but because vLLM batches dozens of concurrent requests at every
inference step and automatically detects shared prompt prefixes.

If a future project ("V3-ish") wants to make Mac MLX evals competitive,
here are the levers ranked by impact-vs-effort. **Don't tackle these
mid-V2** — they're a separate engagement.

### 1. Prompt-cache reuse (5-10× for MMLU-style evals)

MMLU's 5-shot eval re-uses the **same 5-example context** across
hundreds of questions per subject. Currently `MLXBackend.score(...)`
re-runs the full ~2000-token forward pass on every question; the
5-shot prefix is ~80% of the input.

**Fix:** detect prefix reuse server-side, cache the model's KV state at
the prefix boundary, and only run the per-question suffix through the
model on subsequent calls. mlx_lm has the primitives (`make_kv_caches`,
`cache.RotatingKVCache`).

This is exactly what vLLM does automatically via PagedAttention —
that's the dominant reason V2 will be faster than V1, not raw GPU
horsepower.

**Cost:** ~150 LoC in `MLXBackend.score` plus careful state management
across `_MLXWorkerThread`. The lm_eval client doesn't tell us "same
prefix again"; we have to detect it via prompt-prefix matching.

### 2. Skip full `log_softmax` materialization (1.5-2× possibly)

Currently `MLXBackend.score` computes `log_softmax(logits)` over the
full `[seq_len × vocab]` tensor (~512 MB at fp16 for a 2000-token
Llama-8B prompt). We only actually need:

- `log_softmax[i, input_ids[i+1]]` for each position (per-token
  logprob)
- Top-k entries when `logprobs > 0`

For per-token logprobs alone you can compute `logits[i, target] -
logsumexp(logits[i])` per position without materializing the full
softmax. Saves memory bandwidth + ~20-40% time.

For top-k, `mx.argpartition` per position rather than full sort over
vocab.

**Cost:** ~50 LoC in `MLXBackend.score`'s scoring branch.

### 3. Server-side batching for MLX (4-8× at high concurrency)

Extend `Backend.generate()` and `Backend.score()` to accept batches.
Add a request-coalescing scheduler in front of `_MLXWorkerThread`. Use
`mlx_lm.batch_generate` for fixed-size batches.

**Note:** MLX batching is *fixed-batch* (all members run to completion
together), not vLLM-style *continuous batching* (dynamic insert/evict
mid-batch). So even with this, MLX batching is more limited than what
V2 gets for free.

**Cost:** significant — Protocol extension, scheduler, batch-aware
score path. Probably ~500 LoC + tests. **Worth it only if you're
running heavy concurrent loads on Mac, which v1's single-user pattern
does not require.**

### 4. Profile first

Before optimizing, instrument `MLXBackend.score` to time:

- Tokenizer (`tokenizer.encode`) — likely <1%
- Model forward pass — likely 70-90%
- `log_softmax` materialization — possibly 5-20%
- Top-k extraction Python loop — likely <5%
- HTTP overhead — likely <5%

Knowing the breakdown tells you whether (1) and (2) are even worth
doing for *your* model+context-length combination. The forward pass
may dominate so heavily that everything else is noise.

### Pragmatic for routine Mac dev

For day-to-day development you don't need a 14-hour eval. Use any of:

- `--limit 100` per task (~30-40 min, real per-task accuracy with
  ±4-5% stderr)
- `--tasks mmlu_high_school_mathematics` (single subject, ~10 min)
- Llama-3.2-1B-Instruct-4bit instead of 8B (5-8× faster, lower
  fidelity but exercises the same code paths)

Reserve the full 14-hour Llama-8B `mmlu_stem` run for when you
specifically need the published baseline.

## Cross-platform baselines (for cross-checking V2)

`bench/baselines/v1-mac-mlx/` holds the v1 ship measurements. After your
first vLLM bring-up:

| File | What it captures | Compare against |
|---|---|---|
| `throughput-llama-3.1-8b-4bit.json` | TTFT + TPS on M5 Max with Llama-3.1-8B-4bit (~103 tok/s mean) | First vLLM throughput run on the 4080 |
| `vibe-llama-3.1-8b-4bit.md` | 30-prompt qualitative responses | Compare response quality across backends |
| `mmlu-stem-llama-3.1-8b-4bit.json` | MMLU-STEM 5-shot score (lm_eval, ~30-45 min on Mac) | Same eval on the 4080 |
| `throughput-smollm-135m-4bit.json` | Tiny-model baseline | Sanity reference |

## Standing authorizations

`CLAUDE.md` "Standing authorizations" applies on V2 too — same green/red
list. Notable post-v1 additions you may want to write into CLAUDE.md
when V2 work begins:

- The `[bench]` extras group requires `lm-eval[api]>=0.4.5`, not just
  `lm-eval`. Pulling `lm-eval[api]` brings in `tenacity`, `tiktoken`,
  and the OpenAI-compatible API model adapters needed for SC7-style
  evals.
- `setsid` is not on macOS by default — use `nohup ... & disown` for
  detached background processes. (Linux has both.)

## Developer environment notes (post-v1 additions)

Operational gotchas the v1 session hit while bootstrapping the dev env.
These don't affect the project itself — they affect how a fresh Claude
Code session on the V2 PC will set up its tooling.

### GitHub MCP — use the standalone server, not the official plugin

The official `github@claude-plugins-official` plugin from the Claude
Code marketplace points at `https://api.githubcopilot.com/mcp/` and
tries to authenticate via OAuth Dynamic Client Registration (RFC 7591).
GitHub's Copilot MCP server **doesn't support DCR**, so the auth flow
fails with `SDK auth failed: Incompatible auth server: does not support
dynamic client registration` on Claude Code 2.1.116. PAT-based auth via
the plugin's `${GITHUB_PERSONAL_ACCESS_TOKEN}` header is bypassed
because the SDK tries OAuth first.

Working pattern (verified 2026-05-02 on macOS):

1. `brew install github-mcp-server` — installs GitHub's open-source
   stdio MCP server (separate from the Copilot endpoint).
2. Generate a fine-grained PAT at <https://github.com/settings/personal-access-tokens/new>
   with read/write access to the repos you'll touch.
3. Add the token to `~/.claude/settings.json` under the top-level
   `env` block (NOT under `mcpServers` — that key isn't in the
   settings.json schema and validation will reject it):

   ```json
   "env": {
     "GITHUB_PERSONAL_ACCESS_TOKEN": "github_pat_..."
   }
   ```

4. Disable the broken plugin: flip
   `"github@claude-plugins-official": false` in `enabledPlugins`.
5. Register the standalone server at user scope:

   ```bash
   claude mcp add -s user github-local /opt/homebrew/bin/github-mcp-server stdio
   ```

   The token from `settings.json` `env` propagates to the spawned MCP
   server automatically; no `-e` flag needed.

6. Verify via `claude mcp list` (should show `github-local: ✓
   Connected`). The server's tools become visible only in *new* Claude
   Code sessions started after the `mcp add` call — restart the CLI
   for them to load.

If the V2 PC is on Linux: replace `/opt/homebrew/bin/github-mcp-server`
with the appropriate Linux install path (apt, binary download from
GitHub releases, or `brew` on Linuxbrew).

## V2 kickoff order

1. Read [`docs/plans/post-v1-vllm.md`](./plans/post-v1-vllm.md) — V2 scoping doc with open questions
2. Resolve the sync-vs-async `Backend` Protocol question in that plan
3. Write the V2 implementation plan (subagent-sized tasks, mirror of `2026-04-28-v1-mac-mlx.md`)
4. Set up the worktree under `.worktrees/v2-pc-vllm/` (project-local, gitignored)
5. Bring up `VLLMBackend.generate()` first, then `score()`, then capability detection
6. Run the same SC1–SC9 walkthrough as v1 — they should mostly Just Work because the route surface is unchanged

## Don't re-litigate

These are settled (carry-over from v1's `RESUME.md`):

- Custom FastAPI server, not `mlx_lm.server` / LM Studio / Ollama / vLLM's `serve` command (ADR 0003)
- `Backend` Protocol from day 1 (ADR 0003)
- Browser client = FastAPI + Jinja2 + HTMX. **No JS framework.**
- SQLite stdlib for history + presets. **No ORM.**
- Server `:8080`, client `:8000`, both `127.0.0.1`
- `lm-evaluation-harness` for quality evals; `bench/` is first-class
- Vision / multimodal / tool calling / fine-tuning all **deferred** (post-V2)
- Type hints `X | None` (not `Optional[X]`)
- SQL `ORDER BY` always with `rowid` tiebreaker
- Push to `main` is green-list when fast-forward + clean tree
- `waiting-on-you:` marker required for confirm-first asks
- One model loaded at a time (hot-swap via `/admin/models/load`); parallel inference deferred
- Inline code in tool calls: temp files + `git commit -F` (CLAUDE.md "Tooling conventions")
