import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.hashing import hasher
from backend.app.auth.service import auth_service
from backend.app.core.config import settings
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
async def test_password_hasher():
    """Verify Argon2id hashing and verification logic."""
    raw_pass = "ComplexP@ssw0rd!123"
    hashed = hasher.hash(raw_pass)
    assert hashed.startswith("$argon2id$")
    assert hasher.verify(hashed, raw_pass) is True
    assert hasher.verify(hashed, "WrongPassword") is False
    assert hasher.verify(hashed, "") is False

    with pytest.raises(ValueError):
        hasher.hash("short")


@pytest.mark.asyncio
async def test_admin_bootstrap(monkeypatch):
    """Verify safe, idempotent administrator bootstrap."""
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_USERNAME", "sysadmin")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "SuperSecureAdminSecret!99")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "admin@corepanel.local")

    # First bootstrap
    auth_service.bootstrap_admin_if_configured()
    users = auth_service.list_users()
    assert len(users) == 1
    assert users[0].username == "sysadmin"
    assert "admin" in users[0].roles
    assert "users.manage" in users[0].permissions

    # Second bootstrap must be idempotent
    auth_service.bootstrap_admin_if_configured()
    users_after = auth_service.list_users()
    assert len(users_after) == 1


@pytest.mark.asyncio
async def test_auth_login_and_logout_flow():
    """Test full login, cookie issuance, /auth/me profile, and logout revocation."""
    # Create user
    created_user = auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="alice",
            password="SecurePassword123!",
            email="alice@example.com",
            roles=["admin"],
            is_active=True,
        )
    )
    assert created_user.username == "alice"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invalid Login
        res_fail = await client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "WrongPassword"}
        )
        assert res_fail.status_code == 401
        assert res_fail.json()["error"]["code"] == "UNAUTHORIZED"

        # 2. Valid Login
        res_login = await client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "SecurePassword123!"}
        )
        assert res_login.status_code == 200
        data = res_login.json()
        assert data["success"] is True
        assert data["user"]["username"] == "alice"
        assert "password_hash" not in str(data)  # Never leak password hash
        assert "corepanel_session" in res_login.cookies

        cookie_val = res_login.cookies.get("corepanel_session")
        assert cookie_val is not None

        # 3. Access /auth/me with session cookie
        res_me = await client.get("/api/v1/auth/me", cookies={"corepanel_session": cookie_val})
        assert res_me.status_code == 200
        assert res_me.json()["user"]["username"] == "alice"
        assert "users.read" in res_me.json()["effective_permissions"]

        # 4. Logout
        res_logout = await client.post(
            "/api/v1/auth/logout", cookies={"corepanel_session": cookie_val}
        )
        assert res_logout.status_code == 200

        # 5. Access /auth/me after logout must be 401
        res_me_after = await client.get(
            "/api/v1/auth/me", cookies={"corepanel_session": cookie_val}
        )
        assert res_me_after.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_cannot_login_or_access():
    """Verify deactivated user rejection on login and session invalidation."""
    user = auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="bob",
            password="BobPassword123!",
            email="bob@example.com",
            roles=["viewer"],
            is_active=False,
        )
    )
    assert user.is_active is False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cannot login
        res = await client.post(
            "/api/v1/auth/login", json={"username": "bob", "password": "BobPassword123!"}
        )
        assert res.status_code == 401
        assert "deactivated" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_rbac_permission_enforcement():
    """Verify 401 for unauthenticated, 403 for missing permissions, and 200 for allowed."""
    # Create viewer (has users.read, roles.read, but NOT users.manage or roles.manage)
    auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="viewer_user",
            password="ViewerPassword123!",
            email="viewer@example.com",
            roles=["viewer"],
            is_active=True,
        )
    )

    # Create admin
    auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="admin_user",
            password="AdminPassword123!",
            email="admin@example.com",
            roles=["admin"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated -> 401
        res_unauth = await client.get("/api/v1/users")
        assert res_unauth.status_code == 401

        # 2. Login as Viewer
        login_viewer = await client.post(
            "/api/v1/auth/login", json={"username": "viewer_user", "password": "ViewerPassword123!"}
        )
        viewer_cookie = {"corepanel_session": login_viewer.cookies.get("corepanel_session")}

        # Viewer can read users
        res_read_users = await client.get("/api/v1/users", cookies=viewer_cookie)
        assert res_read_users.status_code == 200
        assert len(res_read_users.json()) >= 2

        # Viewer CANNOT create user -> 403 Forbidden
        res_create_forbidden = await client.post(
            "/api/v1/users",
            json={"username": "charlie", "password": "CharliePassword123!", "roles": ["viewer"]},
            cookies=viewer_cookie,
        )
        assert res_create_forbidden.status_code == 403
        assert res_create_forbidden.json()["error"]["code"] == "FORBIDDEN"

        # 3. Login as Admin
        login_admin = await client.post(
            "/api/v1/auth/login", json={"username": "admin_user", "password": "AdminPassword123!"}
        )
        admin_cookie = {"corepanel_session": login_admin.cookies.get("corepanel_session")}

        # Admin CAN create user -> 201
        res_create_ok = await client.post(
            "/api/v1/users",
            json={"username": "charlie", "password": "CharliePassword123!", "roles": ["viewer"]},
            cookies=admin_cookie,
        )
        assert res_create_ok.status_code == 201
        assert res_create_ok.json()["username"] == "charlie"


@pytest.mark.asyncio
async def test_user_management_crud_and_safety_checks():
    """Verify user update, conflict detection, and self-delete prevention."""
    admin = auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="superadmin",
            password="SuperPassword123!",
            email="superadmin@example.com",
            roles=["admin"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_admin = await client.post(
            "/api/v1/auth/login", json={"username": "superadmin", "password": "SuperPassword123!"}
        )
        admin_cookie = {"corepanel_session": login_admin.cookies.get("corepanel_session")}

        # 1. Duplicate username conflict
        res_dup = await client.post(
            "/api/v1/users",
            json={"username": "superadmin", "password": "AnotherPassword123!"},
            cookies=admin_cookie,
        )
        assert res_dup.status_code == 409

        # 2. Create another user
        res_create = await client.post(
            "/api/v1/users",
            json={"username": "target_user", "password": "TargetPassword123!", "roles": ["viewer"]},
            cookies=admin_cookie,
        )
        assert res_create.status_code == 201
        target_id = res_create.json()["id"]

        # 3. Update target user
        res_update = await client.patch(
            f"/api/v1/users/{target_id}",
            json={"is_active": False},
            cookies=admin_cookie,
        )
        assert res_update.status_code == 200
        assert res_update.json()["is_active"] is False

        # 4. Delete target user
        res_del = await client.delete(f"/api/v1/users/{target_id}", cookies=admin_cookie)
        assert res_del.status_code == 200

        # 5. Admin cannot delete self
        res_self_del = await client.delete(f"/api/v1/users/{admin.id}", cookies=admin_cookie)
        assert res_self_del.status_code == 400
        assert "cannot delete your own" in res_self_del.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_roles_and_permissions_endpoints():
    """Verify role creation, permissions listing, and system role protection."""
    auth_service.create_user(
        payload=auth_service.create_user.__annotations__["payload"](
            username="admin_sec",
            password="SecPassword123!",
            email="sec@example.com",
            roles=["admin"],
            is_active=True,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login", json={"username": "admin_sec", "password": "SecPassword123!"}
        )
        cookie = {"corepanel_session": login_res.cookies.get("corepanel_session")}

        # List permissions
        res_perms = await client.get("/api/v1/permissions", cookies=cookie)
        assert res_perms.status_code == 200
        perm_names = [p["name"] for p in res_perms.json()]
        assert "users.read" in perm_names
        assert "roles.manage" in perm_names

        # List roles
        res_roles = await client.get("/api/v1/roles", cookies=cookie)
        assert res_roles.status_code == 200
        role_names = [r["name"] for r in res_roles.json()]
        assert "admin" in role_names
        assert "viewer" in role_names

        # Create custom role
        res_new_role = await client.post(
            "/api/v1/roles",
            json={
                "name": "user_operator",
                "description": "Custom role for user ops",
                "permissions": ["users.read", "users.manage"],
            },
            cookies=cookie,
        )
        assert res_new_role.status_code == 201
        custom_role_id = res_new_role.json()["id"]

        # Delete custom role
        res_del_role = await client.delete(f"/api/v1/roles/{custom_role_id}", cookies=cookie)
        assert res_del_role.status_code == 200

        # Attempt to delete built-in admin role -> 400
        admin_role_id = [r["id"] for r in res_roles.json() if r["name"] == "admin"][0]
        res_del_admin = await client.delete(f"/api/v1/roles/{admin_role_id}", cookies=cookie)
        assert res_del_admin.status_code == 400
        assert "built-in" in res_del_admin.json()["error"]["message"].lower()
