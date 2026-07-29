---
name: deploy-bl1nk-app
description: Build the bl1nk-agent base image, run uv sync, then deploy the unified bl1nk-app with `modal deploy modal_app.py --name bl1nk` — plus the separate bl1nk-search flow
source: auto-skill
extracted_at: '2026-07-09T12:34:11.889Z'
---

# Deploy the unified bl1nk-app to Modal

The repo has exactly one unified Modal app (post-July 2026 unification, commit `ace0fc5`) and one separately-deployed search service. This skill covers both deploy flows and the build ordering that catches the most common mistakes.

## When to use

- First-time deploy of the unified app.
- After a code change to `modal-apps/bl1nk-app/modal_app.py` or any of its submodules.
- After bumping the `bl1nk-agent:latest` base image contents (toolchain upgrade, new package).
- Deploying or updating the `bl1nk-search` vector search service.

## Pre-flight: do these before deploying

1. **Authentication.** Pick one of:
   - Interactive: `modal setup` (browser OAuth — does **not** work headless or in Termux).
   - Headless: copy `.env.example` to `.env` at the repo root, fill in `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` from <https://modal.com/settings>. The app reads them via `uv run --env-file .env ...`.
2. **Python deps.** From `modal-apps/bl1nk-app/`: `uv sync`.
3. **Base image is published.** The app's `modal_app.py` does `image = modal.Image.from_name("bl1nk-agent:latest")`. If the image doesn't exist on Modal yet, the deploy will fail at first function invocation. See "Building or updating bl1nk-agent" below.

## Deploy the unified app

From `modal-apps/bl1nk-app/`:

```bash
uv run modal deploy modal_app.py --name bl1nk
```

The `--name bl1nk` is the **deployed app name on Modal** (visible at <https://modal.com/apps>); it matches the `APP_NAME = "bl1nk"` constant in `modal_app.py`. Don't rename it casually — the GitHub webhook config, Linear automations, and any external clients pin to this name.

## Local serve (no deploy)

```bash
cd modal-apps/bl1nk-app
uv run modal serve modal_app.py
```

Use this for local iteration. `serve` creates an ephemeral app that auto-reloads on file changes; `deploy` creates a persistent deployment.

## Building or updating the `bl1nk-agent` base image

The base image is built by `modal-images/build_bl1nk_agent.py`. It is **not** a `modal deploy` — it is `modal run`, which builds the image and publishes it under three tags via the shared `_tags.publish_versioned()` helper.

```bash
cd /home/billl/02dev/bl1nk-modal    # or your repo root
modal run modal-images/build_bl1nk_agent.py
```

The published image is `bl1nk-agent:latest`. To bump the major version (e.g., `v1` → `v2`), use the `bump-base-image-version` skill — do not hand-edit the `publish(...)` call or hand-type a date.

**Important:** `modal-apps/bl1nk-app/modal_app.py` also defines an **in-process** `_make_sandbox_image()` function with the same install steps. This is the image used when the app *creates a new Modal sandbox* at runtime (e.g., via `SandboxManager.create_sandbox`). When you change the base image, update both — the published one is for the app itself, the in-process one is for sandboxes. They should stay byte-equivalent. The published `bl1nk-agent:latest` is the simpler one to keep current; the in-process one is the source of truth for sandbox creation.

## Deploying the `bl1nk-search` service

The search service is a separate Modal app, not part of `bl1nk-app`. Two steps:

```bash
cd modal-images

# 1. Build the bl1nk-search image (publishes :latest, :v1, :v1-YYYYMMDD)
modal run build_bl1nk_search.py

# 2. Deploy the search service
modal deploy deploy_bl1nk_search.py
```

The `bl1nk-search` service spec lives in `docs/BL1NK_SEARCH_V1_SPEC.md`. The service provides embedding indexing and reranked query endpoints; tests live at `modal-images/tests/test_search_service.py`.

## Common mistakes to avoid

- **Deploying with the wrong name.** `--name bl1nk` is correct. Older code paths in `scripts/publish.sh`, `scripts/check.sh`, and `SETUP.md` reference `modal-sandbox-v2.1` — those are stale, do not copy them.
- **Running `modal run` instead of `modal deploy` for the app.** `modal run` is for **building images** (`build_bl1nk_agent.py`, `build_bl1nk_rust.py`, `build_bl1nk_search.py`); `modal deploy` is for serving the app (`modal_app.py`, `deploy_bl1nk_search.py`).
- **Forgetting `uv sync`.** New deps in `pyproject.toml` won't be picked up by `modal deploy` until you've run `uv sync` in `modal-apps/bl1nk-app/`. `uv` manages both the local venv and the Modal-deployed environment.
- **Forgetting `--env-file .env`.** Headless deploys need `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET`. Either run via `uv run --env-file .env modal deploy ...` or export the variables in the shell.
- **Deploying before the base image exists.** `modal deploy modal_app.py` will succeed (it just uploads code), but the first webhook invocation will fail with an "image not found" error. Always build the image first.

## Smoke test after deploy

The app exposes a `dev()` function that runs `shutil.which` on every tool the image installs (`git`, `gh`, `node`, `npm`, `bun`, `cargo`, `rustc`, `claude`). Invoke it from the Modal dashboard or via:

```bash
modal run modal-apps/bl1nk-app/modal_app.py::dev
```

If every tool reports a path (not "not found"), the image is good. If `claude` is "not found", the Claude CLI install step in `build_bl1nk_agent.py` may have hit a network blip; re-run `modal run modal-images/build_bl1nk_agent.py`.

## How to apply

Use this skill for any `modal deploy` or `modal run` of the unified app or the search service. If the user is asking about the Rust engine specifically (the PyO3 module under `modal-apps/bl1nk-app/engine/`), use the `build-rust-engine-on-modal` skill instead — the engine is built into the sandbox image via `maturin develop`, not deployed as a separate Modal function.
