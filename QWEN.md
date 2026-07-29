# QWEN.md — bl1nk-modal

Instructional context for AI agents working in this monorepo.

> The project itself uses Thai in `README.md` and `conductor/*.md` (per `conductor/product-guidelines.md`); Qwen Code replies in English unless told otherwise. Don't translate existing Thai docs to English — they are the project's house style.

---

## 1. What this repo is

`bl1nk-modal` is a **personal monorepo of Modal apps** that form the infrastructure layer for an AI coding agent. After a July 2026 unification (commit `ace0fc5`), four previously-separate apps (`modal-runner`, `modal-agy`, `modal-sandbox`, `modal-opencode`) were merged into a single unified app.

**Top-level layout:**

| Path | Purpose |
| --- | --- |
| `modal-apps/bl1nk-app/` | Unified Modal app (Python). Primary dispatch entrypoint + headless subagents + Rust engine. |
| `modal-apps/bl1nk-search/` | Search service (FastAPI + embedding + reranker). Deployed separately from bl1nk-app. |
| `modal-images/` | Shared base-image build scripts (`bl1nk-agent`, `bl1nk-rust`, `bl1nk-search`). Image builds only — no services. |
| `conductor/` | Conductor-style project context (product, tech stack, tracks, specs, style guides). |
| `docs/` | Top-level specs (currently `BL1NK_SEARCH_V1_SPEC.md`). |
| `scripts/` | Repo-level helpers (`install-windows.ps1`, `fix_whitespace.py`). |
| `.claude/` | Claude skills and plugins (used locally; not deployed). |
| `.github/workflows/` | GitHub Actions (only `sync-triage-labels.yml` — manages plain issue labels, NOT the `type:`/`stage:` label taxonomy). |
| `CLAUDE.md` | Companion agent-context file (not in this index, but referenced by `README.md`). |

---

## 2. The unified app: `modal-apps/bl1nk-app/`

Entry point: `modal_app.py`. **App name: `bl1nk`.** **Image it consumes: `bl1nk-agent:latest`**.

### 2.1 Sub-layout

```
modal-apps/bl1nk-app/
├── modal_app.py            # Primary dispatch (FastAPI webhooks + Modal functions)
├── modal_app_service.py    # Service-side entrypoint variant
├── test_endpoint.py        # Manual endpoint smoke test
├── test_simple.py          # Sanity test
├── conftest.py             # Pytest fixtures
├── pyproject.toml          # (note: name is still "modal-sandbox" v0.2.0 — stale, predates unification)
├── environments/           # Environment abstraction (local, docker, modal, daytona, singularity, ssh, managed_modal, …)
├── subagents/              # Headless subagents
│   ├── agy_headless.py
│   ├── opencode.py
│   └── sandbox_runner.py
├── context/agy/            # Per-subagent context (currently only `agy/`)
├── engine/                 # Rust core engine (PyO3 module: sovereign_engine)
│   ├── src/{lib,detector,file_detector,policy,resolver,size_calc}.rs
│   ├── Cargo.toml / Cargo.lock
│   └── TODO.md
├── scripts/                # build.sh, check.sh, publish.sh, setup.sh, shell.sh  ⚠️ some reference old app name
├── tests/                  # conftest, test_api, test_dev, test_line_notify, test_modal_app, test_parse_commit, test_update_task, test_verify_signature, test_webhook
├── SETUP.md, SANDBOX.md, README.md, TODO.md
└── uv.lock
```

### 2.2 Image and runtime

The base image `bl1nk-agent:latest` (built by `modal-images/build_bl1nk_agent.py`) is a `debian_slim` Python 3.12 image with:

- Rust toolchain (rustup, `~/.cargo/bin` on PATH)
- Node.js 22 + npm (via NodeSource)
- Bun
- GitHub CLI (`gh`)
- Claude CLI (`/root/.local/bin/claude`)
- ripgrep 14.1.1 (`/usr/local/bin/rg`)
- A non-root `workspace` user with `$HOME=/home/workspace`

The in-app `_make_sandbox_image()` defines an equivalent image inline for sandbox creation. The two image definitions should stay in sync; the in-process one is the source of truth for fresh sandboxes, while the published one is consumed by the app's own functions.

### 2.3 SandboxManager

`modal_app.py` defines a `SandboxManager` singleton with:

- Background `_AsyncWorker` (dedicated thread + event loop) that bridges sync code to `modal.*.aio` APIs.
- Auto-timeout: `DEFAULT_TIMEOUT=3600s`, `DEFAULT_MAX_LIFETIME=7200s`, cleanup thread every `CLEANUP_INTERVAL=300s`.
- `create_sandbox` / `exec` / `list_sandboxes` / `destroy_sandbox` / `cleanup` API.
- ID handling: a `task_id` (12-hex) is the public handle, with the underlying Modal `ta-…` ID cached once extractable.

The function `dev()` is a toolchain smoke test (returns `shutil.which` results for `git`/`gh`/`node`/`npm`/`bun`/`cargo`/`rustc`/`claude`) — the recommended way to verify the image.

---

## 3. Modal images: `modal-images/`

Three base images, all built via `modal run` (not `modal deploy`):

| Image | Script | Purpose |
| --- | --- | --- |
| `bl1nk-agent:latest` / `v1` / `v1-YYYYMMDD` | `build_bl1nk_agent.py` | Primary agent base (Rust + Node + Bun + gh + claude + hermes + qwen) |
| `bl1nk-rust:latest` / `v2` / `v2-YYYYMMDD` | `build_bl1nk_rust.py` | Sandbox/agent base (Rust + Node + Bun + gh + claude) |
| `bl1nk-search:latest` / `v2` / `v2-YYYYMMDD` | `build_bl1nk_search.py` | Embedding + reranker search service image (service code in `modal-apps/bl1nk-search/`) |

**Tag convention (very strict):** both build scripts publish three tags via the shared `_tags.publish_versioned()` helper — `latest`, the major version (`vN`), and a dated tag (`vN-YYYYMMDD`). To bump the major version, change the single `MAJOR_VERSION` constant in the build script. **Do not** hand-edit `publish(...)` calls or hand-type dates. Consumers always pin to `:latest`, so they don't need to update when a new version is published.

`search_service.py` is the FastAPI app behind the `bl1nk-search` image, now at `modal-apps/bl1nk-search/`. Spec: `docs/BL1NK_SEARCH_V1_SPEC.md`. `modal-apps/bl1nk-search/tests/test_search_service.py` covers it.

---

## 4. Rust engine: `modal-apps/bl1nk-app/engine/`

PyO3 module named **`sovereign_engine`** (a Python-importable Rust extension). Source modules:

- `lib.rs` — public surface + `resolve_full_state()`.
- `detector.rs` — regex-based text attribute detection (legacy `labels.json` parity).
- `file_detector.rs` — file-aware labeling (`.rs` → `lang:rust`, `Cargo.toml` → `type:dep`, etc.).
- `policy.rs` — conflict resolution (e.g. `p:p0` vs `p:p3` → highest priority) and workflow enforcement (can't skip `stage:test`).
- `resolver.rs` — merges all signals (text + files + manual + policy) into a final `Vec<String>`.
- `size_calc.rs` — PR size thresholds and issue keyword detection.

`engine/TODO.md` lists remaining gaps: `exclusive_groups` should be a constant (not recreated per call), regex patterns should be configurable, and no benchmarks exist yet. Unit tests exist for all five source files (`cargo test --all`).

Build path on Modal: `maturin develop` inside a layer with rustup + maturin pre-installed. See `conductor/modal_deployment.md` for the full recipe (layer caching: keep `apt_install` + `rustup` separate from `copy_local_dir` of the engine, so layer cache survives code changes).

---

## 5. Conductor project context: `conductor/`

Follows the Conductor workflow layout:

- `index.md` — entry point.
- `product.md` — original concept: "OpenCode / KiloCode Gateway" (AI agent runtime on Modal). **Historical**; the post-unification framing is in the root README + section 1 above.
- `product-guidelines.md` — security, robustness, code readability, API design. **Includes the Thai-language documentation rule** ("explain critical logic using the Thai language where possible").
- `tech-stack.md` — Python 3.12, FastAPI, Modal, httpx, debian_slim. **Historical** — pre-unification OpenCode/KiloCode framing; verify against actual code.
- `modal.md` — Modal-specific guidelines: explicit `@app.function` resource decorators, minimal `modal.Image`, `os.environ.get()` + `modal.Secret.from_name()` for secrets, generous-but-firm timeouts, stateless functions.
- `modal_deployment.md` — Recipe for the Rust engine on Modal (rustup + maturin, Modal Volume for SQLite state, layer caching for fast rebuilds, `--release` for production).
- `spec.md` — Full spec for the Rust core engine track (5 phases: Rust core → Modal webhook → SQLite on Modal Volume → GitHub API sync → dashboard).
- `tracks.md` + `tracks/rust_engine_20260421/` — active track registry.
- `code_styleguides/{general,python,rust}.md` — coding style.
- `setup_state.json` — Conductor setup state (do not edit by hand).

---

## 6. Build, run, deploy

### 6.1 Local setup

**macOS/Linux:**
```bash
uv sync                            # in modal-apps/bl1nk-app/
uv tool install modal              # if not on PATH
modal setup                        # browser OAuth
# or for headless / Termux: set MODAL_TOKEN_ID + MODAL_TOKEN_SECRET in .env
```

**Windows (one-shot):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```
This installs `uv`, Rust, Modal CLI, pre-commit, then runs `uv sync` in every Python project and installs hooks.

### 6.2 Local dev serve

```bash
cd modal-apps/bl1nk-app
uv run modal serve modal_app.py     # local serve
```

### 6.3 Build the base image

```bash
# From repo root — script does not need a per-app venv.
modal run modal-images/build_bl1nk_agent.py
# (Inside the app, scripts/build.sh wraps `modal run ../../modal-images/build_bl1nk_rust.py`.)
```

### 6.4 Deploy

```bash
cd modal-apps/bl1nk-app
uv run modal deploy modal_app.py --name bl1nk
```

The `bl1nk-search` service deploys separately:
```bash
cd modal-images
modal run build_bl1nk_search.py
cd ../modal-apps/bl1nk-search
uv run modal deploy deploy.py
```

### 6.5 Tests

```bash
cd modal-apps/bl1nk-app
uv run pytest
```

The `tests/` directory covers API, dev smoke test, signature verification, line notify, modal_app, parse_commit, update_task, and webhook. Tests use `pytest-asyncio` with `asyncio_mode = "auto"` and require `mypy` strict mode to pass.

### 6.6 Pre-commit

`.pre-commit-config.yaml` runs:

- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-added-large-files` (upstream).
- Per-project `ruff check . && ruff format --check .` (note: **the per-app paths in this file are stale** — they reference the four pre-unification apps `modal-runner`/`modal-agy`/`modal-sandbox` rather than `bl1nk-app`; running pre-commit on changes to `bl1nk-app` won't trigger the ruff hook until the paths are updated).
- `cargo fmt --check` and `cargo test --all` for the Rust engine (also stale — the path in the config still points at `modal-apps/modal-opencode/engine/Cargo.toml`; the engine now lives at `modal-apps/bl1nk-app/engine/Cargo.toml`).

---

## 7. Development conventions

### 7.1 Style

From `.editorconfig` + per-project config:

- LF line endings, UTF-8, final newline.
- 4-space indent for Python, Rust, shell, PowerShell; 2-space for YAML/JSON/TOML/Markdown.
- 100-char line length for Python and Rust.
- Makefiles use tabs.
- Markdown: trim trailing whitespace = false (preserves hard line breaks).

Python style: **ruff** (line-length 100, target `py312`), **mypy** strict. The pre-commit config also enforces `ruff format --check` per project.

Rust style: `cargo fmt` + `cargo test` enforced for the engine.

### 7.2 Language convention

- **Thai** is the house language for documentation (`conductor/`, READMEs, docstrings in critical logic) — see `conductor/product-guidelines.md`.
- **English** is the agent reply language (per user preference); do not translate existing Thai docs to English unless asked.
- Commit messages and PR descriptions: Thai or English are both seen; both are accepted.

### 7.3 Image versioning — one helper, one constant

`_tags.py` (in `modal-images/`) is the single point of truth for image version/date publishing. To bump a major version, change `MAJOR_VERSION` in the build script and re-run. **Never** hand-edit `publish(...)` calls or hand-type the date.

### 7.4 Modal-specific rules (`conductor/modal.md`)

- Always use explicit `@app.function` decorators (CPU, memory, timeout, GPU).
- Keep `modal.Image` definitions minimal — split into cacheable layers.
- Secrets via `os.environ.get(...)` + `modal.Secret.from_name(...)`. Never hardcode.
- Functions should be stateless; persist state in Modal Volumes or external DBs.
- Use generous-but-firm timeouts; never let external calls run unbounded.

### 7.5 Tooling

- **uv** is the Python toolchain. Each subproject is independent (no workspace `pyproject.toml` at the root).
- **Cargo** for the engine.
- **MCP servers** configured at `.mcp.json`: `context7` (up-to-date library docs) and `linear` (issue tracker).
- **Skills** at `.claude/skills/`: include `triage` (for plain GitHub labels, NOT the `type:`/`stage:` prefix taxonomy) and `productivity/grill-me` (structured goal questioning).

---

## 8. Known stale references (FYI, do not blindly trust)

These files still reference the **pre-unification** four-app layout. When you have to touch them, the new path is `modal-apps/bl1nk-app/`:

| File | Stale reference | Current truth |
| --- | --- | --- |
| `.pre-commit-config.yaml` | Ruff paths under `modal-apps/modal-{runner,agy,sandbox}/`; cargo paths under `modal-apps/modal-opencode/engine/Cargo.toml` | Should point at `modal-apps/bl1nk-app/` and `modal-apps/bl1nk-app/engine/Cargo.toml` |
| `scripts/install-windows.ps1` | `$pythonProjects = @("modal-apps\modal-runner", "modal-apps\modal-agy", "modal-apps\modal-sandbox", "modal-images")` | Should sync `modal-apps\bl1nk-app` instead of the three pre-unification apps |
| `modal-apps/bl1nk-app/scripts/publish.sh` | Deploys as `modal-sandbox-v2.1` | Should deploy as `--name bl1nk` |
| `modal-apps/bl1nk-app/scripts/check.sh` | Looks for `modal-sandbox`/`v2.1` images and deployment | Should look for `bl1nk-agent` / `bl1nk` |
| `modal-apps/bl1nk-app/SETUP.md` | Termux path `/data/data/com.termux/files/home/modal/...`; references `modal-sandbox-v2.1` | Trust `modal-apps/bl1nk-app/README.md` for the current state; the Termux path is the author's Android setup, not a general convention |
| `modal-apps/bl1nk-app/pyproject.toml` | `name = "modal-sandbox"`, `version = "0.2.0"`, description "Modal Sandbox Service - v2.1 architecture" | Should be `name = "bl1nk-app"` post-unification; the deps are still correct |
| `conductor/tech-stack.md`, `conductor/product.md` | OpenCode/KiloCode framing | Historical only — read the root README and section 1 of this file for current state |

---

## 9. Open work (TODO markers)

- `modal-apps/bl1nk-app/TODO.md`: **No auth middleware** on API endpoints (sandbox create/exec are publicly accessible); `scripts/publish.sh` runs `pytest` but `tests/test_upload_download.py` and `tests/test_image.py` are still pending.
- `modal-apps/bl1nk-app/engine/TODO.md`: `exclusive_groups` should be a constant; regex patterns should be configurable; no benchmarks yet.
- `modal-apps/bl1nk-search/TODO.md` (if exists) or `modal-images/TODO.md`: `search_service.py` has global mutable `_index`/`_ids` that are not thread-safe (everything else is resolved).

---

## 10. Quick reference: common commands

```bash
# First-time setup (Linux/macOS)
uv sync && uv tool install modal && modal setup

# First-time setup (Windows)
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1

# Build the agent base image (publishes bl1nk-agent:latest)
modal run modal-images/build_bl1nk_agent.py

# Build the rust base image (publishes bl1nk-rust:latest, v2, v2-YYYYMMDD)
modal run modal-images/build_bl1nk_rust.py

# Build + deploy the search service
modal run modal-images/build_bl1nk_search.py
cd modal-apps/bl1nk-search && uv run modal deploy deploy.py

# Serve locally
cd modal-apps/bl1nk-app && uv run modal serve modal_app.py

# Deploy to Modal as the unified app
cd modal-apps/bl1nk-app && uv run modal deploy modal_app.py --name bl1nk

# Run tests
cd modal-apps/bl1nk-app && uv run pytest

# Lint + format
cd modal-apps/bl1nk-app && ruff check . && ruff format --check .

# Engine
cd modal-apps/bl1nk-app/engine && cargo fmt --check && cargo test --all

# Pre-commit (note: the config has stale per-app paths — see section 8)
pre-commit run --all-files
```
