# BL1NK SEARCH SYSTEM — V1 SPEC (FINAL COMPLETE)

## 0 SYSTEM SCOPE

SYSTEM: bl1nk-search
SCOPE: code search, doc search, session search, memory search
NON-SCOPE: training, fine-tuning, distributed systems, multi-node orchestration, raw data lake

## 1 FUNCTION CONTRACT

- fn index(payload: IndexPayload) -> IndexResult
- fn query(request: QueryRequest) -> QueryResult
- fn delete(request: DeleteRequest) -> DeleteResult
- fn update(request: UpdateRequest) -> UpdateResult

## 2 DATA MODELS

```rust
struct IndexPayload { id: String, source_type: SourceType, content: String, metadata: Metadata }
struct QueryRequest { source_type: SourceType, query: String, top_k: Option<u32> }
struct DeleteRequest { id: String, source_type: SourceType }
struct UpdateRequest { id: String, source_type: SourceType, content: Option<String>, metadata: Option<Metadata> }

enum SourceType { Code, Memory, Doc, Session }
struct Metadata { path: Option<String>, repo: Option<String>, session_id: Option<String>, kb_id: Option<String>, tags: Vec<String>, timestamp: i64, version: Option<String> }

struct IndexResult { success: bool, id: String, trace_id: String, error: Option<Error> }
struct QueryResult { results: Vec<SearchHit>, meta: QueryMeta }
struct DeleteResult { success: bool, id: String, trace_id: String, error: Option<Error> }
struct UpdateResult { success: bool, id: String, trace_id: String, version: Option<String>, error: Option<Error> }

struct SearchHit { id: String, score: f32, content: String }
struct QueryMeta { latency_ms: u128, empty: bool, trace_id: String }
struct Error { code: String, message: String, details: Option<String> }
```

## 3 API CONTRACT

POST /index
POST /query
POST /update
POST /delete
GET /health

## 4 ERROR HANDLING

HTTP Status: 200/400/401/403/404/429/500
Error response: success=false, error.code, error.message, optional error.details, trace_id

## 5 AUTH & SECURITY

API Key required for all endpoints except /health.
Header: Authorization: Bearer token.
Roles: admin -> index/update/delete; user -> query only.

## 6 PAGINATION & LIMITS

default top_k = 10, max top_k = 100.
Optional cursor pagination: next_cursor returned when cursor is provided.

## 7 HEALTH SPEC

GET /health
{
  "status": "ok",
  "latency_ms": 12,
  "services": { "vector_store": "ok", "r2": "ok", "embedder": "ok", "reranker": "ok" },
  "trace_id": "string"
}

## 8 CONSISTENCY RULES

Index: overwrite by id.
Update: partial merge allowed, metadata shallow merge, content overwrite if provided.
Delete: soft delete default, hard delete optional flag.
Versioning: optional per update, monotonic version supported.

## 9 TRACEABILITY

ALL operations MUST include trace_id. Applies to: index, query, update, delete, health.

## 10 CONCURRENCY MODEL

Stateless API layer. Idempotent index/update by id. Concurrent writes allowed. Last-write-wins unless version provided.

## 11 STORAGE CONTRACT

R2: normalized chunks only.
Vector Store: embedding vectors keyed by id + source_type.
Metadata Store: indexed fields only, used for filtering.

## 12 INTERNAL PIPELINE RULES

INDEX: chunk -> embed -> store vector -> store metadata -> store chunk
QUERY: embed query -> vector search -> filter metadata -> rerank -> return

## 13 CLIENT CONTRACT

CLI:
- search index <source>
- search query "<text>"
- search update <id>
- search delete <id>

Tool call:
{
  "name": "query",
  "arguments": {
    "source_type": "code",
    "query": "auth flow"
  }
}
