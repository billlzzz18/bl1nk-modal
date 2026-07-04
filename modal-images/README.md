# Modal Image Builds

Image build สำหรับ Modal ที่มี Rust development environment

## Image: bl1nk-rust

### Tools ที่ติดตั้ง
- Rust + Cargo (rustup)
- Node.js 22 + npm
- Bun
- GitHub CLI (gh)
- Claude CLI
- curl, git, ca-certificates, build-essential, pkg-config, libssl-dev, zip, unzip

### Tags
- `bl1nk-rust:latest`
- `bl1nk-rust:v2`
- `bl1nk-rust:v2-YYYYMMDD` (today's date, e.g. `bl1nk-rust:v2-20260702`)

All three are published automatically by `build_bl1nk_rust.py` via the shared
`_tags.publish_versioned()` helper (also used by `build_bl1nk_search.py`) —
the date is computed at build time, never hand-typed. **To bump the major
version** (`v2` → `v3`), change the one-line `MAJOR_VERSION` constant at the
top of the build script; don't hand-edit the `publish(...)` calls.

### Resources
- Timeout: 2 ชั่วโมง (7200 วินาที)
- CPU: 2 core
- RAM: 8 GB

### Usage

Build scripts publish tags via `modal run`, not `modal deploy` (`deploy` is
for serving apps, not building images):

```bash
modal run build_bl1nk_rust.py
```

## Image: bl1nk-search

Embedding + reranker search service image (`build_bl1nk_search.py`), deployed via `deploy_bl1nk_search.py`. Same tag convention (`latest` / `v1` / `v1-YYYYMMDD`), same `_tags.publish_versioned()` helper, same one-line `MAJOR_VERSION` bump:

```bash
modal run build_bl1nk_search.py
```

## Versioning: one helper, one line per bump

`_tags.py` is shared by both build scripts specifically so a rebuild never means hand-editing a version string in more than one place, or hand-typing today's date. When you need a new major version:

1. Open the build script (`build_bl1nk_rust.py` or `build_bl1nk_search.py`).
2. Change its `MAJOR_VERSION` constant.
3. Run it — `latest`, the new major tag, and today's dated tag are published together.

Everything that *consumes* these images (`modal-apps/modal-runner`, `modal-agy`, `modal-sandbox`, `modal-opencode`) pins to `:latest`, so they never need updating when a new version is published — only the build script's `MAJOR_VERSION` line does.
