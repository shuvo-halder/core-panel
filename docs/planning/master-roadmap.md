# Master Engineering Roadmap (Phases 0 - 27)

| Phase | Phase Name | Description | Status |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Repository Inspection** | Audit existing codebase, evaluate dependencies, verify environment constraints. | **Completed** |
| **Phase 1** | **Architecture & Documentation** | Create comprehensive architecture documentation, threat models, ADR-001, and workplans. | **In Progress** |
| **Phase 2** | **Python/FastAPI Backend Skeleton** | Modular FastAPI application structure, Alembic migrations, Pydantic schemas, Uvicorn setup. | Pending |
| **Phase 3** | **Linux Abstraction Layer** | Implement `LinuxCommandRunner`, safe path resolver, systemd & package manager wrappers. | Pending |
| **Phase 4** | **Privileged Agent (CoreAgent)** | Build root-owned IPC agent with Unix Domain Socket JSON-RPC interface. | Pending |
| **Phase 5** | **Authentication Engine** | Argon2id password hashing, JWT HttpOnly sessions, rate limiting, audit logging. | Pending |
| **Phase 6** | **Role-Based Access Control (RBAC)** | Granular permissions engine, role assignments, middleware authorization guards. | Pending |
| **Phase 7** | **Task Engine & Worker Queue** | Asynchronous SQLite task queue, progress tracker, SSE event log streaming. | Pending |
| **Phase 8** | **Server System Information** | OS detection layer (Debian/Ubuntu), system hardware specs, kernel/hostname inspector. | Pending |
| **Phase 9** | **Real-Time System Monitoring** | `/proc` & `psutil` resource streams (CPU, RAM, Swap, Disk, Net I/O, load averages). | Pending |
| **Phase 10** | **Systemd Service Manager** | View, start, stop, restart, enable, disable system services with safety validation. | Pending |
| **Phase 11** | **Package Manager Integration** | APT/DPKG package manager adapter, package search, safe updates/installs. | Pending |
| **Phase 12** | **Nginx Web Server Manager** | Vhost configuration generator, `nginx -t` validator, safe reloader, site enabler. | Pending |
| **Phase 13** | **Apache Web Server Manager** | Optional Apache vhost generator and configuration manager. | Pending |
| **Phase 14** | **PHP-FPM Pool Manager** | Multi-PHP version pool management, extensions manager, php.ini configuration editor. | Pending |
| **Phase 15** | **Website & Domain Manager** | End-to-end site provisioning, document roots, rewrite rules, SSL binding. | Pending |
| **Phase 16** | **Database Manager** | MySQL/MariaDB & PostgreSQL user creation, DB creation, permissions, and backups. | Pending |
| **Phase 17** | **SSL Manager (ACME / Let's Encrypt)** | Automated Let's Encrypt HTTP-01 challenge issuance, renewal cron, self-signed certs. | Pending |
| **Phase 18** | **File Manager** | Canonical path-jail file explorer, code editor, upload/download, chown/chmod manager. | Pending |
| **Phase 19** | **Cron Job Manager** | Crontab parser, user scheduled job creation, execution log inspector. | Pending |
| **Phase 20** | **WebSSH Terminal** | xterm.js frontend + PTY bridge over WebSockets with ticket authentication. | Pending |
| **Phase 21** | **Backup & Restore System** | Site & DB snapshot archiver, compression, remote storage upload, disaster recovery. | Pending |
| **Phase 22** | **Firewall Manager** | UFW / NFTables rules manager, port opener/closer, IP whitelist/blacklist. | Pending |
| **Phase 23** | **Security Hardening** | Fail2ban integration, SSH port change, root login toggle, security scanner. | Pending |
| **Phase 24** | **Performance Optimization** | API response caching, frontend code-splitting, query tuning, idle RAM benchmarking. | Pending |
| **Phase 25** | **Installer Script** | Idempotent bash installer for Ubuntu 22.04/24.04 & Debian 12. | Pending |
| **Phase 26** | **Upgrade & Migration System** | Panel auto-updater, DB migration executor, zero-downtime reloader. | Pending |
| **Phase 27** | **Release Engineering & Docs** | Final verification matrix, release notes, user manual, distribution packaging. | Pending |
