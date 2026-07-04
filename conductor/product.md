# Product Vision

## Product Overview

**Name:** bl1nk-modal

**Tagline:** A personal monorepo of Modal-hosted apps for AI-agent infrastructure.

**Description:**
bl1nk-modal hosts a set of independent apps deployed on [Modal](https://modal.com)'s serverless cloud:

- **modal-runner** — webhook-driven commit-task tracker (GitHub/GitLab/Azure DevOps → CrateDB → LINE Notify)
- **modal-agy** — orchestrator for the `agy` (Google Antigravity) agent sandbox
- **modal-sandbox** — general-purpose sandbox API (create/exec/upload/download against `modal.Sandbox`)
- **modal-images** — shared dev image build (Rust/Node/Bun/gh/Claude CLI) plus `bl1nk-search`, an embedding + reranker search service
- **modal-opencode/engine** (`sovereign_engine`) — a Rust/pyo3 crate that auto-labels issues/PRs by detecting type/stage/priority/size from text and changed files

## Problem Statement

### The Problem

Local machines can't give a CLI agent and its human user a shared sandbox/workspace to do the same work together, and local RAM/CPU is a hard ceiling for agent workloads.

### Current Solutions

Running agent tooling (sandboxes, dev containers, search) directly on a personal machine or laptop.

### Why They Fall Short

- No shared workspace between the human and the CLI agent (Claude, Hermes, etc.) — each works in isolation.
- Local RAM/CPU limits cap what an agent can run (model inference, large builds, embeddings).
- No workspace reachable from anywhere — the user needs to work from different machines/OSes, including Termux on Android.

Running this on Modal's serverless model instead means elastic compute, no idle cost, and a workspace reachable from anywhere by both the agent and the user.

## Target Users

### Primary Users

**Who:** The repo owner — a solo developer running personal AI coding agents (Claude Code, agy/Antigravity, opencode) day to day.
**Goals:** Shared sandboxed compute and a search-augmented memory index that both the human and the agents can use.
**Pain Points:** Local RAM/CPU ceilings, no single workspace reachable across devices/OSes (including Termux).
**Technical Proficiency:** High — comfortable operating Modal, GitHub Actions, and Rust/Python toolchains directly.

### Secondary Users

**Who:** Other agents the owner runs — Claude, Hermes, and future CLI agents.
**Goals:** Run their backend workloads on Modal reliably, and access the same sandbox/search state the human does.
**Relationship to Primary:** Consumers of the same infrastructure the primary user operates — not separate accounts, but separate processes sharing state.

## Core Value Proposition

### Key Benefits

1. Elastic compute — no local RAM/CPU ceiling for agent workloads.
2. One shared workspace/sandbox reachable by both the human and any agent, from any device.
3. Pay-per-run cost model instead of an always-on local/dedicated machine.

### Value Statement

> Give every agent I run — and myself — the same sandboxed, elastically-scaled workspace, reachable from anywhere.

## Success Metrics

Informal — this is a personal infra repo, not a product with external metrics. The practical signal is:

- Real-world use holds up: the human user, Claude, and Hermes can all drive the stack without babysitting it.
- Hermes (and other agents) can run their backend workloads on Modal reliably.

## Out of Scope

### Explicitly Not Included

- Multi-tenant / external-user support — this is a personal/small-team tool, not a hosted product.
- A polished UI — CLI-first for now.

### Future Considerations

- A Rust CLI + Tauri v2 desktop app (with a bun/npm wrapper), once the CLI and API are stable.
- Additional infrastructure beyond Modal (e.g. GitHub Actions, Cloudflare) as needs grow.

### Non-Goals

- Building a general-purpose SaaS product for external customers.
