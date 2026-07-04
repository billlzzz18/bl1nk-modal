# Development Workflow

## Core Principles

1. **TDD strictness: Moderate** — tests encouraged, not blocking, especially where a project already has good coverage. Not a strict red→green→refactor requirement on every change.
2. **Commit strategy: Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, etc.).
3. **Code review: Optional / self-review OK** — this is a solo-owned repo, but let bot reviewers (Kilo, CodeRabbit, CodeAnt, Gemini Code Assist) run on PRs and address their findings before merging.
4. **Verification checkpoints: only at track completion** — automated tests run per task/phase as work happens; a full manual verification pass is reserved for when the whole track is done.

## Task Lifecycle

Lighter-weight than the strict red→green→refactor loop, matching "Moderate" TDD:

1. **Pick the task** from the track's plan.
2. **Implement it**, adding or updating tests where the change has meaningful logic to verify (pure functions, API contracts, parsers) — skip tests for pure plumbing/config changes.
3. **Run the relevant test suite** for the project(s) touched (`pytest` for Python projects, `cargo test` for the Rust engine).
4. **Commit** with a Conventional Commits message.
5. Repeat for the next task in the track.

## Quality Assurance Gates

| Gate | Requirement | Command |
| --- | --- | --- |
| Tests | Relevant project's test suite passes | `pytest` (Python) / `cargo test` (Rust) |
| Style | `.pre-commit-config.yaml` hooks pass | `pre-commit run --all-files` |
| Bot review | Address findings from CI review bots before merge | (automatic on PR) |

## Development Commands

### Python project (e.g. `modal-apps/modal-runner`)

```bash
cd modal-apps/modal-runner
pip install -e ".[dev]"
pytest
```

### Rust engine

```bash
cd modal-apps/modal-opencode/engine
cargo fmt --check
cargo test
```

### Pre-commit (repo-wide)

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Track Verification Protocol

Per the "verify only at track completion" preference:

1. During the track: run each task's own tests as you go, but don't block on a full end-to-end pass.
2. At track completion: run every affected project's test suite, plus `pre-commit run --all-files`, and do a manual smoke test of the actual behavior changed (per the repo's `/verify` skill) before marking the track done.
