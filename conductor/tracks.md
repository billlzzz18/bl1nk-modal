# Track Registry

This file maintains the registry of all development tracks for bl1nk-modal. Each track represents a distinct body of work with its own spec and implementation plan.

## Status Legend

| Symbol | Status      | Description               |
| ------ | ----------- | -------------------------- |
| `[ ]`  | Pending     | Not yet started           |
| `[~]`  | In Progress | Currently being worked on |
| `[x]`  | Completed   | Finished and verified     |

## Active Tracks

_None yet — run `/conductor:new-track` to create the first one._

## Backlog (per-project `TODO.md`)

Each app directory keeps its own `TODO.md` as a raw, ungroomed backlog — quick notes on missing tests or known code issues, checked off as they're fixed. **This registry and those files work together, not instead of each other:**

- `TODO.md` = fast, low-ceremony notes scoped to one project. Add to it freely; no process required.
- A **track** (this file + `./tracks/<id>/spec.md` + `plan.md`) = a body of work worth planning before touching code — multi-step, cross-cutting, or risky enough to want a spec first.
- **Promote a `TODO.md` item (or a cluster of related ones) to a track via `/conductor:new-track` when you're about to actually work on it.** Don't pre-create tracks for everything in the backlog speculatively — that just duplicates the checklist in a heavier format.

Current unchecked items, for visibility (source of truth is always the linked file, not this snapshot):

| Project | Item | Notes |
| --- | --- | --- |
| [modal-runner](../modal-apps/modal-runner/TODO.md) | Bare `pass` in exception handler (main.py:135, due_date parse) | Should log or re-raise |
| [modal-runner](../modal-apps/modal-runner/TODO.md) | No `modal deploy`/`modal run` entrypoint documented | Docs gap |
| [modal-runner](../modal-apps/modal-runner/TODO.md) | Verify `modal.App` + FastAPI ASGI integration | Needs a read-through, not just a doc fix |
| [modal-agy](../modal-apps/modal-agy/TODO.md) | Missing `tests/test_image.py`, `tests/test_orchestrator.sh` | Test coverage gap |
| [modal-agy](../modal-apps/modal-agy/TODO.md) | `orchestrator.sh` copies `.agents/.qwen/.gemini/.claude` — unverified TARGETS | Could silently no-op for a missing target |
| [modal-agy](../modal-apps/modal-agy/TODO.md) | `run.sh` hardcodes MCP server URLs | Should be configurable |
| [modal-agy](../modal-apps/modal-agy/TODO.md) | `setup.sh` assumes `agy` CLI is available | No fallback/error handling |
| [modal-agy](../modal-apps/modal-agy/TODO.md) | `run_orchestrator()` only catches `FileNotFoundError` | Narrow error handling |
| [modal-sandbox](../modal-apps/modal-sandbox/TODO.md) | **No auth middleware on API endpoints** | Sandbox create/exec is open to anyone — candidate for a real track, not just a checkbox |
| [modal-sandbox](../modal-apps/modal-sandbox/TODO.md) | Missing `tests/test_upload_download.py`, `tests/test_image.py` | Test coverage gap |
| [modal-sandbox](../modal-apps/modal-sandbox/TODO.md) | `scripts/publish.sh` ran `pytest` before tests existed | Resolved now that tests exist — verify the script still runs cleanly |
| [modal-images](../modal-images/TODO.md) | `search_service.py`: `_index`/`_ids` are global mutable state, not thread-safe | Ties into the storage-adapter track already noted in `tech-stack.md` |
| [modal-images](../modal-images/TODO.md) | `pyproject.toml` `py-modules` only lists `build_bl1nk_rust`, missing `search_service` | Packaging gap |
| [modal-opencode/engine](../modal-apps/modal-opencode/engine/TODO.md) | `resolver.rs`: `exclusive_groups` recreated per call instead of a constant | Minor perf/style |
| [modal-opencode/engine](../modal-apps/modal-opencode/engine/TODO.md) | `detector.rs`: regex patterns hardcoded, not configurable | Design question — worth a track if it's actually going to change |
| [modal-opencode/engine](../modal-apps/modal-opencode/engine/TODO.md) | No benchmarks for engine performance | Nice-to-have |
| [modal-opencode](../modal-apps/modal-opencode/TODO.md) | `tests/test_opencode.py` imports functions that don't exist anywhere in the repo (`webhook`, `tool_edit`, `tool_websearch`, `run_conversation`) | Test suite is fully stale against current `opencode.py` (a GitHub App webhook gateway) — found while wiring up `.env.example` for this app |

## Completed Tracks

<!-- Move completed tracks here -->

## Archived Tracks

<!-- Archived tracks are moved here with reason and date -->

| Track ID | Type | Reason | Archived | Folder |
| -------- | ---- | ------ | -------- | ------ |

## Track Creation Checklist

When creating a new track:

1. [ ] Add entry to this registry
2. [ ] Create track folder: `./tracks/{{track-id}}/`
3. [ ] Create spec.md from template
4. [ ] Create plan.md from template
5. [ ] Create metadata.json from template
6. [ ] Update index.md with new track reference

## Notes

- Track IDs should be lowercase with hyphens (e.g., `storage-adapters`, `cli-bootstrap`).
- Keep descriptions concise (one line).
- Prioritize tracks as: critical, high, medium, low.
- Likely first tracks based on the setup conversation: the vector-store/DB/storage adapter split, and the Rust CLI bootstrap.
