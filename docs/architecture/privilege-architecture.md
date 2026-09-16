# Privilege Architecture & Agent Boundaries

## 1. Threat Mitigation & Privilege Boundary

Running a web control panel entirely as `root` creates catastrophic security risks. A single Remote Code Execution (RCE) in an HTTP route or library dependency would grant full host compromise.

CorePanel enforces **Privilege Separation**:

```
┌──────────────────────────────────────────────────────────┐
│                 Unprivileged Web API                     │
│  - User: `corepanel` (UID 998, GID 998)                  │
│  - Capabilities: Reads SQLite DB, serves Web UI/API      │
│  - CANNOT modify system files or run root commands directly
└────────────────────────────┬─────────────────────────────┘
                             │ Local Unix Domain Socket
                             │ Path: `/run/corepanel/agent.sock`
                             │ Permissions: `0660 corepanel:corepanel`
                             ▼
┌──────────────────────────────────────────────────────────┐
│              Privileged Agent (`corepanel-agent`)        │
│  - User: `root` (UID 0)                                  │
│  - Capabilities: Systemd, APT, Chown, Nginx config edit  │
│  - Protocol: JSON-RPC over Unix Domain Socket            │
│  - EXPOSES ONLY CONTROLLED RPC METHODS (NO raw exec)     │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Controlled Agent RPC Interface

The Privileged Agent exposes explicit RPC methods with strict parameter typing:

- `systemd.reload_service(service_name: str)`
- `nginx.test_and_reload(config_path: str)`
- `filesystem.set_ownership(path: str, user: str, group: str)`
- `package.install(package_name: str)`
- `firewall.add_rule(port: int, protocol: str, action: str)`

### Anti-Pattern Prohibition
The Privileged Agent **MUST NOT** expose a general-purpose execution method like `agent.execute_shell_command(cmd: str)`. Exposing arbitrary shell execution completely defeats privilege separation.
