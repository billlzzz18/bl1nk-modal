import importlib
import sys
from unittest.mock import MagicMock

import modal


def test_build_and_publish_bl1nk_search(monkeypatch):
    mock_app = MagicMock()
    monkeypatch.setattr(modal.App, "lookup", MagicMock(return_value=mock_app))

    mock_built = MagicMock()
    monkeypatch.setattr(modal.Image, "build", lambda self, app: mock_built)

    sys.modules.pop("build_bl1nk_search", None)
    try:
        module = importlib.import_module("build_bl1nk_search")
    finally:
        sys.modules.pop("build_bl1nk_search", None)

    modal.App.lookup.assert_called_once_with("bl1nk-search", create_if_missing=True)
    mock_built.publish.assert_any_call("bl1nk-search:latest")
    mock_built.publish.assert_any_call("bl1nk-search:v1")
    assert mock_built.publish.call_count == 3
    assert module.app is mock_app
