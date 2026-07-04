# BL1NK SEARCH SYSTEM — V1 SPEC (FINAL COMPLETE)

---

0 SYSTEM SCOPE

SYSTEM: bl1nk-search

FUNCTIONAL SCOPE:

- code search
- doc search
- session search
- memory search

NON-SCOPE:

- training
- model fine-tuning
- distributed systems
- multi-node orchestration
- raw data lake

---

1 FUNCTION CONTRACT

```
fn index(payload: IndexPayload) -> IndexResult
fn query(request: QueryRequest) -> QueryResult
fn delete(request: DeleteRequest) -> DeleteResult
fn update(request: UpdateRequest) -> UpdateResult
```

---

2 DATA MODELS

### 2.1 IndexPayload

```rust
struct IndexPayload {
    id: String,
    source_type: SourceType,
    content: String,
    metadata: Metadata
}
```

### 2.2 QueryRequest

```rust
struct QueryRequest {
    source_type: SourceType,
    query: String,
    top_k: Option<u32>
}
```

### 2.3 DeleteRequest

```rust
struct DeleteRequest {
    id: String,
    source_type: SourceType
}
```

### 2.4 UpdateRequest

```rust
struct UpdateRequest {
    id: String,
    source_type: SourceType,
    content: Option<String>,
    metadata: Option<Metadata>
}
```

### 2.5 SourceType

```rust
enum SourceType {
    Code,
    Memory,
    Doc,
    Session
}
```

### 2.6 Metadata

```rust
struct Metadata {
    path: Option<String>,
    repo: Option<String>,
    session_id: Option<String>,
    kb_id: Option<String>,
    tags: Vec<String>,
    timestamp: i64,
    version: Option<String>
}
```

### 2.7 IndexResult

```rust
struct IndexResult {
    success: bool,
    id: String,
    trace_id: String,
    error: Option<Error>
}
```

### 2.8 QueryResult

```rust
struct QueryResult {
    results: Vec<SearchHit>,
    meta: QueryMeta
}
```

### 2.9 DeleteResult

```rust
struct DeleteResult {
    success: bool,
    id: String,
    trace_id: String,
    error: Option<Error>
}
```

### 2.10 UpdateResult

```rust
struct UpdateResult {
    success: bool,
    id: String,
    trace_id: String,
    version: Option<String>,
    error: Option<Error>
}
```

### 2.11 SearchHit

```rust
struct SearchHit {
    id: String,
    score: f32,
    content: String
}
```

### 2.12 QueryMeta

```rust
struct QueryMeta {
    latency_ms: u128,
    empty: bool,
    trace_id: String
}
```

### 2.13 Error

```rust
struct Error {
    code: String,
    message: String,
    details: Option<String>
}
```

---

3 API CONTRACT

### 3.1 Endpoints

- POST /index
- POST /query
- POST /update
- POST /delete
- GET /health

---

4 ERROR HANDLING

### 4.1 HTTP Status Mapping

- 200 → success
- 400 → invalid payload / schema error
- 401 → unauthorized
- 403 → forbidden
- 404 → not found
- 429 → rate limit
- 500 → internal error

### 4.2 Error Response

```json
{
  "success": false,
  "error": {
    "code": "STRING",
    "message": "STRING",
    "details": "OPTIONAL"
  },
  "trace_id": "STRING"
}
```

---

5 AUTH & SECURITY

### 5.1 Authentication

API Key required for all endpoints except /health

Header: Authorization: Bearer <token>

### 5.2 Authorization

| role   | permissions           |
|--------|------------------------|
| admin  | index, update, delete  |
| user   | query only             |

---

6 PAGINATION & LIMITS

### 6.1 Query Limits

- default top_k = 10
- max top_k = 100

### 6.2 Pagination Mode

optional: cursor: Option<String>

if cursor is provided: return next_cursor in response

---

7 HEALTH SPEC

GET /health response:

```json
{
  "status": "ok",
  "latency_ms": 12,
  "services": {
    "vector_store": "ok",
    "r2": "ok",
    "embedder": "ok",
    "reranker": "ok"
  },
  "trace_id": "string"
}
```

---

8 CONSISTENCY RULES

### 8.1 Index behavior

default: overwrite by id

### 8.2 Update behavior

- partial merge allowed
- metadata merged shallowly
- content overwrite if provided

### 8.3 Delete behavior

- soft delete default
- hard delete optional flag

### 8.4 Versioning

- optional per update
- monotonic version supported

---

9 TRACEABILITY

ALL operations MUST include trace_id

Applies to:

- index
- query
- update
- delete
- health

---

10 CONCURRENCY MODEL

- stateless API layer
- idempotent index/update operations by id
- concurrent writes allowed
- last-write-wins unless version provided

---

11 STORAGE CONTRACT

### 11.1 R2

normalized chunks only, no raw source dumps

### 11.2 Vector Store

embedding vectors only, keyed by id + source_type

### 11.3 Metadata Store

indexed fields only, used for filtering

---

12 INTERNAL PIPELINE RULES

### 12.1 INDEX

chunk → embed → store vector → store metadata → store chunk

### 12.2 QUERY

embed query → vector search → filter metadata → rerank → return

---

13 CLIENT CONTRACT

CLI:

```
search index <source>
search query "<text>"
search update <id>
search delete <id>
```

TOOL CALL:

```json
{
  "name": "query",
  "arguments": {
    "source_type": "code",
    "query": "auth flow"
  }
}
```

---

END OF SPEC
