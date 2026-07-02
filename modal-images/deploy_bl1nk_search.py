import modal
from modal.mount import Mount

app = modal.App("bl1nk-search")
image = modal.Image.from_name("bl1nk-search:latest")


@app.function(
    image=image,
    gpu="L4",
    timeout=7200,
    mounts=[
        Mount.from_local_file(
            "/data/data/com.termux/files/home/modal/modal-images/search_service.py",
            "/home/workspace/search_service.py",
        )
    ],
)
@modal.asgi_app()
def api():
    import sys
    sys.path.insert(0, "/home/workspace")
    from search_service import app as fastapi_app
    return fastapi_app