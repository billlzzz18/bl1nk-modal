"""Build script template for modal-image-builds skill.

Copy to build_<name>.py and replace placeholders:
- APP_NAME
- IMAGE_TAGS
- PACKAGES list
- TOOLCHAIN commands
"""

import modal


APP_NAME = "<app-name>"


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

built.publish("<name>:latest")
built.publish("<name>:v1")
built.publish("<name>:v1-YYYYMMDD")
