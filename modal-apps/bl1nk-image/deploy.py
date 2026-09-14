import modal

app = modal.App("bl1nk-image")
image = modal.Image.from_name("bl1nk-image:latest")
secret = modal.Secret.from_name("bl1nk-image-auth")


@app.function(
    image=image,
    gpu="L4",
    timeout=3600,
    secrets=[secret],
)
@modal.fastapi_endpoint(label="bl1nk-image-v1")
def api():
    from src.image_service import app as fastapi_app
    return fastapi_app
