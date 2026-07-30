"""Search cache layer — LRU for embeddings + query results.

Embed cache: {content_hash → vector} — avoids re-embedding, critical for API models.
Query cache: {query_hash → results} — TTL-based, for repeated queries.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """Simple LRU cache with max size and optional TTL."""

    def __init__(self, maxsize: int = 1000, ttl: Optional[float] = None):
        self._data: OrderedDict = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._maxsize = maxsize
        self._ttl = ttl  # seconds

    def get(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None
        # TTL check
        if self._ttl is not None:
            age = time.time() - self._timestamps.get(key, 0)
            if age > self._ttl:
                self._data.pop(key, None)
                self._timestamps.pop(key, None)
                return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._timestamps[key] = time.time()
        self._data.move_to_end(key)
        if len(self._data) > self._maxsize:
            oldest = next(iter(self._data))
            self._data.pop(oldest, None)
            self._timestamps.pop(oldest, None)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self) -> None:
        self._data.clear()
        self._timestamps.clear()

    def __len__(self) -> int:
        return len(self._data)

    def keys(self) -> list[str]:
        return list(self._data.keys())


# ── Global caches ────────────────────────────────────────────

# Embedding cache: content_hash → vector (list of float)
# Large maxsize because re-embedding is expensive (especially API models)
embed_cache = LRUCache(maxsize=5000)

# Query result cache: query_hash → [(id, score, content), ...]
# Short TTL because results change with new indexes
query_cache = LRUCache(maxsize=200, ttl=60)

# Rerank cache: query+doc hash → score
rerank_cache = LRUCache(maxsize=2000, ttl=300)


def make_query_hash(query: str, source_type: Optional[str], top_k: int) -> str:
    """Create a deterministic hash for query caching."""
    raw = f"{query}|{source_type or '*'}|{top_k}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_rerank_hash(query: str, doc_id: str) -> str:
    raw = f"rerank|{query}|{doc_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def invalidate_all():
    """Clear all caches — called after index/delete/update."""
    embed_cache.clear()
    query_cache.clear()
    rerank_cache.clear()
