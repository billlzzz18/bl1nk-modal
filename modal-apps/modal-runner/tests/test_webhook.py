import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def stub_signature(monkeypatch):
    monkeypatch.setattr(main, "verify_signature", lambda platform, body, headers: True)


def test_rejects_unsupported_platform():
    resp = client.post("/webhook/bitbucket", content=b"{}")
    assert resp.status_code == 400


def test_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(main, "verify_signature", lambda platform, body, headers: False)
    resp = client.post("/webhook/github", content=b"{}")
    assert resp.status_code == 401


def test_sync_processing_returns_tasks(monkeypatch):
    parsed = [{"task_name": "Fix bug", "status": "Done", "priority": "High"}]
    mock_process = AsyncMock(return_value=parsed)
    monkeypatch.setattr(main, "process_commit_payload", mock_process)

    resp = client.post(
        "/webhook/github?sync=true",
        content=json.dumps({"commits": []}).encode(),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["processed"] == 1
    assert body["tasks"] == parsed
    mock_process.assert_awaited_once()


def test_async_processing_returns_accepted(monkeypatch):
    mock_process = AsyncMock(return_value=[])
    monkeypatch.setattr(main, "process_commit_payload", mock_process)

    resp = client.post(
        "/webhook/gitlab",
        content=json.dumps({"commits": []}).encode(),
    )

    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    mock_process.assert_awaited_once()
