# Implementation Plan

## Phase 1: Security Enhancements [checkpoint: f490af6]
- [x] Task: Enforce Mandatory Password Validation (1e97a78)
  - [x] Write Tests: Ensure missing or invalid passwords return HTTP 401 Unauthorized.
  - [x] Implement Feature: Update `webhook` function in `opencode.py` to make the `password` field strictly required and match `KILO_SERVER_PASSWORD`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Security Enhancements' (Protocol in workflow.md)

## Phase 2: Tool Expansions [checkpoint: 014ec97]
- [x] Task: Implement `tool_edit` (6d2d9c1)
  - [x] Write Tests: Verify `tool_edit` correctly replaces text segments in a file.
  - [x] Implement Feature: Create `tool_edit` function with regex or simple string replacement and add to registry.
- [x] Task: Implement `tool_list_directory` (568b9e7)
  - [x] Write Tests: Verify `tool_list_directory` returns a structured list/tree of files.
  - [x] Implement Feature: Create `tool_list_directory` function and add to registry.
- [x] Task: Implement `tool_websearch` (014ec97)
  - [x] Write Tests: Ensure `tool_websearch` performs an HTTP request and parses results.
  - [x] Implement Feature: Integrate an external search API and replace the placeholder.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Tool Expansions' (Protocol in workflow.md)