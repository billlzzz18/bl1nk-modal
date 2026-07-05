# BL1NK Unified App

Single Modal App replacing 4 previous apps.
- Primary agent dispatch: hermes / agy / opencode / sandbox
- Headless subagents under subagents/
- Tests for union features under tests/

## Run
```bash
uv sync
uv run modal serve modal_app.py
```

## Deploy
```bash
uv run modal deploy modal_app.py --name bl1nk
```
