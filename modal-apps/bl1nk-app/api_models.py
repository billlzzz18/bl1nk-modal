"""Pydantic models for the BL1NK API v1.

Defines request/response shapes for all endpoints.
"""

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    """Factory for timezone-aware UTC now used by Field(default_factory=...)."""
    return datetime.now(timezone.utc)


# ── Agent Dispatch ──────────────────────────────────────────

class RunRequest(BaseModel):
    cmd: str = ""
    sub_agent: str = "hermes"
    env: dict[str, str] = {}
    timeout: int = 3600
    sync: bool = False


class TaskStatus(BaseModel):
    task_id: str
    agent: str
    status: Literal["accepted", "running", "completed", "failed", "timeout", "terminated"]
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None


# ── Sandbox Lifecycle ───────────────────────────────────────

class SandboxCreateRequest(BaseModel):
    image: str = "bl1nk-rust:latest"
    cmd: str = "sleep infinity"
    cpu: int = 1
    memory: int = 1024
    timeout: int = 3600
    env: dict[str, str] = {}


class SandboxStatus(BaseModel):
    sandbox_id: str
    status: Literal["running", "terminated", "timeout"]
    image: str
    created_at: datetime = Field(default_factory=_now_utc)
    uptime_seconds: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage_mb: Optional[int] = None


class ExecRequest(BaseModel):
    cmd: str
    timeout: int = 60


class ExecResult(BaseModel):
    sandbox_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class FileInfo(BaseModel):
    name: str
    type: Literal["file", "dir"]
    size: int
    mode: str


class FileListResult(BaseModel):
    sandbox_id: str
    path: str
    files: list[FileInfo]


# ── Error ───────────────────────────────────────────────────

class ApiError(BaseModel):
    error: str
    detail: str
    status_code: int = 400
