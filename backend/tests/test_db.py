import tempfile
from pathlib import Path

from backend.app.db.sqlite import Database


def test_database_initialization_and_wal():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=db_path)
        test_db.init_database()

        # Verify WAL mode
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.lower() == "wal"

        # Verify metadata
        version = test_db.get_metadata("version")
        assert version is not None

        # Verify migrations
        migrations = test_db.get_applied_migrations()
        assert len(migrations) >= 1
        assert migrations[0]["version"] == 1
        assert migrations[0]["name"] == "0001_baseline_metadata"
