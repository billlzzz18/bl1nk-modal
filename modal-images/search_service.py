from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
import torch
import numpy as np
import faiss
import time
import uuid
import os

from transformers import AutoTokenizer, AutoModel

app = FastAPI(title="bl1nk-search")

API_TOKEN = os.getenv("BL1NK_API_TOKEN", "")
API_TOKEN_ID = os.getenv("BL1NK_TOKEN_ID", "default-token")


def assert_token(authorization: Optional[str]):
    if not API_TOKEN:
        return
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


# Models
EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# Globals
_tokenizer = None
_embed_model = None
_rerank_tokenizer = None
_rerank_model = None
_index: Optional[faiss.IndexFlatIP] = None
_metadata = {}
_ids = []


def get_models():
    global _tokenizer, _embed_model, _rerank_tokenizer, _rerank_model
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL, trust_remote_code=True)
        _embed_model = AutoModel.from_pretrained(EMBED_MODEL, trust_remote_code=True)
        _embed_model.eval()
        if torch.cuda.is_available():
            _embed_model = _embed_model.cuda()
    if _rerank_tokenizer is None:
        _rerank_tokenizer = AutoTokenizer.from_pretrained(RERANK_MODEL)
        _rerank_model = AutoModel.from_pretrained(RERANK_MODEL)
        _rerank_model.eval()
        if torch.cuda.is_available():
            _rerank_model = _rerank_model.cuda()


def embed(text: str) -> np.ndarray:
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=8192, padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.no_grad():
        out = _embed_model(**inputs)
        vec = out.last_hidden_state.mean(dim=1)
    vec = vec / vec.norm(dim=-1, keepdim=True)
    return vec.cpu().numpy().astype("float32")


def rerank(query: str, docs: List[str]) -> List[float]:
    if not docs:
        return []
    pairs = [[query, d] for d in docs]
    inputs = _rerank_tokenizer(pairs, return_tensors="pt", truncation=True, max_length=512, padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.no_grad():
        scores = _rerank_model(**inputs).logits.squeeze(-1)
    return scores.cpu().tolist()


# Data models
class Metadata(BaseModel):
    path: Optional[str] = None
    repo: Optional[str] = None
    session_id: Optional[str] = None
    kb_id: Optional[str] = None
    tags: List[str] = []
    timestamp: int = 0
    version: Optional[str] = None


class SourceType:
    CODE = "code"
    DOC = "doc"
    SESSION = "session"
    MEMORY = "memory"


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


class QueryMeta(BaseModel):
    latency_ms: int
    empty: bool
    trace_id: str


class QueryResult(BaseModel):
    results: List[SearchHit]
    meta: QueryMeta


class DeleteResult(BaseModel):
    success: bool
    id: str
    trace_id: str
    error: Optional[Error] = None


class UpdateRequest(BaseModel):
    id: str
    source_type: str
    content: Optional[str] = None
    metadata: Optional[Metadata] = None


class UpdateResult(BaseModel):
    success: bool
    id: str
    trace_id: str
    version: Optional[str] = None
    error: Optional[Error] = None


class AuthVerifyResponse(BaseModel):
    ok: bool
    token_id: str


@app.get("/")
def root():
    return {
        "service": "bl1nk-search",
        "status": "ok",
        "endpoints": ["/health", "/auth/verify", "/index", "/query", "/update", "/delete", "/code/search", "/docs/search", "/session/search", "/memory/search"],
        "trace_id": str(uuid.uuid4()),
    }


@app.get("/health")
def health():
    services = {
        "vector_store": "ok" if _index is not None else "not_ready",
        "embedder": "ok" if _embed_model is not None else "not_ready",
        "reranker": "ok" if _rerank_model is not None else "not_ready",
        "r2": "ok",
    }
    return {
        "status": "ok",
        "latency_ms": 0,
        "services": services,
        "trace_id": str(uuid.uuid4()),
    }


@app.get("/auth/verify", response_model=AuthVerifyResponse)
def auth_verify(authorization: Optional[str] = Header(None)):
    if not API_TOKEN:
        return AuthVerifyResponse(ok=True, token_id=API_TOKEN_ID)
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    return AuthVerifyResponse(ok=True, token_id=API_TOKEN_ID)


@app.post("/index", response_model=IndexResult)
def index(payload: IndexPayload, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    try:
        get_models()
        vec = embed(payload.content)
        _index.add(vec)
        idx = _index.ntotal - 1
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
        return IndexResult(success=False, id=payload.id, trace_id=tid, error=Error(code="index_error", message=str(e)))


@app.post("/code/search")
def code_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "code"
    return _query_json(request, authorization)


@app.post("/docs/search")
def docs_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "doc"
    return _query_json(request, authorization)


@app.post("/session/search")
def session_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "session"
    return _query_json(request, authorization)


@app.post("/memory/search")
def memory_search(request: dict, authorization: Optional[str] = Header(None)):
    request["source_type"] = "memory"
    return _query_json(request, authorization)


@app.post("/query")
def query(request: dict, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    start = time.time()
    q = request.get("query", "")
    source_type = request.get("source_type")
    top_k = min(request.get("top_k", 10), 100)
    if _index is None or _index.ntotal == 0:
        return _query_empty(tid)
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
            meta = _metadata.get(doc_id, {})
            if source_type and meta.get("source_type") != source_type:
                continue
            hits.append({"id": doc_id, "score": float(scores[0][i]), "content": meta.get("content", "")})
            texts.append(meta.get("content", ""))
            if len(hits) >= top_k:
                break
        if texts:
            rerank_scores = rerank(q, texts)
            for i, h in enumerate(hits):
                h["score"] = rerank_scores[i]
            hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:top_k]
        latency = int((time.time() - start) * 1000)
        return _query_ok(tid, latency, hits)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "query_error", "message": str(e), "trace_id": tid})


def _query_json(request: dict, authorization: Optional[str] = Header(None)):
    return query(request, authorization)


def _query_empty(tid: str):
    return {"results": [], "meta": {"latency_ms": 0, "empty": True, "trace_id": tid}}


def _query_ok(tid: str, latency: int, hits):
    return {
        "results": [{"id": h["id"], "score": h["score"], "content": h["content"]} for h in hits],
        "meta": {"latency_ms": latency, "empty": len(hits) == 0, "trace_id": tid},
    }


@app.post("/delete", response_model=DeleteResult)
def delete(request: dict, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    doc_id = request.get("id")
    source_type = request.get("source_type")
    if doc_id in _metadata:
        del _metadata[doc_id]
    if doc_id in _ids:
        _ids.remove(doc_id)
    return DeleteResult(success=True, id=doc_id, trace_id=tid)


@app.post("/update", response_model=UpdateResult)
def update(request: UpdateRequest, authorization: Optional[str] = Header(None)):
    assert_token(authorization)
    tid = str(uuid.uuid4())
    try:
        if request.id not in _metadata:
            return UpdateResult(success=False, id=request.id, trace_id=tid, error=Error(code="not_found", message="id not found"))
        meta = _metadata[request.id]
        if request.content is not None:
            meta["content"] = request.content
        if request.metadata is not None:
            for k, v in request.metadata.dict(exclude_none=True).items():
                meta[k] = v
        _metadata[request.id] = meta
        return UpdateResult(success=True, id=request.id, trace_id=tid, version=meta.get("version"))
    except Exception as e:
        return UpdateResult(success=False, id=request.id, trace_id=tid, error=Error(code="update_error", message=str(e)))


@app.on_event("startup")
def startup():
    import sys
    sys.setrecursionlimit(2000)
    get_models()
    global _index
    _index = faiss.IndexFlatIP(1024)


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
