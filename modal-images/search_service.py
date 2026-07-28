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
import asyncio
import hashlib
import httpx
import math
import numpy as np
import os
from pathlib import Path
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from transformers import AutoModel, AutoTokenizer

from search_storage import (
    pg_save_meta, pg_delete, r2_save, r2_load, r2_delete, pg_load_all,
)
from search_cache import embed_cache, query_cache, rerank_cache, make_query_hash, make_rerank_hash, invalidate_all


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


TMP_STORE = os.environ.get("TMPDIR", "/tmp") + "/bl1nk-search"


def _fire_and_forget(coro):
    """Run async task in background thread (safe from sync context)."""
    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
            loop.close()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _ensure_tmp_store():
    os.makedirs(TMP_STORE, exist_ok=True)


def _write_content(hash_key: str, content: str):
    """Write raw content to tmp file (not in memory)."""
    _ensure_tmp_store()
    Path(os.path.join(TMP_STORE, f"{hash_key}.txt")).write_text(content, encoding="utf-8")


def _read_content(hash_key: str) -> str:
    """Read raw content from tmp file, fallback to R2."""
    fp = os.path.join(TMP_STORE, f"{hash_key}.txt")
    try:
        return Path(fp).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        content = r2_load(hash_key)
        if content:
            _write_content(hash_key, content)  # cache locally
        return content or ""


def _remove_content(hash_key: str):
    """Remove tmp content file."""
    fp = os.path.join(TMP_STORE, f"{hash_key}.txt")
    try:
        os.remove(fp)
    except OSError:
        pass


def _content(meta: dict) -> str:
    """Get raw content from tmp store using hash field."""
    return _read_content(meta.get("hash", ""))


def _content_truncated(meta: dict, max_len: int = 500) -> str:
    """Get content from tmp, truncated."""
    c = _content(meta)
    return c[:max_len] + "..." if len(c) > max_len else c

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
    """Metadata fields — lightweight, no raw content stored in memory.
    
    Content lives in original sources (tmp, project, qwen memories).
    Search returns metadata + path — fetch content from source when needed.
    """
    model_config = {"extra": "allow"}

    # Identity
    hash: Optional[str] = None         # content hash (dedup / idempotent)
    session_id: Optional[str] = None
    agent: Optional[str] = None        # hermes / agy / opencode / sandbox
    type: Optional[str] = None         # feedback / user / project / reference
    name: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = []
    
    # Source
    source_type: str = ""              # code / doc / session / memory
    path: Optional[str] = None         # where content lives (original file)
    repo: Optional[str] = None
    kb_id: Optional[str] = None
    
    # Agent config (hermes hooks / skills)
    handler: Optional[str] = None
    schedule: Optional[str] = None
    events: Optional[str] = None
    model: Optional[str] = None
    tools: list[str] = []
    author: Optional[str] = None
    version: Optional[str] = None
    
    # Timing
    timestamp: int = 0


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
    note: Optional[str] = None
    chunks: Optional[int] = None
    chunk_ids: Optional[list[str]] = None


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

# BM25 full-text search index (lazy-built)
_bm25: Optional["_BM25Index"] = None


class _BM25Index:
    """Simple in-memory BM25 Okapi index — no extra deps, pure stdlib."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_ids: list[str] = []
        self._tokenized: list[list[str]] = []
        self._avgdl = 0.0
        self._idf: dict[str, float] = {}

    def build(self, docs: list[tuple[str, str]]) -> None:
        """Build index from [(doc_id, content), ...]."""
        self._doc_ids = []
        self._tokenized = []
        total_tokens = 0
        df: dict[str, int] = {}

        for doc_id, content in docs:
            self._doc_ids.append(doc_id)
            tokens = self._tokenize(content)
            self._tokenized.append(tokens)
            total_tokens += len(tokens)
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        n = len(self._doc_ids)
        self._avgdl = total_tokens / max(n, 1)

        # IDF: log((N - df + 0.5) / (df + 0.5))
        for term, doc_freq in df.items():
            self._idf[term] = math.log((n - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_#@\-]+", text.lower())

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Return [(doc_id, bm25_score), ...] sorted descending."""
        q_tokens = self._tokenize(query)
        if not q_tokens or not self._doc_ids:
            return []

        scores: list[tuple[int, float]] = []
        for i, tokens in enumerate(self._tokenized):
            score = 0.0
            doc_len = len(tokens)
            for qt in set(q_tokens):
                tf = tokens.count(qt)
                if tf == 0:
                    continue
                idf = self._idf.get(qt, 0.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1))
                score += idf * numerator / denominator
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: -x[1])
        return [(self._doc_ids[i], s) for i, s in scores[:top_k]]


def _ensure_bm25() -> None:
    """Rebuild BM25 index from current metadata."""
    global _bm25
    with _index_lock:
        alive = [(sid, _content(_metadata.get(sid, {})))
                 for sid in _ids if sid not in _deleted_ids]
        if not alive:
            _bm25 = _BM25Index()
            return
        bm25 = _BM25Index()
        bm25.build(alive)
        _bm25 = bm25


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
    """Dispatch to local or API embedder based on active model type.

    Results cached by content hash (avoids re-embedding, saves API cost).
    """
    cfg = EMBED_MODELS[_active_embed_key]
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    # Check cache
    cached = embed_cache.get(content_hash)
    if cached is not None:
        return np.array(cached, dtype="float32")

    # Compute embedding
    if cfg.get("type") == "api":
        vec = _embed_api(text, cfg)
    else:
        vec = _embed_local(text)

    # Cache result
    embed_cache.put(content_hash, vec.tolist())
    return vec


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
            "/fts/search", "/hybrid/search",
            "/kb/index", "/kb/search", "/kb/list",
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


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for better search coverage."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


# ── Endpoints: index ─────────────────────────────────────────

@app.post("/index")
def index(payload: IndexPayload, authorization: Optional[str] = Header(None)):
    """Index a document. Long content is auto-split into chunks."""
    assert_token(authorization)
    tid = str(uuid.uuid4())
    try:
        get_models()
        chunks = _chunk_text(payload.content)
        chunk_ids = []
        for ci, chunk in enumerate(chunks):
            suffix = f"#chunk{ci}" if len(chunks) > 1 else ""
            chunk_id = f"{payload.id}{suffix}"
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()[:16]

            vec = embed(chunk)
            with _index_lock:
                # Skip if same hash already indexed
                skip = False
                for sid in _ids:
                    if sid not in _deleted_ids and _metadata.get(sid, {}).get("hash") == chunk_hash:
                        skip = True
                        break
                if skip:
                    chunk_ids.append(chunk_id + "(dup)")
                    continue

                if chunk_id in _ids:
                    _deleted_ids.add(chunk_id)
                _index.add(vec)
                _ids.append(chunk_id)
                _write_content(chunk_hash, chunk)

                meta_record = {
                    "hash": chunk_hash,
                    "parent_id": payload.id,
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                    "source_type": payload.source_type,
                    "path": payload.metadata.path,
                    "repo": payload.metadata.repo,
                    "session_id": payload.metadata.session_id,
                    "kb_id": payload.metadata.kb_id,
                    "tags": payload.metadata.tags,
                    "timestamp": payload.metadata.timestamp,
                    "version": payload.metadata.version,
                    "agent": payload.metadata.agent,
                    "type": payload.metadata.type,
                    "name": payload.metadata.name,
                    "description": payload.metadata.description,
                    "handler": payload.metadata.handler,
                    "schedule": payload.metadata.schedule,
                    "events": payload.metadata.events,
                    "model": payload.metadata.model,
                    "tools": payload.metadata.tools,
                    "author": payload.metadata.author,
                }
                if hasattr(payload.metadata, "model_extra") and payload.metadata.model_extra:
                    meta_record.update(payload.metadata.model_extra)
                _metadata[chunk_id] = meta_record
                chunk_ids.append(chunk_id)
                # Persist: metadata → PG, raw content → R2
                meta_record["id"] = chunk_id
                meta_record["content_hash"] = chunk_hash
                _fire_and_forget(pg_save_meta(meta_record))
                r2_save(chunk_hash, chunk)

        global _bm25
        _bm25 = None
        query_cache.clear()
        embed_cache.clear()
        return IndexResult(success=True, id=payload.id, trace_id=tid,
                           chunks=len(chunks), chunk_ids=chunk_ids)
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

    # Check query cache
    qh = make_query_hash(q, source_type, top_k)
    cached = query_cache.get(qh)
    if cached is not None:
        return cached

    with _index_lock:
        if _index is None or _index.ntotal == 0:
            result = {"results": [], "meta": {"latency_ms": 0, "empty": True, "trace_id": tid}}
            query_cache.put(qh, result)
            return result
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
                hits.append({"id": doc_id, "score": float(scores[0][i]), "content": _content(meta)})
                texts.append(_content(meta))
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
    result = {
        "results": [{"id": h["id"], "score": h["score"], "content": h["content"]} for h in hits],
        "meta": {"latency_ms": latency, "empty": len(hits) == 0, "trace_id": tid},
    }
    query_cache.put(qh, result)
    return result


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
    """Search memory (source_type=memory) with optional kb_id filter."""
    request["source_type"] = "memory"
    return query(request, authorization)


# ── Endpoints: Knowledge Base (kb) ───────────────────────────

@app.post("/kb/index")
def kb_index(request: dict, authorization: Optional[str] = Header(None)):
    """Index a document into a knowledge base.

    Convenience wrapper around /index that auto-sets kb_id and source_type.
    """
    assert_token(authorization)
    from pydantic import ValidationError
    kb_id = request.get("kb_id", "")
    if not kb_id:
        raise HTTPException(400, "kb_id is required")

    payload = IndexPayload(
        id=request.get("id", str(uuid.uuid4())),
        source_type=request.get("source_type", "memory"),
        content=request.get("content", ""),
        metadata=Metadata(
            kb_id=kb_id,
            tags=request.get("tags", []),
            path=request.get("path"),
            repo=request.get("repo"),
            session_id=request.get("session_id"),
            timestamp=request.get("timestamp", int(time.time())),
        ),
    )
    return index(payload, authorization)


@app.post("/kb/search")
def kb_search(request: dict, authorization: Optional[str] = Header(None)):
    """Search within a specific knowledge base (kb_id).

    Filters by kb_id in metadata. Returns vector + recency sorted results.
    """
    assert_token(authorization)
    kb_id = request.get("kb_id", "")
    if not kb_id:
        raise HTTPException(400, "kb_id is required")

    tid = str(uuid.uuid4())
    start = time.time()
    query_str = request.get("query", "")
    top_k = min(request.get("top_k", 10), 100)

    with _index_lock:
        # Find all non-deleted docs with matching kb_id
        kb_doc_ids = [
            sid for sid in _ids
            if sid not in _deleted_ids
            and _metadata.get(sid, {}).get("kb_id") == kb_id
        ]
        if not kb_doc_ids:
            latency = int((time.time() - start) * 1000)
            return {"results": [], "meta": {"latency_ms": latency, "empty": True, "trace_id": tid}}

        if not query_str.strip():
            # No query — return recent docs in KB sorted by timestamp
            matches = [(sid, _metadata.get(sid, {}).get("timestamp", 0))
                       for sid in kb_doc_ids]
            matches.sort(key=lambda x: -x[1])
            hits = [{"id": sid, "score": 0, "content": _content_truncated(_metadata.get(sid, {}), 300)}
                    for sid, _ in matches[:top_k]]
            latency = int((time.time() - start) * 1000)
            return {"results": hits, "meta": {"latency_ms": latency, "empty": False, "trace_id": tid}}

        # Has query — use vector search, filter to KB docs only
        get_models()
        q_vec = embed(query_str)
        scores, idxs = _index.search(q_vec, top_k * 3)
        hits = []
        for i, idx in enumerate(idxs[0]):
            if idx < 0 or idx >= len(_ids):
                continue
            sid = _ids[idx]
            if sid not in kb_doc_ids:
                continue
            meta = _metadata.get(sid, {})
            hits.append({"id": sid, "score": float(scores[0][i]),
                         "content": _content_truncated(meta, 500)})
            if len(hits) >= top_k:
                break

    latency = int((time.time() - start) * 1000)
    return {"results": hits, "meta": {"latency_ms": latency, "empty": len(hits) == 0, "trace_id": tid}}


@app.get("/kb/list")
def kb_list(authorization: Optional[str] = Header(None)):
    """List all distinct knowledge base IDs in the index."""
    assert_token(authorization)
    with _index_lock:
        kb_ids = sorted(set(
            meta.get("kb_id", "")
            for sid in _ids if sid not in _deleted_ids
            for meta in [_metadata.get(sid, {})]
            if meta.get("kb_id")
        ))
    return {"kb_ids": kb_ids, "total": len(kb_ids)}

@app.post("/fts/search")
def fts_search(request: dict, authorization: Optional[str] = Header(None)):
    """Pure full-text (BM25) keyword search — no vector similarity."""
    assert_token(authorization)
    query_str = request.get("query", "")
    top_k = min(request.get("top_k", 10), 100)
    source_type = request.get("source_type")

    if _bm25 is None:
        _ensure_bm25()
    if _bm25 is None:
        return {"results": [], "meta": {"latency_ms": 0, "empty": True, "trace_id": str(uuid.uuid4())}}

    start = time.time()
    results = _bm25.search(query_str, top_k)
    hits = []
    for doc_id, score in results:
        meta = _metadata.get(doc_id, {})
        if source_type and meta.get("source_type") != source_type:
            continue
        hits.append({"id": doc_id, "score": round(score, 4),
                     "content": _content_truncated(meta, 500)})
    latency = int((time.time() - start) * 1000)
    return {
        "results": hits,
        "meta": {"latency_ms": latency, "empty": len(hits) == 0, "trace_id": str(uuid.uuid4())},
    }


@app.post("/hybrid/search")
def hybrid_search(request: dict, authorization: Optional[str] = Header(None)):
    """Hybrid search: BM25 + vector scores combined (weighted sum).

    Default weights: 0.3 BM25 + 0.7 vector. Adjust via `alpha` (BM25 weight).
    """
    assert_token(authorization)
    query_str = request.get("query", "")
    top_k = min(request.get("top_k", 10), 100)
    source_type = request.get("source_type")
    alpha = request.get("alpha", 0.3)  # BM25 weight, vector weight = 1 - alpha

    if not query_str.strip():
        return {"results": [], "meta": {"latency_ms": 0, "empty": True, "trace_id": str(uuid.uuid4())}}

    start = time.time()
    tid = str(uuid.uuid4())

    # 1. Get vector results
    vec_resp = query({"query": query_str, "source_type": source_type, "top_k": top_k * 2})
    vec_hits = {h["id"]: h for h in vec_resp.get("results", [])}

    # 2. Get BM25 results
    if _bm25 is None:
        _ensure_bm25()
    bm25_results = _bm25.search(query_str, top_k * 3) if _bm25 else []
    bm25_scores = {doc_id: score for doc_id, score in bm25_results}

    # 3. Combine with weighted sum
    all_ids = set(vec_hits) | set(bm25_scores)
    combined = []
    for doc_id in all_ids:
        v_score = vec_hits[doc_id]["score"] if doc_id in vec_hits else 0.0
        b_score = bm25_scores.get(doc_id, 0.0)
        # Normalize BM25 to [0,1] if possible
        total = (1 - alpha) * v_score + alpha * min(b_score / 10.0, 1.0)
        meta = _metadata.get(doc_id, {})
        if source_type and meta.get("source_type") != source_type:
            continue
        combined.append({"id": doc_id, "score": round(total, 4),
                         "content": _content_truncated(meta, 500)})

    combined.sort(key=lambda x: -x["score"])
    latency = int((time.time() - start) * 1000)
    return {
        "results": combined[:top_k],
        "meta": {"latency_ms": latency, "empty": len(combined) == 0, "trace_id": tid},
    }


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

    Filters by source_type, tags, repo, path, session_id, kb_id,
    plus ANY extra field stored in metadata (dynamic).
    Supports pagination via offset/limit. Results sorted by recency.
    """
    assert_token(authorization)

    # Known fields (explicit for backward compat)
    source_type = request.get("source_type")
    tags_filter = set(request.get("tags", []) or [])
    repo = request.get("repo")
    path_prefix = request.get("path_prefix")
    session_id = request.get("session_id")
    kb_id = request.get("kb_id")
    # Dynamic field filters — any extra key=value
    filters = request.get("filters", {}) or {}
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
            # Dynamic filters: match any key=value
            matched = True
            for fk, fv in filters.items():
                if fk in ("source_type", "tags", "repo", "path", "session_id", "kb_id",
                          "path_prefix", "offset", "limit", "filters"):
                    continue  # handled above
                # Support both scalar and list values
                mv = meta.get(fk)
                if isinstance(fv, list):
                    if mv not in fv:
                        matched = False
                        break
                elif mv != fv:
                    matched = False
                    break
            if not matched:
                continue
            matches.append((meta.get("timestamp", 0), sid, meta))

    matches.sort(key=lambda x: -x[0])
    page = matches[offset:offset + limit]

    return {
        "total": len(matches),
        "offset": offset,
        "limit": limit,
        "results": [
            {"id": sid, "source_type": m.get("source_type"),
             "score": 0, "content": _content_truncated(m, 300),
             "metadata": {k: v for k, v in m.items() if k != "content"}}
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
            "content": _content_truncated(meta, 200),
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
            meta = _metadata.pop(doc_id, {})
            _deleted_ids.add(doc_id)
            # Remove from PG + R2
            _fire_and_forget(pg_delete(doc_id))
            if meta.get("hash"):
                r2_delete(meta["hash"])
        else:
            _deleted_ids.add(doc_id)

    global _bm25
    _bm25 = None  # invalidate BM25 cache
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
            _write_content(meta.get("hash", ""), request.get("content", ""))
        for k in ("source_type", "path", "repo", "session_id", "kb_id", "tags", "timestamp", "version"):
            if k in request:
                meta[k] = request[k]
            elif "metadata" in request and k in request["metadata"]:
                meta[k] = request["metadata"][k]

    return {"success": True, "id": doc_id, "trace_id": tid, "version": meta.get("version")}


# ── Endpoints: admin (compress — auto-compress feature) ──────

@app.post("/admin/compress")
def admin_compress(authorization: Optional[str] = Header(None)):
    """Compact index: acknowledge deleted entries, reset state.

    No re-embedding — raw content not stored in memory.
    Deleted vectors remain in FAISS but filtered by _deleted_ids set.
    """
    assert_token(authorization)
    tid = str(uuid.uuid4())

    with _index_lock:
        removed = len(_deleted_ids)
        alive = len(_ids) - removed
        _deleted_ids.clear()

    return {"success": True, "trace_id": tid,
            "acknowledged_deleted": removed, "remaining": alive}


def _maybe_free_cuda():
    """Free GPU memory if CUDA is available."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ── Endpoints: daemon (triggered by Modal cron) ──────────────

@app.post("/daemon/compact")
def daemon_compact(authorization: Optional[str] = Header(None)):
    """Full index compaction: rebuild FAISS from scratch, removing deleted vectors."""
    assert_token(authorization)
    tid = str(uuid.uuid4())

    with _index_lock:
        alive = [(sid, _content(_metadata.get(sid, {})))
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
    """Initialize: FAISS index, models, and restore from persistent storage."""
    sys.setrecursionlimit(2000)
    get_models()
    global _index, _metadata, _ids
    _index = faiss.IndexFlatIP(EMBED_MODELS[_active_embed_key]["dim"])

    # Try to restore metadata from PostgreSQL + rebuild FAISS from R2
    try:
        loop = asyncio.get_event_loop()
        rows = loop.run_until_complete(pg_load_all())
        if rows:
            for row in rows:
                sid = row.get("id", "")
                content_hash = row.get("content_hash") or row.get("hash", "")
                content = r2_load(content_hash)
                if not content:
                    continue
                # Re-embed
                vec = embed(content)
                _index.add(vec)
                _ids.append(sid)
                row.pop("id", None)
                _metadata[sid] = row
            print(f"[startup] Restored {len(rows)} docs from PG + R2")
    except Exception as e:
        print(f"[startup] PG/R2 restore skipped: {e}")


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
