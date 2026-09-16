# CorePanel - Documentation Hub

Welcome to the official technical documentation for **CorePanel**, an open-source, production-grade Linux server management and hosting control panel.

---

## 📚 Documentation Index

### 🏛️ Architecture & Design
- [System Architecture](architecture/system-architecture.md) — High-level platform design, control plane vs. privileged agent separation.
- [Backend Architecture](architecture/backend-architecture.md) — FastAPI modular monolith structure, async execution, and lifecycle.
- [Frontend Architecture](architecture/frontend-architecture.md) — Next.js / React, Server Components, state management, and performance strategy.
- [Linux Abstraction Layer](architecture/linux-abstraction.md) — Subprocess isolation, command runner, and OS provider adapters.
- [Privilege Model](architecture/privilege-architecture.md) — Non-root API, Unix domain socket IPC, and privileged agent boundaries.
- [Task Architecture](architecture/task-architecture.md) — Async worker pool, SQLite task state, streaming logs, and cancellation.
- [Realtime Architecture](architecture/realtime-architecture.md) — SSE for streams and metrics, WebSockets for PTY terminal.
- [Data Architecture](architecture/data-architecture.md) — SQLite WAL database schema, migrations, and system-state verification.
- [Security Architecture](architecture/security-architecture.md) — Defense-in-depth, RBAC, input sanitization, and session security.

---

### 📋 Roadmap & Planning
- [Master Roadmap](planning/master-roadmap.md) — 27-phase master roadmap from repository inspection to distribution.
- [Implementation Plan](planning/implementation-plan.md) — Detailed execution steps for upcoming development phases.
- [Feature Roadmap](planning/feature-roadmap.md) — Module breakdown (Websites, Nginx, PHP, Databases, SSL, Terminal, etc.).
- [Pending Work](planning/pending-work.md) — Real-time tracking of current, completed, and upcoming tasks.

---

### 🛡️ Security & Testing
- [Threat Model](security/threat-model.md) — STRIDE analysis, trust boundaries, attack vectors, and mitigations.
- [Security Checklist](security/security-checklist.md) — Mandatory verification criteria before release.
- [Test Strategy](testing/test-strategy.md) — Unit, integration, Linux adapter, failure recovery, and benchmark suites.

---

### 📐 Architecture Decision Records (ADRs)
- [ADR-001: Backend Language Selection (Python/FastAPI)](decisions/ADR-001-backend-python.md) — Evaluation of Python vs. Go vs. Node.js for Linux server management.
