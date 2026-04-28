# 0001 — Python tooling: uv + ruff + pytest

- **Status:** Accepted
- **Date:** 2026-04-27
- **Deciders:** project owner

## Context

`local-model` is a Python project (MLX-backed inference server, plus possibly a Python chat client). We need to pick:

1. An environment / dependency manager.
2. A formatter + linter.
3. A test runner.

Constraints:

- Single-developer project running on macOS / Apple Silicon.
- Want fast iteration, reproducible installs, and minimal yak-shaving.
- No CI initially, so tooling must be useful locally on its own.

## Decision

| Concern | Tool |
|---|---|
| Env + deps | **uv** |
| Format + lint | **ruff** (single binary covers both) |
| Tests | **pytest** |

Concretely:

- Project metadata lives in `pyproject.toml`. Dependencies are managed via `uv add` / `uv remove`. Lockfile (`uv.lock`) is committed.
- `ruff format` + `ruff check` run before commits. Configured under `[tool.ruff]` in `pyproject.toml`. No separate `black` / `isort` / `flake8`.
- `pytest` for the test suite. No `unittest` boilerplate.

## Alternatives considered

- **pip + venv + pip-tools** — works but slow, no built-in lockfile workflow, requires juggling multiple tools.
- **poetry** — mature, but slower than uv and has had repeated dependency-resolution rough edges. uv is now the consensus pick on macOS.
- **conda / mamba** — overkill; we don't need non-Python binary deps that conda excels at.
- **black + isort + flake8** — three tools where one (ruff) suffices. Ruff is also dramatically faster.

## Consequences

**Positive**

- One command (`uv sync`) sets up a working dev environment from a fresh clone.
- One tool (`ruff`) covers formatting and linting; faster feedback loop.
- Standard `pyproject.toml` keeps the project portable if we ever migrate off uv.

**Negative / risks**

- `uv` is younger than pip/poetry. Mitigation: it is now widely adopted and Astral-backed; if it ever stalls, `pyproject.toml` is portable to any other PEP 621 tool.
- Contributors unfamiliar with `uv` need a brief README setup section. Mitigated by adding setup instructions to `README.md` once the first package is scaffolded.

## Follow-ups

- Add a Setup section to `README.md` with `uv sync` instructions when the first Python package is created.
- Add `[tool.ruff]` config to `pyproject.toml` at scaffolding time (line length, target Python version, rule selection).
- Revisit if/when CI is introduced — `uv` and `ruff` both have official GitHub Actions.
