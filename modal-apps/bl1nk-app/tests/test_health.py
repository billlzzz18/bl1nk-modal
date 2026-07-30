"""Integration-lite tests via TestClient — sandbox endpoints mocked at store seam."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from modal_app import api

client = TestClient(api)
API = "/api/v1"


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "version": "1.0.0"}


class TestRun:
    def test_run_hermes(self):
        resp = client.post(f"{API}/run/hermes", json={"sub_agent": "hermes"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "hermes"

    def test_run_unknown_agent_returns_400(self):
        resp = client.post(f"{API}/run/unknown", json={"sub_agent": "hermes"})
        assert resp.status_code == 400

    def test_run_hermes_delegates_to_agy(self):
        resp = client.post(
            f"{API}/run/hermes",
            json={"sub_agent": "agy", "cmd": "test", "sync": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"].startswith("task_")
        assert body["result"]["delegated_to"] == "agy"


class TestSandboxAPI:
    """All sandbox endpoints tested through the SandboxStore seam."""

    @patch("modal_app.sandbox_store")
    def test_create_sandbox(self, mock_store):
        mock_store.create.return_value = {
            "sandbox_id": "sb_001", "status": "running",
            "image": "bl1nk-rust:latest", "created_at": "2026-01-01T00:00:00",
        }
        resp = client.post(f"{API}/sandboxes", json={"cmd": "sleep 10"})
        assert resp.status_code == 201
        assert resp.json()["sandbox_id"] == "sb_001"
        mock_store.create.assert_called_once()

    @patch("modal_app.sandbox_store")
    def test_get_running_sandbox(self, mock_store):
        mock_store.get.return_value = {
            "sandbox_id": "sb_001", "status": "running",
            "image": "bl1nk-rust:latest", "created_at": "2026-01-01T00:00:00",
            "uptime_seconds": 42,
        }
        resp = client.get(f"{API}/sandboxes/sb_001")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        assert resp.json()["uptime_seconds"] == 42

    @patch("modal_app.sandbox_store")
    def test_get_unknown_sandbox_404(self, mock_store):
        mock_store.get.return_value = None
        resp = client.get(f"{API}/sandboxes/nonexistent")
        assert resp.status_code == 404

    @patch("modal_app.sandbox_store")
    def test_delete_sandbox(self, mock_store):
        mock_store.delete.return_value = {"sandbox_id": "sb_001", "status": "terminated"}
        resp = client.delete(f"{API}/sandboxes/sb_001")
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"

    @patch("modal_app.sandbox_store")
    def test_delete_unknown_404(self, mock_store):
        mock_store.delete.side_effect = KeyError("not found")
        resp = client.delete(f"{API}/sandboxes/nonexistent")
        assert resp.status_code == 404

    @patch("modal_app.sandbox_store")
    def test_exec_returns_output(self, mock_store):
        mock_store.exec.return_value = {"exit_code": 0, "stdout": "ok\n", "stderr": "", "duration_ms": 5}
        resp = client.post(f"{API}/sandboxes/sb_001/exec", json={"cmd": "echo ok"})
        assert resp.status_code == 200
        assert resp.json()["exit_code"] == 0
        assert resp.json()["stdout"] == "ok\n"

    @patch("modal_app.sandbox_store")
    def test_exec_unknown_404(self, mock_store):
        mock_store.exec.side_effect = KeyError("not found")
        resp = client.post(f"{API}/sandboxes/nonexistent/exec", json={"cmd": "echo"})
        assert resp.status_code == 404

    @patch("modal_app.sandbox_store")
    def test_list_files(self, mock_store):
        mock_store.list_files.return_value = {
            "sandbox_id": "sb_001", "path": "/tmp",
            "files": [{"name": "a.txt", "type": "file", "size": 10, "mode": "-rw-r--r--"}],
        }
        resp = client.get(f"{API}/sandboxes/sb_001/files?path=/tmp")
        assert resp.status_code == 200
        assert len(resp.json()["files"]) == 1

    @patch("modal_app.sandbox_store")
    def test_list_files_unknown_404(self, mock_store):
        mock_store.list_files.side_effect = KeyError("not found")
        resp = client.get(f"{API}/sandboxes/nonexistent/files")
        assert resp.status_code == 404


class TestTasks:
    def test_get_task_not_found(self):
        resp = client.get(f"{API}/tasks/nonexistent")
        assert resp.status_code == 404

    def test_run_creates_task(self):
        resp = client.post(
            f"{API}/run/hermes",
            json={"sub_agent": "hermes", "sync": True},
        )
        task_id = resp.json()["task_id"]

        resp2 = client.get(f"{API}/tasks/{task_id}")
        assert resp2.status_code == 200
        assert resp2.json()["task_id"] == task_id
