import modal

app = modal.App("bl1nk-search")
image = modal.Image.from_name("bl1nk-search:latest")
secret = modal.Secret.from_name("bl1nk-search-auth")


@app.function(
    image=image,
    gpu="L4",
    timeout=7200,
    secrets=[secret],
)
@modal.fastapi_endpoint(label="bl1nk-search-v2")
def api():
    from search_service import app as fastapi_app
    return fastapi_app
