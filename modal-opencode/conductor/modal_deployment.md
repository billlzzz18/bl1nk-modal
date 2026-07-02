# Modal Deployment Guide (Rust Engine)

## 1. Modal Image Definition
เพื่อให้สามารถใช้งาน Rust Engine ภายใน Modal ได้ เราต้องติดตั้ง Rust Toolchain และ `maturin` ภายใน Image definition

```python
import modal

# นิยาม Image ที่มี Rust toolchain
rust_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "clang", "pkg-config")
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        "export PATH=$PATH:$HOME/.cargo/bin",
        "pip install maturin"
    )
)

app = modal.App("sovereign-gateway", image=rust_image)
```

## 2. Building the Engine
การ Build Rust module ภายใน Modal แนะนำให้ใช้ `run_commands` เพื่อทำ `maturin build` หรือ `maturin develop`

```python
# เพิ่มโค้ด engine และ build
rust_image = (
    rust_image
    .copy_local_dir("./engine", "/root/engine")
    .run_commands(
        "cd /root/engine && maturin develop"
    )
)
```

## 3. Persistent Storage (Modal Volumes)
ใช้ Modal Volume สำหรับ SQLite เพื่อให้ข้อมูล State และ Timeline ไม่หายไปเมื่อ Container หยุดทำงาน

```python
volume = modal.Volume.from_name("sovereign-state-vol", create_if_missing=True)

@app.function(volumes={"/data": volume})
def webhook_handler(payload):
    # เชื่อมต่อ SQLite ที่ /data/state.db
    pass
```

## 4. Best Practices
- **Layer Caching:** แยกขั้นตอนการติดตั้ง `apt_install` และ `rustup` ออกจากขั้นตอนการ `copy` โค้ด เพื่อให้ Modal สามารถแคชเลเยอร์พื้นฐานได้ (ไม่ต้องโหลด Rust ใหม่ทุกครั้งที่แก้โค้ด)
- **Environment Variables:** ใช้ `modal.Secret.from_name("github-secrets")` สำหรับเก็บ API Keys
- **Build Optimization:** ใช้ `--release` flag เมื่อ deploy ขึ้น Production เพื่อประสิทธิภาพสูงสุดของ Rust Engine
