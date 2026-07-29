from fastapi.testclient import TestClient


def _build_test_app():
    from fastapi import FastAPI

    api = FastAPI()

    @api.get("/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @api.get("/")
    def root():
        return {"app": "bl1nk"}

    return api


client = TestClient(_build_test_app())


def test_health():
    assert client.get("/health").json() == {"status": "ok", "version": "1.0.0"}


def test_root():
    assert client.get("/").json()["app"] == "bl1nk"
