# Track Specification: Rust Core Engine Integration for OpenCode Gateway

## 1. Overview
This track introduces a new architecture for the OpenCode/KiloCode Gateway workflow by integrating a high-performance **Rust Core Engine** via PyO3 into the existing Modal (Python) environment. The new system handles GitHub webhooks, parses and normalizes labels, resolves state, detects blockers, and stores tracking data in a persistent layer. Finally, it exposes a Dashboard API for real-time monitoring.

## 2. Architecture Flow
Modal Webhook (Python) ↓ Rust Engine (PyO3 module) ↓ State Resolver + Label Parser + Constraint Engine ↓ Storage Layer (SQLite) ↓ Dashboard API ↓ UI Layer (Render/Netlify)

## 3. Functional Requirements

### 3.1 Phase 0 - Rust Core Engine (PyO3)
- Create a new Rust crate `sovereign_engine` configured as a `cdylib`.
- Implement core functions to be called from Python:
  - `normalize_labels(labels)`: Parses GitHub labels based on a configurable mapping (e.g., `agent:`, `state:`, `type:`).
  - `resolve_state()`: Validates logical groups (agent, state, type, priority).
  - `detect_blockers()`: Identifies labels indicating a blocked state (e.g., `blocking`, `conflict`).
  - `build_timeline_event(event_type, labels, actor, timestamp)`: Constructs an event object for the timeline.
- Compile the engine into a Python wheel using `maturin`.

### 3.2 Phase 1 - Modal Webhook Receiver
- Create a FastAPI endpoint `POST /api/github/webhook` running on Modal.
- Create an installation callback endpoint `GET /install/callback`.
- Configure Modal Secrets: `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`.

### 3.3 Phase 2 - Storage Layer (SQLite)
- Implement SQLite for state and timeline tracking (optimized for Modal Volumes).
- Define schemas for:
  - **installation**: `installation_id`, `owner`, `repo`, `installed_at`
  - **timeline**: `event_id`, `timestamp`, `repo`, `issue_or_pr_id`, `event_type`, `labels`, `actor`
  - **current_state**: `repo`, `issue_or_pr_id`, `current_labels`, `current_state`, `blocked`, `last_agent`, `updated_at`

### 3.4 Phase 3-6 - Webhook Logic & Rust Processing
- Verify GitHub webhook signatures (`X-Hub-Signature-256`).
- Extract event type, payload metadata, and labels.
- Pass labels to `sovereign_engine` to normalize, resolve state, and detect blockers.
- Update the SQLite database:
  - Append to the `timeline` table.
  - Update or insert the `current_state` table with the new state, blocked status, and assigned agent.

### 3.5 Phase 7 - Deployment
- Deploy the Python webhook logic and the compiled Rust module to Modal.

### 3.6 Phase 8-11 - GitHub App Configuration & Installation
- Create a GitHub App with permissions to read issues, PRs, and contents, and subscribe to events (issues, issue_comment, pull_request, push, label).
- Configure Webhook and Setup URLs pointing to the Modal endpoints.
- Handle App installation, store `installation_id`, and generate `installation_access_token` to read initial metadata.

### 3.7 Phase 12-13 - Dashboard API and UI
- Build a Dashboard API (`GET /state`, `GET /timeline`, `GET /repos`, `GET /issues`) on Modal.
- Implement a UI Layer (e.g., on Render or Netlify) that displays:
  - Current State View
  - Timeline/Event Log
  - Blocker Alerts
  - Agent Activity

## 4. Non-Functional Requirements
- **Performance:** The label parsing and state resolution must be offloaded to Rust for maximum performance.
- **Configurability:** The label mapping rules in the Rust engine must be configurable (e.g., via JSON or ENV) and support custom additions.
- **Data Persistence:** SQLite must be backed by a persistent Modal Volume to prevent data loss between serverless invocations.

## 5. Out of Scope
- Direct code generation or execution by AI agents (handled in separate modules/tracks).
- Complex multi-tenancy beyond simple `owner`/`repo` tracking in SQLite.