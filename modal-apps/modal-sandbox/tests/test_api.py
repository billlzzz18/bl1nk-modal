from unittest.mock import MagicMock

import modal
import pytest
from fastapi.testclient import TestClient

import modal_app

client = TestClient(modal_app.api)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "0.2.0"}


def test_ready():
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"ready": True}


def test_version():
    resp = client.get("/version")
    assert resp.json() == {"app": "modal-sandbox", "image": "bl1nk-rust:latest"}


def test_info():
    resp = client.get("/info")
    assert resp.json() == {
        "runtime": "modal",
        "app": "modal-sandbox",
        "architecture": "sandbox-id-based",
    }


def test_create_sandbox(monkeypatch):
    mock_sandbox = MagicMock()
    mock_sandbox.object_id = "sb-123"
    monkeypatch.setattr(modal.Sandbox, "create", MagicMock(return_value=mock_sandbox))

    resp = client.post("/sandbox", json={"cmd": ["sleep", "10"]})

    assert resp.status_code == 200
    assert resp.json() == {"sandbox_id": "sb-123", "status": "created"}


def test_delete_sandbox(monkeypatch):
    mock_sandbox = MagicMock()
    monkeypatch.setattr(modal.Sandbox, "from_id", MagicMock(return_value=mock_sandbox))

    resp = client.delete("/sandbox/sb-123")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "sandbox_id": "sb-123"}
    mock_sandbox.terminate.assert_called_once()


def test_exec_in_sandbox(monkeypatch):
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout.read.return_value = "ok\n"
    mock_process.stderr.read.return_value = ""

    mock_sandbox = MagicMock()
    mock_sandbox.exec.return_value = mock_process
    monkeypatch.setattr(modal.Sandbox, "from_id", MagicMock(return_value=mock_sandbox))

    resp = client.post("/sandbox/sb-123/exec", json={"cmd": ["echo", "ok"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "sandbox_id": "sb-123",
        "returncode": 0,
        "stdout": "ok\n",
        "stderr": "",
    }
    mock_sandbox.exec.assert_called_once_with("echo", "ok")


def test_get_status_running(monkeypatch):
    mock_sandbox = MagicMock()
    mock_sandbox.poll.return_value = None
    monkeypatch.setattr(modal.Sandbox, "from_id", MagicMock(return_value=mock_sandbox))

    resp = client.get("/sandbox/sb-123")

    assert resp.json() == {"sandbox_id": "sb-123", "status": "running", "returncode": None}


def test_get_status_terminated(monkeypatch):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_sandbox = MagicMock()
    mock_sandbox.poll.return_value = mock_result
    monkeypatch.setattr(modal.Sandbox, "from_id", MagicMock(return_value=mock_sandbox))

    resp = client.get("/sandbox/sb-123")

    assert resp.json() == {"sandbox_id": "sb-123", "status": "terminated", "returncode": 1}


def test_list_files(monkeypatch):
    mock_sandbox = MagicMock()
    mock_sandbox.filesystem.list_files.return_value = ["a.txt", "b.txt"]
    monkeypatch.setattr(modal.Sandbox, "from_id", MagicMock(return_value=mock_sandbox))

    resp = client.get("/sandbox/sb-123/files", params={"path": "/tmp"})

    assert resp.json() == {"sandbox_id": "sb-123", "path": "/tmp", "files": ["a.txt", "b.txt"]}
    mock_sandbox.filesystem.list_files.assert_called_once_with("/tmp")
