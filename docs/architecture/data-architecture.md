# Data Architecture & Storage Strategy

## 1. Storage Paradigm

CorePanel utilizes **SQLite** with **Write-Ahead Logging (WAL)** enabled as its primary metadata control-plane database.

### Core Philosophy: Linux Host is Source of Truth
SQLite stores panel metadata (users, roles, sessions, website tracking definitions, scheduled tasks, audit logs, panel configuration). 

However, real-time operating system state (service running state, active network interfaces, installed packages, process list, disk usage) is **always verified live** by querying system APIs or `/proc` rather than trusting cached DB values.

---

## 2. SQLite Database Configuration

- **Location:** `/var/lib/corepanel/data/panel.db` (or local `data/panel.db` during development)
- **WAL Mode:** Enabled (`PRAGMA journal_mode=WAL;`) for high-concurrency read/write performance.
- **Foreign Keys:** Enforced (`PRAGMA foreign_keys=ON;`).
- **Synchronous Mode:** Set to `NORMAL` for optimal performance without risking DB corruption.

---

## 3. Database Schema (SQLAlchemy 2.0 Models)

```
┌─────────────────┐       ┌─────────────────┐
│     users       │       │     roles       │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄─────┐│ id (PK)         │
│ username (UQ)   │      ││ name (UQ)       │
│ email (UQ)      │      ││ description     │
│ password_hash   │      │└─────────────────┘
│ role_id (FK)    ├──────┘
│ is_active       │       ┌─────────────────┐
│ created_at      │       │   audit_logs    │
└────────┬────────┘       ├─────────────────┤
         │                │ id (PK)         │
         │                │ user_id (FK)    │
         └───────────────►│ action          │
                          │ target          │
                          │ ip_address      │
                          │ timestamp       │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│    websites     │       │    databases    │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ domain (UQ)     │       │ name (UQ)       │
│ root_path       │       │ db_type         │
│ php_version     │       │ db_user         │
│ ssl_enabled     │       │ created_at      │
│ created_at      │       └─────────────────┘
└─────────────────┘
```

---

## 4. Schema Migrations via Alembic

All database schema evolutions are managed using version-controlled **Alembic** migrations. Direct manual schema modifications are strictly prohibited.
