# Mandatory Security Checklist

Every feature and release candidate MUST pass all checklist items before being marked DONE.

## 1. Input & Command Execution Security
- [ ] No `shell=True` used in any `subprocess` invocation.
- [ ] No raw string concatenation or interpolation used in command arguments.
- [ ] Executable paths strictly whitelisted and validated.
- [ ] Argument parameters validated via Pydantic regex / type schemas.

## 2. Path & File Operations Security
- [ ] All file paths resolved using canonical path resolution (`realpath` / `resolve`).
- [ ] File operations checked against allowed root directories (`/var/www`, `/etc/nginx`, `/var/log`).
- [ ] Symlinks verified to prevent directory escape.

## 3. Auth & Session Management
- [ ] Passwords hashed with Argon2id.
- [ ] Session tokens stored in `HttpOnly`, `SameSite=Strict`, `Secure` cookies.
- [ ] Rate limiting enforced on authentication and high-risk endpoints.
- [ ] RBAC permissions verified backend-side on every privileged endpoint.

## 4. Privilege Boundary & IPC
- [ ] Web API runs as unprivileged user `corepanel`.
- [ ] Unix Domain Socket `/run/corepanel/agent.sock` restricted to `0660 corepanel:corepanel`.
- [ ] Privileged agent exposes only explicit typed RPC methods — no arbitrary shell execution.

## 5. Information Protection
- [ ] Stack traces disabled in production responses.
- [ ] Passwords, API keys, and session tokens excluded from application logs.
- [ ] CORS policy restricts untrusted origins.
