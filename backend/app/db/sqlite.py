import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.core.logging import logger


class Database:
    """SQLite Database Manager with WAL mode and migration tracking."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path

    def get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enforce WAL mode, foreign keys, and normal sync
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_database(self) -> None:
        """Initialize database schema tables for migrations and application metadata."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Migration tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
            """)

            # Application metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # Record baseline metadata if not present
            cursor.execute("SELECT value FROM app_metadata WHERE key = 'version'")
            row = cursor.fetchone()
            now = datetime.now(timezone.utc).isoformat()
            if not row:
                cursor.execute(
                    "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
                    ("version", settings.APP_VERSION, now),
                )
                cursor.execute(
                    "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
                    ("environment", settings.ENVIRONMENT, now),
                )

            # Record initial baseline migration
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "0001_baseline_metadata", now),
                )

            # Migration 2: Auth and RBAC
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 2")
            if not cursor.fetchone():
                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE,
                        password_hash TEXT NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_login_at TEXT
                    );
                """)

                # Create roles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        id TEXT PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        is_system INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                # Create permissions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS permissions (
                        id TEXT PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        resource TEXT NOT NULL,
                        action TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)

                # Create user_roles junction table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_roles (
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                        assigned_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, role_id)
                    );
                """)

                # Create role_permissions junction table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS role_permissions (
                        role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                        permission_id TEXT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                        assigned_at TEXT NOT NULL,
                        PRIMARY KEY (role_id, permission_id)
                    );
                """)

                # Create user_sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        last_activity_at TEXT NOT NULL,
                        is_revoked INTEGER NOT NULL DEFAULT 0
                    );
                """)

                # Indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);"
                )

                # Seed base permissions
                base_permissions = [
                    (
                        "perm_users_read",
                        "users.read",
                        "View user accounts and profiles",
                        "users",
                        "read",
                    ),
                    (
                        "perm_users_manage",
                        "users.manage",
                        "Create, modify, and delete user accounts",
                        "users",
                        "manage",
                    ),
                    (
                        "perm_roles_read",
                        "roles.read",
                        "View roles and granted permissions",
                        "roles",
                        "read",
                    ),
                    (
                        "perm_roles_manage",
                        "roles.manage",
                        "Create, modify, and delete security roles",
                        "roles",
                        "manage",
                    ),
                ]
                for p_id, p_name, p_desc, p_res, p_act in base_permissions:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO permissions (id, name, description, resource, action, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (p_id, p_name, p_desc, p_res, p_act, now),
                    )

                # Seed default system roles
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO roles (id, name, description, is_system, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    ("role_admin", "admin", "Full system administrator", 1, now, now),
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO roles (id, name, description, is_system, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    ("role_viewer", "viewer", "Read-only system observer", 1, now, now),
                )

                # Link all permissions to admin
                for p_id, _, _, _, _ in base_permissions:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        ("role_admin", p_id, now),
                    )

                # Link read-only permissions to viewer
                for p_id in ("perm_users_read", "perm_roles_read"):
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        ("role_viewer", p_id, now),
                    )

                # Record migration 2
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (2, "0002_auth_and_rbac", now),
                )

            # Migration 3: System Read RBAC Permission (Phase 3)
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 3")
            if not cursor.fetchone():
                logger.info("Applying migration 0003_system_read_permission...")
                system_permissions = [
                    (
                        "perm_system_read",
                        "system.read",
                        "View system metrics, OS identity, and resource utilization",
                        "system",
                        "read",
                    ),
                ]
                for p_id, p_name, p_desc, p_res, p_act in system_permissions:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO permissions (id, name, description, resource, action, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (p_id, p_name, p_desc, p_res, p_act, now),
                    )

                # Assign system.read to admin and viewer roles
                for role_id in ("role_admin", "role_viewer"):
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        (role_id, "perm_system_read", now),
                    )

                # Record migration 3
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (3, "0003_system_read_permission", now),
                )

            # Migration 4: Services Management RBAC Permissions and Audit Logs Table (Phase 4)
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 4")
            if not cursor.fetchone():
                logger.info("Applying migration 0004_services_and_audit_log...")

                # 1. Create audit_logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id TEXT PRIMARY KEY,
                        user_id TEXT,
                        username TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details TEXT,
                        ip_address TEXT,
                        request_id TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);")

                # 2. Seed services permissions
                services_permissions = [
                    (
                        "perm_services_read",
                        "services.read",
                        "View systemd service units, status, and states",
                        "services",
                        "read",
                    ),
                    (
                        "perm_services_start",
                        "services.start",
                        "Start systemd services",
                        "services",
                        "start",
                    ),
                    (
                        "perm_services_stop",
                        "services.stop",
                        "Stop systemd services",
                        "services",
                        "stop",
                    ),
                    (
                        "perm_services_restart",
                        "services.restart",
                        "Restart systemd services",
                        "services",
                        "restart",
                    ),
                    (
                        "perm_services_enable",
                        "services.enable",
                        "Enable systemd services at boot",
                        "services",
                        "enable",
                    ),
                    (
                        "perm_services_disable",
                        "services.disable",
                        "Disable systemd services at boot",
                        "services",
                        "disable",
                    ),
                ]
                for p_id, p_name, p_desc, p_res, p_act in services_permissions:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO permissions (id, name, description, resource, action, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (p_id, p_name, p_desc, p_res, p_act, now),
                    )

                # Assign all service permissions to admin role
                for p_id, _, _, _, _ in services_permissions:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id, assigned_at)
                        VALUES (?, ?, ?)
                    """,
                        ("role_admin", p_id, now),
                    )

                # Assign ONLY services.read to viewer role
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO role_permissions (role_id, permission_id, assigned_at)
                    VALUES (?, ?, ?)
                """,
                    ("role_viewer", "perm_services_read", now),
                )

                # Record migration 4
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (4, "0004_services_and_audit_log", now),
                )

            conn.commit()
            logger.info("SQLite database initialized successfully in WAL mode.")

    def get_metadata(self, key: str) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC"
            )
            return [dict(row) for row in cursor.fetchall()]


db = Database()
