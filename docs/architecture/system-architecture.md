# System Architecture

## 1. High-Level Overview

CorePanel is designed as a lightweight, single-server Linux management control panel. It enforces a strict separation between the **User Interface**, the **Unprivileged Control Plane (FastAPI)**, and the **Privileged Execution Agent (CoreAgent)**.

```
┌────────────────────────────────────────────────────────┐
│                   Browser (Client)                     │
│    Next.js / React UI / xterm.js / Recharts / SSE     │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS / WSS
                            ▼
┌────────────────────────────────────────────────────────┐
│            Control Plane (FastAPI - Unprivileged)      │
│  - REST API & WebSockets & SSE                         │
│  - Auth (JWT, Argon2id, Rate Limiter)                  │
│  - RBAC Authorization Engine                           │
│  - Task Queue & State Machine (SQLite)                 │
│  - Config Generator & Business Logic                   │
└───────────────────────────┬────────────────────────────┘
                            │ Local Unix Domain Socket
                            │ Encrypted / Peer Credential Auth
                            ▼
┌────────────────────────────────────────────────────────┐
│            Privileged Agent (CoreAgent - Root)         │
│  - Systemd Unit Operations                             │
│  - File System Ownership / ACL / Chown                 │
│  - Package Management (apt/dpkg)                       │
│  - Nginx / Apache Reload & Testing                     │
│  - User & Group Management                             │
│  - WebSSH PTY Bridge                                   │
└───────────────────────────┬────────────────────────────┘
                            │ Native Subprocess / Syscalls
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Linux Kernel & System                 │
│  - /proc, /sys, systemd, nftables/ufw, filesystem      │
└────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Principles

1. **Single-Node Operational Simplicity:** Designed specifically for single VPS or dedicated server management. No external cluster orchestrator required.
2. **Defense-in-Depth & Privilege Isolation:** The Web API layer runs as a dedicated unprivileged user (`corepanel`). Only the minimal `corepanel-agent` binary runs as `root`, communicating exclusively over a local Unix domain socket with strict RPC method whitelisting.
3. **Non-Blocking Asynchronous Design:** Long-running system operations (e.g. package upgrades, SSL issuance, database creation) run via an asynchronous task runner streaming progress over SSE or WebSockets.
4. **Source-of-Truth Hierarchy:** Panel metadata (users, settings, task state) resides in SQLite with WAL mode. Real-time system state (service health, disk usage, active processes) is always inspected directly from Linux interfaces (`/proc`, `systemctl`).
