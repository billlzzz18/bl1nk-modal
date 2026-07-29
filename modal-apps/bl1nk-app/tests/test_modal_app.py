import modal_app


def test_sandbox_manager_singleton():
    assert modal_app.get_sandbox_manager() is modal_app.get_sandbox_manager()


def test_sandbox_manager_defaults():
    mgr = modal_app.SandboxManager()
    assert mgr.DEFAULT_TIMEOUT == 3600
    assert mgr.DEFAULT_MAX_LIFETIME == 7200
    assert mgr.CLEANUP_INTERVAL == 300


def test_list_sandboxes_empty():
    assert modal_app.SandboxManager().list_sandboxes() == []


def test_destroy_nonexistent():
    assert modal_app.SandboxManager().destroy_sandbox("nonexistent") is False
