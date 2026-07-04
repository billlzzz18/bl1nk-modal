import modal
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
import tempfile

APP_NAME = "modal-sandbox"

app = modal.App(APP_NAME)
api = FastAPI(title="Modal Sandbox API", version="0.2.0")


class SandboxCreateRequest(BaseModel):
    cmd: list[str] = ["sleep", "infinity"]
    timeout: int = 3600
    cpu: float = 1.0
    memory: int = 1024
    env: dict[str, str] = {}
    image_name: str = "bl1nk-rust:latest"


class ExecRequest(BaseModel):
    cmd: list[str]


def _make_image(image_name: str) -> modal.Image:
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
        )
        .env({"HOME": "/home/workspace", "PATH": "/home/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin"})
    )


image = _make_image("bl1nk-rust:latest")


@api.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@api.get("/ready")
def ready():
    return {"ready": True}


@api.get("/version")
def version():
    return {"app": APP_NAME, "image": "bl1nk-rust:latest"}


@api.get("/info")
def info():
    return {"runtime": "modal", "app": APP_NAME, "architecture": "sandbox-id-based"}


@api.post("/sandbox")
def create(req: SandboxCreateRequest):
    """Create a new sandbox and return its ID."""
    sandbox_image = _make_image(req.image_name)
    sb = modal.Sandbox.create(
        *req.cmd,
        image=sandbox_image,
        app=app,
        timeout=req.timeout,
        cpu=req.cpu,
        memory=req.memory,
        env=req.env,
    )
    return {"sandbox_id": sb.object_id, "status": "created"}


@api.delete("/sandbox/{sid}")
def delete(sid: str):
    """Terminate a sandbox by ID."""
    sb = modal.Sandbox.from_id(sid)
    sb.terminate()
    return {"deleted": True, "sandbox_id": sid}


@api.post("/sandbox/{sid}/exec")
def exec_cmd(sid: str, req: ExecRequest):
    """Execute a command in an existing sandbox."""
    sb = modal.Sandbox.from_id(sid)
    p = sb.exec(*req.cmd)
    p.wait()
    return {
        "sandbox_id": sid,
        "returncode": p.returncode,
        "stdout": p.stdout.read() if p.stdout else "",
        "stderr": p.stderr.read() if p.stderr else "",
    }


@api.post("/sandbox/{sid}/upload")
async def upload(sid: str, file: UploadFile):
    """Upload a file to a sandbox."""
    sb = modal.Sandbox.from_id(sid)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(await file.read())
        local = f.name
    sb.filesystem.copy_from_local(local, "/" + file.filename)
    return {"uploaded": file.filename, "sandbox_id": sid}


@api.get("/sandbox/{sid}/download")
def download(sid: str, path: str):
    """Download a file from a sandbox."""
    sb = modal.Sandbox.from_id(sid)
    dst = tempfile.mktemp()
    sb.filesystem.copy_to_local(path, dst)
    return {"saved_to": dst, "sandbox_id": sid}


@api.get("/sandbox/{sid}/files")
def list_files(sid: str, path: str = "/"):
    """List files in a sandbox directory."""
    sb = modal.Sandbox.from_id(sid)
    files = sb.filesystem.list_files(path)
    return {"sandbox_id": sid, "path": path, "files": files}


@api.get("/sandbox/{sid}")
def get_status(sid: str):
    """Get sandbox status via poll."""
    sb = modal.Sandbox.from_id(sid)
    result = sb.poll()
    return {
        "sandbox_id": sid,
        "status": "running" if result is None else "terminated",
        "returncode": result.returncode if result else None,
    }


@api.get("/sandbox/{sid}/logs")
def logs(sid: str):
    """Get sandbox logs."""
    sb = modal.Sandbox.from_id(sid)
    return {"sandbox_id": sid, "result": str(sb.poll())}


@app.function(image=image)
def dev() -> dict[str, str]:
    """Smoke-test entrypoint: verify the toolchain baked into the image is on PATH."""
    import shutil

    tools = ["git", "gh", "node", "npm", "bun", "cargo", "rustc"]
    results = {}
    for tool in tools:
        path = shutil.which(tool)
        results[tool] = path if path is not None else "not found"
    return results


@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    return api
