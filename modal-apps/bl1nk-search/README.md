# bl1nk-search

Search service for bl1nk — embedding indexing + reranked queries.
Deployed as a separate Modal app (not part of `bl1nk-app`).

## Setup

```bash
cd modal-apps/bl1nk-search && uv sync
```

## Deploy

```bash
# 1. Build the bl1nk-search image (from repo root)
cd modal-images && modal run build_bl1nk_search.py

# 2. Deploy the search service
cd ../modal-apps/bl1nk-search && uv run modal deploy deploy.py
```

## Test

```bash
cd modal-apps/bl1nk-search && uv run pytest
```

## Spec

See `docs/BL1NK_SEARCH_V1_SPEC.md` for the full API contract.
