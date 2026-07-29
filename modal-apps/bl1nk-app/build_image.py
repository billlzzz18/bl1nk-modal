"""Build and publish bl1nk-agent image."""
import modal

app = modal.App("bl1nk-agent-build")


def build_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "curl", "git", "ca-certificates", "build-essential",
            "pkg-config", "libssl-dev", "zip", "unzip",
        )
        .run_commands(
            "curl https://sh.rustup.rs -sSf | sh -s -- -y",
            "ln -sf /root/.cargo/bin/* /usr/local/bin/",
            "rustup default stable",
            "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
            "apt-get install -y nodejs",
            "curl -fsSL https://bun.sh/install | bash",
            "ln -sf /root/.bun/bin/bun /usr/local/bin/",
            "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | "
            "dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
            "apt-get update",
            "apt-get install -y gh",
            "curl -fsSL https://claude.ai/install.sh | bash",
            "/root/.local/bin/claude --version",
            "useradd -m -s /bin/bash workspace",
            "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
            "chown -R workspace:workspace /home/workspace",
            "rustc --version",
            "cargo --version",
            "git --version",
            "gh --version",
            "node --version",
            "npm --version",
            "bun --version",
            "python3 -m pip install modal fastapi uvicorn",
            "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-x86_64-unknown-linux-musl.tar.gz | tar -xz",
            "mv ripgrep-14.1.1-x86_64-unknown-linux-musl/rg /usr/local/bin/rg && chmod +x /usr/local/bin/rg",
            "rg --version || true",
            # Install Hermes Agent
            "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash",
            # Install Qwen Code CLI
            "curl -fsSL https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen-standalone.sh | bash",
            # Cleanup: remove .git, tests, __pycache__, node_modules from hermes repo to save ~1.5G
            "rm -rf /usr/local/lib/hermes-agent/.git /usr/local/lib/hermes-agent/tests /usr/local/lib/hermes-agent/__pycache__ /usr/local/lib/hermes-agent/node_modules",
            "rm -rf /tmp/* /var/tmp/*",
            # Symlink tools installed to /root/.local/bin into /usr/local/bin (so they survive HOME=/home/workspace)
            "ln -sf /root/.local/bin/qwen /usr/local/bin/qwen",
            "ln -sf /root/.cargo/bin/cargo /usr/local/bin/cargo",
            "ln -sf /root/.cargo/bin/rustup /usr/local/bin/rustup",
            "ln -sf /root/.cargo/bin/rustc /usr/local/bin/rustc",
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
        built.publish("bl1nk-agent:latest")
    print("Image published: bl1nk-agent:latest")
