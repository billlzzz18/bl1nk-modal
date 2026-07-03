from unittest.mock import MagicMock, patch

import build_bl1nk_rust


def test_build_reports_found_and_missing_tools():
    def fake_run(args, capture_output, text):
        tool = args[1]
        result = MagicMock()
        if tool in ("rustc", "cargo"):
            result.returncode = 0
            result.stdout = f"/usr/local/bin/{tool}\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = build_bl1nk_rust.build.local()

    assert result["rustc"] == "/usr/local/bin/rustc"
    assert result["cargo"] == "/usr/local/bin/cargo"
    assert result["git"] == "not found"
    assert set(result.keys()) == {"rustc", "cargo", "git", "gh", "node", "npm", "bun"}
