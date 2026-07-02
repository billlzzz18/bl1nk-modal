# AGENTS.md — Agy Agent Instructions

General instructions for AI agents working in this sandbox.

## What This Is

A Modal sandbox with agy CLI, git, GitHub CLI, and Rust toolchain.

## Core Principles

- **Always verify before reporting success** — check actual output, don't assume
- **Keep secrets out of output** — never echo API keys, tokens, or credentials
- **Push to git when done** — sandbox files are ephemeral, git is permanent
- **Ask before destructive actions** — confirm before force push, delete, etc.

## Workflow

1. Install plugin: `agy plugin install <plugin-url>`
2. Clone project: `git clone <project-url> /tmp/project`
3. Work in project: `cd /tmp/project`
4. Push changes: `git push`

## Tools Available

- `agy` — AI agent CLI (skills, plugins, MCP)
- `git` — version control
- `gh` — GitHub CLI
- `cargo` — Rust build system
- `python3` — Python runtime
