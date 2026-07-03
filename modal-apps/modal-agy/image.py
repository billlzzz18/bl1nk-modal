import modal
import os

CONTEXT_DIR = os.path.expanduser("~/modal-agy/context")

agi_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "curl", "git", "ca-certificates", "gnupg",
        "openssh-client", "jq", "unzip", "build-essential",
        "pkg-config", "libssl-dev", "python3", "python3-pip"
    )
    # GitHub CLI
    .run_commands(
        "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg "
        "| dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg "
        "&& chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg "
        '&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" '
        "| tee /etc/apt/sources.list.d/github-cli.list > /dev/null "
        "&& apt-get update -qq && apt-get install -y -qq gh"
    )
    # Node.js + npm + npx (for MCP servers)
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash - "
        "&& apt-get install -y -qq nodejs"
    )
    # Antigravity CLI (agy)
    .run_commands("curl -fsSL https://antigravity.google/cli/install.sh | bash")
    # Rust toolchain
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs "
        "| sh -s -- -y --default-toolchain stable"
    )
    # All tools in PATH
    .env({
        "PATH": "/root/.cargo/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "CARGO_HOME": "/root/.cargo",
        "RUSTUP_HOME": "/root/.rustup",
    })
    # Agent context + MCP settings → ~/.gemini/ (baked into image)
    .add_local_dir(CONTEXT_DIR, remote_path="/root/.gemini", copy=True)
)

app = modal.App("agy-image", image=agi_image)


@app.function(cpu=1, memory=5120, timeout=600)
def run_cmd(cmd: str = ""):
    """Run command. MCP servers configured in settings.json."""
    import subprocess, os
    
    env = os.environ.copy()
    env["PATH"] = "/root/.cargo/bin:/root/.local/bin:" + env.get("PATH", "")
    env["CARGO_HOME"] = "/root/.cargo"
    env["RUSTUP_HOME"] = "/root/.rustup"
    
    if cmd:
        r = subprocess.run(cmd, shell=True, env=env, timeout=600)
        return r.returncode
    else:
        print("=== Modal AGY Sandbox ===")
        print("Tools: git, gh, agy, cargo, rustc, node, npm, npx")
        print("MCP: filesystem, memory, sequential-thinking, exa, zapier, context7")
        print("Resources: cpu=1, memory=5120MB")
        return 0
