#!/usr/bin/env python3
"""Normalize line endings and trailing whitespace across every tracked file.

Repo-wide, OS-agnostic (pure stdlib) so it runs the same way on Linux,
macOS, Windows, and Termux. Complements the trailing-whitespace /
end-of-file-fixer pre-commit hooks, which only touch staged files at
commit time — this walks the whole tree in one pass.

Usage:
    python3 scripts/fix_whitespace.py          # fix in place
    python3 scripts/fix_whitespace.py --check  # report only, exit 1 if dirty
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Extensions we normalize. Lockfiles and binaries are deliberately excluded.
TEXT_SUFFIXES = {
    ".py",
    ".rs",
    ".sh",
    ".ps1",
    ".toml",
    ".md",
    ".yml",
    ".yaml",
    ".json",
}

# Files whose trailing whitespace is meaningful (e.g. Markdown's
# two-trailing-spaces line break) and should not be stripped.
PRESERVE_TRAILING_WHITESPACE_SUFFIXES = {".md"}

SKIP_NAME_SUFFIXES = ("uv.lock", "Cargo.lock")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    paths = [REPO_ROOT / p for p in out.split("\0") if p]
    return [
        p
        for p in paths
        if p.suffix in TEXT_SUFFIXES and not p.name.endswith(SKIP_NAME_SUFFIXES)
    ]


def normalize(text: str, preserve_trailing_whitespace: bool) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not preserve_trailing_whitespace:
        lines = [line.rstrip() for line in lines]
    text = "\n".join(lines)
    text = text.rstrip("\n") + "\n" if text.strip("\n") or text else text
    return text


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    dirty: list[Path] = []

    for path in tracked_files():
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary or already gone

        if not original:
            continue

        preserve = path.suffix in PRESERVE_TRAILING_WHITESPACE_SUFFIXES
        fixed = normalize(original, preserve)

        if fixed != original:
            dirty.append(path)
            if not check_only:
                path.write_text(fixed, encoding="utf-8")

    if dirty:
        verb = "Would fix" if check_only else "Fixed"
        for path in dirty:
            print(f"{verb}: {path.relative_to(REPO_ROOT)}")
        if check_only:
            print(f"\n{len(dirty)} file(s) need normalizing. Run without --check to fix.")
            return 1
        print(f"\n{len(dirty)} file(s) normalized.")
        return 0

    print("Nothing to fix — all tracked text files are already normalized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
