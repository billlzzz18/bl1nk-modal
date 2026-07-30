"""Tests for hermes_constants and hermes_cli stubs, plus import guards.

Verifies that all environment modules import cleanly without the
original hermes-agent dependencies.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


class TestHermesConstants:
    def test_get_hermes_home_default(self):
        from hermes_constants import get_hermes_home

        result = get_hermes_home()
        assert result == Path.home() / ".hermes"

    def test_get_hermes_home_override(self):
        from hermes_constants import get_hermes_home

        with patch.dict(os.environ, {"HERMES_HOME": "/custom/hermes"}):
            result = get_hermes_home()
            assert result == Path("/custom/hermes")

    def test_get_hermes_home_override_none(self):
        from hermes_constants import get_hermes_home_override

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HERMES_HOME", None)
            assert get_hermes_home_override() is None

    def test_get_hermes_home_override_set(self):
        from hermes_constants import get_hermes_home_override

        with patch.dict(os.environ, {"HERMES_HOME": "/override"}):
            result = get_hermes_home_override()
            assert result == Path("/override")

    def test_apply_subprocess_home_env(self):
        from hermes_constants import apply_subprocess_home_env

        env: dict[str, str] = {}
        apply_subprocess_home_env(env)
        assert "HOME" in env
        assert "HERMES_HOME" in env

    def test_apply_subprocess_home_env_preserves_existing(self):
        from hermes_constants import apply_subprocess_home_env

        env = {"HOME": "/existing"}
        apply_subprocess_home_env(env)
        assert env["HOME"] == "/existing"


class TestHermesCliSubprocessCompat:
    def test_windows_hide_flags_returns_int(self):
        from hermes_cli._subprocess_compat import windows_hide_flags

        result = windows_hide_flags()
        assert isinstance(result, int)

    def test_windows_hide_flags_on_linux(self):
        from hermes_cli._subprocess_compat import windows_hide_flags

        if sys.platform != "win32":
            assert windows_hide_flags() == 0

    def test_windows_hide_flags_on_windows(self):
        if sys.platform == "win32":
            from hermes_cli._subprocess_compat import windows_hide_flags

            assert windows_hide_flags() == subprocess.CREATE_NO_WINDOW


class TestEnvironmentImports:
    """All environment modules must import cleanly without hermes-agent deps."""

    MODULES = [
        "environments.base",
        "environments.modal_utils",
        "environments.managed_modal",
        "environments.file_sync",
        "environments.local",
        "environments.modal",
        "environments.docker",
        "environments.singularity",
        "environments.daytona",
        "environments.ssh",
    ]

    def test_all_modules_import(self):
        for mod_name in self.MODULES:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Failed to import {mod_name}"

    def test_base_has_get_sandbox_dir(self):
        from environments.base import get_sandbox_dir

        result = get_sandbox_dir()
        assert isinstance(result, Path)

    def test_file_sync_has_FileSyncManager(self):
        from environments.file_sync import FileSyncManager

        assert FileSyncManager is not None
