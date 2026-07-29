---
name: bump-base-image-version
description: Bump the major version of bl1nk-rust or bl1nk-search by editing exactly one constant — never hand-edit publish() calls or hand-type dates
source: auto-skill
extracted_at: '2026-07-09T12:34:11.889Z'
---

# Bump a base image version (bl1nk-rust / bl1nk-search)

The `modal-images/` directory has a strict "one helper, one constant" rule for image versioning. Violating it is the single most common mistake agents make when working in this repo. This skill is the canonical way to bump a major version.

## When to use

- Bumping `bl1nk-rust` from `v2` → `v3`
- Bumping `bl1nk-search` from `v1` → `v2`
- **NOT** for changing the image contents (toolchain upgrades, new packages) — that's a code change to the build script, not a version bump. The version tracks major architectural releases, not every code change.

## What the rule actually is

`modal-images/_tags.py` exposes `publish_versioned()` which is the **only** mechanism for publishing these images. It is shared by both `build_bl1nk_rust.py` and `build_bl1nk_search.py` precisely so that "rebuild" never means hand-editing a version string in more than one place, or hand-typing today's date.

Every successful build publishes **three tags** automatically:

| Tag | Source | Example |
| --- | --- | --- |
| `:latest` | hardcoded | `bl1nk-rust:latest` |
| `:vN` | `MAJOR_VERSION` constant at the top of the build script | `bl1nk-rust:v2` |
| `:vN-YYYYMMDD` | today's date, computed at build time | `bl1nk-rust:v2-20260709` |

Consumers (`modal-apps/bl1nk-app/modal_app.py` and the search service) **always pin to `:latest`**, so they never need updating when a new version is published.

## The procedure

To bump the major version of, e.g., `bl1nk-rust`:

1. Open `modal-images/build_bl1nk_rust.py`.
2. Find the `MAJOR_VERSION` constant near the top of the file.
3. Change `MAJOR_VERSION = "v2"` → `MAJOR_VERSION = "v3"`.
4. Run the build: `cd modal-images && modal run build_bl1nk_rust.py`.
5. Confirm the build script published all three tags: `bl1nk-rust:latest`, `bl1nk-rust:v3`, `bl1nk-rust:v3-YYYYMMDD`.

The same procedure applies to `bl1nk-search` via `build_bl1nk_search.py` and `MAJOR_VERSION = "v1"` → `"v2"`.

## What you must NOT do

- **Do not** hand-edit `publish(...)` calls inside the build script to add a "new" tag. The script calls `publish_versioned()` once; that helper does all three publishes. Adding a manual `publish(...)` call duplicates the date logic and breaks the rule.
- **Do not** hand-type today's date in a tag, in a doc, in a comment, or in a script. The date is computed from `datetime.now()` inside `_tags.py` so builds are reproducible from the script alone.
- **Do not** change a consumer to pin to `:v2` or `:v2-20260709` "to be safe". Consumers pin to `:latest`; if a consumer needs to be pinned to a dated tag, that's a separate decision and means something is wrong with `:latest`.
- **Do not** introduce a new build script that bypasses `_tags.py`. If you need a new base image, copy one of the existing scripts and update the `MAJOR_VERSION` constant.
- **Do not** version-bump as a way to "force a rebuild". Modal's image cache keys on the build script contents; if the script content didn't change, the existing image is reused regardless of the tag.

## Verifying it worked

```bash
modal image list | grep bl1nk-rust
# Expect: bl1nk-rust:latest, bl1nk-rust:v3, bl1nk-rust:v3-20260709
```

If you see only `:v2` and no `:v3`, the bump didn't take. The most common cause is editing the wrong constant — there is only one `MAJOR_VERSION` per script, so grep for it:

```bash
grep -n MAJOR_VERSION modal-images/build_bl1nk_rust.py
```

## Why this rule exists (context)

The `modal-images/TODO.md` records that `build_bl1nk_rust.py` originally never built or published the image at all, and `build_bl1nk_search.py` hand-typed the version/date in three separate `built.publish(...)` calls. The `_tags.publish_versioned()` helper was introduced specifically to retire both classes of error. Adding a manual `publish(...)` call reintroduces the original bug pattern. The "no hand-typed date" rule is enforced by `_tags.py` reading `datetime.now()` itself — even a passing test in the build script can't catch a manual date that's correct for today but wrong tomorrow.

## How to apply

Use this skill any time the user says "bump the image", "cut a new version of bl1nk-rust", or asks why `:latest` and `:v2` disagree. If the user wants a code change to the image (new tool, version bump of Node, etc.), that's a different skill — change the build script's `run_commands(...)` block, do not touch `MAJOR_VERSION`.
