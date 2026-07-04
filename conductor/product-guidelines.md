# Product Guidelines

This is a personal infrastructure repo, not a public-facing product — most of the standard product-guidelines sections (brand voice tables, accessibility compliance, audience messaging) don't apply. What follows is the trimmed set that actually matters here.

## Voice & Tone

Casual and friendly, **primarily in Thai** — documentation should read like notes to oneself, not a public-facing product. Code comments and identifiers stay in English (matches the existing codebase); prose (READMEs, TODOs, this file) can be Thai or English as fits the author.

### Words We Avoid

- Marketing language ("seamless", "revolutionary", "best-in-class") — this is infra for one person and their agents, not a pitch.

## Design Principles

### Principle 1: Simplicity

Reuse existing image tags; rebuild only when the base toolchain, model, or dependencies actually change. Re-deploying a web function does not require rebuilding the image.

**Do:**

- Use `modal.Image.from_name("<tag>")` in deploy scripts.
- Keep build and deploy scripts separate (`build_*.py` vs `deploy_*.py`).

**Don't:**

- Rebuild an image just to ship a route-handler change.

### Principle 2: Cost-awareness

Modal compute costs money per run. Every `modal run` / `modal shell` invocation is billed.

**Do:**

- Get code right locally first; build once.
- Control cost per job — pick resources (CPU/GPU/memory) appropriate to that specific workload, not a one-size-fits-all default.

**Don't:**

- Iterate on Modal itself as a debugging loop.

### Principle 3: Flexible, organized architecture

Favor an architecture that's easy to extend (e.g. the vector-store/DB/storage adapter split) over one that's rigid but "complete."

**Do:**

- Keep each app's dependencies and concerns scoped to its own directory (`modal-apps/<name>/pyproject.toml`).
- Design for swapping a component (e.g. FAISS → another vector store) without touching the rest.

**Don't:**

- Couple apps together through shared global state.

## Error Handling Philosophy

- Be specific about what failed and why.
- Don't swallow exceptions silently (`except: pass`) — log or re-raise.
- Prefer explicit HTTP status codes that match documented API contracts (see the `modal-runner` webhook fix: the async path returns 202 because that's what its own docstring promises).
