# Security Threat Model (STRIDE Framework)

## 1. System Overview & Trust Boundaries

The system contains three main trust boundaries:
1. **Untrusted Client Boundary:** Browser frontend interacting over HTTPS / WebSockets.
2. **Unprivileged Control Plane Boundary:** FastAPI application running as restricted system user `corepanel`.
3. **Privileged CoreAgent Boundary:** Root daemon listening exclusively on Unix domain socket `/run/corepanel/agent.sock`.

---

## 2. STRIDE Threat Analysis

| STRIDE Threat Category | Potential Attack Vector | System Defense Mitigation |
| :--- | :--- | :--- |
| **Spoofing** | Attacker spoofs session cookie or JWT to impersonate admin. | Argon2id password hashing, JWT signed with secret key, HttpOnly + SameSite=Strict cookies, IP brute force lockouts. |
| **Tampering** | Parameter tampering in API requests to execute command injection or path traversal (`../../etc/passwd`). | Strict Pydantic schemas, `LinuxCommandRunner` using direct argument lists without `shell=True`, canonical `realpath()` path jail checks. |
| **Repudiation** | Admin performs malicious system changes and denies action. | Append-only SQLite `audit_logs` table recording user ID, action, target, IP, and timestamp. |
| **Information Disclosure** | Stack traces or secret environment keys leaked in API error responses. | Custom global exception handlers sanitizing error responses into structured JSON envelopes without internal stack traces. |
| **Denial of Service** | Resource exhaustion via excessive API requests or WebSockets flood. | IP rate-limiting via Slowapi/limiter, Uvicorn connection limits, bounded background worker pool. |
| **Elevation of Privilege** | Attacker compromises Web API process and attempts to execute root commands. | Privilege separation: API runs as unprivileged user `corepanel`. IPC agent enforces explicit method whitelisting and rejects raw command execution. |
