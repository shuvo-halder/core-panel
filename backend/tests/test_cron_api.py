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
from backend.app.core.errors import BadRequestError, ConflictError, NotFoundError
from backend.app.core.validators import (
    validate_cron_command,
    validate_cron_comment,
    validate_cron_schedule,
    validate_cron_username,
)
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    CronJob,
    CronListResult,
    CronOverview,
    CronSource,
)
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database with Phase 9 migrations for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


# -----------------------------------------------------------------------------
# Unit Tests for Cron Validators (Safe, Read-Only, Injection-Proof)
# -----------------------------------------------------------------------------

def test_validate_cron_username():
    """Verify username validation accepts valid local OS users and rejects malicious syntax."""
    # root exists on any Linux system
    assert validate_cron_username("root") == "root"

    # Invalid names
    invalid_cases = [
        "",
        " ",
        "root; rm -rf /",
        "root&whoami",
        "../root",
        "/etc/passwd",
        "root\x00malicious",
        "-root",
        "this_user_definitely_does_not_exist_99999",
    ]
    for case in invalid_cases:
        with pytest.raises(BadRequestError):
            validate_cron_username(case)


def test_validate_cron_schedule():
    """Verify standard 5-field and special cron expressions are validated strictly."""
    # Valid 5-field
    assert validate_cron_schedule("* * * * *") == "* * * * *"
    assert validate_cron_schedule("*/5 * * * *") == "*/5 * * * *"
    assert validate_cron_schedule("0 2 * * *") == "0 2 * * *"
    assert validate_cron_schedule("30 3 * * 0") == "30 3 * * 0"
    assert validate_cron_schedule("0 0 1 1 *") == "0 0 1 1 *"
    assert validate_cron_schedule("15,45 8-17 * * 1-5") == "15,45 8-17 * * 1-5"

    # Valid special expressions
    assert validate_cron_schedule("@reboot") == "@reboot"
    assert validate_cron_schedule("@daily") == "@daily"
    assert validate_cron_schedule("@hourly") == "@hourly"
    assert validate_cron_schedule("@weekly") == "@weekly"
    assert validate_cron_schedule("@monthly") == "@monthly"
    assert validate_cron_schedule("@yearly") == "@yearly"
    assert validate_cron_schedule("@annually") == "@annually"

    # Invalid schedules
    invalid_cases = [
        "",
        "* * *",             # too few fields
        "* * * * * *",       # too many fields
        "60 * * * *",         # minute out of range (0-59)
        "* 24 * * *",         # hour out of range (0-23)
        "* * 32 * *",         # day of month out of range (1-31)
        "* * * 13 *",         # month out of range (1-12)
        "* * * * 8",          # day of week out of range (0-7)
        "@invalid_expr",      # unsupported special expression
        "; rm -rf /",         # shell injection attempt
        "* * * * *; curl | sh",
        "* * * * *\n0 0 * * *",
    ]
    for case in invalid_cases:
        with pytest.raises(BadRequestError):
            validate_cron_schedule(case)


def test_validate_cron_command():
    """Verify cron command validation prevents control character and newline injection."""
    # Valid commands
    assert validate_cron_command("/usr/local/bin/backup.sh") == "/usr/local/bin/backup.sh"
    assert validate_cron_command("python3 /opt/app/run.py --flag") == "python3 /opt/app/run.py --flag"
    assert validate_cron_command("/usr/bin/find /tmp -type f -mtime +7 -delete > /dev/null 2>&1") == "/usr/bin/find /tmp -type f -mtime +7 -delete > /dev/null 2>&1"

    # Invalid commands: newline / carriage-return / null byte injection
    invalid_cases = [
        "",
        "   ",
        "/bin/echo hello\n* * * * * /bin/evil",
        "/bin/echo hello\r* * * * * /bin/evil",
        "/bin/echo\x00/bin/evil",
    ]
    for case in invalid_cases:
        with pytest.raises(BadRequestError):
            validate_cron_command(case)


def test_validate_cron_comment():
    """Verify cron comments reject newline injection to preserve crontab formatting."""
    assert validate_cron_comment(None) is None
    assert validate_cron_comment("Daily backup") == "Daily backup"
    assert validate_cron_comment("  # Note about task  ") == "Note about task"

    # Multi-line comment attempt
    with pytest.raises(BadRequestError):
        validate_cron_comment("Note 1\n* * * * * /bin/evil")


# -----------------------------------------------------------------------------
# API Endpoint Integration Tests (Authentication & RBAC)
# -----------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed in test runner environment")
@pytest.mark.asyncio
async def test_cron_endpoints_unauthenticated():
    """All /api/v1/cron/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET endpoints
        res_overview = await client.get("/api/v1/cron/overview")
        assert res_overview.status_code == 401

        res_jobs = await client.get("/api/v1/cron/jobs")
        assert res_jobs.status_code == 401

        res_job = await client.get("/api/v1/cron/jobs/cron_123")
        assert res_job.status_code == 401

        res_users = await client.get("/api/v1/cron/users")
        assert res_users.status_code == 401

        # Mutation endpoints
        res_post = await client.post("/api/v1/cron/jobs", json={
            "owner": "root",
            "schedule": "0 0 * * *",
            "command": "/usr/bin/true",
        })
        assert res_post.status_code == 401

        res_put = await client.put("/api/v1/cron/jobs/cron_123", json={
            "owner": "root",
            "schedule": "0 0 * * *",
            "command": "/usr/bin/true",
        })
        assert res_put.status_code == 401

        res_delete = await client.delete("/api/v1/cron/jobs/cron_123?owner=root")
        assert res_delete.status_code == 401


@pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed in test runner environment")
@pytest.mark.asyncio
async def test_cron_viewer_rbac_permissions(monkeypatch):
    """Viewer role has cron.read: allowed to list/view, forbidden (403) from mutations."""
    mock_job = CronJob(
        id="cron_test1",
        owner="root",
        schedule="0 0 * * *",
        minute="0",
        hour="0",
        day_of_month="*",
        month="*",
        day_of_week="*",
        command="/usr/bin/backup.sh",
        comment="Test backup",
        enabled=True,
        source=CronSource.USER_CRONTAB,
        is_editable=True,
        original_hash="hash1234",
    )

    async def mock_get_overview():
        return CronOverview(
            total_jobs=1,
            active_jobs=1,
            disabled_jobs=0,
            users_with_crontabs=1,
            user_jobs_count=1,
            system_jobs_count=0,
            cron_d_jobs_count=0,
            periodic_jobs_count=0,
            available_sources=[CronSource.USER_CRONTAB],
        )

    async def mock_list_jobs(**kwargs):
        return CronListResult(
            items=[mock_job],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )

    async def mock_get_job(job_id: str):
        if job_id == "cron_test1":
            return mock_job
        return None

    monkeypatch.setattr("backend.app.api.v1.cron.cron_manager.get_overview", mock_get_overview)
    monkeypatch.setattr("backend.app.api.v1.cron.cron_manager.list_jobs", mock_list_jobs)
    monkeypatch.setattr("backend.app.api.v1.cron.cron_manager.get_job", mock_get_job)

    # Create viewer user
    user = auth_service.create_user(UserCreate(
        username="viewer_user",
        password="SecurePassword123!",
        roles=["viewer"],
    ))
    session = auth_service.create_session(user.id)
    cookies = {"corepanel_session": session.id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # Allowed reads
        res_overview = await client.get("/api/v1/cron/overview")
        assert res_overview.status_code == 200
        assert res_overview.json()["total_jobs"] == 1

        res_jobs = await client.get("/api/v1/cron/jobs")
        assert res_jobs.status_code == 200
        assert len(res_jobs.json()["items"]) == 1

        res_job = await client.get("/api/v1/cron/jobs/cron_test1")
        assert res_job.status_code == 200
        assert res_job.json()["id"] == "cron_test1"

        # Forbidden mutations
        res_create = await client.post("/api/v1/cron/jobs", json={
            "owner": "root",
            "schedule": "0 0 * * *",
            "command": "/bin/true",
        })
        assert res_create.status_code == 403

        res_update = await client.put("/api/v1/cron/jobs/cron_test1", json={
            "owner": "root",
            "schedule": "0 0 * * *",
            "command": "/bin/true",
        })
        assert res_update.status_code == 403

        res_delete = await client.delete("/api/v1/cron/jobs/cron_test1?owner=root")
        assert res_delete.status_code == 403
