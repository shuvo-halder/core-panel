# ADR-001: Selection of Python (FastAPI) as Primary Backend Platform

- **Status:** Accepted
- **Date:** 2026-09-16
- **Authors:** Principal Systems Architect & Core Engineering Team
- **Target Context:** Production-grade Linux Server Control Panel

---

## 1. Context & Problem Statement

Building a production-grade, lightweight, and extensible Linux server management control panel requires a backend framework capable of handling:
1. Low-level Linux administration tasks (systemd, user management, storage manipulation, process inspection).
2. Asynchronous API I/O and real-time streaming (SSE for logs/tasks, WebSockets for terminal PTY).
3. Complex configuration management (parsing and validating Nginx, Apache, PHP-FPM, MySQL, PostgreSQL, and Let's Encrypt configurations).
4. High developer productivity, maintainability, and rapid integration of system libraries.

We evaluated three primary backend runtime candidate stacks:
- **Python 3.12+ (FastAPI + Pydantic + Uvicorn)**
- **Go (Golang 1.22+)**
- **Node.js (TypeScript + Express/Fastify)**

---

## 2. Comparative Evaluation Matrix

| Criterion | Python (FastAPI) | Go (Golang) | Node.js (TypeScript) |
| :--- | :--- | :--- | :--- |
| **Linux Integration & OS Automation** | **Superior** (`os`, `subprocess`, `ctypes`, `pwd`, `grp`, `psutil`) | Strong (`os/exec`, `syscall`), but verbose for complex string/config parsing | Moderate (requires child_process, native bindings complex) |
| **Subprocess Management & Isolation** | **Excellent** (`asyncio.subprocess` with stream readers & signals) | Excellent (`os/exec.Cmd` with context cancellation) | Moderate (`child_process.spawn`, event loop memory overhead) |
| **Filesystem & Config Processing** | **Superior** (`pathlib`, `jinja2`, `configparser`, regex) | Moderate (text/template, struct mapping requires boilerplate) | Moderate (fs/promises, handlebars/ejs) |
| **Async I/O & Realtime (SSE/WS)** | **Excellent** (`asyncio`, `starlette` WebSockets & EventSource) | Superior (goroutines, channels) | Excellent (Event loop, ws) |
| **Memory Footprint (Idle)** | ~30–45 MB (Optimized Uvicorn/FastAPI) | ~10–20 MB (Compiled binary) | ~40–60 MB (Node runtime) |
| **Developer Productivity & Ecosystem** | **Highest** (Batteries-included, massive DevOps ecosystem) | High (Type safety, fast compile, concise) | High (TypeScript, shared frontend models) |
| **Security & Privilege Control** | **Strong** (Explicit privilege separation, Pydantic strict schemas) | Strong (Single binary, minimal dependencies) | Moderate (NPM supply chain complexity) |

---

## 3. Technical Rationale for Python (FastAPI)

### A. Linux Systems Management Native Capabilities
Linux server control panels spend a significant portion of execution time reading `/proc`, managing systemd units, parsing system configurations (Nginx vhosts, PHP pool configs), manipulating permissions (`chown`, `chmod`), and managing package managers (`apt`, `dpkg`). Python's standard library (`pathlib`, `subprocess`, `pwd`, `grp`, `shutil`, `tempfile`) and ecosystem (`psutil`, `jinja2`, `pyOpenSSL`) provide expressive, safe, and battle-tested tools for systems automation without requiring heavy C bindings or boilerplate code.

### B. High Performance Async via FastAPI & Uvicorn
Using Python 3.12+ with FastAPI and Uvicorn yields non-blocking I/O capable of sustaining thousands of concurrent API requests, log streams, and monitoring polling instances. By isolating blocking CPU/OS commands into dedicated worker threads or background processes, FastAPI maintains low latency while preserving standard Python syntax.

### C. Type Safety & Validation via Pydantic v2
Pydantic v2 provides Rust-backed, high-speed validation for API request payloads, configuration schemas, and command arguments, mitigating input injection vulnerabilities at the entry barrier.

---

## 4. Addressing Python's Potential Drawbacks

1. **Memory Footprint:** Python processes can consume more memory than compiled Go binaries if unconstrained. 
   - *Mitigation:* We enforce strict process boundaries, optimize Uvicorn worker counts (single worker for single-node control plane), use standard library modules where possible, and avoid importing heavy data-science or unnecessary third-party packages.
2. **Global Interpreter Lock (GIL):** CPU-bound tasks in Python can block execution threads.
   - *Mitigation:* Long-running CPU or blocking system tasks (e.g., building packages, compiling Nginx modules, database dumps) are offloaded to dedicated background process workers or the Privileged Agent via Unix domain sockets.

---

## 5. Final Decision

We select **Python 3.12+ with FastAPI, Pydantic, and Uvicorn** as the primary backend platform for CorePanel. 

This decision balances developer efficiency, rich Linux systems integration capabilities, robust security primitives, and low operational complexity while satisfying the performance and memory constraints of lightweight VPS deployments.
