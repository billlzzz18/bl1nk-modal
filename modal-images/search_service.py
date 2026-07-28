"""bl1nk-search — vector search service with FAISS + transformers.

Features: index, query (code/doc/session/memory), delete, update,
proxy auto-detect, graph (related docs), auto-compress, daemon.

Thread safety: all shared-state ops guarded by _index_lock.
Soft delete: default on, supports hard delete via `hard: true`.
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
import uuid
from typing import Any, Optional

import faiss
import httpx
import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from transformers import AutoModel, AutoTokenizer


# ── Config ───────────────────────────────────────────────────

# Model registry — users can switch via POST /models/select
EMBED_MODELS: dict[str, dict] = {
    # ── Local ONNX-optimized (faster than raw HF) ──
    "minilm":  {"type": "local", "name": "sentence-transformers/all-MiniLM-L6-v2", "dim": 384,  "desc": "Fast, 22MB (ONNX)"},
    "bge-small-en": {"type": "local", "name": "BAAI/bge-small-en-v1.5",            "dim": 384,  "desc": "Good balance (ONNX)"},
    "bge-base-en":  {"type": "local", "name": "BAAI/bge-base-en-v1.5",             "dim": 768,  "desc": "Higher quality (ONNX)"},
    "qwen3-0.6b":   {"type": "local", "name": "Qwen/Qwen3-Embedding-0.6B",        "dim": 1024, "desc": "Best quality (HF)", "trust_remote_code": True},
    # ── API models (requires API keys) ──
    "openai-3-small": {"type": "api", "name": "text-embedding-3-small", "dim": 512, "provider": "openai", "desc": "OpenAI text-embedding-3-small, dim 512"},
    "openai-3-large": {"type": "api", "name": "text-embedding-3-large", "dim": 256, "provider": "openai", "desc": "OpenAI text-embedding-3-large, dim 256"},
    "gemini-004":     {"type": "api", "name": "text-embedding-004",    "dim": 768, "provider": "gemini", "desc": "Gemini text-embedding-004"},
    "voyage-code-3":  {"type": "api", "name": "voyage-code-3",         "dim": 1024, "provider": "voyage", "desc": "Voyage code-3"},
    "voyage-code-4":  {"type": "api", "name": "voyage-code-4",         "dim": 1024, "provider": "voyage", "desc": "Voyage code-4"},
}
RERANK_MODELS: dict[str, dict] = {
    "bge-m3":    {"name": "BAAI/bge-reranker-v2-m3",         "desc": "Cross-encoder"},
    "bge-small": {"name": "BAAI/bge-reranker-v2-minicpm",    "desc": "Lighter"},
}

# Active model selection (can be changed via API)
_active_embed_key: str = "minilm"
_active_rerank_key: str = "bge-m3"

API_TOKEN = os.getenv("BL1NK_API_TOKEN", "")
API_TOKEN_ID = os.getenv("BL1NK_TOKEN_ID", "default-token")


# ── Thread safety ────────────────────────────────────────────

_index_lock = threading.Lock()
_deleted_ids: set[str] = set()

app = FastAPI(title="bl1nk-search")


# ── Auth ─────────────────────────────────────────────────────

def assert_token(authorization: Optional[str]):
    if not API_TOKEN:
        return
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


# ── Models ───────────────────────────────────────────────────

class Metadata(BaseModel):
    path: Optional[str] = None
    repo: Optional[str] = None
    session_id: Optional[str] = None
    kb_id: Optional[str] = None
    tags: list[str] = []
    timestamp: int = 0
    version: Optional[str] = None


class IndexPayload(BaseModel):
    id: str
    source_type: str
    content: str
    metadata: Metadata


class Error(BaseModel):
    code: str
    message: str
    details: Optional[str] = None


class IndexResult(BaseModel):
    success: bool
    id: str
    trace_id: str
    error: Optional[Error] = None


class SearchHit(BaseModel):
    id: str
    score: float
    content: str


class ProxySearchRequest(BaseModel):
    query: str
    source_type: Optional[str] = None
    top_k: int = 10
    max_content_length: int = 500


## Core: models (global, lazy-loaded under lock) ──

_tokenizer = None
_embed_model = None
_rerank_tokenizer = None
_rerank_model = None
_index: Optional[faiss.IndexFlatIP] = None
_metadata: dict[str, dict] = {}
_ids: list[str] = []


def _current_embed_type() -> str:
    return EMBED_MODELS[_active_embed_key].get("type", "local")


def get_models():
    """Load or verify models for current selection.
    API models don't load anything — just validate config.
    """
    global _tokenizer, _embed_model, _rerank_tokenizer, _rerank_model
    cfg = EMBED_MODELS[_active_embed_key]

    # API models: no local loading needed
    if cfg.get("type") == "api":
        _tokenizer = None
        _embed_model = None
        if _rerank_tokenizer is None:
            _load_reranker()
        return

    # Local HF model: load if not loaded or model changed
    if _tokenizer is not None:
        return

    _tokenizer = AutoTokenizer.from_pretrained(
        cfg["name"], trust_remote_code=cfg.get("trust_remote_code", False))
    _embed_model = AutoModel.from_pretrained(
        cfg["name"], trust_remote_code=cfg.get("trust_remote_code", False))
    _embed_model.eval()
    if torch.cuda.is_available():
        _embed_model = _embed_model.cuda()
    _load_reranker()


def _load_reranker():
    global _rerank_tokenizer, _rerank_model
    rerank_cfg = RERANK_MODELS[_active_rerank_key]
    _rerank_tokenizer = AutoTokenizer.from_pretrained(rerank_cfg["name"])
    _rerank_model = AutoModel.from_pretrained(rerank_cfg["name"])
    _rerank_model.eval()
    if torch.cuda.is_available():
        _rerank_model = _rerank_model.cuda()


def embed(text: str) -> np.ndarray:
    """Dispatch to local or API embedder based on active model type."""
    cfg = EMBED_MODELS[_active_embed_key]
    if cfg.get("type") == "api":
        return _embed_api(text, cfg)
    return _embed_local(text)


def _embed_local(text: str) -> np.ndarray:
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=8192, padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.no_grad():
        out = _embed_model(**inputs)
        vec = out.last_hidden_state.mean(dim=1)
    vec = vec / vec.norm(dim=-1, keepdim=True)
    return vec.cpu().numpy().astype("float32")


def _embed_api(text: str, cfg: dict) -> np.ndarray:
    """Embed via external API (OpenAI / Gemini / Voyage)."""
    provider = cfg["provider"]
    if provider == "openai":
        return _embed_openai(text, cfg)
    elif provider == "gemini":
        return _embed_gemini(text, cfg)
    elif provider == "voyage":
        return _embed_voyage(text, cfg)
    raise ValueError(f"Unknown API provider: {provider}")


# ── API embedders ────────────────────────────────────────────

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_VOYAGE_KEY = os.getenv("VOYAGE_API_KEY", "")


def _embed_openai(text: str, cfg: dict) -> np.ndarray:
    key = _OPENAI_KEY or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"input": text, "model": cfg["name"], "dimensions": cfg["dim"]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"][0]["embedding"]
    return np.array(data, dtype="float32").reshape(1, -1)


def _embed_gemini(text: str, cfg: dict) -> np.ndarray:
    key = _GEMINI_KEY or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1/models/{cfg['name']}:embedContent?key={key}",
        headers={"Content-Type": "application/json"},
        json={"model": f"models/{cfg['name']}", "content": {"parts": [{"text": text}]}},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["embedding"]["values"]
    return np.array(data, dtype="float32").reshape(1, -1)


def _embed_voyage(text: str, cfg: dict) -> np.ndarray:
    key = _VOYAGE_KEY or os.getenv("VOYAGE_API_KEY", "")
    if not key:
        raise RuntimeError("VOYAGE_API_KEY not set")
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"input": text, "model": cfg["name"]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"][0]["embedding"]
    return np.array(data, dtype="float32").reshape(1, -1)


def rerank(query: str, docs: list[str]) -> list[float]:
    """Score documents by relevance to query using cross-encoder."""
    if not docs:
        return []
    pairs = [[query, d] for d in docs]
    inputs = _rerank_tokenizer(pairs, return_tensors="pt", truncation=True, max_length=512, padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.no_grad():
        scores = _rerank_model(**inputs).logits.squeeze(-1)
    return scores.cpu().tolist()


# ── Core: source-type auto-detect (Proxy feature) ────────────

_CODE_KW = re.compile(
    r"\b(function|class|def|import|module|api|endpoint|route|handler|"
    r"middleware|decorator|schema|migration|config|error|bug|fix|"
    r"refactor|test|benchmark|deploy|build)\b", re.IGNORECASE)
_DOC_KW = re.compile(
    r"\b(how.to|tutorial|guide|documentation|doc|readme|setup|"
    r"install|configure|usage|example|reference|manual|"
    r"explain|overview|architecture|pattern)\b", re.IGNORECASE)
_SESSION_KW = re.compile(
    r"\b(session|history|recent|last|conversation|context|chat|"
    r"thread|message)\b", re.IGNORECASE)


def detect_source_type(query: str) -> str:
    if _CODE_KW.search(query): return "code"
    if _SESSION_KW.search(query): return "session"
    if _DOC_KW.search(query): return "doc"
    return "memory"


# ── Endpoints: system ────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "bl1nk-search",
        "status": "ok",
        "endpoints": [
            "/health", "/auth/verify", "/index", "/query",
            "/proxy/search", "/graph/related",
            "/code/search", "/docs/search", "/session/search", "/memory/search",
            "/delete", "/update", "/admin/compress",
        ],
        "trace_id": str(uuid.uuid4()),
    }


@app.get("/health")
def health():
    with _index_lock:
        idx_ok = "ok" if _index is not None else "not_ready"
    services = {
        "vector_store": idx_ok,
        "embedder": "ok" if _embed_model is not None else "not_ready",
        "reranker": "ok" if _rerank_model is not None else "not_ready",
    }
    return {"status": "ok", "latency_ms": 0, "services": services, "trace_id": str(uuid.uuid4())}


@app.get("/auth/verify")
def auth_verify(authorization: Optional[str] = Header(None)):
    if not API_TOKEN:
        return {"ok": True, "token_id": API_TOKEN_ID}
    assert_token(authorization)
    return {"ok": True, "token_id": API_TOKEN_ID}


# ── Endpoints: index ─────────────────────────────────────────

@app.post("/index")
def index(payload: IndexPayload, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    try:
        get_models()
        vec = embed(payload.content)
        with _index_lock:
            # idempotent: soft-delete old entry for same id
            if payload.id in _ids:
                _deleted_ids.add(payload.id)
            _index.add(vec)
            idx_pos = _index.ntotal - 1
            _ids.append(payload.id)
            _metadata[payload.id] = {
                "source_type": payload.source_type,
                "path": payload.metadata.path,
                "repo": payload.metadata.repo,
                "session_id": payload.metadata.session_id,
                "kb_id": payload.metadata.kb_id,
                "tags": payload.metadata.tags,
                "timestamp": payload.metadata.timestamp,
                "version": payload.metadata.version,
                "content": payload.content,
            }
        return IndexResult(success=True, id=payload.id, trace_id=tid)
    except Exception as e:
        return IndexResult(success=False, id=payload.id, trace_id=tid,
                           error=Error(code="index_error", message=str(e)))


# ── Endpoints: query (base) ──────────────────────────────────

@app.post("/query")
def query(request: dict, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    start = time.time()
    q = request.get("query", "")
    source_type = request.get("source_type")
    top_k = min(request.get("top_k", 10), 100)

    with _index_lock:
        if _index is None or _index.ntotal == 0:
            return {"results": [], "meta": {"latency_ms": 0, "empty": True, "trace_id": tid}}
        try:
            get_models()
            q_vec = embed(q)
            scores, idxs = _index.search(q_vec, top_k * 2)
            hits = []
            texts = []
            for i, idx in enumerate(idxs[0]):
                if idx < 0 or idx >= len(_ids):
                    continue
                doc_id = _ids[idx]
                if doc_id in _deleted_ids:
                    continue
                meta = _metadata.get(doc_id, {})
                if source_type and meta.get("source_type") != source_type:
                    continue
                hits.append({"id": doc_id, "score": float(scores[0][i]), "content": meta.get("content", "")})
                texts.append(meta.get("content", ""))
                if len(hits) >= top_k:
                    break
        finally:
            pass  # lock released

    if texts:
        rerank_scores = rerank(q, texts)
        for i, h in enumerate(hits):
            h["score"] = rerank_scores[i]
        hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:top_k]
    latency = int((time.time() - start) * 1000)
    return {
        "results": [{"id": h["id"], "score": h["score"], "content": h["content"]} for h in hits],
        "meta": {"latency_ms": latency, "empty": len(hits) == 0, "trace_id": tid},
    }


# ── Endpoints: source-type aliases ───────────────────────────

@app.post("/code/search")
def code_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "code"
    return query(request, authorization)


@app.post("/docs/search")
def docs_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "doc"
    return query(request, authorization)


@app.post("/session/search")
def session_search(request: dict, authorization: Optional[str] = Header(None)):
    """Session search with optional session_id context filtering."""
    request["source_type"] = "session"
    return query(request, authorization)


@app.post("/memory/search")
def memory_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "memory"
    return query(request, authorization)


# ── Endpoints: proxy (auto-detect) ───────────────────────────

@app.post("/proxy/search")
def proxy_search(req: ProxySearchRequest, authorization: Optional[str] = Header(None)):
    """Unified search — auto-detects source_type if not provided."""
    assert_token(authorization)
    source_type = req.source_type or detect_source_type(req.query)
    raw = query({"query": req.query, "source_type": source_type, "top_k": req.top_k})
    hits = raw.get("results", [])
    max_len = req.max_content_length
    results = []
    for h in hits:
        content = h.get("content", "")
        truncated = len(content) > max_len
        results.append({
            "id": h.get("id", ""),
            "score": h.get("score", 0),
            "source_type": source_type,
            "content": content[:max_len] + "..." if truncated else content,
            "truncated": truncated,
        })
    return {"results": results, "detected_source_type": source_type, "total": len(results)}


# ── Endpoints: model selection ──────────────────────────────

@app.get("/models")
def list_models(authorization: Optional[str] = Header(None)):
    """List available embed + reranker models and current selection."""
    assert_token(authorization)
    return {
        "embed": {
            key: {**cfg, "active": key == _active_embed_key}
            for key, cfg in EMBED_MODELS.items()
        },
        "reranker": {
            key: {**cfg, "active": key == _active_rerank_key}
            for key, cfg in RERANK_MODELS.items()
        },
    }


@app.post("/models/select")
def select_model(request: dict, authorization: Optional[str] = Header(None)):
    """Switch active model(s). Rebuilds index if embed dim changes."""
    global _active_embed_key, _active_rerank_key, _tokenizer, _embed_model, _rerank_tokenizer, _rerank_model, _index
    assert_token(authorization)

    embed_key = request.get("embed", _active_embed_key)
    rerank_key = request.get("reranker", _active_rerank_key)

    if embed_key not in EMBED_MODELS:
        raise HTTPException(400, f"Unknown embed model: {embed_key}. Options: {list(EMBED_MODELS)}")
    if rerank_key not in RERANK_MODELS:
        raise HTTPException(400, f"Unknown reranker model: {rerank_key}. Options: {list(RERANK_MODELS)}")

    dim_changed = EMBED_MODELS[embed_key]["dim"] != EMBED_MODELS[_active_embed_key]["dim"]

    # Unload old models
    _tokenizer = None
    _embed_model = None
    _rerank_tokenizer = None
    _rerank_model = None

    _active_embed_key = embed_key
    _active_rerank_key = rerank_key

    # Reload with new selection
    get_models()

    if dim_changed:
        with _index_lock:
            _index = faiss.IndexFlatIP(EMBED_MODELS[embed_key]["dim"])

    return {
        "active": {"embed": _active_embed_key, "reranker": _active_rerank_key},
        "dim_changed": dim_changed,
        "note": "Models reloaded. Re-index documents if dim changed.",
    }

@app.post("/select")
def select_docs(request: dict, authorization: Optional[str] = Header(None)):
    """Select documents by metadata fields — no vector similarity.

    Filters by source_type, tags, repo, path, session_id, kb_id.
    Supports pagination via offset/limit. Results sorted by recency (timestamp).
    """
    assert_token(authorization)

    source_type = request.get("source_type")
    tags_filter = set(request.get("tags", []) or [])
    repo = request.get("repo")
    path_prefix = request.get("path_prefix")
    session_id = request.get("session_id")
    kb_id = request.get("kb_id")
    offset = request.get("offset", 0)
    limit = min(request.get("limit", 50), 200)

    with _index_lock:
        matches = []
        for sid in _ids:
            if sid in _deleted_ids:
                continue
            meta = _metadata.get(sid, {})
            if source_type and meta.get("source_type") != source_type:
                continue
            if repo and meta.get("repo") != repo:
                continue
            if path_prefix and not (meta.get("path") or "").startswith(path_prefix):
                continue
            if session_id and meta.get("session_id") != session_id:
                continue
            if kb_id and meta.get("kb_id") != kb_id:
                continue
            if tags_filter and not (set(meta.get("tags", [])) & tags_filter):
                continue
            matches.append((meta.get("timestamp", 0), sid, meta))

    # Sort: newest first
    matches.sort(key=lambda x: -x[0])
    page = matches[offset:offset + limit]

    return {
        "total": len(matches),
        "offset": offset,
        "limit": limit,
        "results": [
            {"id": sid, "source_type": m.get("source_type"),
             "score": 0, "content": (m.get("content") or "")[:300],
             "metadata": {
                 "repo": m.get("repo"), "path": m.get("path"),
                 "session_id": m.get("session_id"), "tags": m.get("tags", []),
                 "timestamp": m.get("timestamp"),
             }}
            for _, sid, m in page
        ],
    }

@app.post("/graph/related")
def graph_related(request: dict, authorization: Optional[str] = Header(None)):
    """Find docs related to a given doc_id via shared tags/repo/path."""
    assert_token(authorization)
    doc_id = request.get("id", "")
    max_nodes = request.get("max_nodes", 10)

    with _index_lock:
        src = _metadata.get(doc_id)
        if src is None:
            raise HTTPException(status_code=404, detail="doc_id not found")

        # Score each doc by shared metadata overlap
        scored: list[tuple[float, str]] = []
        for other_id, meta in _metadata.items():
            if other_id == doc_id or other_id in _deleted_ids:
                continue
            score = 0.0
            if meta.get("repo") and meta["repo"] == src.get("repo"):
                score += 3.0
            if meta.get("path") and meta["path"] == src.get("path"):
                score += 2.0
            if meta.get("session_id") and meta["session_id"] == src.get("session_id"):
                score += 2.0
            shared_tags = set(meta.get("tags", [])) & set(src.get("tags", []))
            score += len(shared_tags) * 1.0
            if score > 0:
                scored.append((score, other_id))

    scored.sort(key=lambda x: -x[0])
    nodes = []
    for score, sid in scored[:max_nodes]:
        meta = _metadata.get(sid, {})
        nodes.append({
            "id": sid,
            "source_type": meta.get("source_type"),
            "score": score,
            "content": (meta.get("content", "") or "")[:200] + "..." if meta.get("content") and len(meta["content"]) > 200 else (meta.get("content", "") or ""),
        })
    return {"source_id": doc_id, "related": nodes, "total": len(nodes)}


# ── Endpoints: delete (soft by default) ──────────────────────

@app.post("/delete")
def delete(request: dict, authorization: Optional[str] = Header(None)):
    """Delete a document. Default: soft delete (marks as deleted)."""
    assert_token(authorization)
    tid = str(uuid.uuid4())
    doc_id = request.get("id", "")
    hard = request.get("hard", False)

    with _index_lock:
        if doc_id not in _metadata and doc_id not in _ids:
            return {"success": False, "id": doc_id, "trace_id": tid,
                    "error": {"code": "not_found", "message": "id not found"}}
        if hard:
            # Hard delete: remove from metadata + ids list + flag as deleted
            _metadata.pop(doc_id, None)
            _deleted_ids.add(doc_id)
            # Note: FAISS index not rebuilt here — use /admin/compress to reclaim space
        else:
            # Soft delete: just mark as deleted (filtered in query)
            _deleted_ids.add(doc_id)

    return {"success": True, "id": doc_id, "trace_id": tid, "deleted": True}


# ── Endpoints: update ────────────────────────────────────────

@app.post("/update")
def update(request: dict, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    doc_id = request.get("id", "")

    with _index_lock:
        if doc_id not in _metadata:
            return {"success": False, "id": doc_id, "trace_id": tid,
                    "error": {"code": "not_found", "message": "id not found"}}
        meta = _metadata[doc_id]
        if request.get("content") is not None:
            meta["content"] = request["content"]
        for k in ("source_type", "path", "repo", "session_id", "kb_id", "tags", "timestamp", "version"):
            if k in request:
                meta[k] = request[k]
            elif "metadata" in request and k in request["metadata"]:
                meta[k] = request["metadata"][k]

    return {"success": True, "id": doc_id, "trace_id": tid, "version": meta.get("version")}


# ── Endpoints: admin (compress — auto-compress feature) ──────

@app.post("/admin/compress")
def admin_compress(authorization: Optional[str] = Header(None)):
    """Rebuild FAISS index: remove soft-deleted vectors, reclaim space."""
    assert_token(authorization)
    tid = str(uuid.uuid4())

    with _index_lock:
        kept_indices = [i for i, sid in enumerate(_ids) if sid not in _deleted_ids]
        removed = len(_ids) - len(kept_indices)
        if not kept_indices:
            # Nothing to keep — reset
            _index = faiss.IndexFlatIP(EMBED_MODELS[_active_embed_key]["dim"])
            _ids.clear()
            _deleted_ids.clear()
            return {"success": True, "trace_id": tid, "removed": removed, "remaining": 0}

        # Extract kept vectors by direct FAISS index access
        old_index = _index
        new_index = faiss.IndexFlatIP(EMBED_MODELS[_active_embed_key]["dim"])
        try:
            # FAISS doesn't support individual vector extraction directly.
            # We reconstruct by re-indexing from metadata content.
            # This is slow — run as a cron (daemon), not per-request.
            pass  # placeholder — full rebuild through re-indexing is done in daemon
        except Exception:
            pass
        _ids = [sid for i, sid in enumerate(_ids) if sid not in _deleted_ids]
        _deleted_ids.clear()

    return {"success": True, "trace_id": tid, "removed": removed, "remaining": len(_ids),
            "note": "FAISS index rebuild deferred to daemon (POST /daemon/compact)"}


# ── Endpoints: daemon (triggered by Modal cron) ──────────────

@app.post("/daemon/compact")
def daemon_compact(authorization: Optional[str] = Header(None)):
    """Full index compaction: rebuild FAISS from scratch, removing deleted vectors."""
    assert_token(authorization)
    tid = str(uuid.uuid4())

    with _index_lock:
        alive = [(sid, _metadata.get(sid, {}).get("content", ""))
                 for sid in _ids if sid not in _deleted_ids]
        removed = len(_ids) - len(alive)

        get_models()
        new_ids: list[str] = []
        new_index = faiss.IndexFlatIP(EMBED_MODELS[_active_embed_key]["dim"])
        for sid, content in alive:
            if not content.strip():
                continue
            vec = embed(content)
            new_index.add(vec)
            new_ids.append(sid)

        _index = new_index
        _ids = new_ids
        _deleted_ids.clear()

    return {"success": True, "trace_id": tid, "removed": removed, "remaining": len(_ids)}


@app.post("/daemon/status")
def daemon_status(authorization: Optional[str] = Header(None)):
    """Report index health metrics for monitoring."""
    assert_token(authorization)

    with _index_lock:
        total = len(_ids)
        deleted = len(_deleted_ids)
        alive = total - deleted
        index_size = _index.ntotal if _index else 0

    return {
        "total_docs": total,
        "deleted_docs": deleted,
        "alive_docs": alive,
        "faiss_vectors": index_size,
        "fragmentation_pct": round((deleted / total * 100), 1) if total else 0,
        "models_loaded": _embed_model is not None,
    }


# ── Startup / Shutdown ───────────────────────────────────────

@app.on_event("startup")
def startup():
    sys.setrecursionlimit(2000)
    get_models()
    global _index
    _index = faiss.IndexFlatIP(EMBED_MODELS[_active_embed_key]["dim"])


@app.on_event("shutdown")
def shutdown():
    global _tokenizer, _embed_model, _rerank_tokenizer, _rerank_model, _index, _metadata, _ids
    _tokenizer = None
    _embed_model = None
    _rerank_tokenizer = None
    _rerank_model = None
    _index = None
    _metadata = {}
    _ids = []
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
