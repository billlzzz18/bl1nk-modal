# TODO - modal-runner (commit-tracker)

## Missing Files
- [x] pyproject.toml - project metadata, dependencies (asyncpg, httpx, fastapi, modal)
- [x] README.md - usage, deployment instructions, env vars (DB_PASSWORD, LINE_NOTIFY_TOKEN)
- [x] .gitignore - Python, .venv, .env, __pycache__, .modal

## Missing Tests
- [x] tests/test_webhook.py - webhook endpoint (GitHub/GitLab/Azure DevOps)
- [x] tests/test_parse_commit.py - parse_commit_message()
- [x] tests/test_verify_signature.py - HMAC signature verification per platform
- [x] tests/test_line_notify.py - send_line_notify()
- [x] tests/test_update_task.py - asyncpg task update

## Code Issues
- [ ] line 135: bare `pass` in exception handler — should log or re-raise
- [ ] No `modal deploy` or `modal run` entrypoint documented
- [ ] main.py mixes modal.App with FastAPI — verify ASGI integration
