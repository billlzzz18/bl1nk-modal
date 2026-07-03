# TODO - modal-images

## Missing Tests
- [ ] tests/test_build_rust.py - verify image build steps
- [ ] tests/test_build_search.py - verify search image build
- [ ] tests/test_search_service.py - FastAPI search/index/query endpoints

## Code Issues
- [ ] build_bl1nk_rust.py line 50: bare `pass` in build() — needs actual build logic
- [ ] build_bl1nk_search.py uses `App.lookup()` which is deprecated — use `App()` with `@app.function`
- [ ] search_service.py line 348: bare `pass` in shutdown() — should cleanup resources
- [ ] search_service.py: `_index` and `_ids` are not thread-safe (global mutable state)
- [ ] pyproject.toml: only lists build_bl1nk_rust in setuptools py-modules, missing search_service
