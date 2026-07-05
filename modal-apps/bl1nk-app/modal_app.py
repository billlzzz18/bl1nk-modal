import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import modal

APP_NAME = "bl1nk"
image = modal.Image.debian_slim(python_version="3.12")

# Hermes install script is executed during image build
image = image.run_commands(
    "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash || "
    "echo 'Hermes install script failed; using fallback.' && "
    "curl -fsSL https://hermes-agent.nousresearch.com/docs > /tmp/hermes-docs.html || true",
)

app = modal.App(APP_NAME)
api = FastAPI(title="BL1NK Unified Agent App", version="1.0.0")
logger = logging.getLogger("uvicorn")


class RunRequest(BaseModel):
    mode: Literal["agent", "sandbox"] = "agent"
    agent: Literal["hermes", "agy", "opencode", "sandbox"] = "hermes"
    cmd: str = ""
    env: dict = {}


def _make_sandbox_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "curl", "git", "ca-certificates", "build-essential",
            "pkg-config", "libssl-dev", "zip", "unzip",
        )
        .run_commands(
            "curl https://sh.rustup.rs -sSf | sh -s -- -y",
            "ln -sf /root/.cargo/bin/* /usr/local/bin/",
            "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
            "apt-get install -y nodejs",
            "curl -fsSL https://bun.sh/install | bash",
            "ln -sf /root/.bun/bin/bun /usr/local/bin/",
            "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | "
            "dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
            "apt-get update",
            "apt-get install -y gh",
            "curl -fsSL https://claude.ai/install.sh | bash",
            "/root/.local/bin/claude --version",
            "useradd -m -s /bin/bash workspace",
            "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
            "chown -R workspace:workspace /home/workspace",
            "rustc --version",
            "cargo --version",
            "git --version",
            "gh --version",
            "node --version",
            "npm --version",
            "bun --version",
        "python3 -m pip install modal"
        "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-x86_64-unknown-linux-musl.tar.gz | tar -xz"
        "mv rg /usr/local/bin/rg && chmod +x /usr/local/bin/rg"
        "rg --version || true"
        )
        .env({
            "HOME": "/home/workspace",
            "PATH": "/home/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin",
        })
    )


@api.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@api.post("/run/{mode}/{agent}")
async def run(mode: str, agent: str, req: RunRequest):
    primary = agent
    sub = req.agent
    cmd = req.cmd

    # ACP / HEADLESS pattern:
    # - Hermes as primary: if caller asks for agy/opencode/sandbox, spawn agent-in-process or delegate to Modal sandbox
    # - AGY as primary: if caller asks for opencode/sandbox, delegate here
    # - OpenCode: headless only

    if primary == "hermes":
        if sub in {"agy", "opencode", "sandbox"}:
            # Hermes dispatches to subagent via Modal sandbox
            return {"primary": "hermes", "delegated_to": sub, "status": "dispatched"}
        # run locally
        return {"primary": "hermes", "cmd": cmd or "hermes --help"}
    if primary == "agy":
        if sub in {"opencode", "sandbox"}:
            return {"primary": "agy", "delegated_to": sub, "status": "dispatched"}
        return {"primary": "agy", "cmd": cmd or "agy --help"}
    if primary == "opencode":
        # Headless mode only
        return {"primary": "opencode", "mode": "headless", "cmd": cmd}
    if primary == "sandbox":
        return {"primary": "sandbox", "cmd": cmd or "sleep infinity"}
    raise HTTPException(400, f"Unknown agent {agent}")


@app.function(image=_make_sandbox_image())
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
