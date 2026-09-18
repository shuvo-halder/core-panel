import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import RoleCreate, UserCreate
from backend.app.auth.service import auth_service
from backend.app.db.sqlite import Database
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        test_db.init_database()
        yield test_db


@pytest.mark.asyncio
async def test_system_endpoints_unauthenticated():
    """All /api/v1/system/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/overview", "/info", "/cpu", "/memory", "/disks", "/network"):
            res = await client.get(f"/api/v1/system{path}")
            assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"
            assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_system_endpoints_authorized_viewer():
    """Users with 'viewer' role (holding 'system.read') can access all system monitoring endpoints."""
    # 1. Create viewer user
    auth_service.create_user(
        payload=UserCreate(
            username="viewer_user",
            password="ViewerPassword123!",
            email="viewer@example.com",
            roles=["viewer"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        res_login = await client.post(
            "/api/v1/auth/login", json={"username": "viewer_user", "password": "ViewerPassword123!"}
        )
        assert res_login.status_code == 200
        cookies = dict(res_login.cookies)

        # 1. System Overview
        res_overview = await client.get("/api/v1/system/overview", cookies=cookies)
        assert res_overview.status_code == 200
        overview_data = res_overview.json()
        assert "identity" in overview_data
        assert "cpu" in overview_data
        assert "memory" in overview_data
        assert "disks" in overview_data
        assert "network" in overview_data
        assert "timestamp" in overview_data
        assert overview_data["identity"]["operating_system"] == "Linux"
        assert overview_data["cpu"]["logical_cores"] >= 1
        assert overview_data["memory"]["total_bytes"] > 0

        # 2. System Info
        res_info = await client.get("/api/v1/system/info", cookies=cookies)
        assert res_info.status_code == 200
        info_data = res_info.json()
        assert info_data["operating_system"] == "Linux"
        assert "hostname" in info_data
        assert "distribution" in info_data
        assert "kernel_version" in info_data
        assert "architecture" in info_data
        assert "uptime_seconds" in info_data

        # 3. CPU Metrics
        res_cpu = await client.get("/api/v1/system/cpu", cookies=cookies)
        assert res_cpu.status_code == 200
        cpu_data = res_cpu.json()
        assert cpu_data["logical_cores"] >= 1
        assert "model_name" in cpu_data
        assert 0.0 <= cpu_data["usage_percent"] <= 100.0
        assert "load_average" in cpu_data
        assert "load_1m" in cpu_data["load_average"]

        # 4. Memory Metrics
        res_mem = await client.get("/api/v1/system/memory", cookies=cookies)
        assert res_mem.status_code == 200
        mem_data = res_mem.json()
        assert mem_data["total_bytes"] > 0
        assert mem_data["available_bytes"] >= 0
        assert 0.0 <= mem_data["usage_percent"] <= 100.0
        assert "swap" in mem_data
        assert "total_bytes" in mem_data["swap"]

        # 5. Disk Mounts
        res_disks = await client.get("/api/v1/system/disks", cookies=cookies)
        assert res_disks.status_code == 200
        disks_data = res_disks.json()
        assert isinstance(disks_data, list)
        if disks_data:
            assert "mount_point" in disks_data[0]
            assert "total_bytes" in disks_data[0]
            assert "used_bytes" in disks_data[0]

        # 6. Network Interfaces
        res_net = await client.get("/api/v1/system/network", cookies=cookies)
        assert res_net.status_code == 200
        net_data = res_net.json()
        assert isinstance(net_data, list)
        if net_data:
            assert "name" in net_data[0]
            assert "state" in net_data[0]
            assert "mac_address" in net_data[0]
            assert "rx_bytes" in net_data[0]
            assert "tx_bytes" in net_data[0]


@pytest.mark.asyncio
async def test_system_endpoints_forbidden_without_permission():
    """Users without 'system.read' permission receive 403 Forbidden."""
    # Create a custom restricted role with no permissions
    auth_service.create_role(
        payload=RoleCreate(
            name="restricted_auditor",
            description="Role without system.read",
            permissions=["users.read"],
        )
    )

    auth_service.create_user(
        payload=UserCreate(
            username="restricted_user",
            password="RestrictedPassword123!",
            roles=["restricted_auditor"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "restricted_user", "password": "RestrictedPassword123!"},
        )
        assert res_login.status_code == 200
        cookies = dict(res_login.cookies)

        # Attempt to access system overview without system.read
        res_overview = await client.get("/api/v1/system/overview", cookies=cookies)
        assert res_overview.status_code == 403
        assert res_overview.json()["error"]["code"] == "FORBIDDEN"
        assert "system.read" in res_overview.json()["error"]["message"]
