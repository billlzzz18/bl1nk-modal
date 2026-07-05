import os
from modal import Image, App

agi_image = (
    Image.debian_slim(python_version="3.12")
    .apt_install("curl","git","gnupg","jq","build-essential","pkg-config","libssl-dev","python3","python3-pip")
    .run_commands(
        "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
        "apt-get update -qq && apt-get install -y -qq gh",
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "curl -fsSL https://antigravity.google/cli/install.sh | bash",
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable",
    )
    .env({"PATH":"/root/.cargo/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
          "CARGO_HOME":"/root/.cargo","RUSTUP_HOME":"/root/.rustup"})
)

agi_app = App("agy-headless", image=agi_image)

@agi_app.function(cpu=1, memory=5120, timeout=1800)
def run(cmd: str = "agy --help"):
    import subprocess
    env = os.environ.copy()
    env["PATH"] = "/root/.cargo/bin:/root/.local/bin:" + env.get("PATH","")
    return subprocess.run(cmd, shell=True, env=env, timeout=1800).returncode
