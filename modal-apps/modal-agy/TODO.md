# TODO - modal-agy (agent-sandbox-orchestrator)

## Missing Files
- [x] pyproject.toml - project metadata and dependencies
- [x] tests/ - test directory

## Missing Tests
- [ ] tests/test_image.py - verify image build (Rust, Node, gh, agy)
- [x] tests/test_modal_app.py - run_orchestrator function
- [ ] tests/test_orchestrator.sh - bash script unit tests

## Code Issues
- [ ] orchestrator.sh copies .agents/.qwen/.gemini/.claude to volume — verify all TARGETS exist
- [ ] run.sh has hardcoded MCP server URLs — should be configurable
- [ ] setup.sh agy plugin install commands may fail if agy CLI not available
- [ ] No error handling in modal_app.py run_orchestrator (FileNotFoundError only)
