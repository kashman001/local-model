# local-model

Local LLM deployment on Apple Silicon using [MLX](https://github.com/ml-explore/mlx), paired with a sample chat application.

## Status

Early development — spec is being drafted. See [`SPEC.md`](./SPEC.md) once available.

## Goals

- Run open-source LLMs locally on macOS, optimized via MLX.
- Expose them through an OpenAI-compatible HTTP API.
- Provide a sample chat client that demonstrates end-to-end usage.

## Architecture (planned)

Two decoupled components:

1. **Inference server** — `mlx-lm.server` (or wrapper) exposing the OpenAI Chat Completions API.
2. **Chat client** — talks to the server over HTTP. UI shape TBD.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for details once written.

## Setup

_Will be populated once the inference server and chat client are scaffolded._

## Documentation

- [`SPEC.md`](./SPEC.md) — functional spec.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system design.
- [`CLAUDE.md`](./CLAUDE.md) — context for Claude Code sessions working on this repo.
- [`docs/decisions/`](./docs/decisions/) — lightweight ADRs for non-obvious choices.

## License

[MIT](./LICENSE).
