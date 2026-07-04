---
name: setup-pre-commit
description: Set up or extend pre-commit hooks for this repo's Python and Rust projects using the `pre-commit` framework (not Husky/npm — this repo has no package.json). Use when user wants to add pre-commit hooks, configure ruff/mypy/pytest checks, or add commit-time formatting/linting/type-checking/tests.
---

# Setup Pre-Commit Hooks

This repo is a **Python + Rust monorepo** — there is no `package.json` anywhere in it. Hooks run through the Python **`pre-commit`** framework (https://pre-commit.com), configured in a single root `.pre-commit-config.yaml`. Never suggest Husky, npm, lint-staged, or Prettier here.

Each Python project lives in its own directory with its own `pyproject.toml` (e.g. `modal-apps/modal-runner`, `modal-apps/modal-agy`, `modal-apps/modal-sandbox`, `modal-images`) — there is no shared root `pyproject.toml` or workspace tool (no uv workspace, no Poetry monorepo). The Rust crate lives at `modal-apps/modal-opencode/engine`.

## What this sets up

- The **pre-commit** framework itself, if not already installed
- Generic hygiene hooks (trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-added-large-files) via the upstream `pre-commit/pre-commit-hooks` repo
- Per-project **ruff** (lint + format) and **mypy** (type-check) hooks, scoped by path, for any Python project that already declares them in its `pyproject.toml` `[dependency-groups].dev`
- Per-project **pytest** hooks, scoped by path, for any Python project with a `tests/` directory
- **cargo fmt** / **cargo test** for the Rust engine, scoped to `modal-apps/modal-opencode/engine`

## Steps

### 1. Read the existing config first

Read `.pre-commit-config.yaml` at the repo root. Extend it — never replace working hooks. The generic hygiene hooks and the `cargo-fmt`/`cargo-test` local hooks (scoped with `files: ^modal-apps/modal-opencode/engine/Cargo.toml`) are the pattern to follow for every new hook: a `repo: local` entry, `language: system`, `pass_filenames: false`, and a `files:` regex anchored to the project's directory.

### 2. Discover Python projects and their declared tools

For each directory with a `pyproject.toml`, read its `[dependency-groups].dev` (or `[project.optional-dependencies]`) to see which of `ruff`, `mypy`, `pytest` it actually declares. **Only add a hook for a tool the project already depends on.** If the user wants a new tool added to a project that doesn't have it, add it to that project's `pyproject.toml` dev deps first and say so — don't add a hook for a tool that isn't installed.

### 3. Add scoped local hooks per project

For each Python project that declares the tool, add a `repo: local` hook scoped to that directory, e.g. for a project at `modal-apps/<name>`:

```yaml
  - repo: local
    hooks:
      - id: ruff-<name>
        name: ruff (<name>)
        entry: bash -c 'cd modal-apps/<name> && ruff check . && ruff format --check .'
        language: system
        pass_filenames: false
        files: ^modal-apps/<name>/
      - id: mypy-<name>
        name: mypy (<name>)
        entry: bash -c 'cd modal-apps/<name> && mypy .'
        language: system
        pass_filenames: false
        files: ^modal-apps/<name>/
      - id: pytest-<name>
        name: pytest (<name>)
        entry: bash -c 'cd modal-apps/<name> && python -m pytest'
        language: system
        pass_filenames: false
        files: ^modal-apps/<name>/
```

Omit whichever of `ruff-<name>` / `mypy-<name>` the project doesn't declare as a dependency. Every project with a `tests/` directory gets a `pytest-<name>` hook.

### 4. Leave the Rust hooks alone

`cargo-fmt` and `cargo-test`, scoped to `modal-apps/modal-opencode/engine/Cargo.toml`, are already correct in this repo. Don't duplicate or restructure them — only touch them if the user reports they're broken.

### 5. Install and verify

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Confirm every new hook passes (or fails for a real, pre-existing reason) before committing.

### 6. Commit

Stage `.pre-commit-config.yaml` and any `pyproject.toml` changes, and commit with a message describing which projects gained which checks.

## Notes

- **No package.json, no Husky, no npm/pnpm/yarn/bun.** If you find yourself reaching for any of those, stop — you're solving the wrong repo's problem.
- **`language: system`, not pre-commit's Python-venv-managed hooks.** Each project has its own dependencies already installed via its own `pyproject.toml`; don't make pre-commit manage separate venvs per hook.
- **Scope every hook with `files:`.** Because each Python project is independent, an unscoped hook would try to run every project's checks on every commit, including unrelated ones — mirror the existing `cargo-fmt`/`cargo-test` pattern.
- **Don't invent tooling a project doesn't have.** Check `pyproject.toml` dev deps before wiring a hook; as of this writing every Python project (`modal-runner`, `modal-agy`, `modal-sandbox`, `modal-images`) declares `ruff` and has a scoped `ruff-<name>` hook, but only `modal-sandbox` declares `mypy`.
