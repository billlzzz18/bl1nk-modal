"""BL1NK Agent API service — sandbox management endpoints.

Imported by modal_app.py's FastAPI endpoint function.
Pattern from modal-images/search_service.py.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional


app = FastAPI(title="BL1NK Unified Agent App", version="1.0.0")

# SandboxManager is injected at startup
_mgr = None


def set_sandbox_manager(mgr):
    global _mgr
    _mgr = mgr


class RunRequest(BaseModel):
    cmd: str
    timeout: int = 120


class SandboxRequest(BaseModel):
    task_id: Optional[str] = None
    timeout: int = 3600
    max_lifetime: int = 7200


@app.get("/")
def root():
    return {
        "app": "bl1nk",
        "endpoints": {
            "sandbox": ["/sandbox/create", "/sandbox/exec/{task_id}", "/sandbox/list", "/sandbox/destroy/{task_id}"],
            "legacy": ["/health", "/run/{mode}/{agent}"],
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/sandbox/create")
def create_sandbox(req: SandboxRequest):
    task_id = _mgr.create_sandbox(
        task_id=req.task_id,
        timeout=req.timeout,
        max_lifetime=req.max_lifetime,
    )
    return {"task_id": task_id, "status": "created", "max_lifetime": req.max_lifetime}


@app.post("/sandbox/exec/{task_id}")
def exec_in_sandbox(task_id: str, req: RunRequest):
    result = _mgr.exec(task_id, req.cmd, timeout=req.timeout)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/sandbox/list")
def list_sandboxes():
    return {"sandboxes": _mgr.list_sandboxes()}


@app.delete("/sandbox/destroy/{task_id}")
def destroy_sandbox(task_id: str):
    ok = _mgr.destroy_sandbox(task_id)
    if not ok:
        raise HTTPException(404, f"Sandbox {task_id} not found")
    return {"task_id": task_id, "status": "destroyed"}


@app.post("/run/{mode}/{agent}")
async def run(mode: str, agent: str, req: RunRequest):
    if agent == "sandbox":
        task_id = _mgr.create_sandbox(max_lifetime=3600)
        result = _mgr.exec(task_id, req.cmd or "echo 'sandbox ready'", timeout=req.timeout)
        return {"task_id": task_id, **result}
    return {"agent": agent, "cmd": req.cmd}
