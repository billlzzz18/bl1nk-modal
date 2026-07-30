"""Simple test without FastAPI."""
import modal

app = modal.App("bl1nk-simple")
image = modal.Image.debian_slim(python_version="3.12")


@app.function(image=image)
def hello():
    return {"message": "hello from modal"}


@app.function(image=image)
@modal.asgi_app()
def api():
    from fastapi import FastAPI
    test_app = FastAPI()

    @test_app.get("/")
    def root():
        return {"status": "ok"}

    return test_app
