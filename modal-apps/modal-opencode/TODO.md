# TODO - modal-opencode (sovereign-gateway)

## Code Issues
- [ ] `tests/test_opencode.py` imports `webhook`, `tool_edit`, `tool_list_directory`, `tool_websearch`, `run_conversation` from `opencode` — **none of these exist anywhere in the repo**. The test file is stale relative to the current `opencode.py` (which implements a GitHub App webhook gateway: `github_webhook`, `sync_labels`, `get_installation_token`, etc.) and does not currently run. Either the test file predates a rewrite of `opencode.py`, or `opencode.py` was swapped out from under it. Needs a decision: rewrite the tests against current `opencode.py`, or restore whatever `opencode.py` shape the tests expect.
- [ ] No `pyproject.toml` / dependency declaration for this app (uses `modal.Image.from_name("bl1nk-rust:latest")`, `fastapi`, `sqlite3` — sqlite3 is stdlib, fastapi comes from the shared image).
