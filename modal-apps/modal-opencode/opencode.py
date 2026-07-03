import modal
from fastapi import FastAPI, Request, HTTPException
import os

# Use the latest shared bl1nk-rust image instead of rebuilding Rust toolchain each deploy
app = modal.App("sovereign-gateway", image=modal.Image.from_name("bl1nk-rust:latest"))
web_app = FastAPI()

import hmac
import hashlib
import json

from fastapi.responses import HTMLResponse

@web_app.get("/", response_class=HTMLResponse)
async def get_ui():
    html_content = """
    <html>
        <head>
            <title>Sovereign Gateway Dashboard</title>
            <style>
                body { font-family: sans-serif; margin: 20px; background: #f4f4f9; }
                h1 { color: #333; }
                table { border-collapse: collapse; width: 100%; background: white; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                th { background-color: #f2f2f2; }
                .blocked { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>Sovereign Gateway Dashboard</h1>
            <h2>Current State</h2>
            <div id="state">Loading...</div>
            <h2>Recent Timeline</h2>
            <div id="timeline">Loading...</div>
            
            <script>
                async function loadData() {
                    const stateRes = await fetch('/api/state');
                    const states = await stateRes.json();
                    let stateHtml = '<table><tr><th>Repo</th><th>ID</th><th>State</th><th>Agent</th><th>Status</th><th>Updated</th></tr>';
                    states.forEach(s => {
                        stateHtml += `<tr>
                            <td>${s.repo}</td>
                            <td>${s.issue_or_pr_id}</td>
                            <td>${s.current_state}</td>
                            <td>${s.last_agent}</td>
                            <td class="${s.blocked ? 'blocked' : ''}">${s.blocked ? 'BLOCKED' : 'OK'}</td>
                            <td>${s.updated_at}</td>
                        </tr>`;
                    });
                    stateHtml += '</table>';
                    document.getElementById('state').innerHTML = stateHtml;

                    const timeRes = await fetch('/api/timeline');
                    const events = await timeRes.json();
                    let timeHtml = '<table><tr><th>Timestamp</th><th>Repo</th><th>Event</th><th>Labels</th><th>Actor</th></tr>';
                    events.forEach(e => {
                        timeHtml += `<tr>
                            <td>${e.timestamp}</td>
                            <td>${e.repo}</td>
                            <td>${e.event_type}</td>
                            <td>${e.labels}</td>
                            <td>${e.actor}</td>
                        </tr>`;
                    });
                    timeHtml += '</table>';
                    document.getElementById('timeline').innerHTML = timeHtml;
                }
                loadData();
                setInterval(loadData, 5000);
            </script>
        </body>
    </html>
    """
    return html_content

import httpx
import time
import jwt

# --- GitHub App Auth Helpers ---

def get_jwt():
    # โหลด Private Key จาก Modal Secret
    private_key = os.environ["GITHUB_PRIVATE_KEY"].replace("\\n", "\n")
    app_id = os.environ["GITHUB_APP_ID"]
    
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

async def get_installation_token(installation_id: str):
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {get_jwt()}",
            "Accept": "application/vnd.github+json",
        }
        res = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=headers
        )
        res.raise_for_status()
        return res.json()["token"]

async def get_changed_files(repo: str, pr_number: int, token: str):
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        res = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files",
            headers=headers
        )
        if res.status_code == 200:
            return [f["filename"] for f in res.json()]
    return []

async def sync_labels(repo: str, issue_number: int, labels: list, token: str):
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        # ใช้ PUT เพื่อแทนที่ labels ทั้งหมดตามที่ Rust Engine ตัดสินใจ
        await client.put(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/labels",
            headers=headers,
            json={"labels": labels}
        )

# --- Webhook Handler ---

@web_app.post("/api/github/webhook")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    
    # Verify Signature
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode()
    expected_signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    import sovereign_engine
    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event")
    installation_id = payload.get("installation", {}).get("id")
    
    if not installation_id:
        return {"status": "ignored", "reason": "no installation id"}

    # Extract Metadata
    repo_name = payload.get("repository", {}).get("full_name", "unknown")
    issue_or_pr = payload.get("issue") or payload.get("pull_request")
    if not issue_or_pr:
        return {"status": "ignored", "reason": "not an issue or pr"}

    issue_id = issue_or_pr.get("number")
    title = issue_or_pr.get("title", "")
    body_text = issue_or_pr.get("body", "")
    current_labels = [l["name"] for l in issue_or_pr.get("labels", [])]
    
    #ดึงไฟล์ที่แก้ (ถ้าเป็น PR)
    changed_files = []
    token = await get_installation_token(installation_id)
    
    if "pull_request" in payload:
        changed_files = await get_changed_files(repo_name, issue_id, token)
        additions = payload["pull_request"].get("additions", 0)
        deletions = payload["pull_request"].get("deletions", 0)
    else:
        additions, deletions = -1, -1

    # ประมวลผลด้วย Rust Engine
    new_labels = sovereign_engine.resolve_full_state(
        title, body_text, additions, deletions, changed_files, current_labels, [], []
    )

    # Sync กลับไปที่ GitHub
    if set(new_labels) != set(current_labels):
        await sync_labels(repo_name, issue_id, new_labels, token)

    # บันทึกลง Database
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Append to timeline
        cursor.execute("""
            INSERT INTO timeline (repo, issue_or_pr_id, event_type, labels, actor)
            VALUES (?, ?, ?, ?, ?)
        """, (repo_name, issue_id, event_type, json.dumps(new_labels), payload.get("sender", {}).get("login", "unknown")))
        
        # Update current state
        state_label = next((l.split(":")[1] for l in new_labels if l.starts_with("stage:")), "unknown")
        agent_label = next((l.split(":")[1] for l in new_labels if l.starts_with("agent:")), "none")
        blocked = any(l.startswith("auto:blocking") or l == "Bug" for l in new_labels)

        cursor.execute("""
            INSERT OR REPLACE INTO current_state 
            (repo, issue_or_pr_id, current_labels, current_state, blocked, last_agent, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (repo_name, issue_id, json.dumps(new_labels), state_label, blocked, agent_label))
        
        conn.commit()

    return {
        "status": "ok",
        "labels": new_labels,
        "blocked": blocked
    }

@web_app.get("/api/state")
async def get_state(repo: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        if repo:
            cursor.execute("SELECT * FROM current_state WHERE repo = ?", (repo,))
        else:
            cursor.execute("SELECT * FROM current_state")
        return [dict(row) for row in cursor.fetchall()]

@web_app.get("/api/timeline")
async def get_timeline(repo: str = None, issue_id: int = None):
    with get_db() as conn:
        cursor = conn.cursor()
        if repo and issue_id:
            cursor.execute("SELECT * FROM timeline WHERE repo = ? AND issue_or_pr_id = ? ORDER BY timestamp DESC", (repo, issue_id))
        elif repo:
            cursor.execute("SELECT * FROM timeline WHERE repo = ? ORDER BY timestamp DESC", (repo,))
        else:
            cursor.execute("SELECT * FROM timeline ORDER BY timestamp DESC LIMIT 100")
        return [dict(row) for row in cursor.fetchall()]

@web_app.get("/api/repos")
async def get_repos():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT repo FROM current_state")
        return [row["repo"] for row in cursor.fetchall()]

@web_app.get("/install/callback")
async def install_callback(installation_id: str, setup_action: str = None):
    # In a real app, you'd exchange this for a token and get repo info
    # For now, we just log the installation
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO installation (installation_id, owner, repo)
            VALUES (?, ?, ?)
        """, (installation_id, "unknown", "unknown"))
        conn.commit()
    
    return {"status": "installed", "installation_id": installation_id}

import sqlite3
from contextlib import contextmanager

# Define persistent volume
volume = modal.Volume.from_name("sovereign-state-vol", create_if_missing=True)
DB_PATH = "/data/state.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    if not os.path.exists("/data"):
        os.makedirs("/data", exist_ok=True)
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Installation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS installation (
                installation_id TEXT PRIMARY KEY,
                owner TEXT,
                repo TEXT,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Timeline table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timeline (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                repo TEXT,
                issue_or_pr_id INTEGER,
                event_type TEXT,
                labels TEXT,
                actor TEXT
            )
        """)
        # Current State table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_state (
                repo TEXT,
                issue_or_pr_id INTEGER,
                current_labels TEXT,
                current_state TEXT,
                blocked BOOLEAN,
                last_agent TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (repo, issue_or_pr_id)
            )
        """)
        conn.commit()

@app.function(volumes={"/data": volume}, secrets=[modal.Secret.from_name("github-secrets")])
@modal.asgi_app()
def fastapi_app():
    init_db()
    return web_app
