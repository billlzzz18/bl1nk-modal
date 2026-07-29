"""Build and publish bl1nk-agent image."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modal-images"))
from _tags import publish_versioned

import modal

MAJOR_VERSION = "v1"

app = modal.App.lookup("bl1nk-agent-build", create_if_missing=True)

# Shared install commands used by both this build script and modal_app.py's
# _make_sandbox_image(). Keep in sync — changes here must be reflected in
# modal_app.py which imports this list.
SHARED_INSTALL_COMMANDS = [
    "curl https://sh.rustup.rs -sSf | sh -s -- -y",
    "ln -sf /root/.cargo/bin/* /usr/local/bin/",
    "rustup default stable",
    "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
    "apt-get install -y nodejs",
    "curl -fsSL https://bun.sh/install | bash",
    "ln -sf /root/.bun/bin/bun /usr/local/bin/",
    (
        "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | "
        "dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
    ),
    (
        'echo "deb [arch=$(dpkg --print-architecture) '
        "signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] "
        'https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list'
    ),
    "apt-get update",
    "apt-get install -y gh",
    "curl -fsSL https://claude.ai/install.sh | bash",
    "/root/.local/bin/claude --version",
    "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-x86_64-unknown-linux-musl.tar.gz | tar -xz",
    "mv ripgrep-14.1.1-x86_64-unknown-linux-musl/rg /usr/local/bin/rg && chmod +x /usr/local/bin/rg",
    "rg --version || true",
    # Install Hermes Agent (download then execute — avoids piping unverified content to bash)
    "curl -fsSL -o /tmp/hermes-install.sh https://hermes-agent.nousresearch.com/install.sh && bash /tmp/hermes-install.sh",
    # Install Qwen Code CLI
    "curl -fsSL -o /tmp/qwen-install.sh https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen-standalone.sh && bash /tmp/qwen-install.sh",
    # Cleanup: remove entire hermes-agent repo (Python source not importable, CLI symlinks below)
    "rm -rf /usr/local/lib/hermes-agent",
    "rm -rf /tmp/* /var/tmp/*",
    # Symlink tools installed to /root/.local/bin into /usr/local/bin (so they survive HOME=/home/workspace)
    "ln -sf /root/.local/bin/qwen /usr/local/bin/qwen",
    "ln -sf /root/.local/bin/claude /usr/local/bin/claude",
    "ln -sf /root/.cargo/bin/cargo /usr/local/bin/cargo",
    "ln -sf /root/.cargo/bin/rustup /usr/local/bin/rustup",
    "ln -sf /root/.cargo/bin/rustc /usr/local/bin/rustc",
]


def build_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "curl", "git", "ca-certificates", "build-essential",
            "pkg-config", "libssl-dev", "zip", "unzip",
        )
        .run_commands(
            "useradd -m -s /bin/bash workspace",
            "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
            "chown -R workspace:workspace /home/workspace",
            *SHARED_INSTALL_COMMANDS,
            "python3 -m pip install modal fastapi uvicorn",
            "rustc --version",
            "cargo --version",
            "git --version",
            "gh --version",
            "node --version",
            "npm --version",
            "bun --version",
        )
        .env({
            "HOME": "/home/workspace",
            "PATH": "/home/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin",
            "RUSTUP_HOME": "/root/.rustup",
            "CARGO_HOME": "/root/.cargo",
        })
    )


@app.local_entrypoint()
def main():
    img = build_image()
    with modal.enable_output():
        built = img.build(app)
        tags = publish_versioned(built, "bl1nk-agent", MAJOR_VERSION)
    print(f"Image published: {', '.join(tags)}")
