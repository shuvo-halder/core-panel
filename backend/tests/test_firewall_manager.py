import asyncio
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Provide minimal mocks for fastapi/pydantic/starlette if running in container without them
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
    fake_pydantic.Field = lambda *args, **kwargs: None
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
    fake_fastapi.Depends = lambda *args, **kwargs: None
    fake_fastapi.Query = lambda *args, **kwargs: None
    sys.modules["fastapi"] = fake_fastapi

    fake_fastapi_exc = types.ModuleType("fastapi.exceptions")
    fake_fastapi_exc.RequestValidationError = Exception
    sys.modules["fastapi.exceptions"] = fake_fastapi_exc

    fake_fastapi_resp = types.ModuleType("fastapi.responses")
    fake_fastapi_resp.JSONResponse = object
    sys.modules["fastapi.responses"] = fake_fastapi_resp

if "starlette.exceptions" not in sys.modules:
    fake_starlette = types.ModuleType("starlette")
    fake_starlette_exc = types.ModuleType("starlette.exceptions")
    fake_starlette_exc.HTTPException = Exception
    sys.modules["starlette"] = fake_starlette
    sys.modules["starlette.exceptions"] = fake_starlette_exc

from backend.app.core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from backend.app.ipc.client import AgentUnavailableError
from backend.app.linux.contracts import (
    FirewallRule,
    FirewallRuleCreate,
    FirewallStatus,
)
from backend.app.linux.firewall import (
    LinuxFirewallManager,
    UFWFirewallProvider,
)


class TestFirewallManager(unittest.IsolatedAsyncioTestCase):

    async def test_fail_closed_ipc_when_agent_socket_missing(self):
        """
        MANDATORY SECURITY INVARIANT:
        If CoreAgent socket is unreachable, provider MUST fail closed with
        AppError(code='IPC_UNAVAILABLE', status_code=503).
        No local fallback allowed.
        """
        # Point to a non-existent socket
        provider = UFWFirewallProvider(socket_path="/tmp/non_existent_corepanel_agent.sock")
        manager = LinuxFirewallManager(provider=provider)

        with self.assertRaises(AppError) as ctx:
            await manager.get_status()

        self.assertEqual(ctx.exception.code, "IPC_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 503)

    async def test_get_status_success(self):
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
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

        manager = LinuxFirewallManager(provider=mock_provider)
        status = await manager.get_status()
        self.assertTrue(status.active)
        self.assertEqual(len(status.rules), 1)

    async def test_add_rule_lockout_risk_rejected_in_fastapi(self):
        """FastAPI layer must independently reject adding a DENY rule targeting SSH."""
        manager = LinuxFirewallManager(provider=AsyncMock())
        rule = FirewallRuleCreate(
            port="22",
            protocol="tcp",
            action="deny",
            direction="in",
            source_ip="any",
        )

        with self.assertRaises(BadRequestError) as ctx:
            await manager.add_rule(rule)

        self.assertEqual(ctx.exception.code, "FIREWALL_LOCKOUT_RISK")
        self.assertIn("Lockout hazard", ctx.exception.message)

    async def test_add_rule_success(self):
        mock_provider = AsyncMock()
        mock_provider.add_rule.return_value = {"success": True, "message": "Rule added"}
        manager = LinuxFirewallManager(provider=mock_provider)

        rule = FirewallRuleCreate(
            port="80",
            protocol="tcp",
            action="allow",
            direction="in",
            source_ip="any",
            comment="HTTP traffic",
        )
        res = await manager.add_rule(rule)
        self.assertTrue(res["success"])
        mock_provider.add_rule.assert_called_once()

    async def test_delete_rule_not_found(self):
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
            installed=True,
            active=True,
            default_incoming="deny",
            default_outgoing="allow",
            default_routed="disabled",
            rules=[],
        )
        manager = LinuxFirewallManager(provider=mock_provider)

        with self.assertRaises(NotFoundError) as ctx:
            await manager.delete_rule(rule_index=99)

        self.assertEqual(ctx.exception.code, "FIREWALL_RULE_NOT_FOUND")

    async def test_delete_rule_signature_mismatch_conflict(self):
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
            installed=True,
            active=True,
            default_incoming="deny",
            default_outgoing="allow",
            default_routed="disabled",
            rules=[
                FirewallRule(
                    rule_index=1,
                    port="80",
                    protocol="tcp",
                    action="ALLOW",
                    direction="IN",
                    source="Anywhere",
                    family="ipv4",
                    signature="80/tcp allow in anywhere ipv4",
                )
            ],
        )
        manager = LinuxFirewallManager(provider=mock_provider)

        with self.assertRaises(ConflictError) as ctx:
            await manager.delete_rule(rule_index=1, expected_signature="443/tcp allow in anywhere ipv4")

        self.assertEqual(ctx.exception.code, "FIREWALL_RULE_CONFLICT")

    async def test_delete_rule_lockout_risk_rejected_in_fastapi(self):
        """FastAPI layer must reject deleting the only SSH allow rule."""
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
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
                    signature="22/tcp allow in anywhere ipv4",
                )
            ],
        )
        manager = LinuxFirewallManager(provider=mock_provider)

        with self.assertRaises(BadRequestError) as ctx:
            await manager.delete_rule(rule_index=1, expected_signature="22/tcp allow in anywhere ipv4")

        self.assertEqual(ctx.exception.code, "FIREWALL_LOCKOUT_RISK")
        self.assertIn("only active rule permitting incoming SSH", ctx.exception.message)

    async def test_delete_rule_success(self):
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
            installed=True,
            active=True,
            default_incoming="deny",
            default_outgoing="allow",
            default_routed="disabled",
            rules=[
                FirewallRule(
                    rule_index=2,
                    port="80",
                    protocol="tcp",
                    action="ALLOW",
                    direction="IN",
                    source="Anywhere",
                    family="ipv4",
                    signature="80/tcp allow in anywhere ipv4",
                )
            ],
        )
        mock_provider.delete_rule.return_value = {"success": True, "message": "Deleted"}
        manager = LinuxFirewallManager(provider=mock_provider)

        res = await manager.delete_rule(rule_index=2, expected_signature="80/tcp allow in anywhere ipv4")
        self.assertTrue(res["success"])

    async def test_toggle_firewall_enable_lockout_risk(self):
        """FastAPI layer must reject enabling firewall if no rule permits SSH."""
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
            installed=True,
            active=False,
            default_incoming="deny",
            default_outgoing="allow",
            default_routed="disabled",
            rules=[
                FirewallRule(
                    rule_index=1,
                    port="80",
                    protocol="tcp",
                    action="ALLOW",
                    direction="IN",
                    source="Anywhere",
                    family="ipv4",
                )
            ],
        )
        manager = LinuxFirewallManager(provider=mock_provider)

        with self.assertRaises(BadRequestError) as ctx:
            await manager.toggle_firewall(enable=True)

        self.assertEqual(ctx.exception.code, "FIREWALL_LOCKOUT_RISK")
        self.assertIn("No active rule permits incoming SSH", ctx.exception.message)

    async def test_toggle_firewall_enable_success(self):
        mock_provider = AsyncMock()
        mock_provider.get_status.return_value = FirewallStatus(
            installed=True,
            active=False,
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
                )
            ],
        )
        mock_provider.toggle.return_value = {"success": True, "active": True}
        manager = LinuxFirewallManager(provider=mock_provider)

        res = await manager.toggle_firewall(enable=True)
        self.assertTrue(res["success"])


if __name__ == "__main__":
    unittest.main()
