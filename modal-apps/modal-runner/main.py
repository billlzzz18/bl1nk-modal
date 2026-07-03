import os
import re
import json
import hmac
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import modal
from modal import App, Secret, web_endpoint, Cron
import asyncpg
import httpx
from fastapi import FastAPI, Request, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# ──────────────── Modal App ────────────────
modal_app = App("commit-tracker")

image = modal.Image.from_name("bl1nk-rust:latest") \
    .pip_install("fastapi", "uvicorn", "httpx", "asyncpg", "python-dotenv")

# ──────────────── FastAPI App ────────────────
app = FastAPI(title="Commit Task Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ปรับเป็นโดเมน Dashboard จริงตอน production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────── Secrets (to be created in Modal) ────────────────
# ชื่อ secret: cratedb-secret
# keys: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
# ชื่อ secret: line-notify-secret
# keys: LINE_TOKEN
# ชื่อ secret: webhook-secrets
# keys: GITHUB_SECRET, GITLAB_SECRET, AZURE_DEVOPS_USERNAME, AZURE_DEVOPS_PASSWORD

# ──────────────── Global Connection Pool ────────────────
pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        # อ่านค่าจาก environment (Modal injects secrets)
        pool = await asyncpg.create_pool(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", 5432)),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            min_size=2,
            max_size=10,
        )
        # สร้างตารางถ้ายังไม่มี
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT,
                    due_date TIMESTAMP,
                    assignee TEXT,
                    repository TEXT,
                    platform TEXT,
                    commit_sha TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
    return pool

# ──────────────── Helper Functions ────────────────

def parse_commit_message(message: str) -> Optional[Dict[str, str]]:
    """
    Template: TaskName:..., Status:..., Priority:..., DueDate:..., Assignee:...
    รองรับตัวคั่น , หรือ ;
    """
    pattern = (
        r"TaskName:\s*(.+?)\s*[,;]?\s*"
        r"Status:\s*(.+?)\s*[,;]?\s*"
        r"Priority:\s*(.+?)\s*"
        r"(?:[,;]?\s*DueDate:\s*(.+?)\s*)?"
        r"(?:[,;]?\s*Assignee:\s*(.+?)\s*)?$"
    )
    m = re.match(pattern, message.strip(), re.IGNORECASE)
    if not m:
        return None
    return {
        "task_name": m.group(1).strip(),
        "status": m.group(2).strip(),
        "priority": m.group(3).strip(),
        "due_date": m.group(4).strip() if m.group(4) else None,
        "assignee": m.group(5).strip() if m.group(5) else None,
    }

def verify_signature(platform: str, body: bytes, headers: dict) -> bool:
    """ตรวจสอบ Webhook signature ตาม platform"""
    if platform == "github":
        secret = os.environ.get("GITHUB_SECRET", "")
        sig = headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    elif platform == "gitlab":
        token = os.environ.get("GITLAB_SECRET", "")
        incoming = headers.get("x-gitlab-token", "")
        return token == incoming
    elif platform == "azure":
        # Azure DevOps ใช้ Basic Auth ด้วย username:password หรือ PAT
        auth = headers.get("authorization", "")
        if auth.startswith("Basic "):
            import base64
            creds = base64.b64decode(auth[6:]).decode().split(":")
            user = os.environ.get("AZURE_DEVOPS_USERNAME", "")
            pw = os.environ.get("AZURE_DEVOPS_PASSWORD", "")
            return creds[0] == user and creds[1] == pw
        return False
    return False

async def update_task(conn: asyncpg.Connection, task: Dict[str, str],
                      repo: str, platform: str, commit_sha: str) -> None:
    """Upsert task ลง CrateDB"""
    task_id = f"{repo}:{task['task_name']}"  # unique per repo
    due_date = None
    if task.get("due_date"):
        try:
            # รองรับหลายรูปแบบ วันเดือนปี
            due_date = datetime.fromisoformat(task["due_date"])
        except:
            pass
    await conn.execute("""
        INSERT INTO tasks (id, task_name, status, priority, due_date, assignee,
                          repository, platform, commit_sha, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            priority = EXCLUDED.priority,
            due_date = EXCLUDED.due_date,
            assignee = EXCLUDED.assignee,
            commit_sha = EXCLUDED.commit_sha,
            updated_at = NOW()
    """, task_id, task["task_name"], task["status"], task["priority"],
       due_date, task.get("assignee"), repo, platform, commit_sha)

async def send_line_notify(message: str) -> None:
    """ส่งข้อความไปยัง LINE Notify"""
    token = os.environ.get("LINE_TOKEN", "")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message}
        )

async def process_commit_payload(payload: dict, platform: str) -> List[dict]:
    """ประมวลผล commits จาก payload, return list of parsed tasks"""
    commits = []
    if platform in ("github", "gitlab"):
        commits = payload.get("commits", [])
    elif platform == "azure":
        # Azure DevOps Push event: payload["commits"]  ก็มี
        commits = payload.get("commits", [])

    repo = payload.get("repository", {}).get("full_name", "unknown")
    pool = await get_pool()
    results = []
    async with pool.acquire() as conn:
        for c in commits:
            msg = c.get("message", "")
            parsed = parse_commit_message(msg)
            if not parsed:
                continue
            sha = c.get("id", "")
            await update_task(conn, parsed, repo, platform, sha)

            # ส่ง LINE Notify
            line_msg = (
                f"📌 Task: {parsed['task_name']}\n"
                f"🔄 Status: {parsed['status']}\n"
                f"⚡ Priority: {parsed['priority']}\n"
                f"👤 Assignee: {parsed.get('assignee', 'N/A')}\n"
                f"📅 Due: {parsed.get('due_date', 'N/A')}\n"
                f"🔗 {repo} ({platform})"
            )
            await send_line_notify(line_msg)
            results.append(parsed)
    return results

# ──────────────── API Endpoints ────────────────

@app.post("/webhook/{platform}")
async def webhook(
    platform: str,
    request: Request,
    background_tasks: BackgroundTasks,
    sync: Optional[bool] = Query(False, description="Process synchronously")
):
    """
    รับ Webhook จาก GitHub/GitLab/Azure DevOps
    platform: github, gitlab, azure
    ?sync=true → รอจนเสร็จแล้วตอบ 200 (default: async ตอบ 202 ทันที)
    """
    if platform not in ("github", "gitlab", "azure"):
        raise HTTPException(status_code=400, detail="Unsupported platform")

    # อ่าน body และตรวจสอบ signature
    body = await request.body()
    headers = request.headers
    if not verify_signature(platform, body, headers):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)

    if sync:
        # ประมวลผลทันทีและตอบกลับ
        processed = await process_commit_payload(payload, platform)
        return {"status": "ok", "processed": len(processed), "tasks": processed}
    else:
        # Fire-and-forget ผ่าน BackgroundTasks (FastAPI)
        # หมายเหตุ: background_tasks ของ FastAPI จะทำงานหลัง response ถูกส่ง
        background_tasks.add_task(process_commit_payload, payload, platform)
        return {"status": "accepted", "detail": "Processing in background"}

@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None, assignee: Optional[str] = None):
    """API สำหรับ Dashboard: ดึงงานทั้งหมด หรือ filter ตาม status/assignee"""
    pool = await get_pool()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status:
        query += " AND status = $1"
        params.append(status)
    if assignee:
        idx = len(params) + 1
        query += f" AND assignee = ${idx}"
        params.append(assignee)
    query += " ORDER BY updated_at DESC"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]

@app.get("/api/summary/weekly")
async def weekly_summary():
    """รายงานสรุปจำนวนงานตามสถานะใน 1 สัปดาห์"""
    pool = await get_pool()
    since = datetime.utcnow() - timedelta(days=7)
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE updated_at >= $1
            GROUP BY status
        """, since)
        return {"since": since.isoformat(), "summary": [dict(r) for r in rows]}

# ──────────────── Modal Cron Jobs ────────────────

@modal_app.function(
    image=image,
    secrets=[
        Secret.from_name("cratedb-secret"),
        Secret.from_name("line-notify-secret"),
    ],
    schedule=Cron("0 9 * * *"),  # ทุกวัน 9 โมงเช้า
)
async def daily_report():
    """ส่งรายงานประจำวันผ่าน LINE Notify"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # งานที่อัปเดตวันนี้
        today = datetime.utcnow().date()
        rows = await conn.fetch("""
            SELECT task_name, status, priority, assignee
            FROM tasks
            WHERE updated_at::date = $1
            ORDER BY priority
        """, today)
        if not rows:
            await send_line_notify("📋 วันนี้ไม่มีการอัปเดตงาน")
            return
        msg = "📋 Daily Task Update\n"
        for r in rows:
            msg += f"• [{r['status']}] {r['task_name']} (Priority: {r['priority']}, Assignee: {r['assignee']})\n"
        await send_line_notify(msg)

@modal_app.function(
    image=image,
    secrets=[
        Secret.from_name("cratedb-secret"),
        Secret.from_name("line-notify-secret"),
    ],
    schedule=Cron("0 9 * * MON"),  # ทุกวันจันทร์ 9 โมง
)
async def weekly_report():
    """ส่งรายงานสรุปประจำสัปดาห์"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        since = datetime.utcnow() - timedelta(days=7)
        rows = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE updated_at >= $1
            GROUP BY status
        """, since)
        msg = "📊 Weekly Summary\n"
        for r in rows:
            msg += f"{r['status']}: {r['count']} tasks\n"
        await send_line_notify(msg)

# ──────────────── Modal Deployment Entrypoint ────────────────
@modal_app.function(
    image=image,
    secrets=[
        Secret.from_name("cratedb-secret"),
        Secret.from_name("line-notify-secret"),
        Secret.from_name("webhook-secrets"),
    ],
)
@modal.asgi_app()
def fastapi_app():
    return app

# สำหรับ local testing (modal serve)
if __name__ == "__main__":
    modal_app.run()
