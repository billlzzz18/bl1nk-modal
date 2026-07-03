# TODO - modal-sandbox

## Missing Tests
- [ ] tests/test_api.py - FastAPI endpoint tests (/health, /ready, /version, /info)
- [ ] tests/test_sandbox.py - create/exec/delete sandbox lifecycle
- [ ] tests/test_upload_download.py - file upload/download
- [ ] tests/test_image.py - _make_image() image build verification

## Code Issues
- [ ] modal_app.py line 177: bare `pass` in dev() function — needs implementation
- [ ] No auth middleware on API endpoints (sandbox create/exec accessible to anyone)
- [ ] scripts/publish.sh runs pytest but no tests exist yet
