"""Search storage backend — persists metadata to PostgreSQL, raw content to R2.

On container start: loads metadata from PG, rebuilds FAISS from R2 content.
On index: writes metadata to PG, raw content to R2.
On query: reads metadata from in-memory cache (synced from PG).

Schema:
  search_docs (
    id TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    parent_id TEXT,
    chunk_index INT DEFAULT 0,
    total_chunks INT DEFAULT 1,
    source_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,       -- key in R2
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Flat metadata fields (indexed)
    agent TEXT, name TEXT, type TEXT, description TEXT,
    path TEXT, repo TEXT, kb_id TEXT, session_id TEXT,
    handler TEXT, schedule TEXT, events TEXT,
    model TEXT, author TEXT, version TEXT,
    tags TEXT[],                     -- PostgreSQL array
    tools TEXT[],
    -- Arbitrary extra fields as JSONB
    extra JSONB DEFAULT '{}'::jsonb
  )
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

# ── Config ───────────────────────────────────────────────────

PG_DSN = os.getenv(
    "SEARCH_PG_DSN",
    f"postgresql://{os.getenv('DB_USER', 'crate')}:{os.getenv('DB_PASSWORD', '')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
    f"/{os.getenv('DB_NAME', 'bl1nk_search')}",
)

R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "")
R2_BUCKET = os.getenv("R2_BUCKET", "bl1nk-search-content")
_R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")  # optional public endpoint


# ── PostgreSQL ───────────────────────────────────────────────

_pg_pool: Any = None  # asyncpg pool, lazily created


async def pg_connect() -> Any:
    """Get or create asyncpg connection pool."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    try:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=5)
        async with _pg_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS search_docs (
                    id TEXT PRIMARY KEY,
                    hash TEXT NOT NULL,
                    parent_id TEXT,
                    chunk_index INT DEFAULT 0,
                    total_chunks INT DEFAULT 1,
                    source_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    agent TEXT, name TEXT, type TEXT, description TEXT,
                    path TEXT, repo TEXT, kb_id TEXT, session_id TEXT,
                    handler TEXT, schedule TEXT, events TEXT,
                    model TEXT, author TEXT, version TEXT,
                    tags TEXT[], tools TEXT[],
                    extra JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_search_docs_hash ON search_docs(hash)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_search_docs_parent ON search_docs(parent_id)
            """)
        return _pg_pool
    except Exception as e:
        print(f"[storage] PG connect failed: {e} (running without persistence)")
        return None


async def pg_save_meta(meta: dict) -> bool:
    """Upsert a document's metadata into PostgreSQL."""
    pool = await pg_connect()
    if pool is None:
        return False
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO search_docs (
                id, hash, parent_id, chunk_index, total_chunks,
                source_type, content_hash,
                agent, name, type, description,
                path, repo, kb_id, session_id,
                handler, schedule, events,
                model, author, version,
                tags, tools, extra
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24)
            ON CONFLICT (id) DO UPDATE SET
                hash=EXCLUDED.hash, updated_at=NOW(),
                source_type=EXCLUDED.source_type, content_hash=EXCLUDED.content_hash,
                agent=EXCLUDED.agent, name=EXCLUDED.name, type=EXCLUDED.type,
                description=EXCLUDED.description, tags=EXCLUDED.tags, extra=EXCLUDED.extra
        """,
            meta.get("id"), meta.get("hash"), meta.get("parent_id"),
            meta.get("chunk_index", 0), meta.get("total_chunks", 1),
            meta.get("source_type", ""), meta.get("content_hash", meta.get("hash", "")),
            meta.get("agent"), meta.get("name"), meta.get("type"), meta.get("description"),
            meta.get("path"), meta.get("repo"), meta.get("kb_id"), meta.get("session_id"),
            meta.get("handler"), meta.get("schedule"), meta.get("events"),
            meta.get("model"), meta.get("author"), meta.get("version"),
            meta.get("tags", []), meta.get("tools", []),
            json.dumps({k: v for k, v in meta.items()
                        if k not in _META_FIELDS and k not in ("id", "hash", "content_hash", "content")}),
        )
        return True


_META_FIELDS = frozenset({
    "id", "hash", "parent_id", "chunk_index", "total_chunks",
    "source_type", "content_hash", "content",
    "agent", "name", "type", "description",
    "path", "repo", "kb_id", "session_id",
    "handler", "schedule", "events",
    "model", "author", "version", "tags", "tools",
})


async def pg_load_all() -> list[dict]:
    """Load all non-deleted metadata from PostgreSQL."""
    pool = await pg_connect()
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM search_docs ORDER BY created_at ASC")
        result = []
        for r in rows:
            meta = dict(r)
            extra = meta.pop("extra", {}) or {}
            if isinstance(extra, str):
                extra = json.loads(extra)
            meta.update(extra)
            meta["content_hash"] = meta.get("content_hash") or meta.get("hash", "")
            result.append(meta)
        return result


async def pg_delete(id: str) -> bool:
    """Mark a document as deleted (soft-delete via DB)."""
    pool = await pg_connect()
    if pool is None:
        return False
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM search_docs WHERE id = $1", id)
        return True


# ── R2 (S3-compatible object storage) ────────────────────────

_r2_client: Optional[httpx.Client] = None


def _r2() -> httpx.Client:
    """Get or create R2 HTTP client (S3-compatible API)."""
    global _r2_client
    if _r2_client is not None:
        return _r2_client
    if not R2_ENDPOINT:
        return None
    from httpx import Auth

    class S3Auth(Auth):
        """Minimal S3-compatible auth for R2 (presigned alternative)."""
        def __init__(self, access_key: str, secret_key: str):
            self.access_key = access_key
            self.secret_key = secret_key

        def auth_flow(self, request):
            # Simple token auth for R2 with compatible endpoints
            request.headers["Authorization"] = f"Bearer {self.access_key}"
            yield request

    _r2_client = httpx.Client(base_url=R2_ENDPOINT, auth=S3Auth(R2_ACCESS_KEY, R2_SECRET_KEY))
    return _r2_client


def r2_save(hash_key: str, content: str) -> bool:
    """Save raw content to R2 bucket."""
    client = _r2()
    if client is None:
        return False
    try:
        resp = client.put(f"/{R2_BUCKET}/{hash_key}.txt", content=content.encode("utf-8"))
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[storage] R2 save failed: {e}")
        return False


def r2_load(hash_key: str) -> Optional[str]:
    """Load raw content from R2 bucket."""
    client = _r2()
    if client is None:
        return None
    try:
        resp = client.get(f"/{R2_BUCKET}/{hash_key}.txt")
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def r2_delete(hash_key: str) -> bool:
    """Delete raw content from R2 bucket."""
    client = _r2()
    if client is None:
        return False
    try:
        resp = client.delete(f"/{R2_BUCKET}/{hash_key}.txt")
        resp.raise_for_status()
        return True
    except Exception:
        return False
