# Rust Style Guide

Rust conventions following the standard Rust API guidelines, `rustfmt`, and `clippy` defaults.

## Naming Conventions

```rust
// Variables and functions: snake_case
let user_name = "John";
fn calculate_total(items: &[Item]) -> u32 { 0 }

// Constants and statics: SCREAMING_SNAKE_CASE
const MAX_CONNECTIONS: u32 = 100;
static DEFAULT_TIMEOUT: u32 = 30;

// Types, traits, enums: PascalCase
struct UserAccount { id: u32 }
trait Repository { fn find(&self, id: u32) -> Option<Item>; }
enum Status { Pending, Active, Completed }

// Modules: snake_case
mod file_detector;

// Crates: kebab-case in Cargo.toml, snake_case when referenced in code
// Cargo.toml: name = "sovereign-engine"
// code:        use sovereign_engine::...;
```

## Formatting

Enforced by `cargo fmt` — don't hand-format, run the tool. This repo's `.pre-commit-config.yaml` runs `cargo fmt --check` on any change to `modal-apps/modal-opencode/engine/Cargo.toml`.

```bash
cargo fmt          # apply formatting
cargo fmt --check  # verify without writing (CI mode)
```

## Linting

`cargo clippy` catches idiom violations `rustfmt` doesn't (e.g. unnecessary clones, `vec![]` after `Vec::new()` + pushes, `&Vec<T>` instead of `&[T]`).

```bash
cargo clippy --all-targets
cargo clippy --fix --lib -p <crate>   # apply the safe auto-fixes
```

## Ownership and Borrowing

```rust
// Prefer borrowing over cloning when the callee doesn't need ownership
fn detect(changed_files: &[String]) -> Vec<String> { vec![] }

// Take &str over &String, &[T] over &Vec<T> in function signatures
fn process(text: &str) {}          // good
fn process(text: &String) {}       // clippy::ptr_arg warning

// Return owned values from constructors/builders
impl Detector {
    pub fn new() -> Self { Self { patterns: Default::default() } }
}
```

## Error Handling

```rust
// Library code: Result<T, E>, never panic on recoverable errors
fn parse_config(raw: &str) -> Result<Config, ConfigError> {
    serde_json::from_str(raw).map_err(ConfigError::from)
}

// unwrap()/expect() are fine for invariants proven at construction
// (e.g. a hardcoded regex that is known to compile), not for I/O or user input
let re = Regex::new(r"^\d+$").unwrap(); // safe: literal pattern, always compiles

// Propagate with `?`, not manual match-and-return
fn read_and_parse(path: &Path) -> Result<Config, AppError> {
    let raw = std::fs::read_to_string(path)?;
    Ok(parse_config(&raw)?)
}
```

## Testing

Unit tests live in a `#[cfg(test)] mod tests` block at the bottom of the file they test, using `use super::*;` to pull in the parent module's items — this is the pattern already used throughout `sovereign_engine`.

```rust
pub struct SizeCalculator;

impl SizeCalculator {
    pub fn calculate_pr_size(additions: i32, deletions: i32) -> String {
        // ...
        # String::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_pr_size_boundaries() {
        assert_eq!(SizeCalculator::calculate_pr_size(30, 20), "xs");
    }
}
```

Run with:

```bash
cargo test          # all tests
cargo test -q       # quiet output
cargo test <name>   # filter by test name substring
```

## pyo3 Extension Crates

`sovereign_engine` is a `cdylib` pyo3 extension module (Python↔Rust bridge). Notes specific to this pattern:

- `Cargo.toml` sets `crate-type = ["cdylib"]` and depends on `pyo3` with the `extension-module` feature.
- `#[pyfunction]` / `#[pymodule]` wrap plain Rust functions — write and test the underlying logic as ordinary Rust first, then expose it.
- `cargo test` works fine for unit tests even with `extension-module` enabled in this repo's current setup — verified against the installed toolchain. If a future pyo3 upgrade breaks `cargo test` with a linker error, the standard fix is to make `extension-module` an opt-in Cargo feature (`default = ["extension-module"]`) and run tests with `cargo test --no-default-features`.

## Common Patterns

### Newtype / marker structs for stateless logic

```rust
// A struct with no fields, used purely to namespace associated functions
pub struct FileDetector;

impl FileDetector {
    pub fn detect(changed_files: &[String]) -> Vec<String> {
        let mut detected = std::collections::HashSet::new();
        // ...
        detected.into_iter().collect()
    }
}
```

### Builder-free construction with `HashMap`/`HashSet` initialization

```rust
use std::collections::HashMap;

pub struct Detector {
    patterns: HashMap<String, Vec<(String, regex::Regex)>>,
}

impl Detector {
    pub fn new() -> Self {
        let mut patterns = HashMap::new();
        patterns.insert("type".to_string(), vec![/* ... */]);
        Self { patterns }
    }
}
```

Prefer `vec![...]` literals over `Vec::new()` + repeated `.push()` calls when the values are known upfront — `clippy::vec_init_then_push` flags the latter.
