# bl1nk-modal

Personal monorepo ของแอปที่รันบน [Modal](https://modal.com) เพื่อเป็นโครงสร้างพื้นฐานให้ AI coding agent (Claude Code, agy/Antigravity, opencode) และตัวเจ้าของ repo เอง — sandbox กลาง, webhook task tracker, ระบบ search และ engine ติดป้าย PR/issue อัตโนมัติ ไม่ใช่โปรดักต์สำหรับคนอื่น เป็นของใช้ส่วนตัวที่แชร์ workspace เดียวกันระหว่างคนกับ agent

## เอาไปใช้ตั้งค่า GitHub "About"

ก็อปสองก้อนนี้ไปใส่ใน repo settings ได้เลย (ปุ่มเฟือง ⚙️ ข้าง "About" ในหน้า repo):

**Description:**

```
Monorepo แอปส่วนตัวที่รันบน Modal สำหรับเป็นโครงสร้างพื้นฐานของ AI coding agent — webhook task tracker, sandbox orchestrator, ระบบ search แบบ embedding/rerank และ Rust engine สำหรับติดป้าย PR/issue อัตโนมัติ
```

**Topics:**

```
modal, serverless, python, rust, fastapi, ai-agents, agent-infrastructure, sandbox, webhook-service, vector-search, embeddings, pyo3, monorepo, claude-code, devtools
```

## มีอะไรอยู่ในนี้บ้าง

Repo นี้เป็น monorepo แบบ deploy แยกอิสระ — แต่ละแอปใน `modal-apps/*` และ `modal-images/` เป็น Modal App ของตัวเอง ไม่แชร์ database หรือ runtime state กัน:

| แอป | ทำอะไร |
| --- | --- |
| `modal-apps/modal-runner` | FastAPI webhook → CrateDB task tracker + แจ้งเตือนผ่าน LINE Notify |
| `modal-apps/modal-agy` | Orchestrator สำหรับ sandbox agent `agy` (Google Antigravity) |
| `modal-apps/modal-sandbox` | Sandbox API ทั่วไป (create/exec/upload/download ผ่าน `modal.Sandbox`) |
| `modal-apps/modal-opencode/engine` | `sovereign_engine` — Rust/pyo3 crate ตรวจจับและติดป้าย label ของ issue/PR อัตโนมัติ |
| `modal-images` | Build image กลาง (Rust/Node/Bun/gh/Claude CLI) + `bl1nk-search` บริการ embedding/rerank search |

## เริ่มต้นใช้งาน

แต่ละโปรเจกต์อิสระจากกัน ต้อง `cd` เข้าไปในโฟลเดอร์นั้นก่อนรันคำสั่งใดๆ ใช้ `uv sync` (ไม่ใช่ `pip install`) ดูรายละเอียดคำสั่ง build/test/deploy ทั้งหมดได้ที่ [`CLAUDE.md`](./CLAUDE.md)

บนเครื่อง Windows ที่ยังไม่มีอะไรติดตั้งเลย รันสคริปนี้เพื่อติดตั้งของที่ต้องใช้ทั้งหมด (`uv`, Rust toolchain, Modal CLI, `pre-commit`) และ sync ทุกโปรเจกต์ให้ในคำสั่งเดียว:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

## อยากรู้เพิ่ม

- [`CLAUDE.md`](./CLAUDE.md) — คำสั่ง build/test/deploy และสถาปัตยกรรมข้ามไฟล์ สำหรับทำงานในโค้ดจริง
- [`conductor/`](./conductor/) — บริบทของโปรเจกต์ (product vision, tech stack, ทีมทำงานยังไง, track งานที่กำลังทำ) เริ่มอ่านที่ [`conductor/index.md`](./conductor/index.md)
- [`BL1NK_SEARCH_V1_SPEC.md`](./BL1NK_SEARCH_V1_SPEC.md) — spec เป้าหมายของ `bl1nk-search` (ของจริงใน `modal-images/search_service.py` ยังไม่ตรง spec ทั้งหมด)
