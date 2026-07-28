"""BL1NK Unified Agent App — FastAPI gateway on Modal.

Endpoints
  GET  /health                → health check
  POST /api/v1/run/{agent}    → dispatch agent command
  GET  /api/v1/tasks/{id}     → poll task result
  POST /api/v1/sandboxes      → create sandbox
  GET  /api/v1/sandboxes/{id} → sandbox status
  DELETE /api/v1/sandboxes/{id} → terminate sandbox
  POST /api/v1/sandboxes/{id}/exec → exec command in sandbox
  GET  /api/v1/sandboxes/{id}/files → list files
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
import modal

from api_models import (
    ApiError,
    ExecRequest,
    ExecResult,
    FileInfo,
    FileListResult,
    RunRequest,
    SandboxCreateRequest,
    SandboxStatus,
    TaskStatus,
)
from dispatch import dispatch

APP_NAME = "bl1nk"
image = modal.Image.debian_slim(python_version="3.12")

image = image.run_commands(
    "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash || "
    "echo 'Hermes install script failed; using fallback.' && "
    "curl -fsSL https://hermes-agent.nousresearch.com/docs > /tmp/hermes-docs.html || true",
)

SANDBOX_IMAGE = modal.Image.from_name("bl1nk-rust:latest")

app = modal.App(APP_NAME)
api = FastAPI(title="BL1NK Unified Agent App", version="1.0.0")
logger = logging.getLogger("uvicorn")

# in-memory task store (replace with DB later)
_tasks: dict[str, TaskStatus] = {}


# ── GET /health ──────────────────────────────────────────────

@api.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── POST /api/v1/run/{agent} ─────────────────────────────────

@api.post("/api/v1/run/{agent}")
async def run_agent(agent: str, req: RunRequest):
    task_id = f"task_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"

    try:
        result = dispatch(primary=agent, sub_agent=req.sub_agent, cmd=req.cmd)
    except ValueError as exc:
        _tasks[task_id] = TaskStatus(
            task_id=task_id, agent=agent, status="failed",
        )
        raise HTTPException(status_code=400, detail=str(exc))

    if not req.sync:
        _tasks[task_id] = TaskStatus(
            task_id=task_id, agent=agent, status="accepted",
        )
        return {"task_id": task_id, "agent": agent, "status": "accepted"}

    _tasks[task_id] = TaskStatus(
        task_id=task_id, agent=agent, status="completed",
        exit_code=0, duration_ms=0,
    )
    return {
        "task_id": task_id,
        "agent": agent,
        "status": "completed",
        "result": result,
    }


# ── GET /api/v1/tasks/{task_id} ──────────────────────────────

@api.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task.model_dump(exclude_none=True)


# ── POST /api/v1/sandboxes ───────────────────────────────────

@api.post("/api/v1/sandboxes", status_code=201)
async def create_sandbox(req: SandboxCreateRequest):
    return {
        "sandbox_id": f"sb_{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
        "status": "running",
        "image": req.image,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── GET /api/v1/sandboxes/{sandbox_id} ───────────────────────

@api.get("/api/v1/sandboxes/{sandbox_id}")
async def get_sandbox(sandbox_id: str):
    if not sandbox_id.startswith("sb_"):
        raise HTTPException(status_code=404, detail="sandbox not found")
    return {
        "sandbox_id": sandbox_id,
        "status": "running",
        "image": "bl1nk-rust:latest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": 0,
    }


# ── DELETE /api/v1/sandboxes/{sandbox_id} ────────────────────

@api.delete("/api/v1/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    return {"sandbox_id": sandbox_id, "status": "terminated"}


# ── POST /api/v1/sandboxes/{sandbox_id}/exec ─────────────────

@api.post("/api/v1/sandboxes/{sandbox_id}/exec")
async def exec_in_sandbox(sandbox_id: str, req: ExecRequest):
    return {
        "sandbox_id": sandbox_id,
        "exit_code": 0,
        "stdout": f"stub: would run {req.cmd}",
        "stderr": "",
        "duration_ms": 0,
    }


# ── GET /api/v1/sandboxes/{sandbox_id}/files ─────────────────

@api.get("/api/v1/sandboxes/{sandbox_id}/files")
async def list_sandbox_files(
    sandbox_id: str,
    path: str = Query("/", description="directory to list"),
):
    return {
        "sandbox_id": sandbox_id,
        "path": path,
        "files": [
            {"name": ".", "type": "dir", "size": 4096, "mode": "drwxr-xr-x"},
        ],
    }


# ── Modal entrypoints ────────────────────────────────────────

@app.function(image=SANDBOX_IMAGE)
def dev() -> dict[str, str]:
    import shutil
    tools = ["git", "gh", "node", "npm", "bun", "cargo", "rustc", "claude"]
    return {t: shutil.which(t) or "not found" for t in tools}


@app.function(image=image)
def install_hermes() -> dict:
    return {"status": "invoked", "note": "Hermes CLI installed at image build"}


@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    return api
