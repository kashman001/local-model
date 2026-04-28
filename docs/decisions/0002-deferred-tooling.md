# 0002 — Deliberately deferred tooling: pre-commit hooks and CI

- **Status:** Accepted
- **Date:** 2026-04-27
- **Deciders:** project owner

## Context

At repo-init time we considered adding:

1. **Pre-commit hooks** (e.g. `pre-commit` framework, husky, or `.git/hooks` scripts running ruff + tests on commit).
2. **CI** (GitHub Actions running ruff + pytest on push / PR).

Both are common to add to a fresh Python repo. We chose to add **neither**, for now.

## Decision

- No pre-commit framework. No `.pre-commit-config.yaml`. Local hooks (`.git/hooks/*`) are also not installed.
- No GitHub Actions workflows. No `.github/workflows/`.

These are *deferred*, not rejected — see "Revisit when" below.

## Reasoning

- **Single-user repo, no runnable code yet.** There is nothing to test and no other contributors to police. Pre-commit's value is mostly enforcing format/lint discipline across many people; CI's value is mostly catching regressions and enforcing checks PRs depend on. Both are weak in a single-developer pre-spec project.
- **Setup cost is non-trivial today, near-zero later.** A `pre-commit` install needs Python tooling configured first, and a CI workflow needs a non-empty test suite to be useful. Adding these *before* `uv sync` even has anything to install is yak-shaving.
- **Conventional discipline can live in the agent loop.** Per `CLAUDE.md`, agents run `ruff format` / `ruff check` / `pytest` as part of the standing-authorizations workflow. That covers the same ground a pre-commit hook would, without an extra moving part.

## Alternatives considered

- **Add `pre-commit` now with stub config** — would force every contributor (just the user, today) to install one more tool to commit. No upside until there are checks worth enforcing.
- **Add a stub GitHub Actions workflow that runs `ruff check`** — possible, but the repo isn't pushed yet, the toolchain isn't scaffolded, and an empty workflow is just noise.
- **Local `.git/hooks/pre-commit` script** — bypassed by `--no-verify` and unmanaged. Worse than the `pre-commit` framework if we're going to add hooks at all.

## Revisit when

Add **pre-commit** when *any* of:

- A second contributor lands.
- We've shipped two consecutive commits with formatting / lint regressions that would have been caught by a pre-commit hook.
- We adopt secrets / large-file scanning that an editor can't replicate.

Add **CI** when *any* of:

- The first runnable code (server or client) lands and has at least a smoke test.
- We start using PRs for the user's own work (i.e. branch protections want green checks).
- Releases / tags are cut and need reproducible build verification.

When either trigger fires, capture the change in a follow-up ADR (`0003-...`) rather than amending this one.

## Consequences

- Lower setup overhead now; faster path to writing actual code.
- No automated guardrail against committing unformatted / failing code — agents are responsible for running ruff + pytest before committing, per `CLAUDE.md` standing authorizations.
- A future "Setup" section in `README.md` won't need a `pre-commit install` step, simplifying onboarding.
