---
name: modal-image-dev
description: >
  Build reproducible Modal dev images for AI agent runtimes.
  Use when: creating a base image with Rust/Node/Bun/GitHub CLI/Claude Code,
  adding embedding/reranker runtime images, or publishing versioned Modal images.
  Covers the user's preferred workspace-user layout, verification steps,
  and Modal SDK gotchas.
triggers:
  - "build modal image"
  - "create modal image"
  - "update modal image"
  - "modal image build"
  - "modal run build"
  - "publish modal image"
  - "modal image names"
  - "build modal image for service"
  - "deploy modal service"
---

# Modal Dev Image Build

Class-level workflow for building versioned Modal images and deploying GPU services for AI agent runtimes.

## 1. App Initialization (MANDATORY)

Always use lookup, never bare `App()`:

```python
app = modal.App.lookup(APP_NAME, create_if_missing=True)
```

Bare `modal.App(APP_NAME)` fails with InvalidError on `image.build(app)`. Bare `App` also blocks decorator-based function registration unless local state is initialized.

## 2. Build Invocation

Use `modal run build_<name>.py` for local builds. `modal deploy` is for serving apps, not image creation.

Place build+publish in top-level script, not inside `@app.function`, because `image.build(app)` requires an initialized app context and local state.

## 3. User's Preferred Runtime Layout

Build phase runs as root. Runtime runs as `workspace`.

```python
image = (
    modal.Image.debian_slim(python_version="3.12")
    # ... installs ...
    .run_commands(
        # user creation + ownership
        "useradd -m -s /bin/bash workspace",
        "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
        "chown -R workspace:workspace /home/workspace",
    )
    .env({
        "HOME": "/home/workspace",
        "PATH": "/home/workspace/.local/bin:/home/workspace/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
    })
)
```

Directory tree expected at runtime:

```
/home/workspace
├── .cache/
├── .cargo/         # symlinked from /root/.cargo during build
├── .claude/
├── .config/
├── .local/bin/
├── .npm/
├── .ssh/           # optional
└── project/        # mounted workload
```

## 4. Toolchain Verification

During build, verify every tool with full path for anything outside `/usr/local/bin`:

```python
"/root/.local/bin/claude --version",
"rustc --version",
"cargo --version",
"git --version",
"gh --version",
"node --version",
"npm --version",
"bun --version",
```

Do NOT rely on PATH mutation inside a single RUN layer for verification; Modal chains RUN commands but environment persistence across them is not guaranteed.

## 5. Claude Code Install

Installer places binary at `~/.local/bin/claude` and warns that PATH is missing. Two fixes:

- Build-time: verify with `/root/.local/bin/claude --version`
- Runtime: include `/home/workspace/.local/bin` in IMAGE PATH env

## 6. Tag Naming Convention

Use `<name>:<major>-<YYYYMMDD>` plus `latest` and `<major>` symlinks.

Examples:
- `bl1nk-rust:latest`
- `bl1nk-rust:v2`
- `bl1nk-rust:v2-20260702`

Forbidden: `v2-02-07-2026`, `20260702-v2`.

Note: `modal image names delete` does NOT exist in current Modal CLI. To clean stale tags, use the dashboard or API. Only `list` is available.

## 7. Verification

After build:

```bash
modal image names list
```

Expected output shows all three tags mapped to the same Image ID.

## 8. Resource Limits

`image.build()` does NOT accept `timeout`, `cpu`, or `memory`. Those kwargs apply to `@app.function`, not image builds. For long builds, rely on Modal's default build timeout or use `modal container` for custom runtimes.

## 9. Long Builds

Foreground terminal has 600s max. For longer builds use:

```python
terminal(command, background=True, notify_on_complete=True, timeout=7200)
```

## 10. Rust Image Specifics

- Symlink cargo and bun into `/usr/local/bin/` so runtime user inherits them.
- Keep `rustup` default toolchain install under root; runtime user reads via PATH or symlinks.

## 11. Service Image Pattern (STRICT SEPARATION)

Build and deploy MUST be in separate files. `@app.function(... gpu=...)` and `@modal.asgi_app()` in the same file breaks local state initialization.

### build_<service>.py

- Base image + apt installs + pip installs + add_local_file(\"service.py\", \"/home/workspace/service.py\")
- Build and publish tags
- No `@app.function`, no `@modal.asgi_app()`

```python
import modal

APP_NAME = "bl1nk-search"

app = modal.App.lookup(APP_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(...)
    .run_commands(...)
    .env({...})
    .pip_install(...)
    .add_local_file("search_service.py", "/home/workspace/search_service.py")
)

with modal.enable_output():
    built = image.build(app)

built.publish("bl1nk-search:latest")
built.publish("bl1nk-search:v1")
built.publish("bl1nk-search:v1-20260702")
```

### deploy_<service>.py

- Pull published image with `modal.Image.from_name("bl1nk-search:latest")`
- Register GPU ASGI function
- Load service module lazily inside `api()` to avoid import-time side effects

```python
import modal

APP_NAME = "bl1nk-search"
IMAGE_NAME = "bl1nk-search:latest"

app = modal.App.lookup(APP_NAME, create_if_missing=True)
image = modal.Image.from_name(IMAGE_NAME)

@app.function(
    image=image,
    gpu="L4",
    timeout=7200,
)
@modal.asgi_app()
def api():
    from search_service import app as fastapi_app
    return fastapi_app
```

## 12. GPU Choice for Embedding + Reranker

Embedding 0.6B and reranker workloads need only L4:

- Default choice: `gpu="L4"`
- Skip A100/H100 for these model sizes
- Load models lazily in `@app.function(...)` startup, not during image build

## 13. Model Selection

User-preferred models for bl1nk-search:

- Embedding: Qwen3 Embedding 0.6B (`Qwen/Qwen3-Embedding-0.6B`) — strong multilingual + code support
- Reranker: BAAI BGE Reranker v2-M3 (`BAAI/bge-reranker-v2-m3`) — multilingual cross-encoder

If user wants same-family stack: Qwen3 Reranker 0.6B is acceptable fallback, but default is BGE v2-M3.

## 14. Health Endpoint Contract

Service health endpoints should expose component readiness:

```json
{
  "status": "ok",
  "latency_ms": 0,
  "services": {
    "vector_store": "ok",
    "r2": "ok",
    "embedder": "ok",
    "reranker": "ok"
  },
  "trace_id": "string"
}
```

All mutating endpoints MUST return `trace_id` in both success and error payloads.

## 15. bl1nk-search Spec Reference

See `references/bl1nk-search-v1-spec.md` for the complete API contract (Index, Query, Update, Delete, Health), data models, error codes, trace_id requirements, and curl examples.

API endpoints:
- POST /index
- POST /query
- POST /update
- POST /delete
- GET /health

Auth: Bearer token required for all mutating endpoints except /health.

Concurrency: stateless API layer, last-write-wins unless version provided, idempotent index/update by id.

Soft delete is default; hard delete is an optional flag.

## Pitfalls

- **Modal costs money per run.** Every `modal run` and `modal shell` invocation incurs compute charges. Do NOT test iteratively on Modal - get the image right locally first, build once, then use.
- **Don't co-locate build and deploy logic.** User corrected: build script for image; deploy script for service. Mixing them causes local state errors.
- **`add_local_file` must be LAST in image build chain.** Modal raises `InvalidError` if you run build steps after `add_local_file`. Either put it at the end, or keep build and deploy separate.
- **`@modal.local_entrypoint()` is not available** in this Modal SDK version. Use plain `modal run <file>.py` instead.
- **`image.build()` does NOT accept resource kwargs.** Do not pass timeout/cpu/memory.
- **Don't create new files when existing ones work.** When user says copy from location X, don't create at location Y. Use what exists.
- **Load heavy models lazily.** Do not instantiate transformers/torch models at module import time in the service image. Load inside `@app.function` startup to ensure GPU context exists.
- **Match Hermes sandbox resources for consistency.** When building Modal images for use with Hermes, match the sandbox config: `container_cpu: 1`, `container_memory: 5120` (MB).
