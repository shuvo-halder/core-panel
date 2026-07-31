# Universal VPS Management Panel

A production-grade, self-hosted VPS Management Platform designed to be a lightweight, modern, and highly secure alternative to traditional control panels like cPanel, CyberPanel, and aaPanel. 

Manage 90% of your daily server administration tasks—Nginx, Databases, Docker, System Services, Cron jobs, and more—directly from a sleek, High-Density Web GUI without needing to repeatedly open an SSH terminal.

---

## 🌟 Key Features

* **Real-Time Dashboard:** Monitor CPU, RAM, Disk, Network I/O, and Uptime via WebSockets.
* **Web Server Manager:** Configure Nginx virtual hosts, issue Let's Encrypt SSLs, and manage PHP/Node proxies.
* **Database Manager:** Create and manage MySQL/MariaDB and PostgreSQL databases.
* **File Manager:** Full web-based browser for your server's filesystem.
* **Security Center:** Manage UFW/Firewalld, Fail2Ban, and SSH hardening.
* **Web Terminal:** Secure, in-browser bash terminal using Xterm.js.
* **System Services:** Monitor, start, stop, and restart systemd services.
* **Cron Job Manager:** Visual interface to schedule Linux tasks.

---

## 👥 For Users (Server Administrators)

### Prerequisites
* A fresh, clean Linux VPS.
* Supported OS: Ubuntu (20.04/22.04/24.04), Debian (11/12), AlmaLinux/CentOS (8/9), Rocky Linux.
* Root access.

### Quick Installation
You can install the panel using our one-line automated installer. This script will detect your OS, install necessary dependencies (Node.js, Nginx, Certbot), build the application, and start the systemd service.

Run the following command as `root`:
```bash
curl -sSL https://raw.githubusercontent.com/shuvo-halder/core-panel/refs/heads/main/install.sh | bash
```

### Accessing the Panel
Once the installation is complete, the installer will output the access URL.
1. Navigate to `http://<YOUR_SERVER_IP>` in your browser.
2. Log in using the default generated credentials (check `/etc/corepanel/config.json` or the installer output).
3. We highly recommend mapping a domain and enabling SSL via the Web Server manager immediately.

---

## 💻 For Developers

We welcome contributions! The panel is built with a modern API-first architecture.

### Tech Stack
* **Frontend:** React 19, Vite, Tailwind CSS (High Density custom theme).
* **Backend:** Node.js, Express (TypeScript).
* **Database:** PostgreSQL via Prisma ORM (planned Phase 2).
* **Security:** JWT Authentication, Parameterized System Commands (`spawn` without shell evaluation).

### Architecture Documentation
Please review our architectural documentation before contributing:
* [System Architecture (Phase 1)](ARCHITECTURE.md)
* [Database Schema (Phase 2)](SCHEMA.md)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/shuvo-halder/core-panel.git
   cd vps-panel
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up Environment Variables:**
   Copy the `.env.example` to `.env` and configure your local settings.
   ```bash
   cp .env.example .env
   ```

4. **Start the Development Server:**
   This command starts the Express backend and the Vite frontend middleware concurrently using `tsx`.
   ```bash
   npm run dev
   ```
   The panel will be available at `http://localhost:3000`.

5. **Build for Production:**
   ```bash
   npm run build
   ```
   This bundles the React frontend into `/dist` and compiles the Node backend into a standalone `dist/server.cjs` file.

### Security Guidelines
* **No `shell: true`:** When utilizing child processes (e.g., in `src/syscmd.ts`), **always** use `spawn` with array arguments to prevent Remote Code Execution (RCE) via shell injection.
* **JWT Auth:** Ensure all API routes are protected using the `requireAuth` middleware from `src/auth.ts`.
* **Rate Limiting:** Authentication and sensitive endpoints must be rate-limited using `express-rate-limit`.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
