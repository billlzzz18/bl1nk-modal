"""Sandbox command runner.

Consumes the shared bl1nk-rust:latest image instead of redefining it.
"""
from modal import Image, App

IMAGE = Image.from_name("bl1nk-rust:latest")

app = App("sandbox-runner", image=IMAGE)


@app.function(cpu=1, memory=1024, timeout=3600)
def run(cmd: str = "sleep infinity", timeout: int = 3600) -> int:
    import subprocess

    cmd_parts = ["bash", "-lc", cmd] if isinstance(cmd, str) else cmd
    return subprocess.run(cmd_parts, timeout=timeout).returncode
