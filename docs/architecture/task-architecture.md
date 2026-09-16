# Asynchronous Task Architecture

## 1. Non-Blocking Task Execution

Long-running operations (e.g. package installation, Let's Encrypt SSL issuance, database backup dumps, Nginx site provisioning) must **NEVER** block HTTP API requests.

CorePanel uses an asynchronous background task queue with real-time state streaming.

---

## 2. Lightweight Task Runner Strategy

To maintain minimal idle RAM footprint (<30 MB) and avoid heavy external dependencies (such as Redis, RabbitMQ, or Celery), Version 1 uses an **in-process SQLite-backed asyncio Task Worker Pool**.

```
[ POST /api/v1/websites ] ──► [ Task Engine Enqueues Job ]
                                       │
                                       ├─► Returns HTTP 202 Accepted { taskId: "tsk_89ab" }
                                       │
                                       ▼
                            [ SQLite Task Storage ]
                               (State: queued)
                                       │
                                       ▼
                       [ Asyncio Task Worker Pool ]
                       (Executes step-by-step workflow)
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          [ Update Task Progress ]             [ Broadcast Event ]
          (State: running, 45%)                (SSE / WebSockets)
```

---

## 3. Task State Lifecycle & Schema

Task States: `queued` → `running` → `success` | `failed` | `cancelled`

### Task Data Model
```json
{
  "id": "task_92f1b4a0",
  "type": "website.create",
  "status": "running",
  "progress": 60,
  "started_at": "2026-09-16T13:30:00Z",
  "finished_at": null,
  "initiated_by": "admin",
  "target": "example.com",
  "steps": [
    {"name": "validate_domain", "status": "success"},
    {"name": "create_directory", "status": "success"},
    {"name": "generate_nginx_conf", "status": "running"},
    {"name": "reload_nginx", "status": "pending"}
  ],
  "logs": "Creating web root /var/www/example.com...\nGenerating Nginx vhost...",
  "error": null
}
```

---

## 4. Crash Resilience & Orphan Cleanup

Upon daemon startup, a task recovery handler scans SQLite for tasks stuck in `running` or `queued` state. Incomplete non-idempotent tasks are marked as `failed` with diagnostic logs, ensuring process restarts do not leave phantom tasks active in UI.
