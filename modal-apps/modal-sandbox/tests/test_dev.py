from unittest.mock import MagicMock, patch

import modal_app


def test_dev_reports_found_and_missing_tools():
    def fake_run(args, capture_output, text):
        tool = args[1]
        result = MagicMock()
        if tool in ("git", "node"):
            result.returncode = 0
            result.stdout = f"/usr/local/bin/{tool}\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = modal_app.dev.local()

    assert result["git"] == "/usr/local/bin/git"
    assert result["node"] == "/usr/local/bin/node"
    assert result["cargo"] == "not found"
    assert set(result.keys()) == {"git", "gh", "node", "npm", "bun", "cargo", "rustc"}
