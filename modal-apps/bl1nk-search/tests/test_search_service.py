from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

import search_service
from search_service import app, assert_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Each test starts from a clean, unauthenticated, empty-index state."""
    monkeypatch.setattr(search_service, "API_TOKEN", "")
    monkeypatch.setattr(search_service, "_index", search_service.faiss.IndexFlatIP(4))
    monkeypatch.setattr(search_service, "_metadata", {})
    monkeypatch.setattr(search_service, "_ids", [])
    yield


def test_assert_token_noop_when_no_token_configured():
    assert_token(None)  # does not raise


def test_assert_token_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(search_service, "API_TOKEN", "secret")
    with pytest.raises(Exception):
        assert_token(None)


def test_assert_token_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(search_service, "API_TOKEN", "secret")
    with pytest.raises(Exception):
        assert_token("Bearer wrong")


def test_assert_token_accepts_correct_token(monkeypatch):
    monkeypatch.setattr(search_service, "API_TOKEN", "secret")
    assert_token("Bearer secret")  # does not raise


def test_root_lists_endpoints():
    resp = client.get("/")
    body = resp.json()
    assert body["service"] == "bl1nk-search"
    assert "/health" in body["endpoints"]


def test_health_reports_not_ready_before_startup():
    resp = client.get("/health")
    body = resp.json()
    assert body["services"]["embedder"] == "not_ready"


def test_auth_verify_without_token_configured():
    resp = client.get("/auth/verify")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_auth_verify_requires_bearer_when_token_configured(monkeypatch):
    monkeypatch.setattr(search_service, "API_TOKEN", "secret")
    resp = client.get("/auth/verify")
    assert resp.status_code == 401


def test_query_returns_empty_when_index_empty():
    resp = client.post("/query", json={"query": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["meta"]["empty"] is True


def test_index_then_query_roundtrip(monkeypatch):
    vectors = {
        "doc-1": np.array([[1.0, 0.0, 0.0, 0.0]], dtype="float32"),
        "doc-2": np.array([[0.0, 1.0, 0.0, 0.0]], dtype="float32"),
    }
    monkeypatch.setattr(search_service, "get_models", lambda: None)
    monkeypatch.setattr(search_service, "embed", lambda text: vectors[text])
    monkeypatch.setattr(search_service, "rerank", lambda query, docs: [1.0 for _ in docs])

    for doc_id, _ in vectors.items():
        resp = client.post(
            "/index",
            json={
                "id": doc_id,
                "source_type": "doc",
                "content": doc_id,
                "metadata": {},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    resp = client.post("/query", json={"query": "doc-1", "top_k": 5})
    body = resp.json()
    assert body["meta"]["empty"] is False
    ids = {hit["id"] for hit in body["results"]}
    assert ids == {"doc-1", "doc-2"}


def test_delete_removes_metadata():
    search_service._metadata["doc-1"] = {"content": "x"}
    search_service._ids.append("doc-1")

    resp = client.post("/delete", json={"id": "doc-1"})

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "doc-1" not in search_service._metadata
    assert "doc-1" not in search_service._ids


def test_update_returns_not_found_for_unknown_id():
    resp = client.post("/update", json={"id": "missing", "source_type": "doc"})
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"


def test_update_modifies_existing_content():
    search_service._metadata["doc-1"] = {"content": "old", "source_type": "doc"}

    resp = client.post("/update", json={"id": "doc-1", "source_type": "doc", "content": "new"})

    assert resp.json()["success"] is True
    assert search_service._metadata["doc-1"]["content"] == "new"


def test_shutdown_resets_global_state(monkeypatch):
    monkeypatch.setattr(search_service, "_tokenizer", MagicMock())
    monkeypatch.setattr(search_service, "_embed_model", MagicMock())
    monkeypatch.setattr(search_service, "_rerank_tokenizer", MagicMock())
    monkeypatch.setattr(search_service, "_rerank_model", MagicMock())
    monkeypatch.setattr(search_service, "_metadata", {"a": {}})
    monkeypatch.setattr(search_service, "_ids", ["a"])

    search_service.shutdown()

    assert search_service._tokenizer is None
    assert search_service._embed_model is None
    assert search_service._rerank_tokenizer is None
    assert search_service._rerank_model is None
    assert search_service._index is None
    assert search_service._metadata == {}
    assert search_service._ids == []
