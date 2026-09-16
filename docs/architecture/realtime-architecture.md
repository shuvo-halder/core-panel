# Realtime Communication Architecture

## 1. Transport Layer Protocols

CorePanel uses the simplest appropriate transport protocol for each real-time communication need:

| Capability | Transport Protocol | Rationale |
| :--- | :--- | :--- |
| **CRUD & Settings** | Standard HTTP REST (JSON) | Idempotent, simple request/response pattern. |
| **Task Progress & Log Streaming** | Server-Sent Events (SSE) | Unidirectional server-to-client streaming, auto-reconnecting, low overhead. |
| **System Resource Monitoring Streams** | Server-Sent Events (SSE) | Efficient broadcast of CPU, RAM, Disk I/O metrics to dashboard listeners. |
| **WebSSH Terminal** | WebSockets (`/ws/v1/terminal`) | Bidirectional, full-duplex interactive PTY terminal communication. |

---

## 2. Server-Sent Events (SSE) Architecture

SSE connections use FastAPI's `EventSourceResponse`. 

- **Resource Streaming (`/api/v1/monitoring/stream`):** Pushes CPU, memory, network, and disk I/O metrics every 2 seconds to active dashboard connections.
- **Task Log Streaming (`/api/v1/tasks/{task_id}/stream`):** Pushes step updates, log lines, and final completion status. Automatically closes when task reaches `success`, `failed`, or `cancelled`.

---

## 3. WebSSH Terminal Architecture

WebSockets are strictly reserved for interactive terminal sessions:

```
[ Browser (xterm.js) ] ◄── WebSocket ──► [ FastAPI Terminal Handler ]
                                                  │
                                          Unix Domain Socket
                                                  │
                                                  ▼
                                      [ Privileged Agent PTY ]
                                       (creack/pty or pty.fork)
```

1. **Authentication & Ticket Validation:** Client requests a short-lived, single-use terminal session ticket via REST (`POST /api/v1/terminal/ticket`).
2. **WebSocket Handshake:** Client connects to `/ws/v1/terminal?ticket=<ticket>`.
3. **PTY Lifecycle Management:** The backend spawns a pseudo-terminal (PTY) shell session, handles resize signals (`SIGWINCH`), forwards binary terminal frames, and cleans up sub-processes immediately upon disconnect.
