# Technology Stack

## Languages

- **Python** — FastAPI/Modal apps: `modal-runner`, `modal-agy`, `modal-sandbox`, `modal-images`.
- **Rust** — `sovereign_engine` (pyo3 extension crate) in `modal-apps/modal-opencode/engine`.
- **Bash** — setup/orchestrator scripts (`setup.sh`, `orchestrator.sh`, `run.sh`, `build.sh`).

**Planned:** a Rust CLI + desktop app, with a bun/npm wrapper so it's also runnable via `npm` or `bun`.

**Hard constraint:** client-side tooling (CLI, future desktop app) must run on every OS the user works from, **including Termux on Android** — avoid platform-specific assumptions in tooling code.

## Frontend

None yet — CLI-only for now.

**Planned:** Tauri v2 + a web frontend for the desktop app, once the CLI and API are stable.

## Backend

### Language & Framework

**Choice:** Python + FastAPI, deployed on Modal via `modal.asgi_app()` / `modal.fastapi_endpoint()`.

**Rationale:** Modal is the serverless compute target for this whole repo; FastAPI is what every existing web-facing app (`modal-runner`, `modal-sandbox`, `modal-images/search_service.py`) already uses.

### Database

Moving to an **adapter pattern** with three swappable layers:

| Layer | Current implementation | Notes |
| --- | --- | --- |
| Vector store adapter | FAISS `IndexFlatIP`, in-memory | `modal-images/search_service.py` |
| DB adapter | CrateDB via `asyncpg` | `modal-apps/modal-runner/main.py` (task tracking) |
| Storage adapter | TBD | Not yet implemented |

Default implementation runs inside the sandbox/container. Swap out a layer later only if that becomes too costly or wasteful — don't pre-optimize.

### Additional Backend Libraries

| Library | Purpose | Used in |
| --- | --- | --- |
| `asyncpg` | CrateDB client | modal-runner |
| `httpx` | HTTP client (LINE Notify, webhooks) | modal-runner |
| `transformers` / `torch` | Embedding + reranker models | modal-images (bl1nk-search) |
| `faiss-cpu` | Vector search | modal-images (bl1nk-search) |
| `pyo3` | Python↔Rust bridge | modal-opencode/engine |
| `regex`, `serde`/`serde_json` | Rust-side label detection | modal-opencode/engine |

## Infrastructure

### Hosting

**Provider:** Modal (serverless GPU/CPU cloud) — the primary compute/deploy target for now.

**Services used:**

- `modal.Image` — versioned, tagged build images (`bl1nk-rust:latest`/`v2`/`v2-YYYYMMDD`, `bl1nk-search:latest`/`v1`/`v1-YYYYMMDD`)
- `modal.Sandbox` — ephemeral sandboxed execution (modal-sandbox, modal-agy)
- `modal.Cron` — scheduled reports (modal-runner daily/weekly)
- `modal.Secret` — credentials (CrateDB, LINE Notify, webhook signing secrets, bearer tokens)

**Other infrastructure pieces (GitHub Actions for CI/labels, possibly Cloudflare) will likely be added later, but Modal is the focus while the core apps stabilize.**

### CI/CD

**Platform:** GitHub Actions (currently just `.pre-commit-config.yaml`-driven checks locally; no deploy-on-push pipeline yet).

## Development Tools

### Testing

| Type | Tool | Notes |
| --- | --- | --- |
| Python unit tests | `pytest` (+ `pytest-asyncio` where needed) | Per-project `tests/` directories |
| Rust unit tests | `cargo test` | `modal-apps/modal-opencode/engine` |

### Linting & Formatting

**Python:** `ruff` (lint + format) and `mypy` (type-check) — currently only declared in `modal-sandbox/pyproject.toml`; add to other projects as they need it.
**Rust:** `cargo fmt`, `cargo clippy` (fmt enforced via `.pre-commit-config.yaml`).

Pre-commit hooks run via the Python **`pre-commit`** framework (`.pre-commit-config.yaml` at repo root) — **not** Husky/npm; this repo has no `package.json`.

## Decision Log

### Adapter pattern for storage layers

**Date:** 2026-07-04
**Status:** Planned

**Context:** `bl1nk-search` hardcodes FAISS in-memory storage and `modal-runner` hardcodes CrateDB via asyncpg — neither is swappable without a rewrite.

**Decision:** Split storage into three adapters (vector store, DB, storage), each with a default sandbox-local implementation, so a layer can be swapped later without touching the rest of the app.

**Consequences:**

- More upfront interface design work.
- Future backend swaps (e.g. FAISS → another vector store) become isolated changes.

---

### setup-pre-commit skill rewritten for this repo's actual stack

**Date:** 2026-07-04
**Status:** Done

**Context:** The `.claude/skills/setup-pre-commit` skill was written entirely for Node/Husky/npm, but this repo has no `package.json` anywhere and already uses the Python `pre-commit` framework.

**Decision:** Rewrote the skill around `.pre-commit-config.yaml`, scoping `ruff`/`mypy`/`pytest` hooks per Python project directory, leaving the existing `cargo fmt`/`cargo test` hooks untouched.

**Consequences:**

- Future pre-commit setup work in this repo follows the pattern already in place instead of introducing a Node toolchain that doesn't fit.

---

### Shared `_tags.py` helper for image version publishing

**Date:** 2026-07-04
**Status:** Done

**Context:** `build_bl1nk_rust.py` never actually built or published an image — the `latest`/`v2`/`v2-YYYYMMDD` tags documented in `modal-images/README.md` and the `modal-image-builds` skill didn't exist anywhere in code. `build_bl1nk_search.py` did publish tags, but hand-typed the version and today's date into 3 separate `built.publish(...)` calls — a rebuild meant manually editing a date string and remembering to keep it consistent across 3 lines.

**Decision:** Added `modal-images/_tags.py` with `publish_versioned(built, name, major)`, which computes the dated tag and publishes all three in one call. Both build scripts now use it and expose a single `MAJOR_VERSION` constant to bump by hand when needed. Fixed `build_bl1nk_rust.py` to actually call `image.build(app)` + publish. Every *consumer* app already pins `:latest`, so this only affects the build scripts — no downstream app needs updating when a new version publishes.

**Consequences:**

- A version bump is a one-line edit in one file; the date is never hand-typed.
- Any future build script for a new image should reuse this pattern (see the updated `modal-image-builds` skill template) instead of reintroducing hardcoded version/date literals.

---

### Repo-wide formatting, line-ending normalization, and Windows bootstrap

**Date:** 2026-07-04
**Status:** Done

**Context:** There was no root-level `.editorconfig`/`.gitattributes`, so editor indentation and line endings could drift per-directory; `ruff` was only declared in `modal-sandbox/pyproject.toml` even though it's this repo's Python formatter/linter; there was no repo-wide way to sweep whitespace/line-ending drift outside of what `pre-commit` catches on staged files; and there was no bootstrap path for a Windows machine with nothing installed (every existing setup script — `modal-agy/setup.sh`, `modal-sandbox/scripts/setup.sh` — is bash-only).

**Decision:** Added root `.editorconfig` and `.gitattributes` (LF-normalized, lockfiles marked generated). Added matching `ruff` dev-dependency + `[tool.ruff]` config to `modal-runner`, `modal-agy`, and `modal-images` (previously only `modal-sandbox` had it), with scoped `ruff-<name>` pre-commit hooks for all four. Added `scripts/fix_whitespace.py` — pure-stdlib Python, no `sed`/OS-specific tooling — to normalize CRLF/trailing whitespace/final-newline across every tracked text file in one pass, with a `--check` mode for CI. Added `scripts/install-windows.ps1`, a PowerShell bootstrap that installs `uv`, Rust/rustup, the Modal CLI, and `pre-commit`, then runs `uv sync` in every Python project.

**Consequences:**

- New Python projects should follow the same `ruff` dev-dep + `[tool.ruff]` + pre-commit hook pattern from the start rather than adding it later.
- `scripts/` at the repo root is now the home for cross-project tooling (as opposed to per-app `scripts/` dirs like `modal-apps/modal-sandbox/scripts/`); a future Windows-equivalent of any bash-only root script belongs there too.
