# Linux Abstraction Layer

## 1. Design & Purpose

To prevent business logic from embedding raw subprocess calls or shell commands, CorePanel mandates a dedicated **Linux Abstraction Layer**.

All interactions with the underlying operating system flow through structured Python interfaces.

```
[ Business Domain Services ]
 (WebsiteService, DatabaseService, ServiceManager)
           │
           ▼
[ Linux Abstraction Layer ]
 ├── SystemdManager       (list, start, stop, restart, enable, disable)
 ├── PackageManager       (apt/dpkg provider adapters)
 ├── FilesystemManager     (canonical path resolve, chown, chmod, mkdir)
 ├── ProcessManager        (/proc inspection, kill, list)
 ├── NetworkManager        (interface stats, ufw/nftables rules)
 └── UserGroupManager      (useradd, usermod, groupadd)
           │
           ▼
[ Command Runner Service ]
 (subprocess.run / asyncio.create_subprocess_exec)
```

---

## 2. Secure Command Runner (`LinuxCommandRunner`)

The `LinuxCommandRunner` enforces safe command execution:

1. **Zero Shell Concatenation:** Executes binaries directly using argument arrays `[executable, arg1, arg2]`. `shell=True` is strictly prohibited.
2. **Executable Allowlist:** Only explicitly whitelisted binaries (`/usr/bin/systemctl`, `/usr/bin/apt-get`, `/usr/sbin/nginx`, `/usr/bin/ufw`, etc.) can be invoked.
3. **Argument Validation:** All variable arguments (e.g., domain names, service names, file paths) are validated against strict regex schemas.
4. **Timeouts & Execution Contexts:** Default timeouts prevent hung subprocesses from starving backend workers.
5. **Structured Return Object:** Returns a typed `CommandResult` containing `stdout`, `stderr`, `exit_code`, and `duration_ms`.

---

## 3. OS Family Adapter Pattern

To prepare for future OS support (e.g. RHEL/Rocky Linux), OS-specific commands are implemented behind abstract provider interfaces:

- `BasePackageProvider` → `DebianPackageProvider` (`apt-get`, `dpkg`)
- `BaseFirewallProvider` → `UFWFirewallProvider` / `NFTablesProvider`
- `BaseInitProvider` → `SystemdProvider`
