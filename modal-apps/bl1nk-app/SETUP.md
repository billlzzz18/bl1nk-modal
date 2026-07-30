# Setup

## Base Image

`bl1nk-rust:latest` ต้อง build ก่อน deploy app:

```bash
cd modal-images
modal run build_bl1nk_rust.py
```

Image นี้ประกอบด้วย: Rust toolchain, Node.js, GitHub CLI, Claude CLI, Bun

## Deploy

```bash
cd modal-apps/bl1nk-app
modal deploy modal_app.py --name bl1nk
```

## Local serve

```bash
modal serve modal_app.py
```

## Run tests

```bash
cd modal-apps/bl1nk-app
uv run pytest tests/ -v
```
