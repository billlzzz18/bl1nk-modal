from unittest.mock import patch

import build_bl1nk_rust


def test_build_reports_found_and_missing_tools():
    def fake_which(tool):
        if tool in ("rustc", "cargo"):
            return f"/usr/local/bin/{tool}"
        return None

    with patch("shutil.which", side_effect=fake_which):
        result = build_bl1nk_rust.build.local()

    assert result["rustc"] == "/usr/local/bin/rustc"
    assert result["cargo"] == "/usr/local/bin/cargo"
    assert result["git"] == "not found"
    assert set(result.keys()) == {"rustc", "cargo", "git", "gh", "node", "npm", "bun"}
