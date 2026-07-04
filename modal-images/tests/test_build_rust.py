import importlib
import sys
from unittest.mock import MagicMock, patch

import modal


def _import_build_bl1nk_rust(monkeypatch):
    # A real (un-hydrated) App works with @app.function()/.local() without
    # any network access; only App.lookup() and Image.build() need mocking
    # since those are the calls that would otherwise hit Modal's API.
    real_app = modal.App("image-builds")
    monkeypatch.setattr(modal.App, "lookup", MagicMock(return_value=real_app))

    mock_built = MagicMock()
    monkeypatch.setattr(modal.Image, "build", lambda self, app: mock_built)

    sys.modules.pop("build_bl1nk_rust", None)
    try:
        module = importlib.import_module("build_bl1nk_rust")
    finally:
        sys.modules.pop("build_bl1nk_rust", None)
    return module, mock_built


def test_build_and_publish_bl1nk_rust(monkeypatch):
    module, mock_built = _import_build_bl1nk_rust(monkeypatch)

    modal.App.lookup.assert_called_once_with("image-builds", create_if_missing=True)
    mock_built.publish.assert_any_call("bl1nk-rust:latest")
    mock_built.publish.assert_any_call("bl1nk-rust:v2")
    assert mock_built.publish.call_count == 3
    assert module.IMAGE_NAME == "bl1nk-rust"


def test_build_reports_found_and_missing_tools(monkeypatch):
    module, _ = _import_build_bl1nk_rust(monkeypatch)

    def fake_which(tool):
        if tool in ("rustc", "cargo"):
            return f"/usr/local/bin/{tool}"
        return None

    with patch("shutil.which", side_effect=fake_which):
        result = module.build.local()

    assert result["rustc"] == "/usr/local/bin/rustc"
    assert result["cargo"] == "/usr/local/bin/cargo"
    assert result["git"] == "not found"
    assert set(result.keys()) == {"rustc", "cargo", "git", "gh", "node", "npm", "bun"}
