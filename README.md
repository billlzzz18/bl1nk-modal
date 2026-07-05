# bl1nk-modal

Personal monorepo ของแอปที่รันบน [Modal](https://modal.com) เพื่อเป็นโครงสร้างพื้นฐานให้ AI coding agent — sandbox กลาง, webhook task tracker, ระบบ search และ engine ติดป้าย PR/issue อัตโนมัติ

## เอาไปใช้ตั้งค่า GitHub "About"

**Description:** `Monorepo แอปส่วนตัวที่รันบน Modal สำหรับเป็นโครงสร้างพื้นฐานของ AI coding agent — webhook task tracker, sandbox orchestrator, ระบบ search แบบ embedding/rerank และ Rust engine สำหรับติดป้าย PR/issue อัตโนมัติ`

**Topics:** `modal, serverless, python, rust, fastapi, ai-agents, agent-infrastructure, sandbox, webhook-service, vector-search, embeddings, pyo3, monorepo, claude-code, devtools`

## มีอะไรอยู่ในนี้บ้าง

| โครงสร้าง | ทำอะไร |
| --- | --- |
| `modal_apps/modal_app` | Unified agent app + subagents |
| `modal-images` | Build image กลาง + `bl1nk-search` |
| `conductor` | บริบทของโปรเจกต์ |

## เริ่มต้นใช้งาน

ใช้ `uv sync` ใน `modal-apps/modal-app` ได้เลย
ดูรายละเอียดคำสั่ง build/test/deploy ทั้งหมดได้ที่ [`CLAUDE.md`](./CLAUDE.md)

บนเครื่อง Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

## อยากรู้เพิ่ม

- [`CLAUDE.md`](./CLAUDE.md)
- [`conductor/index.md`](./conductor/index.md)
- [`BL1NK_SEARCH_V1_SPEC.md`](./BL1NK_SEARCH_V1_SPEC.md)
