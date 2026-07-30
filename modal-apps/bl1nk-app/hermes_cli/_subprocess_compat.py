"""Minimal stub for hermes_cli._subprocess_compat.

Provides windows_hide_flags() for subprocess creation on Windows.
"""

import subprocess
import sys


def windows_hide_flags() -> int:
    """Return subprocess creation flags to hide the console window on Windows."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0
