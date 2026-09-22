import asyncio
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Lightweight test harness for standalone execution
if "pydantic" not in sys.modules:
    fake_pydantic = types.ModuleType("pydantic")
    class FakeBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump_json(self):
            import json
            return json.dumps(self.__dict__)
        @classmethod
        def model_validate_json(cls, s):
            import json
            inst = cls()
            inst.__dict__.update(json.loads(s))
            return inst
    fake_pydantic.BaseModel = FakeBaseModel
    fake_pydantic.Field = lambda *args, **kwargs: kwargs.get("default", args[0] if args else None)
    fake_pydantic.ConfigDict = dict
    fake_pydantic.EmailStr = str
    sys.modules["pydantic"] = fake_pydantic

if "pydantic_settings" not in sys.modules:
    fake_ps = types.ModuleType("pydantic_settings")
    class FakeSettings:
        LOG_LEVEL = "INFO"
        PORT = 8000
        APP_VERSION = "0.1.0"
        ENVIRONMENT = "test"
    fake_ps.BaseSettings = FakeSettings
    fake_ps.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = fake_ps

if "fastapi" not in sys.modules:
    class FakeStatus:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500
        HTTP_503_SERVICE_UNAVAILABLE = 503

    def fake_route_decorator(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    class FakeRouter:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def post(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def delete(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def put(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.status = FakeStatus
    fake_fastapi.Request = object
    fake_fastapi.APIRouter = FakeRouter
    fake_fastapi.Depends = lambda x: x
    fake_fastapi.Query = lambda *args, **kwargs: kwargs.get("default", None)
    fake_fastapi.FastAPI = MagicMock
    fake_fastapi.Response = MagicMock
    sys.modules["fastapi"] = fake_fastapi

    fake_fastapi_exc = types.ModuleType("fastapi.exceptions")
    fake_fastapi_exc.RequestValidationError = Exception
    sys.modules["fastapi.exceptions"] = fake_fastapi_exc

    fake_fastapi_resp = types.ModuleType("fastapi.responses")
    fake_fastapi_resp.JSONResponse = MagicMock
    sys.modules["fastapi.responses"] = fake_fastapi_resp

    fake_cors = types.ModuleType("fastapi.middleware.cors")
    fake_cors.CORSMiddleware = MagicMock
    sys.modules["fastapi.middleware.cors"] = fake_cors

if "starlette.exceptions" not in sys.modules:
    fake_starlette = types.ModuleType("starlette")
    fake_starlette_exc = types.ModuleType("starlette.exceptions")
    fake_starlette_exc.HTTPException = Exception
    sys.modules["starlette"] = fake_starlette
    sys.modules["starlette.exceptions"] = fake_starlette_exc

if "argon2" not in sys.modules:
    fake_argon = types.ModuleType("argon2")
    fake_argon.PasswordHasher = MagicMock
    fake_argon.Type = MagicMock()
    fake_argon_exceptions = types.ModuleType("argon2.exceptions")
    fake_argon_exceptions.VerifyMismatchError = type("VerifyMismatchError", (Exception,), {})
    fake_argon_exceptions.InvalidHashError = type("InvalidHashError", (Exception,), {})
    sys.modules["argon2"] = fake_argon
    sys.modules["argon2.exceptions"] = fake_argon_exceptions

from backend.app.api.v1.firewall import (
    FirewallRuleCreateRequest,
    FirewallToggleRequest,
    add_firewall_rule,
    delete_firewall_rule,
    get_firewall_status,
    toggle_firewall,
)
from backend.app.auth.models import UserRead
from backend.app.core.errors import BadRequestError, ConflictError, NotFoundError
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    FirewallRule,
    FirewallStatus,
)


class TestFirewallAPI(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_firewall.db"
        self.db = Database(db_path=self.db_path)
        self.db.init_database()

        self.mock_admin = UserRead(
            id="admin_user_id",
            username="admin",
            email="admin@example.com",
            role_id="role_admin",
            role_name="admin",
            is_active=True,
            created_at="2026-01-01T00:00:00Z",
        )
        self.mock_viewer = UserRead(
            id="viewer_user_id",
            username="viewer",
            email="viewer@example.com",
            role_id="role_viewer",
            role_name="viewer",
            is_active=True,
            created_at="2026-01-01T00:00:00Z",
        )

        self.mock_request = MagicMock()
        self.mock_request.client.host = "127.0.0.1"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_database_migration_0012_permissions(self):
        """Verify migration 12 creates firewall permissions and assigns them correctly."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Check permissions exist
            cursor.execute("SELECT name FROM permissions WHERE resource = 'firewall'")
            perms = {row["name"] for row in cursor.fetchall()}
            self.assertIn("firewall.read", perms)
            self.assertIn("firewall.manage", perms)

            # Check admin has both permissions
            cursor.execute("""
                SELECT p.name FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = 'role_admin' AND p.resource = 'firewall'
            """)
            admin_perms = {row["name"] for row in cursor.fetchall()}
            self.assertEqual(admin_perms, {"firewall.read", "firewall.manage"})

            # Check viewer has only firewall.read
            cursor.execute("""
                SELECT p.name FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = 'role_viewer' AND p.resource = 'firewall'
            """)
            viewer_perms = {row["name"] for row in cursor.fetchall()}
            self.assertEqual(viewer_perms, {"firewall.read"})

            # Check migration is recorded in schema_migrations
            cursor.execute("SELECT name FROM schema_migrations WHERE version = 12")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "0012_firewall_permissions")

    @patch("backend.app.api.v1.firewall.firewall_manager.get_status")
    async def test_get_status_endpoint(self, mock_get_status):
        mock_get_status.return_value = FirewallStatus(
            installed=True,
            active=True,
            default_incoming="deny",
            default_outgoing="allow",
            default_routed="disabled",
            rules=[
                FirewallRule(
                    rule_index=1,
                    port="22",
                    protocol="tcp",
                    action="ALLOW",
                    direction="IN",
                    source="Anywhere",
                    family="ipv4",
                    comment="SSH",
                    signature="22/tcp allow in anywhere ipv4",
                )
            ],
            management_ports=[22],
        )

        resp = await get_firewall_status()
        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertTrue(data["installed"])
        self.assertTrue(data["active"])
        self.assertEqual(len(data["rules"]), 1)
        self.assertEqual(data["management_ports"], [22])

    @patch("backend.app.api.v1.firewall.firewall_manager.add_rule")
    @patch("backend.app.api.v1.firewall.audit_service.log_event")
    async def test_add_rule_endpoint_success(self, mock_audit, mock_add_rule):
        mock_add_rule.return_value = {"success": True, "message": "Rule added"}

        req = FirewallRuleCreateRequest(
            port="443",
            protocol="tcp",
            action="allow",
            direction="in",
            source_ip="any",
            comment="HTTPS access",
        )

        resp = await add_firewall_rule(
            rule_req=req,
            request=self.mock_request,
            current_user=self.mock_admin,
        )

        self.assertTrue(resp["success"])
        mock_add_rule.assert_called_once()
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args[1]
        self.assertEqual(audit_call["action"], "firewall.rule_add")
        self.assertEqual(audit_call["user_id"], self.mock_admin.id)

    @patch("backend.app.api.v1.firewall.firewall_manager.delete_rule")
    @patch("backend.app.api.v1.firewall.audit_service.log_event")
    async def test_delete_rule_endpoint_success(self, mock_audit, mock_delete_rule):
        mock_delete_rule.return_value = {"success": True, "message": "Deleted"}

        resp = await delete_firewall_rule(
            rule_index=2,
            request=self.mock_request,
            expected_rule_signature="443/tcp allow in anywhere ipv4",
            current_user=self.mock_admin,
        )

        self.assertTrue(resp["success"])
        mock_delete_rule.assert_called_once_with(
            rule_index=2,
            expected_signature="443/tcp allow in anywhere ipv4",
        )
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args[1]
        self.assertEqual(audit_call["action"], "firewall.rule_delete")

    @patch("backend.app.api.v1.firewall.firewall_manager.toggle_firewall")
    @patch("backend.app.api.v1.firewall.audit_service.log_event")
    async def test_toggle_firewall_endpoint_success(self, mock_audit, mock_toggle):
        mock_toggle.return_value = {"success": True, "active": True}

        req = FirewallToggleRequest(enable=True)
        resp = await toggle_firewall(
            toggle_req=req,
            request=self.mock_request,
            current_user=self.mock_admin,
        )

        self.assertTrue(resp["success"])
        self.assertTrue(resp["active"])
        mock_toggle.assert_called_once_with(enable=True)
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args[1]
        self.assertEqual(audit_call["action"], "firewall.toggle")


if __name__ == "__main__":
    unittest.main()
