---
name: build-rust-engine-on-modal
description: Build and ship the PyO3 sovereign_engine Rust module into a Modal image using maturin, with layer caching that keeps the slow toolchain install from re-running on every code change
source: auto-skill
extracted_at: '2026-07-09T12:34:11.889Z'
---

# Build the Rust engine on Modal

The `sovereign_engine` is a PyO3 module under `modal-apps/bl1nk-app/engine/` that powers PR/issue auto-labeling. It is **not** a separately-deployed Modal function — it is compiled into the sandbox/agent image and imported as a Python module at runtime. The full recipe lives in `conductor/modal_deployment.md`; this skill is the operational version.

## When to use

- Adding a new Rust source file to `engine/src/`.
- Changing any of the existing modules: `lib.rs`, `detector.rs`, `file_detector.rs`, `policy.rs`, `resolver.rs`, `size_calc.rs`.
- Bumping Rust toolchain version, or upgrading `maturin` / `pyo3` versions.
- Adding a new Python-facing function to the engine (anything that goes into `pub fn` in `lib.rs` and is exposed to Python).

## Where the spec lives

`conductor/spec.md` is the authoritative spec for the engine's behavior. The five-phase plan (Rust core → Modal webhook → SQLite on Modal Volume → GitHub API sync → dashboard) defines what each module is supposed to do. If you're changing engine behavior, update the spec alongside the code — the spec is the source of truth, the code is the implementation.

`modal-apps/bl1nk-app/engine/TODO.md` lists known gaps: `exclusive_groups` should be a constant (not recreated per call), regex patterns should be configurable, and there are no benchmarks yet. Read it before starting work to avoid duplicating a known issue.

## The recipe (from `conductor/modal_deployment.md`)

### Local development (fastest)

```bash
cd modal-apps/bl1nk-app/engine
cargo fmt --check
cargo test --all
```

The engine has unit tests for every source file (`detector.rs`, `file_detector.rs`, `resolver.rs`, `policy.rs`, `size_calc.rs`, plus `resolve_full_state()` in `lib.rs`). `cargo test --all` is the pre-commit hook and the first thing CI will run.

For Python-side smoke testing, build the module locally:

```bash
cd modal-apps/bl1nk-app/engine
maturin develop
# then from modal-apps/bl1nk-app/
python -c "import sovereign_engine; print(sovereign_engine.resolve_full_state(...))"
```

### Building into a Modal image (production)

The principle from `conductor/modal_deployment.md`: **layer caching**. Keep the slow, rarely-changing steps (`apt_install`, `rustup`, `pip install maturin`) in one `modal.Image` chain, and the fast, often-changing step (`copy_local_dir("./engine", ...)` + `maturin develop`) in a second chain. Modal's image layer cache keys on the chain contents, so code changes don't trigger a full toolchain reinstall.

```python
# In the image definition (e.g., modal-images/build_bl1nk_agent.py or _make_sandbox_image())
rust_image = (
    modal.Image.debian_slim(python_version="3.12")
    # Layer 1: cached, runs once per toolchain bump.
    .apt_install("git", "clang", "pkg-config")
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        # Rust installed to /root/.cargo during build; SHARED_INSTALL_COMMANDS
        # later moves it to /home/workspace/.cargo and symlinks to /usr/local/bin
        "pip install maturin",
    )
    # Layer 2: invalidated on engine code change.
    .copy_local_dir("./engine", "/root/engine")
    .run_commands("cd /root/engine && maturin develop --release")
)
```

Key details:

- **Use `maturin develop --release`** for production. Debug builds are 10–50× slower at runtime; the engine runs in the hot path of every webhook.
- **`copy_local_dir` must come after the toolchain install.** Reversing the order means Modal re-installs Rust every time a `.rs` file changes.
- **Pin the Rust toolchain in the build script** (e.g., `rustup default 1.XX.0`) once the engine is stable. Without a pin, a future rustup release can break the build silently.
- **The engine directory in Modal is `/root/engine`**, not `modal-apps/bl1nk-app/engine`. The `copy_local_dir` path is relative to where `modal` is invoked from; verify the working directory matches.

### When adding a new Python-callable function

1. Add `#[pymethods]` impl in the relevant `src/*.rs` (or a new file under `src/`).
2. Re-export from `lib.rs`: `pub use new_module::NewType;` and add it to the `#[pymodule] fn sovereign_engine(...)` body.
3. Add a unit test in the same file.
4. From `engine/`, `cargo test --all` to confirm the test passes and nothing else regressed.
5. From `modal-apps/bl1nk-app/`, `maturin develop` then import-test the new function.
6. The pre-commit `cargo-test` hook will run `cargo test --all` automatically on any change to `engine/Cargo.toml`. **Caveat:** the pre-commit `files:` regex currently points at the wrong path (`modal-apps/modal-opencode/engine/Cargo.toml`, the pre-unification location); see `QWEN.md` §8. Update the regex to `modal-apps/bl1nk-app/engine/Cargo.toml` if you want the hook to actually fire.

## Common mistakes to avoid

- **Reinstalling rustup on every rebuild.** The fix is layer ordering: toolchain install must be in a separate `run_commands(...)` call *before* `copy_local_dir`. Modal caches by the chain contents; toolchain steps don't change when engine code changes.
- **Forgetting `--release`.** Debug builds work for tests but tank webhook latency. Set `maturin develop --release` in the image build.
- **Mixing Python and Rust source in the same `copy_local_dir` step.** If you copy both `engine/` and `modal_app.py` into the same layer, Modal can't cache the Python changes independently. Keep the engine copy in its own layer.
- **Adding a `pub fn` to `*.rs` without re-exporting from `lib.rs`.** PyO3 modules need the function registered in the `#[pymodule]` body; the compiler will not warn about a missing registration, only Python will fail at import with `AttributeError`.
- **Treating the engine as a Modal function.** It is a PyO3 module embedded in the sandbox image, called via Python `import sovereign_engine`. There is no `app.function(engine)` in `modal_app.py`.

## Verifying it shipped

After rebuilding the image:

```bash
# In a deployed sandbox or via modal run dev():
python -c "import sovereign_engine; print(dir(sovereign_engine))"
# Expect: ['__name__', 'resolve_full_state', ...new functions...]
```

If the new function is missing, the `lib.rs` re-export is incomplete. If the import itself fails with `ModuleNotFoundError`, `maturin develop` didn't run — check the `run_commands` log in the image build.

## How to apply

Use this skill whenever the user says "add a label rule", "change the policy engine", "make the engine faster", or "expose a new function to Python". Do **not** use this skill for the base image toolchain (that's the `bump-base-image-version` skill) or for the `bl1nk-search` embedding service (that's the `deploy-bl1nk-app` skill).
