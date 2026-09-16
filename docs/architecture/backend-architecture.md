# Backend Architecture (Python / FastAPI)

## 1. Modular Monolith Architecture

The backend is built as a clean, modular Python 3.12+ monolith using **FastAPI**, **Pydantic v2**, and **Uvicorn**.

```
backend/
├── app/
│   ├── main.py                 # FastAPI application factory & lifespan
│   ├── api/
│   │   ├── v1/                 # API Version 1 Routers
│   │   │   ├── auth.py
│   │   │   ├── server.py
│   │   │   ├── websites.py
│   │   │   ├── nginx.py
│   │   │   ├── php.py
│   │   │   ├── databases.py
│   │   │   ├── ssl.py
│   │   │   ├── files.py
│   │   │   ├── terminal.py
│   │   │   └── tasks.py
│   │   └── deps.py             # Dependency injection (Auth, DB, Agent Client)
│   ├── core/
│   │   ├── config.py           # Pydantic Settings
│   │   ├── logging.py          # Structured JSON logging
│   │   └── security.py        # Argon2id, JWT creation & verification
│   ├── linux/                  # Linux Abstraction Layer
│   │   ├── runner.py           # CommandRunner (Subprocess isolation)
│   │   ├── systemd.py          # Systemd unit manager
│   │   ├── packages.py         # APT/DPKG manager
│   │   ├── filesystem.py       # Safe path resolver & operations
│   │   ├── processes.py        # Process inspector (/proc)
│   │   └── networking.py       # Network interface & firewall manager
│   ├── agent/
│   │   └── client.py           # Unix Domain Socket RPC client
│   ├── models/                 # SQLAlchemy 2.0 ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business domain services
│   └── tasks/                  # Task queue worker engine
├── migrations/                 # Alembic database migrations
└── tests/                      # Pytest unit & integration tests
```

---

## 2. Request Handling & Dependency Injection

Every HTTP request undergoes strict pipeline validation:
1. **CORS & Rate Limiting Middleware:** Blocks brute force and unauthorized cross-origin requests.
2. **Authentication Dependency (`get_current_user`):** Extracts JWT from HttpOnly cookie or Bearer token, validates signature, checks session revocation.
3. **RBAC Dependency (`require_permission("websites.create")`):** Enforces fine-grained permission checks against user roles.
4. **Pydantic Schema Validation:** Auto-sanitizes input parameters before business service invocation.
5. **Business Service Layer:** Executes domain rules, generates configurations, calls `LinuxCommandRunner` or IPC `AgentClient`.
6. **Structured Error Handling:** Translates all exceptions into unified JSON error envelopes.
