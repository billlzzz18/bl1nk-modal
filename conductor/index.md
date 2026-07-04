# Conductor - bl1nk-modal

Navigation hub for project context.

## Quick Links

### Core Documents

| Document | Description | Status |
| --- | --- | --- |
| [Product Vision](./product.md) | Product overview and goals | Complete |
| [Product Guidelines](./product-guidelines.md) | Voice, tone, and design principles | Complete |
| [Tech Stack](./tech-stack.md) | Technology decisions | Complete |
| [Workflow](./workflow.md) | Development process | Complete |

### Track Management

| Document | Description |
| --- | --- |
| [Track Registry](./tracks.md) | All development tracks, plus the current cross-project backlog pulled from each app's `TODO.md` |

### Style Guides

| Guide | Language/Domain |
| --- | --- |
| [Python](./code_styleguides/python.md) | Python standards |
| [Rust](./code_styleguides/rust.md) | Rust conventions |
| [TypeScript](./code_styleguides/typescript.md) | TypeScript conventions (for the planned CLI/desktop wrapper) |

## Active Tracks

<!-- Auto-populated by /conductor:new-track -->

None yet.

## Getting Started

Check [Track Registry](./tracks.md) for the current backlog (pulled from each app's `TODO.md`) before starting new work — don't duplicate an item that's already tracked. Run `/conductor:new-track` to promote a backlog item (or cluster of related ones) into a real track once you're about to work on it. Likely first candidates based on the setup conversation:

1. Storage adapter split (vector store / DB / storage adapters) — also ties into the `search_service.py` thread-safety item in the backlog
2. Rust CLI bootstrap (with bun/npm wrapper)
3. Auth middleware for `modal-sandbox`'s API endpoints — currently open to anyone

---

**Last Updated:** 2026-07-04
