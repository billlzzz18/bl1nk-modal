from main import parse_commit_message


def test_parses_all_fields():
    msg = (
        "TaskName: Fix bug, Status: In Progress, Priority: High, "
        "DueDate: 2024-01-01, Assignee: John"
    )
    result = parse_commit_message(msg)
    assert result == {
        "task_name": "Fix bug",
        "status": "In Progress",
        "priority": "High",
        "due_date": "2024-01-01",
        "assignee": "John",
    }


def test_parses_without_optional_fields():
    msg = "TaskName: Fix bug, Status: Done, Priority: Low"
    result = parse_commit_message(msg)
    assert result == {
        "task_name": "Fix bug",
        "status": "Done",
        "priority": "Low",
        "due_date": None,
        "assignee": None,
    }


def test_accepts_semicolon_separators():
    msg = "TaskName: Deploy; Status: Todo; Priority: Medium; Assignee: Alice"
    result = parse_commit_message(msg)
    assert result["task_name"] == "Deploy"
    assert result["assignee"] == "Alice"


def test_case_insensitive_keywords():
    msg = "taskname: Ship it, status: done, priority: low"
    result = parse_commit_message(msg)
    assert result["task_name"] == "Ship it"


def test_returns_none_for_unrelated_message():
    assert parse_commit_message("Just a regular commit message") is None


def test_returns_none_for_missing_priority():
    assert parse_commit_message("TaskName: Fix bug, Status: Done") is None
