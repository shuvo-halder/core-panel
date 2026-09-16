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
                    ("version", settings.APP_VERSION, now)
                )
                cursor.execute(
                    "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
                    ("environment", settings.ENVIRONMENT, now)
                )

            # Record initial baseline migration
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "0001_baseline_metadata", now)
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
            cursor.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC")
            return [dict(row) for row in cursor.fetchall()]


db = Database()
