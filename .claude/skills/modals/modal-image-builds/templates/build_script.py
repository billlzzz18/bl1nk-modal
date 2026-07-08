"""Build script template for modal-image-builds skill.

Copy to build_<name>.py and replace placeholders:
- APP_NAME
- IMAGE_NAME / MAJOR_VERSION
- PACKAGES list
- TOOLCHAIN commands

If this project builds more than one image, extract the publish_versioned()
function below into a shared module (see modal-images/_tags.py in this repo
for a working example) instead of duplicating it per build script.
"""

from datetime import datetime, timezone

import modal


APP_NAME = "<app-name>"
IMAGE_NAME = "<name>"
MAJOR_VERSION = "v1"  # bump this one line for a new major version; never hand-edit publish() calls


def publish_versioned(built, name: str, major: str) -> list[str]:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    tags = [f"{name}:latest", f"{name}:{major}", f"{name}:{major}-{today}"]
    for tag in tags:
        built.publish(tag)
    return tags


app = modal.App.lookup(APP_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        # base packages here
        "curl",
        "git",
        "ca-certificates",
        "build-essential",
        "pkg-config",
        "libssl-dev",
        "zip",
        "unzip",
    )
    .run_commands(
        # toolchain installs here
    )
    .env({
        "HOME": "/home/workspace",
        "PATH": "/home/workspace/.local/bin:/home/workspace/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/home/workspace",
    })
)

with modal.enable_output():
    built = image.build(app)

publish_versioned(built, IMAGE_NAME, MAJOR_VERSION)
