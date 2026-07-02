# Track Specification

## Objective
Implement a functional `websearch` tool to allow the AI agent to search the web and retrieve information. Concurrently, improve the security of the `/webhook` endpoint by enforcing mandatory password validation.

## Scope
- Implement `tool_edit` for targeted code modifications (search and replace).
- Implement `tool_list_directory` (supporting tree-like view) for project exploration.
- Integrate a search API into the `tool_websearch` function.
- Update `webhook` logic in `opencode.py` to reject requests lacking the correct `password`.

## Technical Details
- The search tool should return results securely formatted as JSON to be ingested by the KiloCode / OpenCode conversation loop.
- Password checking must happen before any prompt processing begins.