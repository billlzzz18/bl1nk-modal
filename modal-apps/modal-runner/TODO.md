# TODO - modal-runner (commit-tracker)

## Missing Files
- [ ] pyproject.toml - project metadata, dependencies (asyncpg, httpx, fastapi, modal)
- [ ] README.md - usage, deployment instructions, env vars (DB_PASSWORD, LINE_NOTIFY_TOKEN)
- [ ] .gitignore - Python, .venv, .env, __pycache__, .modal

## Missing Tests
- [ ] tests/test_webhook.py - webhook endpoint (GitHub/GitLab/Azure DevOps)
- [ ] tests/test_parse_commit.py - parse_commit_message()
- [ ] tests/test_verify_signature.py - HMAC signature verification per platform
- [ ] tests/test_line_notify.py - send_line_notify()
- [ ] tests/test_update_task.py - asyncpg task update

## Code Issues
- [ ] line 135: bare `pass` in exception handler — should log or re-raise
- [ ] No `modal deploy` or `modal run` entrypoint documented
- [ ] main.py mixes modal.App with FastAPI — verify ASGI integration
