# BL1NK API v1

Base URL: `https://<workspace>--bl1nk-fastapi-app.modal.run`

---

## `GET /health`

Health check.

**Response `200`**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Agent Dispatch

### `POST /api/v1/run/{agent}`

Dispatch a command to an agent.

**Path params**

| param | values |
|-------|--------|
| agent | `hermes`, `agy`, `opencode`, `sandbox` |

**Request body**
```json
{
  "cmd": "echo hello",
  "sub_agent": "sandbox",
  "env": {"KEY": "VAL"},
  "timeout": 3600,
  "sync": true
}
```

| field | type | default | description |
|-------|------|---------|-------------|
| cmd | string | `""` | command to run |
| sub_agent | string | `"hermes"` | delegate to another agent |
| env | object | `{}` | extra env vars |
| timeout | int | `3600` | max runtime seconds |
| sync | bool | `false` | wait for result (`true`) or fire-and-forget (`false`) |

**Response `200` (sync)**
```json
{
  "task_id": "task_a1b2c3d4",
  "agent": "hermes",
  "status": "completed",
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 42
}
```

**Response `202` (async — fire-and-forget)**
```json
{
  "task_id": "task_a1b2c3d4",
  "agent": "hermes",
  "status": "accepted"
}
```

### `GET /api/v1/tasks/{task_id}`

Poll task result.

**Response `200`**
```json
{
  "task_id": "task_a1b2c3d4",
  "agent": "hermes",
  "status": "running",
  "created_at": "2026-07-29T12:00:00Z",
  "updated_at": "2026-07-29T12:00:05Z"
}
```

Possible `status` values: `accepted`, `running`, `completed`, `failed`, `timeout`, `terminated`

---

## Sandbox Lifecycle

### `POST /api/v1/sandboxes`

Create a new sandbox.

**Request body**
```json
{
  "image": "bl1nk-rust:latest",
  "cmd": "sleep 3600",
  "cpu": 1,
  "memory": 1024,
  "timeout": 3600,
  "env": {"KEY": "VAL"}
}
```

| field | type | default | description |
|-------|------|---------|-------------|
| image | string | `"bl1nk-rust:latest"` | published Modal image name |
| cmd | string | `"sleep infinity"` | initial command |
| cpu | int | `1` | CPU count |
| memory | int | `1024` | MB |
| timeout | int | `3600` | max lifetime seconds |
| env | object | `{}` | env vars |

**Response `201`**
```json
{
  "sandbox_id": "sb_x1y2z3",
  "status": "running",
  "image": "bl1nk-rust:latest",
  "created_at": "2026-07-29T12:00:00Z"
}
```

### `GET /api/v1/sandboxes/{sandbox_id}`

Get sandbox status and metrics.

**Response `200`**
```json
{
  "sandbox_id": "sb_x1y2z3",
  "status": "running",
  "image": "bl1nk-rust:latest",
  "created_at": "2026-07-29T12:00:00Z",
  "uptime_seconds": 300,
  "cpu_usage": 0.15,
  "memory_usage_mb": 256
}
```

### `DELETE /api/v1/sandboxes/{sandbox_id}`

Terminate a sandbox.

**Response `200`**
```json
{
  "sandbox_id": "sb_x1y2z3",
  "status": "terminated"
}
```

### `POST /api/v1/sandboxes/{sandbox_id}/exec`

Execute a command inside a running sandbox.

**Request body**
```json
{
  "cmd": "ls -la /tmp",
  "timeout": 60
}
```

| field | type | default | description |
|-------|------|---------|-------------|
| cmd | string | required | command to run |
| timeout | int | `60` | per-command timeout seconds |

**Response `200`**
```json
{
  "sandbox_id": "sb_x1y2z3",
  "exit_code": 0,
  "stdout": "total 4\ndrwxrwxrwt ...\n",
  "stderr": "",
  "duration_ms": 12
}
```

### `GET /api/v1/sandboxes/{sandbox_id}/files`

List files in a sandbox directory.

**Query params**

| param | default | description |
|-------|---------|-------------|
| path | `/` | directory to list |
| recursive | `false` | list recursively |

**Response `200`**
```json
{
  "sandbox_id": "sb_x1y2z3",
  "path": "/home/workspace",
  "files": [
    {"name": ".bashrc", "type": "file", "size": 124, "mode": "-rw-r--r--"},
    {"name": ".cargo", "type": "dir", "size": 4096, "mode": "drwxr-xr-x"}
  ]
}
```

### `GET /api/v1/sandboxes/{sandbox_id}/files/*`

Read a file from a sandbox.

**Response** — raw file content with `Content-Type: application/octet-stream`

**Response `404`**
```json
{
  "error": "file_not_found",
  "detail": "/home/workspace/missing.txt not found"
}
```

---

## Error format

All errors return consistent shape:

```json
{
  "error": "invalid_agent",
  "detail": "Unknown agent: foo",
  "status_code": 400
}
```

Common error codes: `invalid_agent`, `sandbox_not_found`, `file_not_found`, `timeout`, `internal_error`

---

## Implementation status

| Endpoint | Status |
|----------|--------|
| `GET /health` | ✅ implemented |
| `POST /api/v1/run/{agent}` | ⚡ stub (returns task_id but no real execution) |
| `GET /api/v1/tasks/{task_id}` | ⚡ stub |
| `POST /api/v1/sandboxes` | 🔜 planned |
| `GET /api/v1/sandboxes/{id}` | 🔜 planned |
| `DELETE /api/v1/sandboxes/{id}` | 🔜 planned |
| `POST /api/v1/sandboxes/{id}/exec` | 🔜 planned |
| `GET /api/v1/sandboxes/{id}/files` | 🔜 planned |
| `GET /api/v1/sandboxes/{id}/files/*` | 🔜 planned |
