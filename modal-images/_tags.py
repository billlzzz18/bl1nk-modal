"""Shared image-tag publishing helper.

bl1nk-rust and bl1nk-search both publish the same three-tag convention
(latest / vN / vN-YYYYMMDD, see .claude/skills/modal-image-builds). Without
this, every rebuild means hand-editing a version string and today's date in
two separate files and hoping they stay consistent. Bumping a major version
is now the one line at the call site; the date is never hand-typed.
"""

from datetime import datetime, timezone


def publish_versioned(built, name: str, major: str) -> list[str]:
    """Publish `name:latest`, `name:{major}`, and `name:{major}-YYYYMMDD`.

    Returns the list of tags published, for logging.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    tags = [f"{name}:latest", f"{name}:{major}", f"{name}:{major}-{today}"]
    for tag in tags:
        built.publish(tag)
    return tags
