"""SandboxStore — deep module for sandbox lifecycle on Modal.

Interface: 5 methods + 1 helper, zero Modal leak to callers.
Callers know only sandbox_id strings and typed dicts.
Swap Modal for Docker/K8s by rewriting this one file.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import modal


# ── Public types (no Modal dependency) ──────────────────────

def _fmt_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Internal handle ─────────────────────────────────────────

@dataclass
class _SandboxHandle:
    """Wraps modal.Sandbox + metadata. Never exposed outside this module."""
    sandbox_id: str
    sandbox: modal.Sandbox
    image: str
    created_at: datetime


# ── Store ───────────────────────────────────────────────────

class SandboxStore:
    """Registry of running sandboxes.

    Interface: small (5 methods), deep (covers create → status → exec → files → delete).
    One caller-facing seam — test through it, swap backend behind it.
    """

    def __init__(self):
        self._sandboxes: dict[str, _SandboxHandle] = {}

    # ── create ──────────────────────────────────────────────────

    def create(
        self,
        image: str = "bl1nk-rust:latest",
        cmd: str = "sleep infinity",
        cpu: int = 1,
        memory: int = 1024,
        timeout: int = 3600,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a sandbox and register it.

        Returns: {"sandbox_id", "status", "image", "created_at"}
        """
        sb = modal.Sandbox.create(
            image=image,
            cmd=cmd,
            cpu=cpu,
            memory=memory,
            timeout=timeout,
            env=env or {},
        )
        now = datetime.now(timezone.utc)
        self._sandboxes[sb.object_id] = _SandboxHandle(
            sandbox_id=sb.object_id,
            sandbox=sb,
            image=image,
            created_at=now,
        )
        return {
            "sandbox_id": sb.object_id,
            "status": "running",
            "image": image,
            "created_at": now.isoformat(),
        }

    # ── get ─────────────────────────────────────────────────────

    def get(self, sandbox_id: str) -> Optional[dict[str, Any]]:
        """Return sandbox info with live status, or None if unknown.

        Returns: {"sandbox_id", "status", "image", "created_at", "uptime_seconds"}
        """
        handle = self._sandboxes.get(sandbox_id)
        if handle is None:
            return None
        poll = handle.sandbox.poll()
        now = datetime.now(timezone.utc)
        running = poll is None
        return {
            "sandbox_id": sandbox_id,
            "status": "running" if running else "terminated",
            "image": handle.image,
            "created_at": handle.created_at.isoformat(),
            "uptime_seconds": int((now - handle.created_at).total_seconds()) if running else None,
        }

    # ── delete ──────────────────────────────────────────────────

    def delete(self, sandbox_id: str) -> dict[str, Any]:
        """Terminate a sandbox and remove from registry.

        Raises KeyError if sandbox_id not found.
        Returns: {"sandbox_id", "status"}
        """
        handle = self._sandboxes.pop(sandbox_id, None)
        if handle is None:
            raise KeyError(f"sandbox not found: {sandbox_id}")
        handle.sandbox.terminate()
        return {"sandbox_id": sandbox_id, "status": "terminated"}

    # ── exec ────────────────────────────────────────────────────

    def exec(self, sandbox_id: str, cmd: str) -> dict[str, Any]:
        """Run a command inside a running sandbox.

        Raises KeyError if sandbox not found.
        Returns: {"exit_code", "stdout", "stderr", "duration_ms"}
        """
        handle = self._sandboxes.get(sandbox_id)
        if handle is None:
            raise KeyError(f"sandbox not found: {sandbox_id}")
        proc = handle.sandbox.exec(cmd)
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.read().decode() if proc.stdout else "",
            "stderr": proc.stderr.read().decode() if proc.stderr else "",
            "duration_ms": 0,
        }

    # ── list_files ──────────────────────────────────────────────

    def list_files(self, sandbox_id: str, path: str = "/") -> dict[str, Any]:
        """List directory contents inside a sandbox.

        Raises KeyError if sandbox not found.
        Returns: {"sandbox_id", "path", "files": [{"name", "type", "size", "mode"}, ...]}
        """
        handle = self._sandboxes.get(sandbox_id)
        if handle is None:
            raise KeyError(f"sandbox not found: {sandbox_id}")
        entries = handle.sandbox.filesystem.list_files(path)
        return {
            "sandbox_id": sandbox_id,
            "path": path,
            "files": [
                {
                    "name": e.name,
                    "type": "dir" if getattr(e, "is_dir", False) else "file",
                    "size": getattr(e, "size", 0),
                    "mode": getattr(e, "mode", ""),
                }
                for e in entries
            ],
        }

    # ── list (utility) ──────────────────────────────────────────

    def list(self) -> list[dict[str, Any]]:
        """Return info for all registered sandboxes.

        Returns: [{"sandbox_id", "status", "image", "created_at", "uptime_seconds"}, ...]
        """
        return [self.get(sid) for sid in list(self._sandboxes.keys()) if self.get(sid) is not None]
