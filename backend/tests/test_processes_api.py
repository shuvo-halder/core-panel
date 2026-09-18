import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import ProcessInfo, ProcessListResult
from backend.app.linux.processes import LinuxProcessCollector
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


@pytest.mark.asyncio
async def test_processes_endpoints_unauthenticated():
    """All /api/v1/processes/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET endpoints
        res_list = await client.get("/api/v1/processes")
        assert res_list.status_code == 401
        assert res_list.json()["error"]["code"] == "UNAUTHORIZED"

        res_get = await client.get("/api/v1/processes/100")
        assert res_get.status_code == 401

        # POST mutation endpoints
        for action in ("terminate", "kill"):
            res_post = await client.post(f"/api/v1/processes/100/{action}")
            assert res_post.status_code == 401


@pytest.mark.asyncio
async def test_processes_viewer_rbac_permissions(monkeypatch):
    """Viewer role has processes.read only: allowed to list/view, forbidden from mutations."""
    mock_process = ProcessInfo(
        pid=1234,
        ppid=1,
        name="nginx",
        username="www-data",
        uid=33,
        state="sleeping",
        cpu_percent=0.5,
        memory_rss_bytes=10485760,
        memory_vsz_bytes=52428800,
        memory_percent=0.25,
        start_time="2026-09-18T10:00:00Z",
        start_time_ticks=123456,
        threads=4,
        command_summary="nginx: worker",
        is_protected=False,
    )

    class MockProcessCollector:
        def list_processes(self, *args, **kwargs):
            return ProcessListResult(
                items=[mock_process],
                total=1,
                page=1,
                page_size=50,
                total_pages=1,
            )

        def get_process(self, pid: int):
            return mock_process if pid == 1234 else None

    monkeypatch.setattr("backend.app.api.v1.processes.process_collector", MockProcessCollector())

    # Create viewer user
    user = auth_service.create_user(
        UserCreate(username="viewer_user", password="ViewerPassword123!", role_names=["viewer"])
    )
    token = auth_service.create_session_token(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"panel_session": token},
    ) as client:
        # Viewer can list processes
        res_list = await client.get("/api/v1/processes")
        assert res_list.status_code == 200
        assert res_list.json()["total"] == 1
        assert res_list.json()["items"][0]["pid"] == 1234

        # Viewer can get single process
        res_get = await client.get("/api/v1/processes/1234")
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "nginx"

        # Viewer is forbidden from terminating or killing processes
        res_term = await client.post("/api/v1/processes/1234/terminate")
        assert res_term.status_code == 403
        assert res_term.json()["error"]["code"] == "FORBIDDEN"

        res_kill = await client.post("/api/v1/processes/1234/kill")
        assert res_kill.status_code == 403
        assert res_kill.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_processes_admin_rbac_and_mutations(monkeypatch):
    """Admin has full process permissions: terminate and kill via IPC with audit logging."""
    mock_process = ProcessInfo(
        pid=5678,
        ppid=1,
        name="rogue_worker",
        username="app",
        uid=1000,
        state="running",
        cpu_percent=98.5,
        memory_rss_bytes=104857600,
        memory_vsz_bytes=524288000,
        memory_percent=2.5,
        start_time="2026-09-18T10:00:00Z",
        start_time_ticks=999999,
        threads=2,
        command_summary="python rogue.py",
        is_protected=False,
    )

    class MockProcessCollector:
        def list_processes(self, *args, **kwargs):
            return ProcessListResult(
                items=[mock_process],
                total=1,
                page=1,
                page_size=50,
                total_pages=1,
            )

        def get_process(self, pid: int):
            return mock_process if pid == 5678 else None

    monkeypatch.setattr("backend.app.api.v1.processes.process_collector", MockProcessCollector())

    # Mock IPC client
    mock_ipc = AsyncMock()
    mock_ipc.execute.side_effect = lambda operation, payload, **kwargs: {
        "success": True,
        "pid": payload["pid"],
        "operation": "terminate" if "terminate" in operation else "kill",
        "signal": "SIGTERM" if "terminate" in operation else "SIGKILL",
        "status": "signal_sent",
        "message": f"Signal sent to process {payload['pid']}",
    }
    monkeypatch.setattr("backend.app.api.v1.processes.ipc_client", mock_ipc)

    # Create admin user
    user = auth_service.create_user(
        UserCreate(username="admin_proc", password="AdminPassword123!", role_names=["admin"])
    )
    token = auth_service.create_session_token(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"panel_session": token},
    ) as client:
        # Admin can terminate process
        res_term = await client.post("/api/v1/processes/5678/terminate")
        assert res_term.status_code == 200
        assert res_term.json()["success"] is True
        assert res_term.json()["signal"] == "SIGTERM"

        # Admin can kill process
        res_kill = await client.post("/api/v1/processes/5678/kill")
        assert res_kill.status_code == 200
        assert res_kill.json()["success"] is True
        assert res_kill.json()["signal"] == "SIGKILL"

        # Verify audit log entries
        from backend.app.audit.service import audit_service

        events = audit_service.get_recent_events(limit=10)
        assert len(events) >= 2
        actions = [e["action"] for e in events]
        assert "processes.terminate" in actions
        assert "processes.kill" in actions


@pytest.mark.asyncio
async def test_pid_validation_and_protected_process_rejection(monkeypatch):
    """Verifies PID range validation and rejection of protected processes (PID 1, self)."""
    user = auth_service.create_user(
        UserCreate(username="admin_proc_val", password="AdminPassword123!", role_names=["admin"])
    )
    token = auth_service.create_session_token(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"panel_session": token},
    ) as client:
        # Invalid PIDs
        for bad_pid in ("0", "-5", "abc", "999999999"):
            res = await client.post(f"/api/v1/processes/{bad_pid}/terminate")
            assert res.status_code in (400, 422)

        # PID 1 rejection
        res_pid1 = await client.post("/api/v1/processes/1/terminate")
        assert res_pid1.status_code in (400, 403)
        assert "PROTECTED" in res_pid1.json()["error"]["code"]

        res_pid1_kill = await client.post("/api/v1/processes/1/kill")
        assert res_pid1_kill.status_code in (400, 403)
        assert "PROTECTED" in res_pid1_kill.json()["error"]["code"]


def test_linux_process_collector_mock_proc():
    """Tests LinuxProcessCollector parsing of stat, status, and cmdline files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_proc = Path(tmpdir)

        # Create mock /proc/stat
        (mock_proc / "stat").write_text("cpu 100 200 300 400 50 10 5 0\nbtime 1700000000\n")

        # Create mock /proc/uptime
        (mock_proc / "uptime").write_text("10000.50 80000.20\n")

        # Create mock /proc/meminfo
        (mock_proc / "meminfo").write_text("MemTotal:        16384000 kB\nMemFree:          8192000 kB\n")

        # Create process directory 9999
        p9999 = mock_proc / "9999"
        p9999.mkdir()

        # Mock /proc/9999/stat
        # comm is (test_daemon)
        stat_line = (
            "9999 (test_daemon) S 1 9999 9999 0 -1 4194560 100 0 0 0 "
            "50 20 0 0 20 0 2 0 50000 104857600 2560 18446744073709551615"
        )
        (p9999 / "stat").write_text(stat_line)

        # Mock /proc/9999/status
        (p9999 / "status").write_text(
            "Name:\ttest_daemon\nState:\tS (sleeping)\nUid:\t1000\t1000\t1000\t1000\nVmRSS:\t10240 kB\nVmSize:\t102400 kB\n"
        )

        # Mock /proc/9999/cmdline
        (p9999 / "cmdline").write_bytes(b"/usr/bin/test_daemon\x00--config\x00/etc/test.conf\x00")

        collector = LinuxProcessCollector(proc_path=mock_proc)
        result = collector.list_processes()

        assert result.total == 1
        proc = result.items[0]
        assert proc.pid == 9999
        assert proc.name == "test_daemon"
        assert proc.ppid == 1
        assert proc.state == "sleeping"
        assert proc.memory_rss_bytes == 10240 * 1024
        assert "--config /etc/test.conf" in (proc.command_summary or "")
        assert proc.threads == 2

        # Test single process fetch
        proc_single = collector.get_process(9999)
        assert proc_single is not None
        assert proc_single.pid == 9999
