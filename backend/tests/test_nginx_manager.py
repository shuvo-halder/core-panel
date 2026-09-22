import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

# Mocks for environments without fastapi/pydantic installed
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
    sys.modules["pydantic"] = fake_pydantic

if "pydantic_settings" not in sys.modules:
    fake_ps = types.ModuleType("pydantic_settings")
    class FakeSettings:
        LOG_LEVEL = "INFO"
    fake_ps.BaseSettings = FakeSettings
    fake_ps.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = fake_ps

if "fastapi" not in sys.modules:
    class FakeStatus:
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.status = FakeStatus
    fake_fastapi.Request = object
    fake_fastapi.APIRouter = lambda *args, **kwargs: None
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

from backend.app.core.errors import AppError, BadRequestError, NotFoundError
from backend.app.ipc.client import AgentUnavailableError
from backend.app.linux.contracts import SiteConfig, SiteProxyConfig, SiteSSLConfig
from backend.app.linux.nginx import (
    MANAGED_HEADER_PREFIX,
    LinuxNginxManager,
)


class TestLinuxNginxManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.avail_dir = os.path.join(self.test_dir, "sites-available")
        self.enabled_dir = os.path.join(self.test_dir, "sites-enabled")
        os.makedirs(self.avail_dir, exist_ok=True)
        os.makedirs(self.enabled_dir, exist_ok=True)

        self.patch_avail = patch("backend.app.linux.nginx.SITES_AVAILABLE_DIR", self.avail_dir)
        self.patch_enabled = patch("backend.app.linux.nginx.SITES_ENABLED_DIR", self.enabled_dir)
        self.patch_avail.start()
        self.patch_enabled.start()

        self.manager = LinuxNginxManager(socket_path="/tmp/nonexistent_socket.sock")

    def tearDown(self):
        self.patch_avail.stop()
        self.patch_enabled.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_config_static_site(self):
        site = SiteConfig(
            name="static.example.com",
            server_names=["static.example.com", "www.static.example.com"],
            listen=80,
            listen_ipv6=True,
            root="/var/www/static.example.com/html",
            proxy=SiteProxyConfig(enabled=False),
            ssl=SiteSSLConfig(enabled=False),
            access_log=True,
            error_log=True,
            index=["index.html", "index.htm"],
            client_max_body_size="10m",
            enabled=True,
            managed=True,
        )

        cfg = self.manager._generate_nginx_config(site)
        self.assertTrue(cfg.startswith(MANAGED_HEADER_PREFIX))
        self.assertIn("listen 80;", cfg)
        self.assertIn("listen [::]:80;", cfg)
        self.assertIn("server_name static.example.com www.static.example.com;", cfg)
        self.assertIn("root /var/www/static.example.com/html;", cfg)
        self.assertIn("try_files $uri $uri/ =404;", cfg)
        self.assertIn("access_log /var/log/nginx/static.example.com.access.log;", cfg)

    def test_generate_config_reverse_proxy(self):
        site = SiteConfig(
            name="api.example.com",
            server_names=["api.example.com"],
            listen=8080,
            listen_ipv6=False,
            root=None,
            proxy=SiteProxyConfig(enabled=True, target="http://127.0.0.1:3000", preserve_host=True),
            ssl=SiteSSLConfig(enabled=False),
            access_log=False,
            error_log=True,
            index=["index.html"],
            client_max_body_size="50m",
            enabled=True,
            managed=True,
        )

        cfg = self.manager._generate_nginx_config(site)
        self.assertIn("listen 8080;", cfg)
        self.assertIn("proxy_pass http://127.0.0.1:3000;", cfg)
        self.assertIn("proxy_set_header Host $host;", cfg)
        self.assertIn("access_log off;", cfg)
        self.assertIn("client_max_body_size 50m;", cfg)

    async def test_list_and_get_sites(self):
        # Create a managed site
        m_path = os.path.join(self.avail_dir, "app.com")
        with open(m_path, "w") as f:
            f.write(f"{MANAGED_HEADER_PREFIX}\nserver {{\n    listen 80;\n    server_name app.com;\n    root /var/www/html;\n}}\n")

        # Create an unmanaged site
        u_path = os.path.join(self.avail_dir, "default")
        with open(u_path, "w") as f:
            f.write("server {\n    listen 80 default_server;\n    server_name _;\n    root /var/www/html;\n}\n")

        # Enable app.com
        os.symlink(m_path, os.path.join(self.enabled_dir, "app.com"))

        sites = await self.manager.list_sites()
        self.assertEqual(len(sites), 2)

        app_site = await self.manager.get_site("app.com")
        self.assertIsNotNone(app_site)
        self.assertTrue(app_site.managed)
        self.assertTrue(app_site.enabled)
        self.assertEqual(app_site.listen, 80)
        self.assertEqual(app_site.server_names, ["app.com"])

        default_site = await self.manager.get_site("default")
        self.assertIsNotNone(default_site)
        self.assertFalse(default_site.managed)
        self.assertFalse(default_site.enabled)

    async def test_update_unmanaged_site_rejected(self):
        # Create an unmanaged site
        u_path = os.path.join(self.avail_dir, "legacy.net")
        with open(u_path, "w") as f:
            f.write("server {\n    listen 80;\n    server_name legacy.net;\n}\n")

        candidate = SiteConfig(
            name="legacy.net",
            server_names=["legacy.net"],
            listen=80,
            listen_ipv6=False,
            root="/var/www/html",
            proxy=SiteProxyConfig(enabled=False),
            ssl=SiteSSLConfig(enabled=False),
            access_log=True,
            error_log=True,
            index=["index.html"],
            client_max_body_size="10m",
            enabled=True,
            managed=True,
        )

        with self.assertRaises(BadRequestError) as ctx:
            await self.manager.update_site("legacy.net", candidate)
        self.assertIn("unmanaged", str(ctx.exception).lower())

    async def test_delete_unmanaged_site_rejected(self):
        # Create unmanaged site
        u_path = os.path.join(self.avail_dir, "root.org")
        with open(u_path, "w") as f:
            f.write("server { listen 80; }")

        with self.assertRaises(BadRequestError) as ctx:
            await self.manager.delete_site("root.org")
        self.assertIn("unmanaged", str(ctx.exception).lower())

    async def test_delete_nonexistent_site_raises_404(self):
        with self.assertRaises(NotFoundError):
            await self.manager.delete_site("nonexistent.com")

    @patch.object(LinuxNginxManager, "_call_agent_operation", new_callable=AsyncMock)
    async def test_create_site_success(self, mock_call):
        mock_call.return_value = {"success": True}

        site = SiteConfig(
            name="fresh.com",
            server_names=["fresh.com"],
            listen=80,
            listen_ipv6=False,
            root="/var/www/html",
            proxy=SiteProxyConfig(enabled=False),
            ssl=SiteSSLConfig(enabled=False),
            access_log=True,
            error_log=True,
            index=["index.html"],
            client_max_body_size="10m",
            enabled=True,
            managed=True,
        )

        created = await self.manager.create_site(site)
        self.assertEqual(created.name, "fresh.com")
        mock_call.assert_called_once()
        self.assertEqual(mock_call.call_args[0][0], "nginx.site_deploy")

    async def test_ipc_unavailable_fails_closed(self):
        """
        BLOCKER-1 Verification:
        When CoreAgent Unix socket is unreachable, any mutation or status request
        MUST fail closed with AppError(code='IPC_UNAVAILABLE', status_code=503).
        No local handler can run, no file written, no symlink created.
        """
        # Ensure socket definitely does not exist
        self.manager.socket_path = "/tmp/nonexistent_corepanel_agent.sock"
        self.manager.ipc_client.socket_path = "/tmp/nonexistent_corepanel_agent.sock"

        # 1. get_status fails closed
        with self.assertRaises(AppError) as ctx:
            await self.manager.get_status()
        self.assertEqual(ctx.exception.code, "IPC_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 503)

        # 2. reload fails closed
        with self.assertRaises(AppError) as ctx:
            await self.manager.reload()
        self.assertEqual(ctx.exception.code, "IPC_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 503)

        # 3. create_site fails closed without modifying filesystem
        site = SiteConfig(
            name="failclosed.com",
            server_names=["failclosed.com"],
            listen=80,
            listen_ipv6=False,
            root="/var/www/html",
            proxy=SiteProxyConfig(enabled=False),
            ssl=SiteSSLConfig(enabled=False),
            access_log=True,
            error_log=True,
            index=["index.html"],
            client_max_body_size="10m",
            enabled=True,
            managed=True,
        )
        with self.assertRaises(AppError) as ctx:
            await self.manager.create_site(site)
        self.assertEqual(ctx.exception.code, "IPC_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 503)

        # Confirm no file was created on filesystem
        self.assertFalse(os.path.exists(os.path.join(self.avail_dir, "failclosed.com")))
        self.assertFalse(os.path.exists(os.path.join(self.enabled_dir, "failclosed.com")))

    async def test_ipc_timeout_fails_closed(self):
        """
        Verify that IPC timeout or connection error raises AppError(IPC_UNAVAILABLE).
        """
        with patch.object(self.manager.ipc_client, "execute", side_effect=AgentUnavailableError("Timed out")):
            with self.assertRaises(AppError) as ctx:
                await self.manager.get_status()
            self.assertEqual(ctx.exception.code, "IPC_UNAVAILABLE")
            self.assertEqual(ctx.exception.status_code, 503)

    async def test_unmanaged_site_enable_and_disable_rejected(self):
        """
        LOW-1 Verification:
        FastAPI rejects enable and disable calls for unmanaged configurations
        before touching IPC or modifying symlinks.
        """
        unmanaged_path = os.path.join(self.avail_dir, "legacy-custom.org")
        with open(unmanaged_path, "w") as f:
            f.write("server {\n    listen 80;\n    server_name legacy-custom.org;\n}\n")

        with self.assertRaises(BadRequestError) as ctx:
            await self.manager.enable_site("legacy-custom.org")
        self.assertEqual(ctx.exception.code, "SITE_UNMANAGED")

        # Symlink must NOT be created
        self.assertFalse(os.path.exists(os.path.join(self.enabled_dir, "legacy-custom.org")))

        with self.assertRaises(BadRequestError) as ctx:
            await self.manager.disable_site("legacy-custom.org")
        self.assertEqual(ctx.exception.code, "SITE_UNMANAGED")


if __name__ == "__main__":
    unittest.main()
