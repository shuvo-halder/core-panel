# CorePanel

CorePanel is a lightweight, modern, and secure Linux server management control panel. It is architected for single-node VPS and dedicated server administration with strict privilege separation, high-performance async APIs, and parameterized system interaction.

---

## 🏛️ Architecture Overview

CorePanel enforces defense-in-depth through strict process and privilege boundaries:

```text
React / Vite Frontend (SPA)
            │
            │ HTTP / REST / WebSockets / SSE
            ▼
Unprivileged Control Plane (FastAPI)
  - Runs as unprivileged user (`corepanel`)
  - Request validation & structured error handling
  - SQLite metadata database (WAL mode)
  - Safe Linux command runner & OS detection
            │
            │ Versioned JSON IPC (0660 Unix Domain Socket)
            ▼
Privileged Agent (CoreAgent)
  - Runs as `root`
  - Strict operation registry & allowlist
  - ZERO arbitrary shell execution methods
            │
            ▼
Linux Operating System (/proc, systemd, apt, network)
```

---

## 🔒 Security Principles

1. **Privilege Separation:** The web-facing FastAPI application runs unprivileged. Privileged host interactions are delegated to the local `corepanel-agent` daemon via Unix domain socket (`/run/corepanel/agent.sock`).
2. **Zero Arbitrary Shell Execution:** Both the backend `LinuxCommandRunner` and the `CoreAgent` operation registry strictly disallow `shell=True` and arbitrary command strings. All commands are parameterized with binary allowlisting and control-character filtering.
3. **Structured Validation & Redaction:** All API payloads and IPC frames are strictly validated using Pydantic schemas. Application logging uses structured JSON with automatic redaction of sensitive credentials, tokens, and keys.
4. **Source of Truth:** Real-time host state (services, resource utilization, network interfaces) is queried live from kernel interfaces (`/proc`, systemd) rather than cached indefinitely.

---

## 📂 Repository Structure

```text
.
├── .env.example                     # Environment template
├── .gitignore                       # Git ignore definitions
├── LICENSE                          # MIT License
├── README.md                        # Project documentation
├── metadata.json                    # Application metadata
├── package.json                     # Frontend dependencies
├── pyproject.toml                   # Python tools (Ruff, Pytest)
├── index.html                       # Frontend HTML entrypoint
├── tsconfig.json                    # TypeScript configuration
├── vite.config.ts                   # Vite bundler configuration
│
├── agent/                           # Privileged Agent Daemon
│   ├── app/
│   │   ├── ipc/
│   │   │   ├── protocol.py          # Pydantic IPC Request/Response schemas
│   │   │   └── server.py            # Async Unix socket server (0660 permissions)
│   │   ├── operations/
│   │   │   └── registry.py          # Allowlisted privileged operations
│   │   └── main.py                  # Agent daemon entrypoint
│   └── tests/
│       └── test_agent_ipc.py        # IPC lifecycle & security unit tests
│
├── backend/                         # Unprivileged FastAPI Control Plane
│   ├── requirements.txt             # Production Python dependencies
│   ├── requirements-dev.txt         # Development & test dependencies
│   ├── app/
│   │   ├── main.py                  # FastAPI application factory & middlewares
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── health.py        # Health check & version endpoints
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings management
│   │   │   ├── errors.py            # Unified domain error handling
│   │   │   └── logging.py           # Redacted structured JSON logging
│   │   ├── db/
│   │   │   └── sqlite.py            # WAL-mode SQLite manager & migrations
│   │   └── linux/
│   │       ├── contracts.py         # Subsystem interfaces & models
│   │       ├── os_detect.py         # /etc/os-release parser
│   │       └── runner.py            # Safe subprocess execution engine
│   └── tests/
│       ├── test_app.py              # API endpoint tests
│       ├── test_db.py               # SQLite WAL & migration tests
│       ├── test_os_detect.py        # OS matrix compatibility tests
│       └── test_runner.py           # Command allowlist & injection tests
│
├── docs/                            # Architectural Specifications
│   ├── README.md
│   ├── architecture/                # Detailed subsystem designs
│   ├── decisions/                   # Architecture Decision Records (ADRs)
│   ├── planning/                    # Feature & master roadmaps
│   ├── security/                    # Threat models & security checklists
│   └── testing/                     # Test strategy & matrices
│
└── src/                             # React SPA Frontend
    ├── App.tsx                      # Primary UI component
    ├── index.css                    # Tailwind CSS entrypoint
    └── main.tsx                     # React DOM mount point
```

---

## 🛠️ Development & Testing

### Python Backend & Agent Setup
```bash
# Install Python dependencies
pip install -r backend/requirements-dev.txt

# Run Python unit & integration tests
pytest

# Run Ruff linter
ruff check .
```

### Frontend Setup
```bash
# Install frontend dependencies
npm install

# Build frontend bundle
npm run build
```

---

## 📄 License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

