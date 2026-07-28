# TODO

## Tests
- [x] Strategy pattern dispatch tests (test_dispatch.py — 27 tests)
- [x] FastAPI endpoint tests (test_health.py — 3 tests)
- [ ] file upload/download test
- [ ] Subagent integration test (sandbox runner, opencode)

## Code
- [x] Fix string concatenation bug in `_make_sandbox_image()`
- [x] Deduplicate image definitions (consume `bl1nk-rust:latest` via `Image.from_name()`)
- [x] Strategy pattern for agent dispatch (dispatch.py)
- [x] Remove stale tests from old modal-runner/modal-sandbox codebase
- [ ] Auth middleware on API endpoints (sandbox create/exec accessible to anyone)
