import os
from modal import Image, App

image = (
    Image.debian_slim(python_version="3.12")
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        "ln -sf /root/.cargo/bin/* /usr/local/bin/",
    )
    .env({"PATH":"/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
          "CARGO_HOME":"/root/.cargo","RUSTUP_HOME":"/root/.rustup"})
)

app = App("opencode-headless", image=image)

@app.function(cpu=1, memory=1024, timeout=600)
def run(cmd: str = "sovereign_engine --help"):
    import subprocess
    return subprocess.run(cmd, shell=True, timeout=600).returncode
