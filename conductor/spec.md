# Track Specification: Rust Core Engine (Advanced State Machine & Auto-Labeling)

## 1. Overview
This track replaces the legacy Bash-based labeling scripts with a high-performance, deterministic **Rust Core Engine** hosted on Modal as a full-fledged **GitHub App**. 

The goal is to go beyond simple text-matching to create a "Policy Enforcement Engine" that acts as a centralized brain for the repository. It will validate state transitions, perform file-aware labeling, auto-resolve blockers, and synchronize states across related PRs and Issues, providing intelligent oversight without the high latency or cost of LLM/AI.

## 2. Architecture Flow
1. **GitHub App Installation:** Installed on repos, subscribing to `push`, `pull_request`, `issues`, and `issue_comment` events.
2. **Modal Webhook (Python):** Verifies app signature, fetches detailed payload (including changed file lists via REST API if needed).
3. **Rust Engine (PyO3 module):**
   - **Text Analysis:** Regex detection for basic attributes (`stage`, `p`, etc.).
   - **File-Aware Analysis:** Inspects changed files (e.g., `.rs` -> `lang:rust`, `Cargo.toml` -> `type:dep`).
   - **Constraint & Policy Engine:** Enforces valid state transitions (e.g., cannot skip `stage:test` if source code changed).
   - **Cross-Reference Sync:** Calculates state updates for linked issues when a PR changes status.
4. **Storage Layer (SQLite):** Persists the timeline and current state.
5. **Dashboard API:** Exposes state and timeline.

## 3. Functional Requirements

### 3.1 Phase 0 - Rust Core State Machine (PyO3)
- **Text Detector (`detector.rs`):** Regex matching for attributes based on legacy `labels.json`.
- **Size Calculator (`size_calc.rs`):** PR line change thresholds and Issue keyword detection.
- **File-Aware Detector (`file_detector.rs`):** *[NEW]* 
  - Analyzes the list of files changed in a PR.
  - Assigns `lang:*` based on extensions (`.py`, `.rs`, `.js`).
  - Assigns `type:*` based on paths (e.g., `tests/` -> `stage:test` or `type:test`, `docs/` -> `type:docs`).
- **Policy & Constraint Engine (`policy.rs`):** *[NEW]* 
  - Detects conflicting labels (e.g., `p:p0` and `p:p3`) and resolves to highest priority.
  - Enforces workflow: If code files changed, ensure `stage:test` or `stage:review` is required before `stage:finalize`.
- **State Resolver (`resolver.rs`):**
  - Merges all signals (Text, Files, Manual, Policies) into a final, sanitized `Vec<String>`.

### 3.2 Phase 1 - Modal Webhook Receiver (Python)
- Handle `POST /api/github/webhook` and verify `X-Hub-Signature-256`.
- Extract text payload.
- *[NEW]* For PR events, fetch the list of changed files using GitHub App Installation tokens to feed into the Rust File-Aware Detector.
- Call Rust engine: `resolve_full_state(title, body, additions, deletions, changed_files, current_labels, ...)`.

### 3.3 Phase 2 - Storage Layer (SQLite)
- Persistent SQLite on Modal Volumes for `timeline`, `current_state`, and `installation`.

### 3.4 Phase 3 - Advanced GitHub API Integration & Sync
- **Webhook Response:** Apply diffs to issue/PR labels.
- **Deep PR-Issue Sync (`sync.rs/py`):** *[NEW]*
  - If a PR is marked `rev:ready`, automatically remove `status:blocked` on the linked Issue.
  - Sync critical labels (`p:*`, `type:*`) downwards from Issue to PR.

### 3.5 Phase 4 - Dashboard API and UI
- `GET /api/state`, `GET /api/timeline` and HTML Dashboard.

## 4. Non-Functional Requirements
- **Deterministic & Fast:** Rust engine must execute complex policy checks in <50ms.
- **Robust Auth:** Must use GitHub App short-lived installation tokens.

## 5. Out of Scope
- AI/LLM token usage for basic state machine decisions.
