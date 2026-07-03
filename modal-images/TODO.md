# TODO - modal-images

## Missing Tests
- [x] tests/test_build_rust.py - verify image build steps
- [x] tests/test_build_search.py - verify search image build
- [x] tests/test_search_service.py - FastAPI search/index/query endpoints

## Code Issues
- [x] build_bl1nk_rust.py: build() now runs a toolchain smoke-test instead of a bare `pass`
- [ ] build_bl1nk_search.py uses `App.lookup()` which is deprecated — use `App()` with `@app.function`
- [x] search_service.py: shutdown() now clears model/index globals and frees CUDA cache
- [ ] search_service.py: `_index` and `_ids` are not thread-safe (global mutable state)
- [ ] pyproject.toml: only lists build_bl1nk_rust in setuptools py-modules, missing search_service
