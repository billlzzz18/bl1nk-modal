"""Search workflow — queue, worker, pipeline, orchestration on Modal.

Primitives:
  Queue    → modal.Queue (distributed, survives scale-to-zero)
  Worker   → @app.function (background consumer)
  Pipeline → chained @app.function calls
  Workflow → orchestration via .map() / .spawn()

Flow:
  client → submit() → Queue → worker() → embed() → store() → notify()
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

import modal

# ── Modal App ────────────────────────────────────────────────

app = modal.App("bl1nk-search-workflow")
queue = modal.Queue.from_name("bl1nk-search-queue", create_if_missing=True)
results = modal.Dict.from_name("bl1nk-search-results", create_if_missing=True)

# Image with search service dependencies
workflow_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("transformers>=4.40", "torch>=2.2", "faiss-cpu>=1.7", "numpy>=1.24", "httpx>=0.27")
    .add_local_file("modal-images/search_service.py", "/root/search_service.py")
    .add_local_file("modal-images/search_storage.py", "/root/search_storage.py")
)


# ── Task types ───────────────────────────────────────────────

class WorkflowTask:
    INDEX = "index"
    DELETE = "delete"
    COMPRESS = "compress"
    REBUILD = "rebuild"


# ── Pipeline stages ──────────────────────────────────────────

@app.function(image=workflow_image, timeout=120)
def stage_ingest(task: dict) -> dict:
    """Stage 1: validate + chunk the input document."""
    print(f"[ingest] task={task.get('id')}")
    content = task.get("content", "")
    if not content.strip():
        return {**task, "status": "failed", "error": "empty content"}

    # Chunk
    from search_service import _chunk_text
    chunks = _chunk_text(content)
    return {
        **task,
        "status": "ingested",
        "chunks": chunks,
        "num_chunks": len(chunks),
    }


@app.function(image=workflow_image, timeout=120, gpu="any")
def stage_embed(task: dict) -> dict:
    """Stage 2: embed each chunk (calls search_service.embed)."""
    import sys
    sys.path.insert(0, "/root")
    from search_service import get_models, embed

    print(f"[embed] task={task.get('id')}, chunks={task.get('num_chunks')}")
    get_models()

    vectors = []
    for chunk in task.get("chunks", []):
        vec = embed(chunk)
        vectors.append(vec.tolist())

    return {**task, "status": "embedded", "vectors": vectors}


@app.function(image=workflow_image, timeout=120)
def stage_store(task: dict) -> dict:
    """Stage 3: store to FAISS + PostgreSQL + R2."""
    import sys
    sys.path.insert(0, "/root")
    from search_service import faiss, _index_lock, _ids, _index, _metadata, _write_content
    from search_storage import pg_save_meta, r2_save

    print(f"[store] task={task.get('id')}")
    chunk_ids = []
    for i, (chunk, vec_data) in enumerate(zip(task.get("chunks", []), task.get("vectors", []))):
        import hashlib, numpy as np, json, asyncio

        chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()[:16]
        chunk_id = f"{task['id']}#chunk{i}"

        vec = np.array(vec_data, dtype="float32").reshape(1, -1)

        with _index_lock:
            if chunk_id in _ids:
                continue
            if _index is None:
                import faiss as fi
                _index = fi.IndexFlatIP(len(vec_data))
            _index.add(vec)
            _ids.append(chunk_id)
            _write_content(chunk_hash, chunk)

        meta = {
            "id": chunk_id, "hash": chunk_hash,
            "parent_id": task.get("id"), "chunk_index": i,
            "total_chunks": task.get("num_chunks", 1),
            "source_type": task.get("source_type", "memory"),
            "agent": task.get("agent"), "name": task.get("name"),
            "type": task.get("type"), "path": task.get("path"),
            "repo": task.get("repo"), "session_id": task.get("session_id"),
            "kb_id": task.get("kb_id"), "tags": task.get("tags", []),
            "timestamp": int(time.time()),
        }
        _metadata[chunk_id] = meta

        # Fire-and-forget persistence
        meta_copy = dict(meta)
        meta_copy["content_hash"] = chunk_hash
        try:
            from search_service import _fire_and_forget
            _fire_and_forget(pg_save_meta(meta_copy))
            r2_save(chunk_hash, chunk)
        except Exception:
            pass
        chunk_ids.append(chunk_id)

    return {**task, "status": "stored", "chunk_ids": chunk_ids}


@app.function(image=workflow_image, timeout=30)
def stage_notify(task: dict) -> dict:
    """Stage 4: notify (log result). Future: webhook, LINE notify."""
    print(f"[notify] task={task.get('id')} → {task.get('status')}, chunks={len(task.get('chunk_ids', []))}")
    task["status"] = "completed"
    task["completed_at"] = time.time()
    # Store result
    results[task.get("id", str(uuid.uuid4()))] = task
    return task


# ── Worker (queue consumer) ──────────────────────────────────

@app.function(image=workflow_image, concurrency_limit=3, timeout=300)
def worker():
    """Background worker: pop from queue, run pipeline, store result."""
    print("[worker] started, waiting for tasks...")
    while True:
        raw = queue.get(block=True, timeout=60)
        if raw is None:
            break
        task = json.loads(raw) if isinstance(raw, str) else raw

        try:
            # Pipeline: ingest → embed → store → notify
            result = stage_embed.remote(stage_ingest.remote(task))
            result = stage_store.remote(result)
            result = stage_notify.remote(result)
        except Exception as e:
            print(f"[worker] failed: {e}")
            results[task.get("id", "unknown")] = {"status": "failed", "error": str(e)}


# ── Submit API ───────────────────────────────────────────────

@app.function(image=workflow_image, timeout=30)
def submit(task: dict) -> dict:
    """Submit a task to the workflow queue. Returns immediately."""
    task_id = task.get("id", str(uuid.uuid4()))
    task["id"] = task_id
    queue.put(json.dumps(task))
    return {"task_id": task_id, "status": "queued"}


@app.function(image=workflow_image, timeout=30)
def get_result(task_id: str) -> Optional[dict]:
    """Poll for task result."""
    return results.get(task_id)


# ── Scheduled maintenance ────────────────────────────────────

@app.function(schedule=modal.Cron("0 6 * * 0"), timeout=600)
def weekly_maintenance():
    """Weekly: rebuild index, clean up."""
    print("[maintenance] starting weekly search maintenance...")
    submit({"id": "maint-weekly", "type": WorkflowTask.REBUILD, "source_type": "system"})
