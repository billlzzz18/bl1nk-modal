import asyncio
import logging
import threading
import time
import uuid
from typing import Any, Optional

import modal

# ponytail: inline because Modal containers don't have modal-images/ on sys.path.
# Keep in sync with build_bl1nk_agent.py SHARED_INSTALL_COMMANDS.
SHARED_INSTALL_COMMANDS = [
    "curl https://sh.rustup.rs -sSf | sh -s -- -y",
    "rustup default stable",
    "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
    "apt-get install -y nodejs",
    "curl -fsSL https://bun.sh/install | bash",
    "ln -sf /root/.bun/bin/bun /usr/local/bin/",
    "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
    'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
    "apt-get update",
    "apt-get install -y gh",
    "curl -fsSL https://claude.ai/install.sh | bash",
    "/root/.local/bin/claude --version",
    "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-x86_64-unknown-linux-musl.tar.gz | tar -xz",
    "mv ripgrep-14.1.1-x86_64-unknown-linux-musl/rg /usr/local/bin/rg && chmod +x /usr/local/bin/rg",
    "rg --version || true",
    "curl -fsSL -o /tmp/hermes-install.sh https://hermes-agent.nousresearch.com/install.sh && bash /tmp/hermes-install.sh",
    "curl -fsSL -o /tmp/qwen-install.sh https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen-standalone.sh && bash /tmp/qwen-install.sh",
    "rm -rf /usr/local/lib/hermes-agent",
    "rm -rf /tmp/* /var/tmp/*",
    "ln -sf /root/.local/bin/qwen /usr/local/bin/qwen",
    "ln -sf /root/.local/bin/claude /usr/local/bin/claude",
    # Move Rust toolchain to workspace-owned dir so workspace user can write
    "mv /root/.rustup /home/workspace/.rustup",
    "mv /root/.cargo /home/workspace/.cargo",
    "ln -sf /home/workspace/.cargo/bin/cargo /usr/local/bin/cargo",
    "ln -sf /home/workspace/.cargo/bin/rustup /usr/local/bin/rustup",
    "ln -sf /home/workspace/.cargo/bin/rustc /usr/local/bin/rustc",
    "chown -R workspace:workspace /home/workspace/.rustup /home/workspace/.cargo",
]

APP_NAME = "bl1nk"
image = modal.Image.from_name("bl1nk-agent:latest")
app = modal.App(APP_NAME)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AsyncWorker — background event loop for Modal SDK async calls
# ---------------------------------------------------------------------------


class _AsyncWorker:
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=30)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def run_coroutine(self, coro, timeout=600):
        if self._loop is None or self._loop.is_closed():
            if asyncio.iscoroutine(coro):
                coro.close()
            raise RuntimeError("AsyncWorker loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def stop(self):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=10)


# ---------------------------------------------------------------------------
# SandboxManager — create/exec/destroy with auto-timeout
# ---------------------------------------------------------------------------


class SandboxManager:
    """Modal sandbox manager with auto-timeout to prevent cost leaks."""

    DEFAULT_TIMEOUT = 3600
    DEFAULT_MAX_LIFETIME = 7200
    CLEANUP_INTERVAL = 300

    def __init__(self):
        self._worker: _AsyncWorker | None = None
        self._sandboxes: dict[str, dict] = {}
        self._cleanup_thread: Optional[threading.Thread] = None

    def _ensure_worker(self):
        if self._worker is None:
            self._worker = _AsyncWorker()
            self._worker.start()
            self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        def _cleanup_loop():
            while True:
                time.sleep(self.CLEANUP_INTERVAL)
                self._cleanup_expired()

        self._cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_expired(self):
        now = time.time()
        expired = [
            task_id
            for task_id, info in self._sandboxes.items()
            if now - info["created_at"] > info["max_lifetime"]
        ]
        for task_id in expired:
            logger.warning("Auto-destroying expired sandbox: task=%s", task_id)
            self.destroy_sandbox(task_id)

    def create_sandbox(
        self,
        task_id: str | None = None,
        image_spec: Any = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_lifetime: int = DEFAULT_MAX_LIFETIME,
    ) -> str:
        self._ensure_worker()
        task_id = task_id or uuid.uuid4().hex[:12]
        img = image_spec or image

        async def _create():
            modal_app = await modal.App.lookup.aio(APP_NAME, create_if_missing=True)
            sandbox = await modal.Sandbox.create.aio(
                "sleep",
                "infinity",
                image=img,
                app=modal_app,
                timeout=timeout,
            )
            # Get Modal task_id from sandbox object - try various methods
            modal_task_id = None
            # Try direct attributes
            for attr in ["task_id", "object_id", "id", "_id", "task"]:
                val = getattr(sandbox, attr, None)
                if val and isinstance(val, str) and val.startswith("ta-"):
                    modal_task_id = val
                    break
            # Try repr
            if not modal_task_id:
                sandbox_repr = repr(sandbox)
                import re

                match = re.search(r"ta-[A-Za-z0-9]+", sandbox_repr)
                if match:
                    modal_task_id = match.group(0)
            return modal_app, sandbox, modal_task_id

        modal_app, sandbox, modal_task_id = self._worker.run_coroutine(_create(), timeout=300)
        self._sandboxes[task_id] = {
            "app": modal_app,
            "sandbox": sandbox,
            "modal_task_id": modal_task_id,
            "created_at": time.time(),
            "max_lifetime": max_lifetime,
        }
        logger.info(
            "Sandbox created: task=%s, modal_task=%s (max_lifetime=%ds)",
            task_id,
            modal_task_id,
            max_lifetime,
        )
        return task_id

    def exec(
        self,
        task_id: str,
        command: str,
        timeout: int = 120,
    ) -> dict:
        self._ensure_worker()
        entry = self._sandboxes.get(task_id)
        if not entry:
            return {"error": f"Sandbox {task_id} not found", "exit_code": 1}

        sandbox = entry["sandbox"]

        # If we don't have modal_task_id yet, try to get it from env
        if not entry.get("modal_task_id"):

            async def _get_task_id():
                proc = await sandbox.exec.aio("bash", "-c", "echo $MODAL_TASK_ID")
                output = await proc.stdout.read.aio()
                await proc.wait.aio()
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                return output.strip()

            try:
                modal_task_id = self._worker.run_coroutine(_get_task_id(), timeout=10)
                if modal_task_id and modal_task_id.startswith("ta-"):
                    entry["modal_task_id"] = modal_task_id
            except Exception:
                pass

        async def _exec():
            proc = await sandbox.exec.aio("bash", "-c", command, timeout=timeout)
            stdout = await proc.stdout.read.aio()
            stderr = await proc.stderr.read.aio()
            exit_code = await proc.wait.aio()
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            output = stdout
            if stderr:
                output = f"{stdout}\n{stderr}" if stdout else stderr
            return output, exit_code

        try:
            output, exit_code = self._worker.run_coroutine(_exec(), timeout=timeout + 30)
            return {"output": output, "exit_code": exit_code}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}

    def list_sandboxes(self) -> list[dict]:
        now = time.time()
        result = []
        for task_id, info in self._sandboxes.items():
            result.append(
                {
                    "task_id": task_id,
                    "modal_task_id": info.get("modal_task_id"),
                    "age_seconds": int(now - info["created_at"]),
                    "max_lifetime": info["max_lifetime"],
                    "remaining_seconds": max(
                        0, int(info["max_lifetime"] - (now - info["created_at"]))
                    ),
                }
            )
        return result

    def destroy_sandbox(self, task_id: str) -> bool:
        entry = self._sandboxes.pop(task_id, None)
        if not entry:
            return False

        async def _terminate():
            await entry["sandbox"].terminate.aio()

        if self._worker:
            try:
                self._worker.run_coroutine(_terminate(), timeout=15)
            except Exception:
                pass
        logger.info("Sandbox destroyed: task=%s", task_id)
        return True

    def cleanup(self):
        for task_id in list(self._sandboxes.keys()):
            self.destroy_sandbox(task_id)
        if self._worker:
            self._worker.stop()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager


# ---------------------------------------------------------------------------
# Image definition
# ---------------------------------------------------------------------------


def _make_sandbox_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "curl",
            "git",
            "ca-certificates",
            "build-essential",
            "pkg-config",
            "libssl-dev",
            "zip",
            "unzip",
        )
        .run_commands(
            "useradd -m -s /bin/bash workspace",
            "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
            "chown -R workspace:workspace /home/workspace",
            *SHARED_INSTALL_COMMANDS,
            "python3 -m pip install modal fastapi uvicorn",
            "rustc --version",
            "cargo --version",
            "git --version",
            "gh --version",
            "node --version",
            "npm --version",
            "bun --version",
        )
        .env(
            {
                "HOME": "/home/workspace",
                "PATH": "/home/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin",
                "RUSTUP_HOME": "/home/workspace/.rustup",
                "CARGO_HOME": "/home/workspace/.cargo",
            }
        )
    )


# ---------------------------------------------------------------------------
# Modal Functions
# ---------------------------------------------------------------------------


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
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    api = FastAPI(title="BL1NK Unified Agent App", version="1.0.0")
    mgr = get_sandbox_manager()

    class RunRequest(BaseModel):
        cmd: str
        timeout: int = 120

    class SandboxRequest(BaseModel):
        task_id: str | None = None
        timeout: int = 3600
        max_lifetime: int = 7200

    @api.get("/")
    def root():
        return {
            "app": "bl1nk",
            "endpoints": {
                "sandbox": [
                    "/sandbox/create",
                    "/sandbox/exec/{task_id}",
                    "/sandbox/list",
                    "/sandbox/modal-task/{task_id}",
                    "/sandbox/destroy/{task_id}",
                ],
                "legacy": ["/health", "/run/{mode}/{agent}"],
            },
        }

    @api.get("/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @api.post("/sandbox/create")
    def create_sandbox(req: SandboxRequest):
        task_id = mgr.create_sandbox(
            task_id=req.task_id,
            timeout=req.timeout,
            max_lifetime=req.max_lifetime,
        )
        return {"task_id": task_id, "status": "created", "max_lifetime": req.max_lifetime}

    @api.post("/sandbox/exec/{task_id}")
    def exec_in_sandbox(task_id: str, req: RunRequest):
        result = mgr.exec(task_id, req.cmd, timeout=req.timeout)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result

    @api.get("/sandbox/list")
    def list_sandboxes():
        return {"sandboxes": mgr.list_sandboxes()}

    @api.get("/sandbox/modal-task/{task_id}")
    def get_modal_task_id(task_id: str):
        """Get Modal task ID for a sandbox (for use with `modal shell`)."""
        entry = mgr._sandboxes.get(task_id)
        if not entry:
            raise HTTPException(404, f"Sandbox {task_id} not found")
        modal_task_id = entry.get("modal_task_id")
        if not modal_task_id:
            # Try to get it from env
            result = mgr.exec(task_id, "echo $MODAL_TASK_ID", timeout=5)
            modal_task_id = result.get("output", "").strip()
        return {"task_id": task_id, "modal_task_id": modal_task_id}

    @api.get("/sandbox/debug/{task_id}")
    def debug_sandbox(task_id: str):
        """Debug endpoint to inspect sandbox object attributes."""
        entry = mgr._sandboxes.get(task_id)
        if not entry:
            raise HTTPException(404, f"Sandbox {task_id} not found")
        sandbox = entry["sandbox"]
        # Get all attributes including private ones
        all_attrs = {}
        for k, v in vars(sandbox).items():
            all_attrs[k] = str(v)[:200]
        return {
            "task_id": task_id,
            "repr": repr(sandbox)[:500],
            "attrs": all_attrs,
            "dir": [x for x in dir(sandbox) if not x.startswith("__")],
        }

    @api.delete("/sandbox/destroy/{task_id}")
    def destroy_sandbox(task_id: str):
        ok = mgr.destroy_sandbox(task_id)
        if not ok:
            raise HTTPException(404, f"Sandbox {task_id} not found")
        return {"task_id": task_id, "status": "destroyed"}

    @api.post("/run/{mode}/{agent}")
    async def run(mode: str, agent: str, req: RunRequest):
        if agent == "sandbox":
            task_id = mgr.create_sandbox(max_lifetime=3600)
            result = mgr.exec(task_id, req.cmd or "echo 'sandbox ready'", timeout=req.timeout)
            return {"task_id": task_id, **result}
        return {"agent": agent, "cmd": req.cmd}

    return api
