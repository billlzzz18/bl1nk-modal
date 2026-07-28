"""Vector store abstraction — pluggable backends behind a single seam.

Interface:
  search(query_vec, top_k, filter_fn) → [(id, score, meta)]
  upsert(id, vec, metadata)
  delete(id)
  list() → [id]
  rebuild(docs)  — full re-index

Backends:
  FAISS   — in-memory, fast, ephemeral (default)
  Qdrant  — self-hosted vector DB
  Milvus  — distributed vector DB  
  LanceDB — serverless, embedded
  Zilliz  — managed Milvus cloud
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

import numpy as np


# ── Interface ────────────────────────────────────────────────

class VectorStore(ABC):
    """Seam: all vector operations behind one interface."""

    @abstractmethod
    def search(self, query_vec: np.ndarray, top_k: int = 10,
               filter_fn: Optional[Callable[[str], bool]] = None) -> list[tuple[str, float, dict]]:
        ...

    @abstractmethod
    def upsert(self, id: str, vec: np.ndarray, metadata: dict) -> None:
        ...

    @abstractmethod
    def delete(self, id: str) -> None:
        ...

    @abstractmethod
    def list_ids(self) -> list[str]:
        ...

    @abstractmethod
    def rebuild(self, docs: list[tuple[str, str, dict]]) -> None:
        """Full re-index from [(id, content, metadata), ...]."""
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        ...


# ── FAISS (default, in-memory) ──────────────────────────────

class FAISSStore(VectorStore):
    """In-memory FAISS — fast, ephemeral, no infra needed."""

    def __init__(self, dim: int = 384):
        import faiss
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self._ids: list[str] = []
        self._metadata: dict[str, dict] = {}

    @property
    def dim(self) -> int:
        return self._dim

    def search(self, query_vec, top_k=10, filter_fn=None):
        if self._index.ntotal == 0:
            return []
        scores, idxs = self._index.search(query_vec, top_k * 2)
        results = []
        for i, idx in enumerate(idxs[0]):
            if idx < 0 or idx >= len(self._ids):
                continue
            sid = self._ids[idx]
            if filter_fn and not filter_fn(sid):
                continue
            meta = self._metadata.get(sid, {})
            results.append((sid, float(scores[0][i]), meta))
            if len(results) >= top_k:
                break
        return results

    def upsert(self, id, vec, metadata):
        if id in self._ids:
            idx = self._ids.index(id)
            # FAISS doesn't support direct update — mark old, add new
            self._ids[idx] = f"__deleted_{id}"
        self._index.add(vec)
        self._ids.append(id)
        self._metadata[id] = metadata

    def delete(self, id):
        if id in self._ids:
            idx = self._ids.index(id)
            self._ids[idx] = f"__deleted_{id}"
        self._metadata.pop(id, None)

    def list_ids(self):
        return [sid for sid in self._ids if not sid.startswith("__deleted_")]

    def rebuild(self, docs):
        import faiss
        self._index = faiss.IndexFlatIP(self._dim)
        self._ids = []
        self._metadata = {}
        for sid, content, meta in docs:
            vec = meta.pop("__vector__", None)
            if vec is not None:
                self._index.add(vec)
                self._ids.append(sid)
                self._metadata[sid] = meta


# ── Qdrant ──────────────────────────────────────────────────

class QdrantStore(VectorStore):
    """Qdrant vector database — remote, persistent."""

    def __init__(self, dim: int = 384, collection: str = "bl1nk_search",
                 host: str = "", api_key: str = ""):
        self._dim = dim
        self._collection = collection
        self._host = host or os.getenv("QDRANT_HOST", "localhost")
        self._api_key = api_key or os.getenv("QDRANT_API_KEY", "")
        self._client = None

    def _connect(self):
        if self._client is not None:
            return
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams
        self._client = QdrantClient(host=self._host, api_key=self._api_key or None)
        # Ensure collection exists
        try:
            self._client.get_collection(self._collection)
        except Exception:
            self._client.create_collection(
                self._collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.DOT),
            )

    @property
    def dim(self) -> int:
        return self._dim

    def search(self, query_vec, top_k=10, filter_fn=None):
        self._connect()
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        hits = self._client.search(
            self._collection,
            query_vector=query_vec[0].tolist(),
            limit=top_k,
        )
        results = []
        for h in hits:
            sid = h.id
            if filter_fn and not filter_fn(sid):
                continue
            results.append((sid, h.score, h.payload or {}))
        return results

    def upsert(self, id, vec, metadata):
        self._connect()
        from qdrant_client.http.models import PointStruct
        self._client.upsert(
            self._collection,
            points=[PointStruct(id=id, vector=vec[0].tolist(), payload=metadata)],
        )

    def delete(self, id):
        self._connect()
        self._client.delete(self._collection, points_selector=[id])

    def list_ids(self):
        self._connect()
        from qdrant_client.http.models import Filter
        scroll = self._client.scroll(self._collection, limit=10000)
        return [p.id for p in scroll[0]]

    def rebuild(self, docs):
        self._connect()
        from qdrant_client.http.models import PointStruct
        self._client.delete_collection(self._collection, ignore_errors=True)
        from qdrant_client.http.models import Distance, VectorParams
        self._client.create_collection(
            self._collection,
            vectors_config=VectorParams(size=self._dim, distance=Distance.DOT),
        )
        points = []
        for sid, content, meta in docs:
            vec = meta.pop("__vector__", None)
            if vec is not None:
                points.append(PointStruct(id=sid, vector=vec[0].tolist(), payload=meta))
        if points:
            self._client.upsert(self._collection, points=points)


# ── Milvus ──────────────────────────────────────────────────

class MilvusStore(VectorStore):
    """Milvus vector database — distributed, persistent."""

    def __init__(self, dim: int = 384, collection: str = "bl1nk_search",
                 host: str = "", port: str = ""):
        self._dim = dim
        self._collection = collection
        self._host = host or os.getenv("MILVUS_HOST", "localhost")
        self._port = port or os.getenv("MILVUS_PORT", "19530")
        self._connected = False

    def _connect(self):
        if self._connected:
            return
        from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
        connections.connect(host=self._host, port=self._port)
        if utility.has_collection(self._collection):
            self._col = Collection(self._collection)
        else:
            schema = CollectionSchema([
                FieldSchema("id", DataType.VARCHAR, max_length=255, is_primary=True),
                FieldSchema("vector", DataType.FLOAT_VECTOR, dim=self._dim),
                FieldSchema("metadata", DataType.JSON),
            ])
            self._col = Collection(self._collection, schema)
            idx = {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}}
            self._col.create_index("vector", idx)
        self._col.load()
        self._connected = True

    @property
    def dim(self) -> int:
        return self._dim

    def search(self, query_vec, top_k=10, filter_fn=None):
        self._connect()
        results = self._col.search(
            data=query_vec,
            anns_field="vector",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=["id", "metadata"],
        )
        hits = []
        for r in results[0]:
            sid = r.id
            if filter_fn and not filter_fn(sid):
                continue
            hits.append((sid, r.score, r.entity.get("metadata", {})))
        return hits

    def upsert(self, id, vec, metadata):
        self._connect()
        self._col.upsert([[id, vec[0].tolist(), metadata]])

    def delete(self, id):
        self._connect()
        self._col.delete(f'id == "{id}"')

    def list_ids(self):
        self._connect()
        results = self._col.query(expr="", output_fields=["id"], limit=10000)
        return [r["id"] for r in results]

    def rebuild(self, docs):
        self._connect()
        from pymilvus import utility
        utility.drop_collection(self._collection)
        self._connected = False
        self._connect()
        for sid, content, meta in docs:
            vec = meta.pop("__vector__", None)
            if vec is not None:
                self._col.insert([[sid, vec[0].tolist(), meta]])


# ── LanceDB ─────────────────────────────────────────────────

class LanceDBStore(VectorStore):
    """LanceDB — serverless, embedded vector DB (local files)."""

    def __init__(self, dim: int = 384, uri: str = "/tmp/lancedb"):
        self._dim = dim
        self._uri = uri
        self._table = None

    def _connect(self):
        if self._table is not None:
            return
        import lancedb
        db = lancedb.connect(self._uri)
        try:
            self._table = db.open_table("bl1nk_search")
        except Exception:
            import pyarrow as pa
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self._dim)),
                pa.field("metadata", pa.string()),
            ])
            self._table = db.create_table("bl1nk_search", schema=schema)

    @property
    def dim(self) -> int:
        return self._dim

    def search(self, query_vec, top_k=10, filter_fn=None):
        self._connect()
        results = self._table.search(query_vec[0].tolist()).limit(top_k).to_list()
        hits = []
        for r in results:
            sid = r.get("id", "")
            if filter_fn and not filter_fn(sid):
                continue
            import json
            meta = json.loads(r.get("metadata", "{}"))
            hits.append((sid, r.get("_distance", 0), meta))
        return hits

    def upsert(self, id, vec, metadata):
        self._connect()
        import json
        # LanceDB merge_insert upsert
        self._table.merge_insert(["id"]).when_matched_update_all().execute([{
            "id": id, "vector": vec[0].tolist(), "metadata": json.dumps(metadata),
        }])

    def delete(self, id):
        self._connect()
        self._table.delete(f'id = "{id}"')

    def list_ids(self):
        self._connect()
        results = self._table.search().limit(10000).to_list()
        return [r.get("id", "") for r in results]

    def rebuild(self, docs):
        import pyarrow as pa
        self._table = None
        import lancedb
        db = lancedb.connect(self._uri)
        try:
            db.drop_table("bl1nk_search")
        except Exception:
            pass
        self._connect()
        import json
        data = []
        for sid, content, meta in docs:
            vec = meta.pop("__vector__", None)
            if vec is not None:
                data.append({"id": sid, "vector": vec[0].tolist(), "metadata": json.dumps(meta)})
        if data:
            self._table.add(data)


# ── Factory ──────────────────────────────────────────────────

def create_vector_store(backend: str = "faiss", dim: int = 384, **kwargs) -> VectorStore:
    """Factory: create vector store by backend name.

    backends: faiss, qdrant, milvus, lancedb
    env vars: VECTOR_STORE_BACKEND, QDRANT_HOST, MILVUS_HOST, etc.
    """
    backend = backend or os.getenv("VECTOR_STORE_BACKEND", "faiss")
    if backend == "faiss":
        return FAISSStore(dim=dim)
    elif backend == "qdrant":
        return QdrantStore(dim=dim, **kwargs)
    elif backend == "milvus":
        return MilvusStore(dim=dim, **kwargs)
    elif backend == "lancedb":
        return LanceDBStore(dim=dim, **kwargs)
    elif backend in ("zilliz", "ziliz"):
        # Zilliz is managed Milvus — same API, different host
        return MilvusStore(dim=dim, host=kwargs.get("host") or os.getenv("ZILLIZ_HOST", ""),
                           port=kwargs.get("port") or os.getenv("ZILLIZ_PORT", "19530"))
    else:
        raise ValueError(f"Unknown vector store backend: {backend}. Options: faiss, qdrant, milvus, lancedb, zilliz")
