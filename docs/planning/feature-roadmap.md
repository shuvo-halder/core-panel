# Feature Roadmap by Functional Domain

## 1. Core Server & Monitoring
- [ ] Server Overview Dashboard (CPU, RAM, Swap, Disk, Net I/O gauges)
- [ ] Real-time Metric Streams (SSE 2-second interval)
- [ ] Process Inspector & Manager (List, search, signal kill, CPU/RAM usage)
- [ ] Hardware Specs & OS Kernel Inspector

## 2. Web Hosting & Domains
- [ ] Website Creation Wizard (Domain, document root, PHP version, SSL)
- [ ] Nginx VirtualHost Generator & Configuration Editor
- [ ] Apache VirtualHost Generator (Optional/Secondary)
- [ ] Reverse Proxy Manager (Port forwarding, WebSocket proxy rules)
- [ ] Domain Alias & Redirect Manager

## 3. Runtimes & Databases
- [ ] PHP-FPM Multi-Version Manager (Install 8.1, 8.2, 8.3, 8.4; pool config; ext manager)
- [ ] MySQL / MariaDB Manager (Create DB, create user, grant privileges, dump/restore)
- [ ] PostgreSQL Manager (Create DB, create user, schema management)
- [ ] Redis Service Manager (Instance management, memory config, flush cache)

## 4. Security & SSL
- [ ] Let's Encrypt / ACME Automated SSL Issuance & Auto-Renew Cron
- [ ] Custom SSL Certificate Manager (Upload crt & key)
- [ ] UFW / NFTables Firewall Rule Manager
- [ ] Fail2ban Brute Force Protection Manager
- [ ] SSH Security Hardening (Port change, root permit toggle, key manager)

## 5. Storage & File Operations
- [ ] Web File Manager (Explorer, code editor, upload, extract zip/tar, chmod/chown)
- [ ] Scheduled Backup Engine (Full server / website / DB snapshots to local or S3)
- [ ] Disks & Mount Points Inspector (`df -h`, inode tracking)

## 6. System & Automation
- [ ] Systemd Service Manager (List, start, stop, restart, enable, disable)
- [ ] Cron Job Manager (Create, edit, toggle, view execution logs)
- [ ] WebSSH Terminal (xterm.js PTY shell session)
- [ ] Package Manager (APT / DPKG updates, package search, security updates)
- [ ] Audit Log Viewer (Searchable event logs with user, IP, action, timestamp)
