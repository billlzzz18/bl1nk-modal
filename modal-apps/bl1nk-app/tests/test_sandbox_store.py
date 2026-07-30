"""SandboxStore unit tests — pure logic, no Modal API calls.

Tests cross the SandboxStore seam (the public interface).
Modal.Sandbox is mocked so tests run offline.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sandbox_store import SandboxStore


class TestSandboxStore:
    """Every test goes through the public interface — no modal.Sandbox leak."""

    # ── create ─────────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_create_returns_running(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_001"
        mock_create.return_value = mock_sb

        store = SandboxStore()
        result = store.create(image="img:latest", cmd="sleep 10", cpu=1, memory=256, timeout=60, env={})

        assert result["sandbox_id"] == "sb_abc_001"
        assert result["status"] == "running"
        assert result["image"] == "img:latest"
        mock_create.assert_called_once()

    @patch("modal.Sandbox.create")
    def test_create_registers_internal_handle(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_002"
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        assert "sb_abc_002" in store._sandboxes
        assert store._sandboxes["sb_abc_002"].sandbox is mock_sb

    # ── get ────────────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_get_returns_live_info(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_003"
        mock_sb.poll.return_value = None  # running
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        info = store.get("sb_abc_003")

        assert info is not None
        assert info["sandbox_id"] == "sb_abc_003"
        assert info["status"] == "running"
        assert info["uptime_seconds"] is not None

    @patch("modal.Sandbox.create")
    def test_get_terminated_status(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_004"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_sb.poll.return_value = mock_result  # terminated
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        info = store.get("sb_abc_004")

        assert info["status"] == "terminated"
        assert info["uptime_seconds"] is None

    def test_get_unknown_returns_none(self):
        store = SandboxStore()
        assert store.get("nonexistent") is None

    # ── delete ─────────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_delete_terminates_and_removes(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_005"
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        result = store.delete("sb_abc_005")

        assert result["status"] == "terminated"
        mock_sb.terminate.assert_called_once()
        assert store.get("sb_abc_005") is None

    def test_delete_unknown_raises(self):
        store = SandboxStore()
        with pytest.raises(KeyError, match="not found"):
            store.delete("nonexistent")

    # ── exec ───────────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_exec_returns_output(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_006"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout.read.return_value = b"hello\n"
        mock_proc.stderr.read.return_value = b""
        mock_sb.exec.return_value = mock_proc
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        result = store.exec("sb_abc_006", "echo hello")

        assert result["exit_code"] == 0
        assert result["stdout"] == "hello\n"
        assert result["stderr"] == ""

    def test_exec_unknown_raises(self):
        store = SandboxStore()
        with pytest.raises(KeyError, match="not found"):
            store.exec("nonexistent", "cmd")

    # ── list_files ─────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_list_files_returns_entries(self, mock_create):
        mock_sb = MagicMock()
        mock_sb.object_id = "sb_abc_007"
        fake_entry = MagicMock()
        fake_entry.name = "test.txt"
        fake_entry.is_dir = False
        fake_entry.size = 100
        fake_entry.mode = "-rw-r--r--"
        mock_sb.filesystem.list_files.return_value = [fake_entry]
        mock_create.return_value = mock_sb

        store = SandboxStore()
        store.create()
        result = store.list_files("sb_abc_007", "/tmp")

        assert result["path"] == "/tmp"
        assert len(result["files"]) == 1
        assert result["files"][0]["name"] == "test.txt"
        assert result["files"][0]["type"] == "file"

    def test_list_files_unknown_raises(self):
        store = SandboxStore()
        with pytest.raises(KeyError, match="not found"):
            store.list_files("nonexistent", "/")

    # ── list ───────────────────────────────────────────────────

    @patch("modal.Sandbox.create")
    def test_list_returns_all(self, mock_create):
        def make_sb(sid):
            sb = MagicMock()
            sb.object_id = sid
            sb.poll.return_value = None
            return sb

        mock_create.side_effect = [make_sb("sb_001"), make_sb("sb_002")]

        store = SandboxStore()
        store.create()
        store.create()
        all_sbs = store.list()

        assert len(all_sbs) == 2
        assert {s["sandbox_id"] for s in all_sbs} == {"sb_001", "sb_002"}

    def test_list_empty(self):
        store = SandboxStore()
        assert store.list() == []
