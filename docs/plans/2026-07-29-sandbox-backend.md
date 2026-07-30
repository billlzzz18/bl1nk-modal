# Sandbox Backend Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace all sandbox API stubs with real `modal.Sandbox` calls so sandbox create/exec/terminate/files work against live Modal sandboxes.

**Architecture:** A `SandboxStore` class wraps `modal.Sandbox.create()` and keeps a `dict[sandbox_id, SandboxHandle]` registry. Each endpoint in `modal_app.py` delegates to `SandboxStore` methods. The store is a thin adapter — easy to mock in tests, easy to swap for a different backend later.

**Tech Stack:** Modal SDK (`modal.Sandbox`, `Sandbox.create()`, `Sandbox.exec()`), FastAPI, Pytest + monkeypatch

**Design pattern:** Adapter — `SandboxStore` wraps `modal.Sandbox` behind a seam that the API layer talks to.

---

### Task 1: Create `SandboxHandle` dataclass + `SandboxStore` class

**Objective:** Define a handle that wraps a `modal.Sandbox` instance plus metadata, and a Store that manages the registry.

**Files:**
- Create: `modal-apps/bl1nk-app/sandbox_store.py`

**Step 1: Write failing test**

Create: `modal-apps/bl1nk-app/tests/test_sandbox_store.py`

```python
"""Tests for SandboxStore — pure logic, mocks Modal."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sandbox_store import SandboxStore, SandboxHandle


class TestSandboxHandle:
    def test_handle_holds_fields(self):
        mock_sb = MagicMock()
        now = datetime.now(timezone.utc)
        h = SandboxHandle(sandbox_id="sb_001", sandbox=mock_sb, image="img:latest", created_at=now)
        assert h.sandbox_id == "sb_001"
        assert h.image == "img:latest"
        assert h.created_at == now
        assert h.sandbox is mock_sb


class TestSandboxStore:
    def test_create_returns_sandbox_id(self):
        store = SandboxStore()
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_mock_001"

        with patch("modal.Sandbox.create", return_value=mock_sb) as mock_create:
            result = store.create(image="img:latest", cmd="sleep 10", cpu=1, memory=256, timeout=60, env={})

        assert result["sandbox_id"] == "sb_mock_001"
        assert result["status"] == "running"
        mock_create.assert_called_once_with(
            image="img:latest", cmd="sleep 10", cpu=1, memory=256, timeout=60, env={},
        )

    def test_get_returns_handle(self):
        store = SandboxStore()
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_001"
        store._sandboxes["sb_001"] = SandboxHandle(
            sandbox_id="sb_001", sandbox=mock_sb, image="img", created_at=datetime.now(timezone.utc),
        )

        result = store.get("sb_001")
        assert result is not None
        assert result.sandbox_id == "sb_001"

    def test_get_unknown_returns_none(self):
        store = SandboxStore()
        assert store.get("nonexistent") is None

    def test_delete_terminates_and_removes(self):
        store = SandboxStore()
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_001"
        store._sandboxes["sb_001"] = SandboxHandle(
            sandbox_id="sb_001", sandbox=mock_sb, image="img", created_at=datetime.now(timezone.utc),
        )

        result = store.delete("sb_001")
        assert result["status"] == "terminated"
        mock_sb.terminate.assert_called_once()
        assert "sb_001" not in store._sandboxes

    def test_delete_unknown_returns_error(self):
        store = SandboxStore()
        result = store.delete("nonexistent")
        assert result["status"] == "not_found"
```

**Step 2: Run test to verify failure**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/test_sandbox_store.py -v`
Expected: FAIL — "ModuleNotFoundError: No module named 'sandbox_store'"

**Step 3: Write minimal implementation**

```python
"""SandboxStore — adapter around modal.Sandbox.

Wraps Modal's Sandbox.create() behind a registry so the API layer
doesn't deal with Modal SDK directly. Swap this for a different
backend (e.g. Docker SDK) without touching the API routes.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import modal


@dataclass
class SandboxHandle:
    sandbox_id: str
    sandbox: modal.Sandbox
    image: str
    created_at: datetime


class SandboxStore:
    """Registry of running sandboxes backed by modal.Sandbox."""

    def __init__(self):
        self._sandboxes: dict[str, SandboxHandle] = {}

    def create(
        self,
        image: str = "bl1nk-rust:latest",
        cmd: str = "sleep infinity",
        cpu: int = 1,
        memory: int = 1024,
        timeout: int = 3600,
        env: dict[str, str] | None = None,
    ) -> dict:
        sb = modal.Sandbox.create(
            image=image,
            cmd=cmd,
            cpu=cpu,
            memory=memory,
            timeout=timeout,
            env=env or {},
        )
        handle = SandboxHandle(
            sandbox_id=sb.object_id,
            sandbox=sb,
            image=image,
            created_at=datetime.now(timezone.utc),
        )
        self._sandboxes[sb.object_id] = handle
        return {"sandbox_id": sb.object_id, "status": "running", "image": image}

    def get(self, sandbox_id: str) -> Optional[SandboxHandle]:
        return self._sandboxes.get(sandbox_id)

    def delete(self, sandbox_id: str) -> dict:
        handle = self._sandboxes.pop(sandbox_id, None)
        if handle is None:
            return {"status": "not_found"}
        handle.sandbox.terminate()
        return {"sandbox_id": sandbox_id, "status": "terminated"}
```

**Step 4: Run test to verify pass**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/test_sandbox_store.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add modal-apps/bl1nk-app/sandbox_store.py modal-apps/bl1nk-app/tests/test_sandbox_store.py
git commit -m "feat(sandbox): add SandboxStore adapter for modal.Sandbox lifecycle"
```

---

### Task 2: Wire `POST /api/v1/sandboxes` to real `modal.Sandbox.create()`

**Objective:** Replace the stub response with a real `SandboxStore.create()` call.

**Files:**
- Modify: `modal-apps/bl1nk-app/modal_app.py` (lines ~97-103)
- Test: `modal-apps/bl1nk-app/tests/test_health.py`

**Step 1: Write failing test**

Update `tests/test_health.py::TestSandboxAPI::test_create_sandbox`:

```python
def test_create_sandbox(self):
    resp = client.post(f"{API}/sandboxes", json={"cmd": "sleep 10", "cpu": 1, "memory": 256})
    assert resp.status_code == 201
    body = resp.json()
    assert body["sandbox_id"].startswith("sb_") or body["sandbox_id"].startswith("sb-")
    assert body["status"] == "running"
```

**Step 2: Run test to verify it passes against current stub**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/test_health.py::TestSandboxAPI -v`
Expected: current test still passes with stub

**Step 3: Wire endpoint to SandboxStore**

In `modal_app.py`:

Add import at top:
```python
from sandbox_store import SandboxStore

# singleton store (injected in tests)
sandbox_store = SandboxStore()
```

Replace `create_sandbox` body:
```python
@api.post("/api/v1/sandboxes", status_code=201)
async def create_sandbox(req: SandboxCreateRequest):
    return sandbox_store.create(
        image=req.image,
        cmd=req.cmd,
        cpu=req.cpu,
        memory=req.memory,
        timeout=req.timeout,
        env=req.env,
    )
```

**Step 4: Run tests (may need to patch SandboxStore in test)**

Since `modal.Sandbox.create()` will be called, the test needs to patch it:

```python
from unittest.mock import patch, MagicMock
from modal_app import api, sandbox_store

class TestSandboxAPI:
    @patch("modal.Sandbox.create")
    def test_create_sandbox(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb-001"
        mock_create.return_value = mock_sb

        resp = client.post(f"{API}/sandboxes", json={"cmd": "sleep 10"})
        assert resp.status_code == 201
        assert resp.json()["sandbox_id"] == "sb-001"
```

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/test_health.py::TestSandboxAPI::test_create_sandbox -v`
Expected: PASS

**Step 5: Commit**

```bash
git add modal-apps/bl1nk-app/modal_app.py modal-apps/bl1nk-app/tests/test_health.py
git commit -m "feat(api): wire POST /sandboxes to real modal.Sandbox.create()"
```

---

### Task 3: Wire `GET /api/v1/sandboxes/{id}` and `DELETE /api/v1/sandboxes/{id}`

**Objective:** Use `SandboxStore.get()` to check `sandbox.poll()` for status, and `SandboxStore.delete()` to terminate.

**Files:**
- Modify: `modal-apps/bl1nk-app/modal_app.py`
- Test: `modal-apps/bl1nk-app/tests/test_health.py`

**Step 1: Write failing test**

```python
@patch("modal_app.sandbox_store")
def test_get_running_sandbox(self, mock_store):
    mock_handle = MagicMock()
    mock_handle.sandbox_id = "sb_001"
    mock_handle.sandbox.poll.return_value = None  # None = still running
    mock_handle.image = "bl1nk-rust:latest"
    mock_store.get.return_value = mock_handle

    resp = client.get(f"{API}/sandboxes/sb_001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

@patch("modal_app.sandbox_store")
def test_get_unknown_sandbox(self, mock_store):
    mock_store.get.return_value = None
    resp = client.get(f"{API}/sandboxes/nonexistent")
    assert resp.status_code == 404

@patch("modal_app.sandbox_store")
def test_delete_sandbox(self, mock_store):
    mock_store.delete.return_value = {"sandbox_id": "sb_001", "status": "terminated"}
    resp = client.delete(f"{API}/sandboxes/sb_001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "terminated"
```

**Step 2: Run test**

Expected: FAIL — endpoints still return stub data

**Step 3: Wire endpoints**

Replace `get_sandbox`:
```python
@api.get("/api/v1/sandboxes/{sandbox_id}")
async def get_sandbox(sandbox_id: str):
    handle = sandbox_store.get(sandbox_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="sandbox not found")
    poll = handle.sandbox.poll()
    status = "running" if poll is None else "terminated"
    created = handle.created_at
    uptime = int((datetime.now(timezone.utc) - created).total_seconds()) if status == "running" else None
    return {
        "sandbox_id": sandbox_id,
        "status": status,
        "image": handle.image,
        "created_at": created.isoformat(),
        "uptime_seconds": uptime,
    }
```

Replace `delete_sandbox`:
```python
@api.delete("/api/v1/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    result = sandbox_store.delete(sandbox_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="sandbox not found")
    return result
```

**Step 4: Run tests**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/test_health.py::TestSandboxAPI -v`
Expected: all 6 sandbox tests PASS

**Step 5: Commit**

```bash
git add modal-apps/bl1nk-app/modal_app.py modal-apps/bl1nk-app/tests/test_health.py
git commit -m "feat(api): wire GET+DElETE /sandboxes to real SandboxStore"
```

---

### Task 4: Wire `POST /api/v1/sandboxes/{id}/exec`

**Objective:** Call `sandbox.exec()` to run commands in the sandbox and capture stdout/stderr/returncode.

**Files:**
- Modify: `modal-apps/bl1nk-app/modal_app.py`
- Modify: `modal-apps/bl1nk-app/tests/test_health.py`

**Step 1: Write failing test**

```python
@patch("modal_app.sandbox_store")
def test_exec_returns_output(self, mock_store):
    mock_handle = MagicMock()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout.read.return_value = b"hello\n"
    mock_proc.stderr.read.return_value = b""
    mock_handle.sandbox.exec.return_value = mock_proc
    mock_store.get.return_value = mock_handle

    resp = client.post(f"{API}/sandboxes/sb_001/exec", json={"cmd": "echo hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_code"] == 0
    assert body["stdout"] == "hello\n"
```

**Step 2: Run test**

Expected: FAIL — stub returns hardcoded output

**Step 3: Wire endpoint**

```python
@api.post("/api/v1/sandboxes/{sandbox_id}/exec")
async def exec_in_sandbox(sandbox_id: str, req: ExecRequest):
    handle = sandbox_store.get(sandbox_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="sandbox not found")
    proc = handle.sandbox.exec(req.cmd)
    stdout = proc.stdout.read().decode() if proc.stdout else ""
    stderr = proc.stderr.read().decode() if proc.stderr else ""
    return {
        "sandbox_id": sandbox_id,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": 0,
    }
```

**Step 4: Run tests**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/ -v`
Expected: all 38+ tests PASS (new + existing)

**Step 5: Commit**

```bash
git add modal-apps/bl1nk-app/modal_app.py modal-apps/bl1nk-app/tests/test_health.py
git commit -m "feat(api): wire POST /sandboxes/{id}/exec to sandbox.exec()"
```

---

### Task 5: Wire `GET /api/v1/sandboxes/{id}/files`

**Objective:** Call `sandbox.filesystem.list_files()` to list directory contents.

**Files:**
- Modify: `modal-apps/bl1nk-app/modal_app.py`
- Modify: `modal-apps/bl1nk-app/tests/test_health.py`

**Step 1: Write failing test**

```python
@patch("modal_app.sandbox_store")
def test_list_files(self, mock_store):
    mock_handle = MagicMock()
    mock_fake_file = MagicMock()
    mock_fake_file.name = "test.txt"
    mock_handle.sandbox.filesystem.list_files.return_value = [mock_fake_file]
    mock_store.get.return_value = mock_handle

    resp = client.get(f"{API}/sandboxes/sb_001/files?path=/tmp")
    assert resp.status_code == 200
    assert len(resp.json()["files"]) == 1
```

**Step 2: Run test**

Expected: FAIL — stub returns hardcoded 1 file

**Step 3: Wire endpoint**

```python
@api.get("/api/v1/sandboxes/{sandbox_id}/files")
async def list_sandbox_files(
    sandbox_id: str,
    path: str = Query("/", description="directory to list"),
):
    handle = sandbox_store.get(sandbox_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="sandbox not found")
    files = handle.sandbox.filesystem.list_files(path)
    return {
        "sandbox_id": sandbox_id,
        "path": path,
        "files": [
            {"name": f.name, "type": "dir" if f.is_dir else "file", "size": 0, "mode": ""}
            for f in files
        ],
    }
```

**Step 4: Run tests**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/ -v`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add modal-apps/bl1nk-app/modal_app.py modal-apps/bl1nk-app/tests/test_health.py
git commit -m "feat(api): wire GET /sandboxes/{id}/files to sandbox.filesystem"
```

---

### Task 6: Integration test — full sandbox lifecycle

**Objective:** End-to-end test that creates a sandbox, checks status, runs exec, deletes it.

**Files:**
- Modify: `modal-apps/bl1nk-app/tests/test_health.py`

**Step 1: Write integration test**

```python
@patch("modal_app.sandbox_store")
class TestSandboxLifecycle:
    def test_full_lifecycle(self, mock_store):
        mock_handle = MagicMock()
        mock_handle.sandbox_id = "sb_life_001"
        mock_store.create.return_value = {"sandbox_id": "sb_life_001", "status": "running", "image": "img"}
        mock_store.get.return_value = mock_handle

        # create
        resp = client.post(f"{API}/sandboxes", json={"cmd": "sleep 60"})
        assert resp.status_code == 201
        sb_id = resp.json()["sandbox_id"]

        # get status
        mock_handle.sandbox.poll.return_value = None
        resp = client.get(f"{API}/sandboxes/{sb_id}")
        assert resp.json()["status"] == "running"

        # exec
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout.read.return_value = b"done"
        mock_proc.stderr.read.return_value = b""
        mock_handle.sandbox.exec.return_value = mock_proc
        resp = client.post(f"{API}/sandboxes/{sb_id}/exec", json={"cmd": "echo done"})
        assert resp.json()["exit_code"] == 0

        # delete
        mock_store.delete.return_value = {"sandbox_id": sb_id, "status": "terminated"}
        resp = client.delete(f"{API}/sandboxes/{sb_id}")
        assert resp.json()["status"] == "terminated"
```

**Step 2: Run tests**

Run: `cd modal-apps/bl1nk-app && python -m pytest tests/ -v`
Expected: all tests PASS

**Step 3: Commit**

```bash
git add modal-apps/bl1nk-app/tests/test_health.py
git commit -m "test(api): add full sandbox lifecycle integration test"
```

---

### Verification

**Final test run:**
```bash
cd modal-apps/bl1nk-app && python -m pytest tests/ -v
```
Expected: all tests PASS

**Served check** (optional — needs Modal credentials):
```bash
modal serve modal_app.py
```
Expected: FastAPI starts, `GET /health` returns 200, sandbox endpoints don't crash.

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1. SandboxStore + SandboxHandle | `sandbox_store.py` (new) | 7 tests |
| 2. POST /sandboxes → create | `modal_app.py` | 1 test |
| 3. GET/DELETE /sandboxes | `modal_app.py` | 3 tests |
| 4. POST /sandboxes/{id}/exec | `modal_app.py` | 1 test |
| 5. GET /sandboxes/{id}/files | `modal_app.py` | 1 test |
| 6. Full lifecycle integration | `test_health.py` | 1 test |
