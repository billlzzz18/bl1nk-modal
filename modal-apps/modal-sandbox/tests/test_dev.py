from unittest.mock import patch

import modal_app


def test_dev_reports_found_and_missing_tools():
    def fake_which(tool):
        if tool in ("git", "node"):
            return f"/usr/local/bin/{tool}"
        return None

    with patch("shutil.which", side_effect=fake_which):
        result = modal_app.dev.local()

    assert result["git"] == "/usr/local/bin/git"
    assert result["node"] == "/usr/local/bin/node"
    assert result["cargo"] == "not found"
    assert set(result.keys()) == {"git", "gh", "node", "npm", "bun", "cargo", "rustc"}
