# FastAPI Endpoint Notes

## `fastapi_endpoint` vs `asgi_app`

- `@modal.fastapi_endpoint()` - creates a Modal web endpoint/function reachable at `<workspace>--<label>.modal.run`. Use `label=` to control subdomain.
- `@modal.asgi_app()` - full ASGI app web function.
- Both are public web functions. `fastapi_endpoint` is the preferred modern decorator.

## Label Forces New Container

Changing the `label` argument forces Modal to provision a fresh container. Use this when code changes but image tags do not.

## Recursion Pitfall With Wrapped Routes

When wrapper route handlers call other route handlers that return Pydantic `response_model` instances, FastAPI can recurse during JSON encoding and raise `RecursionError`.

Bad:
```python
@app.post("/code/search", response_model=QueryResult)
def code_search(...):
    return query(...)  # query() returns QueryResult(...)
```

Fix:
```python
@app.post("/code/search", response_model=QueryResult)
def code_search(...):
    return _query_json(...)  # returns dict, not QueryResult

def _query_json(request, authorization):
    return query(request, authorization)
```

Or avoid wrapper routes that call Pydantic-returning routes entirely. Mapped paths can share logic by returning plain dicts.

## BGE Reranker Load Report Noise

`BAAI/bge-reranker-v2-m3` emits:
- `UNEXPECTED` for classifier.* weights — normal, ignore.
- `MISSING` for pooler.dense.* — normal, initialized at runtime.

These are not errors and do not require retraining or model changes.

## Mapped Search Paths

Preferred mapped paths for search:
- `/code/search`
- `/docs/search`
- `/session/search`
- `/memory/search`

Each maps directly to `/query` with a fixed `source_type`. Prefer returning plain dicts from shared query helpers to avoid FastAPI response model recursion.

## Deployment Pattern

```
modal-images/
  build_bl1nk_search.py   # image build + publish tags only
  deploy_bl1nk_search.py  # endpoint/function deploy using Image.from_name()
  search_service.py       # FastAPI app
```

Rebuild image only when base deps change; redeploy deploy script for code changes.
