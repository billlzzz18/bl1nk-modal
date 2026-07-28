"""Modal integration test — run on actual Modal infra.

Tests the search service roundtrip: index → verify content in tmp → query → verify result.

Usage:
  modal run modal-images/tests/test_search_modal.py
"""

import os

import modal

APP_NAME = "test-bl1nk-search"

app = modal.App(APP_NAME)

# Same image as production, but lighter (no ONNX export needed for test)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi>=0.100.0",
        "transformers>=4.40",
        "torch>=2.2",
        "faiss-cpu>=1.7",
        "numpy>=1.24",
        "httpx>=0.27",
    )
    .add_local_file("modal-images/search_service.py", "/root/search_service.py")
)


@app.function(image=image, timeout=300)
def test_search_roundtrip():
    """Index a doc, verify content written to tmp, query it back."""
    import sys
    sys.path.insert(0, "/root")

    # Standard import (not dynamic) avoids Pydantic forward-ref issues
    # Disable auth for test
    os.environ["BL1NK_API_TOKEN"] = ""

    import search_service as svc
    from fastapi.testclient import TestClient

    # Manually init the FAISS index + models (bypasses startup event timing)
    import faiss
    svc._index = faiss.IndexFlatIP(svc.EMBED_MODELS[svc._active_embed_key]["dim"])
    # Load models (first call downloads from HF)
    try:
        svc.get_models()
    except Exception as e:
        print(f"[WARN] model load (non-fatal for tests): {e}")

    client = TestClient(svc.app)

    # 1. Health check
    resp = client.get("/health")
    assert resp.status_code == 200, f"health failed: {resp.json()}"
    print(f"[PASS] health: {resp.json()['status']}")

    # 2. Index a document
    content = "def hello(): print('Hello, Modal!')"
    index_resp = client.post("/index", json={
        "id": "test-001",
        "source_type": "code",
        "content": content,
        "metadata": {
            "name": "hello function",
            "type": "test",
            "agent": "hermes",
            "repo": "bl1nk-modal",
            "tags": ["python", "test"],
        },
    })
    assert index_resp.status_code == 200, f"index failed: {index_resp.json()}"
    idx_body = index_resp.json()
    assert idx_body["success"] is True, f"index not successful: {idx_body}"
    print(f"[PASS] index: id={idx_body['id']}")

    # 3. Verify content written to tmp
    stored_hash = svc._metadata["test-001"]["hash"]
    tmp_path = f"{svc.TMP_STORE}/{stored_hash}.txt"
    assert os.path.exists(tmp_path), f"tmp file not found: {tmp_path}"
    stored_content = open(tmp_path).read()
    assert stored_content == content, f"tmp content mismatch"
    print(f"[PASS] tmp content: {tmp_path} ({len(stored_content)} bytes)")

    # 4. Query it back
    query_resp = client.post("/query", json={"query": "hello function", "top_k": 5})
    assert query_resp.status_code == 200, f"query failed: {query_resp.json()}"
    results = query_resp.json().get("results", [])
    assert len(results) > 0, f"no results: {query_resp.json()}"
    hit = results[0]
    assert hit["id"] == "test-001", f"wrong result id: {hit}"
    assert "Hello, Modal!" in hit.get("content", ""), f"content not found"
    print(f"[PASS] query: found id={hit['id']} score={hit['score']:.4f}")

    # 5. Verify metadata fields preserved
    meta = svc._metadata["test-001"]
    assert meta["agent"] == "hermes", f"agent field missing"
    assert meta["name"] == "hello function", f"name field missing"
    assert meta["repo"] == "bl1nk-modal", f"repo field missing"
    assert "python" in meta.get("tags", []), f"tags missing"
    print(f"[PASS] metadata: agent={meta.get('agent')}, name={meta.get('name')}")

    # 6. Idempotent — same content, skip
    dup_resp = client.post("/index", json={
        "id": "test-002",
        "source_type": "code",
        "content": content,
        "metadata": {"name": "duplicate"},
    })
    assert dup_resp.status_code == 200
    assert dup_resp.json().get("note") == "duplicate, skipped", f"dedup failed"
    print(f"[PASS] dedup: same hash skipped")

    # 7. Compress
    compress_resp = client.post("/admin/compress")
    assert compress_resp.status_code == 200
    print(f"[PASS] compress: {compress_resp.json()}")

    print("\n✅ All integration tests passed on Modal!")
    return True
