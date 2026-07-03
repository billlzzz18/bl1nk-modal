---
name: modal-image-builds
description: >-
  Build and deploy Modal images for Rust/Node/Bun/CLI development environments
  and AI agent runtimes. Covers image definition, workspace-user pattern,
  build/deploy separation, named-image tagging, ASGI service deployment on L4,
  Bearer token auth, embedding/reranker runtimes, and GitHub secret sync.
  Trigger: modal image, deploy modal, bl1nk-rust, bl1nk-search, build image,
  modal.Image, L4, workspace user container, auth verify, bearer token,
  embedding reranker, bl1nk-search-auth.
---

# Modal Image Builds

## Build Phase Pattern

- Build as root
- Install system deps via `apt_install`
- Install language toolchains via `run_commands`
- If embedding service files into the image, use `image.add_local_file("service.py", "/home/workspace/service.py", copy=True)` so they are available at runtime without mounts
- Create `workspace` user non-interactively
- Create workspace dirs and chown
- Symlink binaries into `/usr/local/bin/`
- Set `HOME`, `PATH`, `PYTHONPATH` envs
- Publish tags at end
- **Reuse existing image tags whenever possible.** Rebuild only when base toolchain, model, or dependency changes. Models belong in the image, not mounted at deploy time. Re-deploying a web function does not require rebuilding the image.

## Workspace User Layout

```
/home/workspace
├── .cache/
├── .cargo/
├── .claude/
├── .config/
├── .local/
├── .npm/
├── .ssh/          # optional
├── project/
└── workspace/     # optional
```

## Tag Convention

- `latest`
- `v1`, `v2`, ...
- `v1-YYYYMMDD`

Example: `bl1nk-search:v1-20260702`

## Service Deployment Pattern

Split build and deploy into separate files:
- `build_*.py` builds the image and publishes tags
- `deploy_*.py` defines web functions using `modal.Image.from_name()`

Import service code inside function body, not at module level, otherwise
local import resolution fails.

## FastAPI Endpoint on L4

Use `@modal.fastapi_endpoint(label="...")` when the user explicitly wants
Modal-style endpoints. `label` controls the subdomain: `<workspace>--<label>.modal.run`.

```python
@app.function(image=image, gpu="L4", timeout=7200)
@modal.fastapi_endpoint(label="bl1nk-search-v2")
def api():
    from service_module import app as fastapi_app
    return fastapi_app
```

`@modal.asgi_app()` is for full ASGI apps and produces a standard web function URL.
Both create public URLs. If the deployed URL is the only requirement, either works;
use the user's stated preference.

**Pitfall:** changing route handlers inside a FastAPI app does **not** require
rebuilding the image. Rebuild only when base toolchains, model weights, or
Python dependencies change. Re-deploy with `modal deploy deploy_*.py` after
changing service code.

## PYTHONPATH

When adding local files to an image, set `PYTHONPATH` to the directory
containing them so remote imports resolve.

## Secret Management Pattern

Store tokens in both Modal and GitHub so CI and deployed services share the same secret values:

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

Never echo or store raw secret values in chat history or plain-text files. Pipe secrets directly to `gh secret set` via stdin instead of printing them.

## Auth API Pattern

- Add `/auth/verify` endpoint for debugging token issues without exposing protected resources
- Add `/` root endpoint returning service name and available endpoints
- Apply `assert_token` middleware to protected endpoints: `/index`, `/query`, `/update`, `/delete`
- Leave `/health` and `/auth/verify` accessible or protected per spec

## User Preferences

- **Do not echo raw secrets/tokens in chat.** Even debug attempts should route through verification endpoints.
- **"Take out of gitignore" means remove from `.gitignore`, then `git add` and commit.** Do not delete working-tree files unless explicitly instructed.
- **Prefer one successful image over rebuilding.** Models and toolchains belong in the image. Reuse `modal.Image.from_name()` in deploy scripts. Rebuild only when base deps change, not when service code changes.
- **Minimal explanation.** User prefers direct execution over verbose planning or retry narration.
- **If the user asks for Modal endpoints, use `@modal.fastapi_endpoint(label=...)` rather than explaining alternatives.**
- **`modal endpoint list` is for LLM inference endpoints (`modal endpoint create --model ...`). Custom web services should be deployed as web functions/endpoints.** Do not confuse the two.

## Git Cleanup for Embedded Repos

If Git warns about an embedded repository inside the working tree:

1. **If the user says "take it out"**: remove the path from `.gitignore`, then `git add -A` and commit. Do NOT delete working-tree files.
2. If the inner repo should be ignored as source code: add its path to `.gitignore`, then `git rm --cached -r <path>` to remove it from the index while keeping files on disk
3. To delete only the inner `.git` metadata: `rm -rf <path>/.git`, then `git add -A`
4. If the outer `.git` itself becomes corrupted or missing, re-init locally and `git push --force` to restore remote history

Prefer option 1 when the user explicitly wants the folder tracked in the parent repo.

## Actual API surface (verified)

- `modal.Image.debian_slim(python_version="3.12")`
- `.apt_install(...)`
- `.run_commands(...)`
- `.env({...})`
- `.pip_install(...)`
- `.add_local_file(src, dst, copy=True)` — use `copy=True` to embed files in image
- `image.build(app)` with `modal.enable_output()`
- `built.publish("name:tag")`
- `modal.App.lookup("name", create_if_missing=True)` for build scripts
- `modal.App("name")` for deploy scripts
- `modal.Image.from_name("name:tag")`
- `@app.function(image=..., gpu="L4", timeout=...)` — no `mounts=[...]` in Modal 1.5.1
- `@modal.asgi_app()`
- **Do not pass `mounts=[...]` to `@app.function` in Modal 1.5.1 — it raises `TypeError`. Use `add_local_file(..., copy=True)` during image build instead.**

## Example Build/Deploy Layout

```
modal-images/
  build_<name>.py          # builds image + publishes tags
  deploy_<name>.py         # defines modal functions using Image.from_name()
  <service>.py             # FastAPI app imported inside deploy function
```

## Templates

- `templates/build_script.py` - build script skeleton
- `templates/deploy_script.py` - deploy script with mount example

## References

- `references/modal-1.5.1-notes.md` - verified API surface and mount quirk for Modal 1.5.1
- `references/ai-agent-search-runtime.md` - verified embedding/reranker/L4 stack for code+multilingual search services
- `references/auth-verify-pattern.md` - `/auth/verify` and `/` root endpoint patterns for debugging bearer-token services
- `references/fastapi-endpoint-notes.md` - `@modal.fastapi_endpoint` vs `@modal.asgi_app`, label-controlled subdomains, recursion pitfall when wrapping FastAPI route handlers, and BGE reranker load-report noise
