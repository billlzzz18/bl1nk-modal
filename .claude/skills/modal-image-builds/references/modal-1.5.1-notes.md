## Modal 1.5.1 Mount API

Verified signatures:
- `Mount.add_local_file(local_path, remote_path)` - instance method
- `Mount.from_local_file(...)` does NOT exist
- Usage: `mount = Mount(); mount.add_local_file(...); mounts=[mount]`

## Verified Build/Deploy Split

Build script (`build_*.py`):
- Use `modal.App.lookup(APP_NAME, create_if_missing=True)`
- Use `with modal.enable_output(): built = image.build(app)`
- Publish tags at end with `built.publish(...)`
- Embed service files with `image.add_local_file("service.py", "/home/workspace/service.py", copy=True)`

Deploy script (`deploy_*.py`):
- Use `app = modal.App("name")`
- Use `modal.Image.from_name("name:tag")`
- Import service inside function body, not at module level
- Do NOT pass `mounts=[...]` to `@app.function()`; it raises TypeError in Modal 1.5.1

## Claude CLI Path

Installs to `~/.local/bin/claude` (version 2.1.198 as of 2026-07-02)
Build-time verification: `/root/.local/bin/claude --version`
Runtime: symlink to `/usr/local/bin/claude` or set PATH

## Auth Pattern

Bearer token auth middleware for FastAPI:
- Load `API_TOKEN` and `API_TOKEN_ID` from env
- Add `authorization: Optional[str] = Header(None)` to protected endpoints
- Call `assert_token(authorization)` at the start of each protected endpoint
- Provide unauthenticated `/auth/verify` endpoint returning `{ "ok": true, "token_id": "..." }`

## Git Cleanup for Embedded Repos

If Git warns about an embedded repository:
1. Add path to `.gitignore`
2. `git rm --cached -r <path>` to remove from index only
3. To remove only inner `.git`: `rm -rf <path>/.git` then `git add -A`
4. If outer `.git` is lost: re-init and force-push
