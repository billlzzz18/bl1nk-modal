"""Minimal stub for hermes_constants — provides path defaults for environments/.

The original hermes_constants module lives in the hermes-agent codebase.
This stub provides the same interface so environments/ can import cleanly.
"""

import os
from pathlib import Path


def get_hermes_home() -> Path:
    """Return the hermes home directory (~/.hermes or $HERMES_HOME)."""
    override = os.environ.get("HERMES_HOME")
    if override:
        return Path(override)
    return Path.home() / ".hermes"


def get_hermes_home_override() -> Path | None:
    """Return HERMES_HOME override if set, else None."""
    override = os.environ.get("HERMES_HOME")
    return Path(override) if override else None


def apply_subprocess_home_env(env: dict[str, str]) -> None:
    """Ensure HOME and HERMES_HOME are set in a subprocess env dict."""
    hermes_home = get_hermes_home()
    env.setdefault("HERMES_HOME", str(hermes_home))
    env.setdefault("HOME", str(Path.home()))
