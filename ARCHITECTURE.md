# ARCHITECTURE — local-model

> System design. The *how*. For the *what*, see [`SPEC.md`](./SPEC.md).
>
> Last updated: 2026-04-28.

## 1. System overview (C4 Container)

```mermaid
flowchart TB
    User((User))

    subgraph Mac["M5 Max MacBook Pro · Phase 1"]
        MacServer["FastAPI server :8080"]
        MacBackend["MLXBackend<br/>(mlx_lm)"]
        MacStore[("SQLite<br/>history.db")]
        MacServer --> MacBackend
        MacServer --> MacStore
    end

    subgraph PC["Windows / Linux PC · Phase 2"]
        PCServer["FastAPI server :8080"]
        PCBackend["VLLMBackend<br/>(vllm)"]
        PCStore[("SQLite<br/>history.db")]
        PCServer --> PCBackend
        PCServer --> PCStore
    end

    Client["Browser chat client<br/>FastAPI + HTMX :8000"]

    User --> Client
    Client -->|"/v1/chat/completions (SSE)"| MacServer
    Client -.->|Phase 2| PCServer

    style PC stroke-dasharray: 5 5
    style PCServer stroke-dasharray: 5 5
    style PCBackend stroke-dasharray: 5 5
    style PCStore stroke-dasharray: 5 5
```

**Shape.** Each host runs its own server process — same codebase, the `Backend` Protocol implementation chosen at startup by config. The browser client is a *separate* small FastAPI process that knows about one or more inference endpoints. HTTP between client and server is stateless except for explicit `/history/*` and `/presets/*` endpoints; persistence lives on the server side.

## 2. Server internals (C4 Component)

```mermaid
flowchart LR
    HTTP["FastAPI app"] --> Router["Chat-completion handler"]
    Router --> Stream["SSE streaming generator"]
    Router --> History["History DAO"]
    Router --> Presets["Preset DAO"]
    Stream --> Backend["Backend Protocol"]
    Router --> Registry["Model registry"]
    Registry --> Backend
    Backend --> MLX["MLXBackend"]
    Backend -.-> VLLM["VLLMBackend (phase 2)"]
    History --> DB[("SQLite")]
    Presets --> DB
    Stream --> Timing["Timing hooks<br/>(TTFT / TPS)"]
    HTTP --> Admin["/admin/* routes"]
    Admin --> Registry
    Admin --> Timing
```

| Component | File (proposed) | Responsibility |
|---|---|---|
| FastAPI app | `src/server/app.py` | Process entry, route table, lifespan hooks (load default model on startup, free on shutdown) |
| Chat-completion handler | `src/server/routes/chat.py` | Validate request (Pydantic), parse sampling params, dispatch to backend, return streaming or non-streaming response |
| SSE streaming generator | `src/server/streaming.py` | Wrap backend token iterator into Server-Sent Events; emit per-token chunks + a trailer with TTFT/TPS |
| Backend Protocol | `src/server/backends/base.py` | The interface; defines `load`, `unload`, `generate`, `model_info`, `loaded_models`. Plus dataclasses `Token`, `ModelInfo` |
| `MLXBackend` | `src/server/backends/mlx_backend.py` | Phase 1 impl, uses `mlx_lm.load` and `mlx_lm.stream_generate` |
| `VLLMBackend` | `src/server/backends/vllm_backend.py` | Phase 2 impl, wraps `vllm.AsyncLLMEngine` |
| Model registry | `src/server/registry.py` | Tracks the currently loaded model; enforces "one model at a time" in v1 |
| History DAO | `src/server/store/history.py` | Plain `sqlite3` wrapper for `Conversation` + `Message` tables |
| Preset DAO | `src/server/store/presets.py` | Plain `sqlite3` wrapper for `Preset` table |
| DB connection | `src/server/store/db.py` | Single connection, schema migrations on startup |
| Timing hooks | `src/server/timing.py` | Instruments TTFT and TPS around each `generate()` call; exposes via `/admin/stats` and SSE trailers |
| Config | `src/server/config.py` | Pydantic Settings — env vars + defaults |

## 3. Backend abstraction

```mermaid
classDiagram
    class Backend {
        <<Protocol>>
        +load(model_id: str) ModelInfo
        +unload(model_id: str) None
        +generate(messages, params) Iterator~Token~
        +model_info(model_id) ModelInfo
        +loaded_models() list~ModelInfo~
    }
    class MLXBackend {
        -models: dict
        +load(model_id) ModelInfo
        +generate(messages, params) Iterator~Token~
    }
    class VLLMBackend {
        -engine: AsyncLLMEngine
        +load(model_id) ModelInfo
        +generate(messages, params) Iterator~Token~
    }
    class Token {
        +text: str
        +token_id: int
        +logprob: float
        +elapsed_ms: float
    }
    class ModelInfo {
        +id: str
        +display_name: str
        +context_length: int
        +memory_mb: int
        +backend_kind: str
    }
    Backend <|.. MLXBackend
    Backend <|.. VLLMBackend
    Backend ..> Token
    Backend ..> ModelInfo
```

`Backend` is a `typing.Protocol`, not an `abc.ABC`. Rationale, alternatives, and consequences are captured in [ADR 0003](./docs/decisions/0003-server-architecture.md). In short: lighter, doesn't force inheritance, plays well with structural typing, and lets us write a fake `Backend` for tests in ~20 lines.

## 4. Model lifecycle

```mermaid
stateDiagram-v2
    [*] --> Unloaded
    Unloaded --> Loading: load(model_id)
    Loading --> Ready: weights mapped
    Loading --> Failed: OOM / not found
    Ready --> Generating: request arrives
    Generating --> Ready: stream complete
    Ready --> Unloading: swap or shutdown
    Unloading --> Unloaded
    Failed --> [*]
```

v1 holds **one model at a time**. A swap is `unload(current) → load(new)`, serialized via the model registry's lock. Parallel multi-model serving is explicitly deferred (see [SPEC §6](./SPEC.md#6-non-goals-v1)).

## 5. Data flow — canonical chat request

```mermaid
sequenceDiagram
    participant U as User
    participant C as Browser client
    participant S as Server
    participant B as Backend
    participant DB as SQLite

    U->>C: types prompt, sends
    C->>S: POST /history/messages (user)
    S->>DB: insert user msg
    C->>S: POST /v1/chat/completions {messages, model, stream:true}
    S->>B: generate(messages, params)
    B->>B: tokenize, init KV cache
    Note over B: t0 = now (TTFT start)
    loop tokens
        B-->>S: yield token
        S-->>C: SSE chunk {content}
        C-->>U: paint token
    end
    B-->>S: stream end + final stats
    S->>DB: insert assistant msg + TTFT + TPS
    S-->>C: SSE chunk {done:true, ttft_ms, tps}
    C-->>U: enable input, show TPS
```

## 6. Data flow — model swap

```mermaid
sequenceDiagram
    participant U as User
    participant C as Browser client
    participant S as Server
    participant R as Registry
    participant B as Backend

    U->>C: picks new model from dropdown
    C->>S: POST /admin/models/load {model_id}
    S->>R: acquire lock
    alt different model already loaded
        R->>B: unload(current)
        B-->>R: ok
    end
    R->>B: load(model_id)
    B-->>R: ModelInfo
    R-->>S: ModelInfo
    S-->>C: 200 {ModelInfo}
    C-->>U: enable input with new model
```

## 7. Storage model

```mermaid
erDiagram
    Conversation ||--o{ Message : contains
    Conversation }o--|| Preset : "uses (optional)"
    Conversation {
        uuid id PK
        text title
        text model_id
        uuid preset_id FK
        timestamp created_at
        timestamp updated_at
    }
    Message {
        uuid id PK
        uuid conversation_id FK
        text role
        text content
        int prompt_tokens
        int completion_tokens
        float tps
        float ttft_ms
        timestamp created_at
    }
    Preset {
        uuid id PK
        text name
        text system_prompt
        json default_params
        timestamp created_at
    }
```

- Single SQLite file at `data/history.db` (gitignored)
- Stdlib `sqlite3` only — no ORM (avoids cognitive overhead, keeps focus on inference)
- Schema migrations on server startup (idempotent `CREATE TABLE IF NOT EXISTS`)
- Foreign keys enforced via `PRAGMA foreign_keys = ON`
- UUIDs stored as `TEXT` (sqlite has no native UUID); generated in Python with `uuid4()`

## 8. API surface

See [`SPEC §9.1`](./SPEC.md#91-server-openai-compatible--project-specific) for the full route table. Implementation notes:

- **OpenAI-compatible routes** match the [OpenAI Chat Completions spec](https://platform.openai.com/docs/api-reference/chat) closely enough that any OpenAI client (Python `openai`, JS `openai`, `curl` examples) works against us by setting `base_url=http://localhost:8080/v1`
- **Project-specific routes** under `/admin`, `/history`, `/presets` use plain JSON, not the OpenAI shape
- All routes return Pydantic-validated responses; errors use FastAPI's standard `HTTPException` with structured detail

## 9. Streaming protocol

The server uses **Server-Sent Events** (SSE) over chunked HTTP for `POST /v1/chat/completions` when `stream=true`. Event shape matches OpenAI's:

```
data: {"id":"...", "choices":[{"delta":{"content":"Hello"}, "index":0}]}

data: {"id":"...", "choices":[{"delta":{"content":" world"}, "index":0}]}

data: {"id":"...", "choices":[{"delta":{}, "finish_reason":"stop", "index":0}], "x_local_model_stats":{"ttft_ms":42.0, "tps":58.7}}

data: [DONE]
```

The `x_local_model_stats` trailer is a **non-standard extension** — OpenAI clients ignore unknown fields, so this is safe. Our own client reads it to update the live TPS / TTFT display.

## 10. Capability detection (startup)

```mermaid
flowchart TD
    Start[Server starts] --> Check{backend_kind in config}
    Check -->|mlx| MLX[Verify mlx import + arm64 + Darwin]
    Check -->|vllm| VLLM[Verify vllm import + CUDA device]
    MLX -->|ok| LoadDefault[Load default model]
    MLX -->|fail| ExitMLX[Exit with clear error]
    VLLM -->|ok| LoadDefault
    VLLM -->|fail| ExitVLLM[Exit with clear error]
    LoadDefault --> Ready[Listen on :8080]
```

No fallback. The error message names the missing requirement (e.g. *"MLX backend unavailable: requires Apple Silicon (got x86_64) and `mlx_lm` (not importable)"*).

## 11. Configuration

Pydantic `Settings` reads from env + `.env`:

| Setting | Default | Notes |
|---|---|---|
| `LOCAL_MODEL_BACKEND` | `mlx` | `mlx` \| `vllm` |
| `LOCAL_MODEL_DEFAULT_MODEL` | `mlx-community/Llama-3.1-8B-Instruct-4bit` | Loaded at startup; can swap later |
| `LOCAL_MODEL_HOST` | `127.0.0.1` | Bind address |
| `LOCAL_MODEL_PORT` | `8080` | Server port |
| `LOCAL_MODEL_DB_PATH` | `data/history.db` | SQLite location |
| `LOCAL_MODEL_LOG_LEVEL` | `INFO` | Standard Python logging level |
| `LOCAL_MODEL_MODELS_DIR` | `models/` | Optional override of HF cache location |

Client has its own settings for the endpoint list:

| Setting | Default | Notes |
|---|---|---|
| `LOCAL_MODEL_CLIENT_ENDPOINTS` | `[{"name":"local","url":"http://127.0.0.1:8080"}]` | JSON list; user adds the PC in Phase 2 |
| `LOCAL_MODEL_CLIENT_PORT` | `8000` | Client UI port |

## 12. Repo layout

```
local-model/
├── src/
│   ├── server/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── streaming.py
│   │   ├── registry.py
│   │   ├── timing.py
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── models.py
│   │   │   ├── admin.py
│   │   │   ├── history.py
│   │   │   └── presets.py
│   │   ├── backends/
│   │   │   ├── base.py            # Protocol + Token + ModelInfo
│   │   │   ├── mlx_backend.py     # Phase 1
│   │   │   └── vllm_backend.py    # Phase 2 stub
│   │   └── store/
│   │       ├── db.py
│   │       ├── history.py
│   │       └── presets.py
│   └── client/
│       ├── app.py                 # FastAPI + HTMX UI
│       ├── templates/             # Jinja2
│       └── static/
├── bench/
│   ├── throughput.py
│   ├── vibe_check.py
│   ├── eval_harness.py
│   ├── prompts/
│   │   └── vibe_check.json
│   └── results/                   # gitignored
├── tests/
│   ├── server/
│   ├── client/
│   └── bench/
├── docs/
│   ├── decisions/                 # ADRs
│   └── diagrams.md
├── models/                        # gitignored — model weights cache
├── data/                          # gitignored — SQLite db
├── SPEC.md
├── ARCHITECTURE.md
├── README.md
├── CLAUDE.md
└── pyproject.toml
```

## 13. Testing strategy

| Layer | Tool | What's tested |
|---|---|---|
| **Unit** | `pytest` | DAOs (against an in-memory SQLite), config parsing, streaming wrapper, timing hooks. Backends tested via a fake `Backend` impl that yields canned tokens — no real model loaded |
| **Integration** | `pytest` + `httpx.AsyncClient` | The FastAPI app end-to-end against the fake backend: route validation, SSE shape, history persistence, admin endpoints |
| **Smoke** | `pytest -m mac_only` | Phase 1 only: spin up the real `MLXBackend` with a tiny model (e.g. `mlx-community/SmolLM-135M-Instruct-4bit`), verify a single chat completion. Marked so it's skipped on machines without MLX |
| **Benchmarks** | `bench/*.py` (not pytest) | Performance + quality. Outputs reports under `bench/results/`. Not run as part of the test suite |

## 14. Cross-cutting concerns

### Logging

Standard library `logging`; configured in `app.py`. JSON formatter optional via env. Per-request correlation ID injected as a context var so async tasks log with the same ID.

### Error handling

- Client errors (bad request, model not loaded, etc.) → `HTTPException` with structured `detail`
- Backend errors during streaming → emit a final SSE event with `finish_reason: "error"` and a `error` field; the client surfaces it inline
- Hard failures during startup (capability check) → log + `sys.exit(1)`. Do not silently fall back

### Concurrency

FastAPI is async-native. Backend `generate()` is a sync iterator; we run it in a worker thread (`anyio.to_thread.run_sync`) so the event loop stays responsive for other clients. With one user there is no realistic contention.

## 15. Deployment topology

### Phase 1 (Mac, single user)

Two terminal windows (or `tmux` panes). Both bound to `127.0.0.1`.

```
Terminal A:  uv run python -m server.app          # :8080, MLX
Terminal B:  uv run python -m client.app          # :8000, browser UI
```

User opens `http://127.0.0.1:8000` in a browser.

### Phase 2 (PC added)

PC runs the same server, with `LOCAL_MODEL_BACKEND=vllm`. Client config is updated to list both endpoints; the user picks per session. Both servers continue to bind `127.0.0.1` — the client app is the only thing that crosses machines (the user opens its UI from whichever machine they're sitting at).
