# Verified AI Search Runtime Stack

This reference captures the working runtime stack for `bl1nk-search` and
future similar multimodal search services on Modal.

## Models

- Embedding: `Qwen/Qwen3-Embedding-0.6B`
- Reranker: `BAAI/bge-reranker-v2-m3`

## Hardware

- GPU: `L4` (24GB VRAM)
- Workspace user pattern with `/home/workspace` HOME + PATH/PYTHONPATH

## Image contents

- Rust + Cargo via rustup
- Node.js 22 + npm (NodeSource)
- Bun
- GitHub CLI (`gh`)
- Claude CLI (`/root/.local/bin/claude`)
- Python deps: fastapi, uvicorn, pydantic, transformers, torch, sentencepiece,
  protobuf, faiss-cpu, numpy

## FastAPI auth pattern

Use Modal secrets for API tokens and enforce `Authorization: Bearer ***
with a small helper:

```python
from fastapi import HTTPException, Header

def assert_token(authorization: Optional[str]):
    if not API_TOKEN:
        return
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
```

Attach `assert_token(authorization)` to protected endpoints only;
leave `/health` public.

Create the secret with:
```bash
modal secret create <name> TOKEN_ID=*** TOKEN_SECRET=***
```

Attach it in deploy:
```python
secret = modal.Secret.from_name("<name>")

@app.function(image=image, gpu="L4", timeout=7200, secrets=[secret])
@modal.asgi_app()
def api():
    from service_module import app as fastapi_app
    return fastapi_app
```

## GitHub secret sync

Use the same token value in both Modal and GitHub so CI/deploy share credentials:

```bash
TOKEN=$(python - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
TID=$(python - <<'PY'
import uuid
print(uuid.uuid4())
PY
)

modal secret create bl1nk-search-auth BL1NK_TOKEN_ID="$TID" BL1NK_API_TOKEN="$TOKEN"
printf '%s' "$TOKEN" | gh secret set BL1NK_API_TOKEN -R owner/repo
printf '%s' "$TID"  | gh secret set BL1NK_TOKEN_ID -R owner/repo
```

Never echo raw secret values in chat or plain-text config files.

## Git cleanup for embedded inner repos

When Git warns about an embedded repository in the working tree:
1. If the inner repo should be ignored as source: add its path to `.gitignore`, then `git rm --cached -r <path>`
2. To remove only inner `.git` metadata: `rm -rf <path>/.git`, then `git add -A`
3. If the outer `.git` is corrupted/lost: re-init locally and `git push --force` to restore remote history

Prefer option 2 when the inner repo is not meant to be versioned independently.

## Verification checklist

- `modal image names list` shows `latest`, `v1`, `v1-YYYYMMDD`
- `/health` returns `200 OK` with services status
- Unauthenticated `/query` returns `401` or `403`
- Authenticated `/query` returns expected JSON shape with `meta.trace_id`
- Claude binary present at `/root/.local/bin/claude --version`
- No `__pycache__` or embedded `.git` in published tree