"""Simple test endpoint to debug modal-fastapi-endpoint issue."""
import modal

app = modal.App("bl1nk-test")
image = modal.Image.debian_slim(python_version="3.12")


@app.function(image=image)
@modal.asgi_app()
def api():
    from fastapi import FastAPI
    test_app = FastAPI(title="Test")

    @test_app.get("/")
    def root():
        return {"status": "ok"}

    return test_app
