# TODO - modal-sandbox

## Missing Tests
- [x] tests/test_api.py - FastAPI endpoint tests (/health, /ready, /version, /info, sandbox lifecycle, files)
- [x] tests/test_dev.py - dev() toolchain smoke-test entrypoint
- [ ] tests/test_upload_download.py - file upload/download
- [ ] tests/test_image.py - _make_image() image build verification

## Code Issues
- [x] modal_app.py: dev() now runs a toolchain smoke-test instead of a bare `pass`
- [ ] No auth middleware on API endpoints (sandbox create/exec accessible to anyone)
- [ ] scripts/publish.sh runs pytest but no tests exist yet
