# Security Architecture & Defense Strategy

## 1. Threat Mitigation Framework

Security is a foundational architectural constraint for CorePanel. Because server management applications handle root-equivalent power, the platform implements strict defense-in-depth measures.

```
[ Request Layer ]      ──► CORS, Rate Limiting, Request Size Limits
[ Auth Layer ]         ──► JWT in Secure HttpOnly Cookies, Argon2id Password Hashing
[ RBAC Layer ]         ──► Granular Permission Verifiers per Endpoint
[ Input Validation ]   ──► Pydantic Strict Typing & Regex Allowlist Filtering
[ Execution Layer ]    ──► LinuxCommandRunner (No shell=True, No Concatenation)
[ Privilege Boundary ] ──► Unprivileged API ◄─ Unix Domain Socket RPC ─► Root Agent
[ Path Security ]      ──► Canonical Path Resolver & Chroot/Sub-tree Jail Guards
```

---

## 2. Core Security Control Standards

### A. Authentication & Password Hashing
- **Hashing Algorithm:** Argon2id (`time_cost=3`, `memory_cost=65536`, `parallelism=4`, random 16-byte salt).
- **Session Tokens:** Stateless JWT signed with HS256/RS256, stored strictly in `HttpOnly`, `SameSite=Strict`, `Secure` cookies.
- **Brute Force Lockout:** Exponential IP & user lockout after 5 consecutive failed login attempts within 15 minutes.

### B. Command Injection Prevention
- Zero string concatenation in shell commands.
- All OS interactions execute directly via argument lists (`['/usr/bin/systemctl', 'restart', 'nginx']`).
- Subprocess execution uses `shell=False`.

### C. Path Traversal & Symlink Escapes
- All file manager operations perform canonical path resolution using `os.path.realpath` / `pathlib.Path.resolve()`.
- Every path is verified to reside within explicit allowed root directories (`/var/www`, `/etc/nginx`, `/var/log`).
- Symlinks pointing outside permitted root targets are rejected.

### D. CSRF & XSS Protections
- Cross-Site Request Forgery (CSRF) protection enforced via `SameSite=Strict` cookies and custom header tokens (`X-CSRF-Token`).
- Content Security Policy (CSP) headers block inline scripts and unauthorized external asset origins.
