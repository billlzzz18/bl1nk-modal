# modal-runner (commit-tracker)

Webhook receiver that parses task metadata out of commit messages (GitHub,
GitLab, Azure DevOps), stores tasks in CrateDB, and notifies LINE Notify.
Deployed as a Modal app with an ASGI (FastAPI) endpoint plus two scheduled
cron jobs for daily/weekly reports.

## Commit message format

```
TaskName: <name>, Status: <status>, Priority: <priority>, DueDate: <iso-date>, Assignee: <name>
```

`DueDate` and `Assignee` are optional.

## Environment / Secrets

Create the following Modal secrets before deploying:

| Secret name | Keys |
|---|---|
| `cratedb-secret` | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |
| `line-notify-secret` | `LINE_TOKEN` |
| `webhook-secrets` | `GITHUB_SECRET`, `GITLAB_SECRET`, `AZURE_DEVOPS_USERNAME`, `AZURE_DEVOPS_PASSWORD` |

```bash
modal secret create cratedb-secret DB_HOST=... DB_PORT=... DB_USER=... DB_PASSWORD=... DB_NAME=...
modal secret create line-notify-secret LINE_TOKEN=...
modal secret create webhook-secrets GITHUB_SECRET=... GITLAB_SECRET=... AZURE_DEVOPS_USERNAME=... AZURE_DEVOPS_PASSWORD=...
```

## Usage

```bash
# local dev server
modal serve main.py

# deploy (registers the ASGI app + cron jobs)
modal deploy main.py
```

## API

- `POST /webhook/{platform}` — `platform` is one of `github`, `gitlab`, `azure`.
  Add `?sync=true` to process synchronously and return the parsed tasks.
- `GET /api/tasks?status=&assignee=` — list tasks, optionally filtered.
- `GET /api/summary/weekly` — task counts by status for the last 7 days.

## Tests

```bash
uv sync
uv run pytest
```
