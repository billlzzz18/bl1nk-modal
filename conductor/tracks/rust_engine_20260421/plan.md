# Implementation Plan: Rust Core Engine (Auto-Labeling Migration)

## Phase 0 - Rust Core State Machine (PyO3)
- [x] Task: Scaffold Rust Project
    - [x] Initialize `sovereign_engine` with `cdylib` and PyO3 bindings.
- [x] Task: Implement Auto-Detect Logic (Bash to Rust Migration)
    - [x] Create `detector.rs`. Implement regex matching for `type:`, `stage:`, `p:`, `lang:`, `env:`, `plat:`, and `constraint:` based on legacy `labels.json` patterns.
- [x] Task: Implement Size Calculation Logic
    - [x] Create `size_calc.rs`. Implement logic for PRs (`additions + deletions` thresholds: 50, 150, 300, 600, 1200, 3000) and fallback regex detection for Issues.
- [x] Task: Implement State Resolver
    - [x] Create `resolver.rs`. Merge detected labels, apply default fallbacks (`stage`, `size`, `p`), and ensure deduplication. Ensure `agent:` is never auto-assigned.
- [x] Task: Expose PyO3 Interface
    - [x] Update `lib.rs` to expose `resolve_full_state(title, body, additions, deletions, current_labels)` to Python.
- [x] Task: Conductor - User Manual Verification 'Phase 0 - Rust Core State Machine' (Protocol in workflow.md)

## Phase 1 - Modal Webhook Receiver (Python)
- [x] Task: Initialize FastAPI App
    - [x] Create `opencode.py` with Modal Image definition (including Rust toolchain and `maturin`).
- [x] Task: Implement Webhook Endpoint
    - [x] Handle `POST /api/github/webhook`.
    - [x] Implement `HMAC-SHA256` signature verification using `GITHUB_WEBHOOK_SECRET`.
- [x] Task: Payload Extraction
    - [x] Extract `title`, `body`, `additions`, `deletions`, and current labels from GitHub Event payload.
- [x] Task: Integrate Rust Engine
    - [x] Call `sovereign_engine.resolve_full_state(...)` from Python.
- [x] Task: Conductor - User Manual Verification 'Phase 1 - Modal Webhook Receiver (Python)' (Protocol in workflow.md)

## Phase 2 - Storage Layer (SQLite)
- [x] Task: Configure Modal Volume
    - [x] Attach `sovereign-state-vol` to the FastAPI app.
- [x] Task: Implement Database Schema
    - [x] Create `timeline`, `current_state`, and `installation` tables via SQLite `CREATE TABLE IF NOT EXISTS`.
- [x] Task: State Persistence Logic
    - [x] Update webhook to `INSERT` timeline events and `UPSERT` current state based on Rust engine output.
- [x] Task: Conductor - User Manual Verification 'Phase 2 - Storage Layer (SQLite)' (Protocol in workflow.md)

## Phase 3 - GitHub API Integration & Sync (Python)
- [ ] Task: Implement Label Sync Logic
    - [ ] Compare current labels with Rust engine output. Determine `ADD_LABELS` and `REMOVE_LABELS`.
- [ ] Task: Execute GitHub API Calls
    - [ ] Use `httpx` in Python to call `POST/DELETE` or `PUT` to `/repos/{owner}/{repo}/issues/{issue_number}/labels` using `GITHUB_PRIVATE_KEY` (App Auth).
- [ ] Task: Implement PR-Issue Label Sync (Bash Migration)
    - [ ] Replicate `sync-pr-labels.sh`. If event is a PR closing an Issue, fetch Issue labels and sync them to the PR.
- [ ] Task: Conductor - User Manual Verification 'Phase 3 - GitHub API Integration & Sync' (Protocol in workflow.md)

## Phase 4 - Dashboard API and UI
- [x] Task: Create Read-Only Endpoints
    - [x] Implement `GET /api/state` and `GET /api/timeline` in FastAPI.
- [x] Task: Implement HTML Dashboard
    - [x] Serve a basic UI at `/` summarizing SQLite data (highlighting active agents and blocked tasks).
- [x] Task: Conductor - User Manual Verification 'Phase 4 - Dashboard API and UI' (Protocol in workflow.md)
