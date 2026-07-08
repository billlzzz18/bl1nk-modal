"""Deploy script template for modal-image-builds skill.

Copy to deploy_<name>.py and replace placeholders:
- APP_NAME
- IMAGE_TAG
- gpu value
"""

import modal
from modal.mount import Mount

app = modal.App("<app-name>")
image = modal.Image.from_name("<name>:latest")

# Optional: mount local source files
mount = Mount()
mount.add_local_file(
    "/absolute/path/to/service.py",
    "/home/workspace/service.py",
)


@app.function(
    image=image,
    gpu="L4",
    timeout=7200,
    mounts=[mount],  # omit if no local files needed
)
@modal.asgi_app()
def api():
    import sys
    sys.path.insert(0, "/home/workspace")
    from service import app as fastapi_app
    return fastapi_app
