from datetime import datetime
from unittest.mock import AsyncMock

from main import update_task


async def test_update_task_upserts_with_parsed_due_date():
    conn = AsyncMock()
    task = {
        "task_name": "Fix bug",
        "status": "Done",
        "priority": "High",
        "due_date": "2024-01-01",
        "assignee": "John",
    }

    await update_task(conn, task, repo="org/repo", platform="github", commit_sha="abc123")

    conn.execute.assert_awaited_once()
    sql, *params = conn.execute.call_args.args
    assert "INSERT INTO tasks" in sql
    assert params[0] == "org/repo:Fix bug"
    assert params[1:4] == ["Fix bug", "Done", "High"]
    assert params[4] == datetime.fromisoformat("2024-01-01")
    assert params[5] == "John"
    assert params[6:9] == ["org/repo", "github", "abc123"]


async def test_update_task_ignores_unparseable_due_date():
    conn = AsyncMock()
    task = {"task_name": "Fix bug", "status": "Done", "priority": "High", "due_date": "not-a-date"}

    await update_task(conn, task, repo="org/repo", platform="gitlab", commit_sha="def456")

    _, *params = conn.execute.call_args.args
    assert params[4] is None


async def test_update_task_without_due_date():
    conn = AsyncMock()
    task = {"task_name": "Ship", "status": "Todo", "priority": "Low"}

    await update_task(conn, task, repo="org/repo", platform="azure", commit_sha="ghi789")

    _, *params = conn.execute.call_args.args
    assert params[4] is None
    assert params[5] is None
