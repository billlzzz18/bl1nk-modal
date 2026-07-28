"""Integration-lite tests via TestClient — no real Modal calls."""

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
    def test_create_sandbox(self):
        resp = client.post(f"{API}/sandboxes", json={})
        assert resp.status_code == 201
        body = resp.json()
        assert body["sandbox_id"].startswith("sb_")
        assert body["status"] == "running"

    def test_get_sandbox(self):
        resp = client.get(f"{API}/sandboxes/sb_123")
        assert resp.status_code == 200
        assert resp.json()["sandbox_id"] == "sb_123"

    def test_get_sandbox_not_found(self):
        resp = client.get(f"{API}/sandboxes/invalid")
        assert resp.status_code == 404

    def test_delete_sandbox(self):
        resp = client.delete(f"{API}/sandboxes/sb_123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"

    def test_exec_in_sandbox(self):
        resp = client.post(
            f"{API}/sandboxes/sb_123/exec",
            json={"cmd": "echo hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sandbox_id"] == "sb_123"
        assert body["exit_code"] == 0

    def test_list_sandbox_files(self):
        resp = client.get(f"{API}/sandboxes/sb_123/files?path=/tmp")
        assert resp.status_code == 200
        assert resp.json()["path"] == "/tmp"


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
