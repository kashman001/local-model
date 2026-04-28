# Diagram index

> Every diagram in `local-model` lives in markdown as a Mermaid code block — no images, no external tools required to read or update them. This file lets future agents (and humans) find the right diagram without grepping.
>
> All diagrams render natively on GitHub. For local preview use VS Code's built-in Mermaid support or any modern markdown viewer.

## Conventions

- **C4 Context (Level 1)** — what's outside the system, the user, the major hosts. Used in `README.md` and `SPEC.md`.
- **C4 Container (Level 2)** — processes / runtimes / data stores inside the system. Used in `ARCHITECTURE.md §1`.
- **C4 Component (Level 3)** — modules inside one container. Used in `ARCHITECTURE.md §2`.
- **Sequence diagrams** — runtime interactions over time. Used for the canonical chat flow and for model swap.
- **State diagrams** — lifecycles. Used for the model registry's state machine.
- **Class diagrams** — Protocol / interface shapes. Used for the `Backend` abstraction.
- **ER diagrams** — persistent data model. Used for the SQLite schema.
- **Decision flowcharts** — used in ADRs to make tradeoff branching legible.

## Index

| Where | Section | Diagram | Purpose |
|---|---|---|---|
| [`README.md`](../README.md) | At-a-glance | C4 Context | One-shot summary of v1 scope |
| [`SPEC.md`](../SPEC.md) | §7 Phasing — overview | flowchart | Phase 1 → Phase 2 → Later |
| [`SPEC.md`](../SPEC.md) | §7 Phasing — Phase 1 | C4 Context | What v1 ships |
| [`SPEC.md`](../SPEC.md) | §7 Phasing — Phase 2 | C4 Context | What Phase 2 adds |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §1 System overview | C4 Container | Per-host server + client + storage |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §2 Server internals | C4 Component | Modules inside the inference server |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §3 Backend abstraction | Class diagram | `Backend` Protocol + impls |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §4 Model lifecycle | State diagram | Unloaded → Loading → Ready → Generating |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §5 Data flow (chat) | Sequence | Browser → server → backend → SSE stream |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §6 Data flow (model swap) | Sequence | Hot-swap via `/admin/models/load` |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §7 Storage model | ER diagram | Conversation / Message / Preset |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | §10 Capability detection | Decision flowchart | Startup checks for each backend |
| [`docs/decisions/0003-server-architecture.md`](./decisions/0003-server-architecture.md) | Decision flowchart | flowchart | Option 1 / 2 / 3 / 4 reasoning |

## Updating diagrams

1. Edit the Mermaid block inline in the markdown file
2. Preview in VS Code (`Ctrl+Shift+V`) or push and check the GitHub render
3. If you add a new diagram, add a row to the index above in the same commit
4. Keep diagrams scoped — if a diagram is doing more than one thing, split it

## Why text-based diagrams (not images)

- AI agents can read, edit, and verify them against the prose alongside
- Diffs are reviewable in normal PRs
- No external tooling, no PNG export step, no out-of-band files
- Future Claude Code sessions can update diagrams when code changes without manual export
