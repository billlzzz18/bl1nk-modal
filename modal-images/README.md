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
- `bl1nk-rust:v2-02-07-2026`

### Resources
- Timeout: 2 ชั่วโมง (7200 วินาที)
- CPU: 2 core
- RAM: 8 GB

### Usage

```bash
modal deploy build_bl1nk_rust.py
```

หรือรัน local:
```bash
modal run build_bl1nk_rust.py
```