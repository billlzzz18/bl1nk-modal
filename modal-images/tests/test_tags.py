from datetime import datetime, timezone
from unittest.mock import MagicMock

from _tags import publish_versioned


def test_publish_versioned_publishes_three_tags():
    built = MagicMock()

    tags = publish_versioned(built, "bl1nk-rust", "v2")

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert tags == ["bl1nk-rust:latest", "bl1nk-rust:v2", f"bl1nk-rust:v2-{today}"]
    assert built.publish.call_count == 3
    for tag in tags:
        built.publish.assert_any_call(tag)


def test_publish_versioned_dated_tag_uses_todays_date():
    built = MagicMock()

    publish_versioned(built, "bl1nk-search", "v1")

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    built.publish.assert_any_call(f"bl1nk-search:v1-{today}")
