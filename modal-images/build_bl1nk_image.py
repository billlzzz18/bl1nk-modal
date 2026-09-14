"""Build the bl1nk-image Modal image with all dependencies."""

import modal

app = modal.App("bl1nk-image-build")

# Define the image with all required packages
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0", "git", "curl")
    .pip_install(
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "pydantic>=2.0",
        "httpx>=0.28.0",
        "numpy>=1.24",
        "Pillow>=10.0",
        "aiofiles>=23.0",
        "python-multipart>=0.0.6",
        "sentence-transformers>=2.2",
        "faiss-cpu>=1.7",
        "torch>=2.2",
        "transformers>=4.40",
        "replicate>=0.25.0",
        "openai>=1.0",
    )
)


@app.function(image=image, timeout=3600)
def build():
    """Build and push the image."""
    import subprocess
    
    # Install the local package
    result = subprocess.run(
        ["pip", "install", "-e", "/workspace/modal-apps/bl1nk-image"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"Install failed: {result.stderr}")
        return False
    
    print("Image built successfully!")
    return True


if __name__ == "__main__":
    # Run the build
    build.remote()
