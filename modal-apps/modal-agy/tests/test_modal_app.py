from unittest.mock import patch

import pytest

import modal_app


def test_run_orchestrator_runs_script_when_present():
    with patch.object(modal_app, "subprocess") as mock_subprocess, \
         patch.object(modal_app.Path, "exists", return_value=True):
        modal_app.run_orchestrator.local()

    mock_subprocess.run.assert_called_once_with(
        ["bash", "/mnt/persistent_agents/orchestrator.sh"],
        timeout=1800,
        check=True,
    )


def test_run_orchestrator_raises_when_script_missing():
    with patch.object(modal_app, "subprocess") as mock_subprocess, \
         patch.object(modal_app.Path, "exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            modal_app.run_orchestrator.local()

    mock_subprocess.run.assert_not_called()
