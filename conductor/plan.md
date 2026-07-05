# Implementation Plan: Rust Core Engine (Advanced Auto-Labeling & Policy)

## Phase 0 - Rust Core State Machine (PyO3)
- [x] Task: Scaffold Rust Project
- [x] Task: Implement Auto-Detect Logic (Bash to Rust Migration)
- [x] Task: Implement Size Calculation Logic
- [ ] Task: Implement File-Aware Detector
    - [ ] Create `file_detector.rs`. Analyze `Vec<String>` of changed file paths to infer `lang:*` and `type:*` (e.g., `tests/`, `Cargo.toml`).
- [ ] Task: Implement Policy & Constraint Engine
    - [ ] Create `policy.rs`. Enforce state transition rules and resolve conflicting labels (e.g., prioritizing `p0` over `p3`).
- [ ] Task: Update State Resolver
    - [ ] Modify `resolver.rs` to ingest File-Aware outputs and apply Policy constraints before finalizing labels.
- [ ] Task: Update PyO3 Interface
    - [ ] Modify `lib.rs` to accept `changed_files: Vec<String>` from Python.
- [ ] Task: Conductor - User Manual Verification 'Phase 0 - Advanced Rust Core State Machine' (Protocol in workflow.md)

## Phase 1 - Modal Webhook Receiver (Python)
- [x] Task: Initialize FastAPI App
- [x] Task: Implement Webhook Endpoint & Signature Verification
- [ ] Task: Implement Changed Files Fetching
    - [ ] If event is PR, use GitHub App token to fetch the list of changed files to pass to Rust.
- [ ] Task: Integrate Updated Rust Engine
    - [ ] Call `sovereign_engine.resolve_full_state(..., changed_files, ...)` from Python.
- [ ] Task: Conductor - User Manual Verification 'Phase 1 - Modal Webhook Receiver' (Protocol in workflow.md)

## Phase 2 - Storage Layer (SQLite)
- [x] Task: Configure Modal Volume
- [x] Task: Implement Database Schema
- [x] Task: State Persistence Logic
- [x] Task: Conductor - User Manual Verification 'Phase 2 - Storage Layer' (Protocol in workflow.md)

## Phase 3 - Advanced GitHub API Integration & Sync (Python)
- [ ] Task: Implement GitHub App Token Management
    - [ ] Generate JWT and short-lived Installation Access Tokens for API calls.
- [ ] Task: Execute GitHub API Label Updates
    - [ ] Compare current labels with Rust engine output and apply changes via REST API.
- [ ] Task: Implement Deep PR-Issue Sync
    - [ ] When a PR updates, find linked issues. Apply policy updates (e.g., unblock issue if PR is ready) based on Rust logic.
- [ ] Task: Conductor - User Manual Verification 'Phase 3 - GitHub API Integration & Sync' (Protocol in workflow.md)

## Phase 4 - Dashboard API and UI
- [x] Task: Create Read-Only Endpoints
- [x] Task: Implement HTML Dashboard
- [x] Task: Conductor - User Manual Verification 'Phase 4 - Dashboard API and UI' (Protocol in workflow.md)
