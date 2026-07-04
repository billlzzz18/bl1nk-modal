---
name: verify
description: Project-specific recipe for actually running bl1nk-modal's apps locally to observe behavior, without needing Modal cloud credentials. Use alongside the general /verify skill.
---

# Verifying bl1nk-modal locally

Every app under `modal-apps/*` and `modal-images/` is a FastAPI app wrapped
by Modal decorators. The FastAPI object underneath is plain, importable, and
servable with `uvicorn` **without any Modal auth** — only calls that actually
touch Modal's network API (`modal.App.lookup()`, `image.build()`,
`modal.Sandbox.create()`, etc.) need credentials or mocking.

## Serving a FastAPI app directly (no Modal auth needed)

```bash
cd modal-apps/modal-runner   # or modal-sandbox
uv sync
uv run --with uvicorn uvicorn main:app --port 8811       # modal-runner: FastAPI object is `app`
uv run --with uvicorn uvicorn modal_app:api --port 8813   # modal-sandbox: FastAPI object is `api`, not `app`
```

Use `--with uvicorn` (not `uv add uvicorn`) so you don't dirty `pyproject.toml`/`uv.lock` with a dev-only tool.

Then drive it with real `curl`, not `TestClient`:

```bash
curl -s -i -X POST http://127.0.0.1:8811/webhook/gitlab -d '{"commits": []}'
```

## search_service.py needs the same ML-dependency stubs as the tests

`torch`/`transformers`/`faiss` aren't real local dependencies (they only exist inside the Modal image). To serve `search_service.py` live, reuse the stubs already in `modal-images/tests/conftest.py` instead of installing multi-GB packages:

```bash
cat > /tmp/serve_search.py <<'EOF'
import sys
sys.path.insert(0, "<repo>/modal-images")
sys.path.insert(0, "<repo>/modal-images/tests")
import conftest  # installs the stubs
from search_service import app
EOF
cd modal-images && uv sync -q
uv run --with uvicorn --with numpy uvicorn /tmp/serve_search:app --port 8814
```

Known gap: `/index` and `/query` work end-to-end through real HTTP with the stubs, but since the stubs return `MagicMock` instead of real tensors, `score` in query results serializes as `{}` rather than a float. The existing pytest suite avoids this by monkeypatching `search_service.embed`/`rerank` directly — the stubs alone aren't enough for a genuine embedding round-trip. Don't add pytest coverage assuming otherwise; it needs either a real model or a monkeypatched `embed`.

## Driving a `@app.function` directly (not an HTTP endpoint)

Modal functions decorated with `@app.function(...)` support `.local()`, which calls the underlying Python function directly, in-process, no network:

```python
import modal_app
result = modal_app.dev.local()  # e.g. modal-sandbox's toolchain smoke-test
```

This is a real call against whatever's actually installed in the current environment (not mocked) — useful for `dev()`/`build()`-style smoke-test functions.

## Driving `build_bl1nk_rust.py` / `build_bl1nk_search.py` without cloud creds

These do real work at **module level** (`app = modal.App.lookup(...)`, `image.build(app)`, `built.publish(...)`) — importing them at all requires network auth. To exercise the actual build+publish logic without credentials, mock only the two network-touching calls and run the file as a script (`exec()` or a subprocess), not via a top-level `import` in a test:

```python
import modal
from unittest.mock import MagicMock

modal.App.lookup = MagicMock(return_value=modal.App("image-builds"))  # real, un-hydrated App — .function()/.local() still work
mock_built = MagicMock()
modal.Image.build = lambda self, app: mock_built

exec(open("build_bl1nk_rust.py").read())
mock_built.publish.assert_any_call(...)  # or just inspect call_args_list
```

Confirms the real behavior: `MAJOR_VERSION` is the only thing you edit for a version bump; the dated tag comes from `datetime.now()` at run time, not a hardcoded string.

## Shell script portability

`modal-apps/modal-sandbox/scripts/build.sh` and `modal-images/build.sh` resolve paths relative to their own location (`SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`), not a hardcoded clone path. To verify a script like this actually stayed portable after an edit, run it from an unrelated `cwd` (e.g. `cd /tmp && bash <repo>/modal-apps/modal-sandbox/scripts/build.sh`) and check any error output/traceback references the correct absolute repo path — if it does, the path resolution worked regardless of the actual bug encountered downstream (e.g. missing Modal auth in a sandboxed environment is expected and orthogonal).

## Known pre-existing gaps found while verifying (not caused by any single change, worth knowing about)

- `modal-runner`'s `get_pool()` reads `os.environ["DB_HOST"]` etc. with no try/except — an unconfigured DB surfaces as a bare-text 500 "Internal Server Error" with no JSON body, both for the sync path (immediate) and the async path (raised in the background task after the 202 already returned, visible only in server logs).
