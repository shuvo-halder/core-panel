import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

try:
    from httpx import ASGITransport, AsyncClient
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.core.errors import BadRequestError
from backend.app.core.validators import (
    validate_log_severity,
    validate_log_source_id,
    validate_log_search,
    validate_log_unit,
)
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    LogEntry,
    LogOverview,
    LogPage,
    LogSource,
)
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database with Phase 10 migrations for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


# -----------------------------------------------------------------------------
# Unit Tests for Log Input Validators
# -----------------------------------------------------------------------------

def test_validate_log_severity():
    """Verify severity validator normalizes valid levels and rejects bad input."""
    assert validate_log_severity(None) is None
    assert validate_log_severity("err") == "ERR"
    assert validate_log_severity("WARNING") == "WARNING"
    assert validate_log_severity("info") == "INFO"

    with pytest.raises(BadRequestError):
        validate_log_severity("UNKNOWN_LEVEL")

    with pytest.raises(BadRequestError):
        validate_log_severity("INFO; DROP TABLE logs")


def test_validate_log_source():
    """Verify log source validator accepts allowlisted source keys."""
    assert validate_log_source_id("JOURNAL") == "JOURNAL"
    assert validate_log_source_id("syslog") == "SYSLOG"
    assert validate_log_source_id("AUTH") == "AUTH"

    with pytest.raises(BadRequestError):
        validate_log_source_id("RANDOM_SOURCE")

    with pytest.raises(BadRequestError):
        validate_log_source_id("../../../etc/shadow")


def test_validate_systemd_unit_name():
    """Verify systemd unit validator prevents shell escapes and flags."""
    assert validate_log_unit(None) is None
    assert validate_log_unit("nginx.service") == "nginx.service"
    assert validate_log_unit("sshd.service") == "sshd.service"

    with pytest.raises(BadRequestError):
        validate_log_unit("sshd; rm -rf /")

    with pytest.raises(BadRequestError):
        validate_log_unit("-u nginx")


def test_validate_log_search_query():
    """Verify search queries reject newlines and enforce length bounds."""
    assert validate_log_search(None) is None
    assert validate_log_search("  failed login  ") == "failed login"

    with pytest.raises(BadRequestError):
        validate_log_search("line1\nline2")


# -----------------------------------------------------------------------------
# API Endpoint Integration Tests (Authentication & RBAC)
# -----------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed in test runner environment")
@pytest.mark.asyncio
async def test_log_endpoints_unauthenticated():
    """All /api/v1/logs/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_overview = await client.get("/api/v1/logs/overview")
        assert res_overview.status_code == 401

        res_sources = await client.get("/api/v1/logs/sources")
        assert res_sources.status_code == 401

        res_logs = await client.get("/api/v1/logs")
        assert res_logs.status_code == 401

        res_audit = await client.get("/api/v1/logs/audit")
        assert res_audit.status_code == 401


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed in test runner environment")
@pytest.mark.asyncio
async def test_logs_rbac_authorization(setup_test_db):
    """Verify that users without logs.read get 403, and users with logs.read get 200."""
    # 1. Create a user with NO permissions
    auth_service.create_user(UserCreate(
        username="unprivileged",
        password="TestPassword123!",
        roles=[]
    ))
    session = auth_service.authenticate_user("unprivileged", "TestPassword123!")

    transport = ASGITransport(app=app)
    cookies = {"corepanel_session": session.session_id}

    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.get("/api/v1/logs/overview")
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

        res_audit = await client.get("/api/v1/logs/audit")
        assert res_audit.status_code == 403

    # 2. Assign viewer role (has system.read, logs.read, audit.read)
    setup_test_db.execute_write(
        "INSERT INTO user_roles (user_id, role_name) VALUES (?, ?)",
        (session.user_id, "viewer"),
    )

    mock_overview = LogOverview(
        available_sources=[
            LogSource(
                id="JOURNAL",
                name="systemd Journal",
                source_type="JOURNAL",
                path=None,
                available=True,
                size_bytes=None,
                last_modified=None,
                description="Central binary journal",
            )
        ],
        journal_available=True,
        total_sources_count=1,
        active_sources_count=1,
        severity_counts={"INFO": 10, "ERR": 2},
        latest_timestamp="2026-09-22T00:00:00Z",
    )

    with patch("backend.app.linux.logs.log_manager.get_overview", new_callable=AsyncMock) as mock_get_overview, \
         patch("backend.app.linux.logs.log_manager.get_sources", new_callable=AsyncMock) as mock_get_sources:
        mock_get_overview.return_value = mock_overview
        mock_get_sources.return_value = mock_overview.available_sources

        async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
            res_ov = await client.get("/api/v1/logs/overview")
            assert res_ov.status_code == 200
            data = res_ov.json()
            assert data["journal_available"] is True
            assert data["total_sources_count"] == 1

            res_src = await client.get("/api/v1/logs/sources")
            assert res_src.status_code == 200
            assert len(res_src.json()) == 1

            res_audit = await client.get("/api/v1/logs/audit")
            assert res_audit.status_code == 200
            assert "items" in res_audit.json()
