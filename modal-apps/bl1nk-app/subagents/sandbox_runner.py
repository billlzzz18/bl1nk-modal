from modal import Image, App, Sandbox

app = App("sandbox-runner")

sandbox_image = (
    Image.debian_slim(python_version="3.12")
    .apt_install("curl","git","ca-certificates","build-essential","pkg-config","libssl-dev","zip","unzip")
    .run_commands(
        "curl https://sh.rustup.rs -sSf | sh -s -- -y",
        "ln -sf /root/.cargo/bin/* /usr/local/bin/",
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "curl -fsSL https://bun.sh/install | bash",
        "ln -sf /root/.bun/bin/bun /usr/local/bin/",
        "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
        "apt-get update && apt-get install -y gh",
        "curl -fsSL https://claude.ai/install.sh | bash",
        "useradd -m -s /bin/bash workspace",
        "mkdir -p /home/workspace/.cache /home/workspace/.claude /home/workspace/.config /home/workspace/.npm",
        "chown -R workspace:workspace /home/workspace",
    )
    .env({"HOME":"/home/workspace","PATH":"/home/workspace/.local/bin:/usr/local/bin:/usr/bin:/bin"})
)

@app.function(image=sandbox_image)
def run(cmd: str = "sleep infinity", timeout: int = 3600):
    import subprocess, os
    cmd_parts = ["bash","-lc",cmd] if isinstance(cmd,str) else cmd
    return subprocess.run(cmd_parts, timeout=timeout).returncode
