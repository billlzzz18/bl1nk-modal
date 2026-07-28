"""Integration-lite tests via TestClient — no real Modal calls."""

from fastapi.testclient import TestClient

from modal_app import api

client = TestClient(api)


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "version": "1.0.0"}


class TestRun:
    def test_run_hermes(self):
        resp = client.post("/run/agent/hermes", json={"agent": "hermes"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["primary"] == "hermes"

    def test_run_unknown_agent_returns_400(self):
        resp = client.post("/run/agent/unknown", json={"agent": "hermes"})
        assert resp.status_code == 400

    def test_run_hermes_delegates_to_agy(self):
        resp = client.post("/run/agent/hermes", json={"agent": "agy", "cmd": "test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["delegated_to"] == "agy"
        assert body["status"] == "dispatched"
