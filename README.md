# bl1nk-modal

Personal monorepo สำหรับแอปที่รันบน [Modal](https://modal.com) เพื่อเป็นโครงสร้างพื้นฐานให้ AI coding agent — unified agent gateway, sandbox runner, ระบบ vector search และ Rust engine สำหรับติดป้าย PR/issue อัตโนมัติ

## เอาไปใช้ตั้งค่า GitHub "About"

**Description:** `Monorepo แอปส่วนตัวที่รันบน Modal สำหรับเป็นโครงสร้างพื้นฐานของ AI coding agent — unified agent gateway (strategy pattern dispatch), ระบบ search แบบ embedding/rerank และ Rust engine สำหรับติดป้าย PR/issue อัตโนมัติ`

**Topics:** `modal, serverless, python, rust, fastapi, ai-agents, agent-infrastructure, sandbox, vector-search, embeddings, pyo3, monorepo, claude-code, devtools`

## มีอะไรอยู่ในนี้บ้าง

| โครงสร้าง | ทำอะไร |
| --- | --- |
| `modal-apps/bl1nk-app` | Unified agent gateway + subagents (strategy dispatch) |
| `modal-apps/bl1nk-search` | Search service (FastAPI + embedding + reranker) |
| `modal-images` | Base image builds (`bl1nk-agent`, `bl1nk-rust`, `bl1nk-search`) |
| `conductor` | บริบทของโปรเจกต์ |

## เริ่มต้นใช้งาน

```bash
# bl1nk-app
cd modal-apps/bl1nk-app && uv sync

# bl1nk-search (separate)
cd modal-apps/bl1nk-search && uv sync
```

ดูรายละเอียดคำสั่ง build/test/deploy ทั้งหมดได้ที่ [`QWEN.md`](./QWEN.md)

บนเครื่อง Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

## อยากรู้เพิ่ม

- [`QWEN.md`](./QWEN.md)
- [`conductor/index.md`](./conductor/index.md)
- [`BL1NK_SEARCH_V1_SPEC.md`](./docs/BL1NK_SEARCH_V1_SPEC.md)
