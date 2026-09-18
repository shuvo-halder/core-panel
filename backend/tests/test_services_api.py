import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import ServiceInfo
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
async def test_services_endpoints_unauthenticated():
    """All /api/v1/services/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET endpoints
        res_list = await client.get("/api/v1/services")
        assert res_list.status_code == 401
        assert res_list.json()["error"]["code"] == "UNAUTHORIZED"

        res_get = await client.get("/api/v1/services/nginx.service")
        assert res_get.status_code == 401

        # POST endpoints
        for action in ("start", "stop", "restart", "enable", "disable"):
            res_post = await client.post(f"/api/v1/services/nginx.service/{action}")
            assert res_post.status_code == 401


@pytest.mark.asyncio
async def test_services_viewer_rbac_permissions(monkeypatch):
    """Viewer role has services.read only: allowed to list/view, forbidden from mutations."""
    # Mock service collector
    mock_service = ServiceInfo(
        unit="nginx.service",
        description="A high performance web server",
        load_state="loaded",
        active_state="active",
        sub_state="running",
        enabled="enabled",
        main_pid=1234,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.services.service_collector.list_services",
        AsyncMock(return_value=[mock_service]),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.services.service_collector.get_service",
        AsyncMock(return_value=mock_service),
    )

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

        # 1. Allowed: GET /services
        res_list = await client.get("/api/v1/services", cookies=cookies)
        assert res_list.status_code == 200
        data = res_list.json()
        assert len(data) == 1
        assert data[0]["unit"] == "nginx.service"

        # 2. Allowed: GET /services/nginx.service
        res_get = await client.get("/api/v1/services/nginx.service", cookies=cookies)
        assert res_get.status_code == 200
        assert res_get.json()["unit"] == "nginx.service"

        # 3. Forbidden: POST mutations
        for action in ("start", "stop", "restart", "enable", "disable"):
            res_mut = await client.post(f"/api/v1/services/nginx.service/{action}", cookies=cookies)
            assert res_mut.status_code == 403
            assert res_mut.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_services_admin_mutations_and_audit_logging(monkeypatch, setup_test_db):
    """Admin role can trigger mutations; CoreAgent IPC is called and audit log records event."""
    mock_service = ServiceInfo(
        unit="nginx.service",
        description="A high performance web server",
        load_state="loaded",
        active_state="active",
        sub_state="running",
        enabled="enabled",
        main_pid=1234,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.services.service_collector.get_service",
        AsyncMock(return_value=mock_service),
    )

    # Mock IPC client
    mock_ipc = AsyncMock(
        return_value={"message": "Successfully performed 'restart' on nginx.service"}
    )
    monkeypatch.setattr("backend.app.api.v1.services.ipc_client.execute", mock_ipc)

    auth_service.create_user(
        payload=UserCreate(
            username="admin_user",
            password="AdminPassword123!",
            email="admin@example.com",
            roles=["admin"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as created admin
        res_login = await client.post(
            "/api/v1/auth/login", json={"username": "admin_user", "password": "AdminPassword123!"}
        )
        assert res_login.status_code == 200
        cookies = dict(res_login.cookies)

        # Execute restart mutation
        res_restart = await client.post("/api/v1/services/nginx.service/restart", cookies=cookies)
        assert res_restart.status_code == 200
        data = res_restart.json()
        assert data["success"] is True
        assert data["operation"] == "restart"
        assert data["unit"] == "nginx.service"
        assert "restart" in data["message"]

        # Verify IPC was called with exact operation and payload
        mock_ipc.assert_called_once()
        call_kwargs = mock_ipc.call_args.kwargs
        assert call_kwargs["operation"] == "systemd.service.restart"
        assert call_kwargs["payload"] == {"unit": "nginx.service"}

        # Verify audit log in SQLite
        with setup_test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT action, resource_type, resource_id, status FROM audit_logs")
            rows = cursor.fetchall()
            assert len(rows) >= 1
            last_entry = rows[-1]
            assert last_entry[0] == "services.restart"
            assert last_entry[1] == "service"
            assert last_entry[2] == "nginx.service"
            assert last_entry[3] == "SUCCESS"


@pytest.mark.asyncio
async def test_services_validation_rejection():
    """Rejects malicious or malformed service names with 400 Bad Request."""
    auth_service.create_user(
        payload=UserCreate(
            username="admin_user2",
            password="AdminPassword123!",
            email="admin2@example.com",
            roles=["admin"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        # Login as admin
        res_login = await client.post(
            "/api/v1/auth/login", json={"username": "admin_user2", "password": "AdminPassword123!"}
        )
        cookies = dict(res_login.cookies)

        invalid_units = [
            "../../etc/shadow.service",
            "nginx.service;rm -rf /",
            "nginx.service|cat",
            "nginx.service `reboot`",
            "nginx.socket",  # non-.service
            "nginx.target",
            "../test.service",
            "service with spaces.service",
            ".service",  # too short (< 9 chars)
        ]

        for bad_unit in invalid_units:
            encoded_unit = quote(bad_unit, safe="")
            res_get = await client.get(f"/api/v1/services/{encoded_unit}", cookies=cookies)
            assert (
                res_get.status_code == 400 or res_get.status_code == 404
            ), f"Expected 400 for '{bad_unit}', got {res_get.status_code}"

            res_post = await client.post(
                f"/api/v1/services/{encoded_unit}/start", cookies=cookies
            )
            assert (
                res_post.status_code == 400 or res_post.status_code == 404
            ), f"Expected 400 for '{bad_unit}', got {res_post.status_code}"
