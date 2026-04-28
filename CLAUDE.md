# CLAUDE.md

Context for Claude Code sessions working on **local-model**. Read this fully before starting any task.

## Project

Local LLM deployment on Apple Silicon using MLX, with a sample chat application. The project targets a single user (the repo owner) running everything on a MacBook Pro.

Architecture (planned, see `ARCHITECTURE.md` once written):

- **Inference server** — MLX-backed, OpenAI-compatible HTTP API (default plan: `mlx-lm.server` or a thin wrapper).
- **Chat client** — talks to the server. UI shape TBD until `SPEC.md` is finalized.

## Workflow

This project is worked on across **multiple Claude Code sessions**. The durable docs below are the inter-session memory — keep them current.

| Doc | Purpose | Update when |
|---|---|---|
| `README.md` | Public-facing overview & setup | User-facing setup changes |
| `SPEC.md` | Functional spec — what we're building | Scope changes |
| `ARCHITECTURE.md` | System design, components, data flow | Architecture changes |
| `docs/decisions/NNNN-*.md` | Lightweight ADRs for non-obvious choices | Any tradeoff call (model choice, framework, UI stack) |
| `CLAUDE.md` | This file — context for sessions | Conventions, model routing, or workflow change |

**Hard rule:** at the end of every non-trivial task, ask "did I make a decision a future session would need to know about? Did architecture or spec change?" If yes, update the relevant doc in the same commit as the code change.

## Model routing

Use the **cheapest Claude model that can do the job correctly**. Default to Sonnet. Switch with `/model` in Claude Code.

| Model | Use for |
|---|---|
| **Haiku 4.5** | File lookups, formatting, simple renames, status checks, `gh` queries, commit messages, simple greps, trivial edits |
| **Sonnet 4.6** *(default)* | Feature implementation, refactors, writing tests, routine debugging, code review |
| **Opus 4.7** | Architecture/spec work, design tradeoffs, gnarly multi-file debugging, anything needing careful reasoning across many constraints |

Don't grind routine work on Opus, and don't attempt architectural reasoning on Haiku.

## Tooling conventions

- **Python**: `uv` for env + dependency management, `ruff` for format + lint, `pytest` for tests. See [`docs/decisions/0001-python-tooling.md`](./docs/decisions/0001-python-tooling.md).
- **Node/TS** *(if a JS frontend lands)*: `pnpm`, TypeScript strict mode, Vite or Next.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`).
- **Branches**: short-lived feature branches off `main`. PRs for non-trivial work.
- **Models on disk**: never commit model weights. They live under `models/` (gitignored) or HuggingFace cache.

## Spec-driven agent workflow

1. `SPEC.md` is the source of truth for *what to build*.
2. Break the spec into agent-sized tasks (~1 PR each).
3. Use Claude Code subagents (`Explore`, `Plan`, `general-purpose`) for parallelizable work.
4. Each agent task should reference the SPEC section it implements.

## Quick reference

- **Local URLs**: TBD (default `mlx-lm.server` is `http://127.0.0.1:8080`).
- **GitHub repo**: `kashman001/local-model` *(planned, public — not yet created; see `memory/project_overview.md` for the exact `git init` + `gh repo create` commands waiting to run)*.
- **Active branch**: `main` (once repo is initialized).
