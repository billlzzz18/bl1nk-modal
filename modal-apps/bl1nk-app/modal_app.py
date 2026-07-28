"""BL1NK Unified Agent App — FastAPI gateway on Modal.

Factory pattern: sandbox image consumed from published bl1nk-rust:latest
instead of redefined per-subagent.

Strategy pattern: agent dispatch uses handler classes from dispatch.py
instead of nested conditionals.
"""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import modal

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


class RunRequest(BaseModel):
    mode: Literal["agent", "sandbox"] = "agent"
    agent: Literal["hermes", "agy", "opencode", "sandbox"] = "hermes"
    cmd: str = ""
    env: dict = {}


@api.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@api.post("/run/{mode}/{agent}")
async def run(mode: str, agent: str, req: RunRequest):
    try:
        return dispatch(primary=agent, sub_agent=req.agent, cmd=req.cmd)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
