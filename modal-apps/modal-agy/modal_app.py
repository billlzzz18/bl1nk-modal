import modal
import subprocess
from pathlib import Path

app = modal.App("agent-sandbox-orchestrator")
volume = modal.Volume.from_name("persistent_agents", create_if_missing=True)

@app.function(image=modal.Image.from_name("bl1nk-rust:latest"), volumes={"/mnt/persistent_agents": volume}, timeout=1800)
def run_orchestrator():
    script = Path("/mnt/persistent_agents/orchestrator.sh")
    if not script.exists():
        raise FileNotFoundError("orchestrator.sh script not found")
    subprocess.run(["bash", str(script)], timeout=1800, check=True)

@app.local_entrypoint()
def main():
    run_orchestrator.remote()
