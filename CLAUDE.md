# CLAUDE.md

Context for Claude Code sessions working on **local-model**. Read this fully before starting any task.

**Session start:** if `RESUME.md` exists at the project root, read it *first* — it's a transient handoff from the previous session and may point you at the immediate next action. Once you've acted on it (or confirmed it's stale because project memory is already current), **delete `RESUME.md`** in the same step. The file is gitignored, so deletion needs no commit.

## Project

Local LLM deployment on Apple Silicon using MLX, with a sample chat application. The project targets a single user (the repo owner) running everything on a MacBook Pro.

Architecture (drafted in [`SPEC.md`](./SPEC.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md), 2026-04-28):

- **Inference server** — custom FastAPI process exposing an OpenAI-compatible HTTP API. Phase 1 ships only `MLXBackend` (uses `mlx_lm` directly, not `mlx_lm.server`). Phase 2 adds `VLLMBackend` for the RTX 4080 PC. Decision recorded in [`docs/decisions/0003-server-architecture.md`](./docs/decisions/0003-server-architecture.md).
- **Chat client** — small FastAPI + Jinja2 + **HTMX** browser app on `:8000`; talks to one or more inference endpoints over HTTP. No JS framework.

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

### Subagent dispatches

When you spin up subagents (e.g. via `superpowers:subagent-driven-development`), apply the same routing logic to **each subagent's `model:` parameter**:

| Subagent task | Model |
|---|---|
| Mechanical implementer (single file, plan-verbatim, dataclass / config / DAO / stub) | **Haiku** |
| Spec-compliance reviewer (cat files, diff against plan, verify commit) | **Haiku** |
| Code-quality reviewer for trivial config / scaffolding tasks | **Haiku** |
| Implementer touching a fast-moving library (MLX, vLLM, AI SDKs) — judgment + adaptation expected | **Sonnet** |
| Code-quality reviewer for substantive logic / integration tasks | **Sonnet** |
| Final pre-merge review across an entire branch | **Sonnet** |

When the plan is well-specified and the task is mechanical, **trust the spec compliance + ruff + pytest** as the quality gate; you don't need a separate code-quality reviewer for every micro-task. Reserve standalone code-quality reviewers for substantive work (real I/O, integrations, multi-file coordination).

## Tooling conventions

- **Python**: `uv` for env + dependency management, `ruff` for format + lint, `pytest` for tests. See [`docs/decisions/0001-python-tooling.md`](./docs/decisions/0001-python-tooling.md).
- **Type hints**: `X | None` over `Optional[X]` (PEP 604, Python 3.10+). Ruff UP045 auto-fixes this — don't fight it. The `from typing import Optional` import is unneeded.
- **SQL ordering**: when the plan or code uses `ORDER BY <semantic column>`, append a deterministic tiebreaker (`rowid` for SQLite). `CURRENT_TIMESTAMP` is second-granularity, so two inserts in the same second tie and re-order non-deterministically. Lexicographic UUID order is **not** a tiebreaker.
- **Verifying library APIs**: when a plan or doc references a fast-moving library (any LLM inference engine, AI SDK, frontend framework), verify current API shape via Context7 (`mcp__plugin_context7_context7__query-docs`) before coding — plan code may be stale against the latest release.
- **Node/TS** *(if a JS frontend lands)*: `pnpm`, TypeScript strict mode, Vite or Next.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`).
- **Branches**: short-lived feature branches off `main`. PRs for non-trivial work.
- **Models on disk**: never commit model weights. They live under `models/` (gitignored) or HuggingFace cache.

## Spec-driven agent workflow

1. `SPEC.md` is the source of truth for *what to build*.
2. Break the spec into agent-sized tasks (~1 PR each).
3. Use Claude Code subagents (`Explore`, `Plan`, `general-purpose`) for parallelizable work.
4. Each agent task should reference the SPEC section it implements.

## Standing authorizations

Pre-approvals so agents can work autonomously. **Anything not on the green list still requires confirmation.** Authorization stands only for the scope written here — extending it requires a CLAUDE.md update, not in-session approval.

**Pre-authorized (proceed without asking):**

- File reads / edits / creates anywhere under the project root, including subagent dispatch.
- Local git ops on **any branch other than `main`**: stage, commit (Conventional Commits), branch create, switch, rebase onto `main`, stash, push to `origin/<feature-branch>`.
- **Push to `main`** when **all** of the following hold — verify each before pushing:
  1. **Working tree is clean.** `git status --porcelain` returns empty (no unstaged, staged-but-uncommitted, or untracked files that risk being included by an interactive flow).
  2. **Push is fast-forward.** Run `git fetch origin main` first, then `git rev-list --left-right --count origin/main...HEAD` must show `0\t<N>` — i.e., `origin/main` has zero commits we don't already have, and we have N≥1 to push.
  3. **No force flags.** Plain `git push origin main` only.

  If any precondition fails, this falls back to the red list and requires confirmation.
- Dependency ops via `uv`: `uv sync`, `uv add`, `uv remove`, `uv lock`. Lockfile changes go in the same commit as the code that needed them.
- Format / lint / test: `ruff format`, `ruff check` (incl. `--fix`), `pytest` with any args.
- Read-only `gh` queries: `gh pr view/list/diff/checks`, `gh issue view/list`, `gh run view/list`, `gh api` GET requests.
- Opening PRs (`gh pr create`) and commenting on PRs / issues.
- Updating `SPEC.md`, `ARCHITECTURE.md`, `docs/decisions/*`, `README.md`, and `CLAUDE.md` when code changes warrant it — same commit as the code (per the Hard rule above).
- Starting and stopping local processes bound to `127.0.0.1` (e.g. the inference server) for testing.

**Always confirm first:**

- Pushing to `main` outside the fast-forward+clean-tree green-list condition above. Force-push anywhere. Merging into `main` (`git merge`, `gh pr merge`).
- `git reset --hard`, `git clean -fd`, `git branch -D`, deleting tags, rewriting published history.
- `gh repo edit`, `gh repo delete`, visibility flips, branch protection changes.
- Closing PRs or issues via `gh`.
- Downloading model weights (typically >1 GB — disk + bandwidth impact). Show the exact command and approximate size before running.
- Editing `.claude/settings.json` to expand `permissions.allow` — agents must not widen their own permissions.
- Any command run with `sudo`.
- Writes outside the project root (HOME dotfiles, system config, sibling repos).
- Long-running foreground processes (>2 min) with no clear stop condition.

**Confirm-first protocol — `waiting-on-you:` markers.** Whenever you need confirmation for a red-list item, end the message with a single line in the form:

> `**waiting-on-you:** <one-line description naming the exact action or command>`

Rules:

- The phrase is lowercase `waiting-on-you:` so a long session can be searched (`grep` / `Cmd+F`) for blocked points.
- **One line only.** Any context goes earlier in the message; the marker is the visual anchor.
- Name the action concretely: `git push origin main` not "push the changes"; `gh pr merge 42 --squash` not "merge the PR".
- Place it last in the message.
- Once the action is approved and executed, do **not** echo `waiting-on-you:` for the resolved item in subsequent messages — only use it for currently-blocked items.

**When ambiguity blocks a task,** use `AskUserQuestion` with batched options (up to 5) rather than turn-by-turn confirmations. (`AskUserQuestion` is its own UI flow and does not need a `waiting-on-you:` marker — the question itself is the marker.)

## Quick reference

- **Local URLs**: inference server `http://127.0.0.1:8080`; browser chat client `http://127.0.0.1:8000` (per [`ARCHITECTURE.md` §15](./ARCHITECTURE.md#15-deployment-topology)).
- **Worktree directory**: `.worktrees/` (project-local, gitignored). Each long-running implementation effort gets its own subdirectory, e.g. `.worktrees/v1-mac-mlx/`. Skills like `superpowers:using-git-worktrees` should pick this up via `grep -i "worktree.*director" CLAUDE.md` and not re-ask.
- **GitHub repo**: `kashman001/local-model` *(planned, public — not yet created; see `memory/project_overview.md` for the exact `git init` + `gh repo create` commands waiting to run)*.
- **Active branch**: `main` (once repo is initialized).
