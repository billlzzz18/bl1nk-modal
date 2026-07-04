# Track Registry

This file maintains the registry of all development tracks for bl1nk-modal. Each track represents a distinct body of work with its own spec and implementation plan.

## Status Legend

| Symbol | Status      | Description               |
| ------ | ----------- | -------------------------- |
| `[ ]`  | Pending     | Not yet started           |
| `[~]`  | In Progress | Currently being worked on |
| `[x]`  | Completed   | Finished and verified     |

## Active Tracks

_None yet — run `/conductor:new-track` to create the first one._

## Completed Tracks

<!-- Move completed tracks here -->

## Archived Tracks

<!-- Archived tracks are moved here with reason and date -->

| Track ID | Type | Reason | Archived | Folder |
| -------- | ---- | ------ | -------- | ------ |

## Track Creation Checklist

When creating a new track:

1. [ ] Add entry to this registry
2. [ ] Create track folder: `./tracks/{{track-id}}/`
3. [ ] Create spec.md from template
4. [ ] Create plan.md from template
5. [ ] Create metadata.json from template
6. [ ] Update index.md with new track reference

## Notes

- Track IDs should be lowercase with hyphens (e.g., `storage-adapters`, `cli-bootstrap`).
- Keep descriptions concise (one line).
- Prioritize tracks as: critical, high, medium, low.
- Likely first tracks based on the setup conversation: the vector-store/DB/storage adapter split, and the Rust CLI bootstrap.
