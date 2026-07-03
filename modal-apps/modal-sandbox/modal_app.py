import modal
from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel
import tempfile

APP_NAME = "modal-sandbox"

app = modal.App(APP_NAME)
image = modal.Image.from_registry("bl1nk-rust:latest")
api = FastAPI(title="Modal Sandbox API", version="0.1.0")

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None

class CreateSandboxRequest(BaseModel):
    cmd: list[str] = ["sleep", "infinity"]
    timeout: int = 3600
    cpu: float = 1
    memory: int = 1024
    env: dict[str, str] = {}

class ExecRequest(BaseModel):
    cmd: list[str]

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/ready")
def ready():
    return {"ready":True}

@app.get("/version")
def version():
    return {"app":APP_NAME,"image":"bl1nk-rust:latest"}

@app.get("/info")
def info():
    return {"runtime":"modal","app":APP_NAME}

@app.post("/sandbox")
def create(req: CreateSandboxRequest):
    sb = modal.Sandbox.create(
        *req.cmd,
        app=app,
        image=image,
        timeout=req.timeout,
        cpu=req.cpu,
        memory=req.memory,
        env=req.env,
    )
    return {"sandbox_id": sb.object_id}

@app.delete("/sandbox/{sid}")
def delete(sid:str):
    sb = modal.Sandbox.from_id(sid)
    sb.terminate()
    return {"deleted":True}

@app.post("/sandbox/{sid}/exec")
def exec_cmd(sid:str, req:ExecRequest):
    sb = modal.Sandbox.from_id(sid)
    p = sb.exec(*req.cmd)
    p.wait()
    return {
        "returncode": p.returncode,
        "stdout": p.stdout.read() if p.stdout else "",
        "stderr": p.stderr.read() if p.stderr else "",
    }

@app.post("/sandbox/{sid}/upload")
async def upload(sid:str, file:UploadFile):
    sb=modal.Sandbox.from_id(sid)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(await file.read())
        local=f.name
    sb.filesystem.copy_from_local(local, "/" + file.filename)
    return {"uploaded":file.filename}

@app.get("/sandbox/{sid}/download")
def download(sid:str, path:str):
    sb=modal.Sandbox.from_id(sid)
    dst=tempfile.mktemp()
    sb.filesystem.copy_to_local(path,dst)
    return {"saved_to":dst}

@app.get("/sandbox/{sid}/logs")
def logs(sid:str):
    sb=modal.Sandbox.from_id(sid)
    return {"result":str(sb.poll())}

@app.function(image=image)
def dev():
    pass

@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    return api
