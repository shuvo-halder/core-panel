import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agent.app.operations.nginx import (
    MANAGED_HEADER_PREFIX,
    _run_nginx_test,
    _validate_safe_name,
    handle_nginx_config_validate,
    handle_nginx_reload,
    handle_nginx_site_deploy,
    handle_nginx_site_disable,
    handle_nginx_site_enable,
    handle_nginx_site_remove,
    handle_nginx_status,
)


class TestNginxOperations(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.avail_dir = os.path.join(self.test_dir, "sites-available")
        self.enabled_dir = os.path.join(self.test_dir, "sites-enabled")
        os.makedirs(self.avail_dir, exist_ok=True)
        os.makedirs(self.enabled_dir, exist_ok=True)

        self.patch_avail = patch("agent.app.operations.nginx.SITES_AVAILABLE_DIR", self.avail_dir)
        self.patch_enabled = patch("agent.app.operations.nginx.SITES_ENABLED_DIR", self.enabled_dir)
        self.patch_avail.start()
        self.patch_enabled.start()

    def tearDown(self):
        self.patch_avail.stop()
        self.patch_enabled.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_name_validation(self):
        # Valid names
        self.assertEqual(_validate_safe_name("example.com"), "example.com")
        self.assertEqual(_validate_safe_name("my-app.local"), "my-app.local")
        self.assertEqual(_validate_safe_name("api_v1.org"), "api_v1.org")

        # Prohibited path traversal and bad characters
        with self.assertRaises(ValueError):
            _validate_safe_name("../etc/passwd")
        with self.assertRaises(ValueError):
            _validate_safe_name("foo/bar")
        with self.assertRaises(ValueError):
            _validate_safe_name("; rm -rf /")
        with self.assertRaises(ValueError):
            _validate_safe_name("-invalid-start")
        with self.assertRaises(ValueError):
            _validate_safe_name(".hidden")

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    async def test_handle_nginx_status(self, mock_test):
        mock_test.return_value = (True, "syntax is ok")
        status = await handle_nginx_status({})
        self.assertIn("installed", status)
        self.assertIn("sites_available_count", status)
        self.assertIn("sites_enabled_count", status)
        self.assertTrue(status["config_valid"])

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    @patch("agent.app.operations.nginx._reload_nginx", new_callable=AsyncMock)
    async def test_site_deploy_and_reload(self, mock_reload, mock_test):
        mock_test.return_value = (True, "syntax is ok")
        mock_reload.return_value = (True, "Reloaded")

        content = f"{MANAGED_HEADER_PREFIX}\nserver {{ listen 80; server_name test.com; }}"
        res = await handle_nginx_site_deploy({
            "site_name": "test.com",
            "config_content": content,
            "enabled": True,
        })

        self.assertTrue(res["success"])
        # Verify file in sites-available
        avail_file = os.path.join(self.avail_dir, "test.com")
        self.assertTrue(os.path.isfile(avail_file))
        # Verify symlink in sites-enabled
        enabled_link = os.path.join(self.enabled_dir, "test.com")
        self.assertTrue(os.path.islink(enabled_link))

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    @patch("agent.app.operations.nginx._reload_nginx", new_callable=AsyncMock)
    async def test_site_deploy_protects_unmanaged_file(self, mock_reload, mock_test):
        # Create an unmanaged file (missing managed header)
        unmanaged_file = os.path.join(self.avail_dir, "legacy.com")
        with open(unmanaged_file, "w") as f:
            f.write("server { listen 80; server_name legacy.com; }")

        with self.assertRaises(ValueError) as ctx:
            await handle_nginx_site_deploy({
                "site_name": "legacy.com",
                "config_content": f"{MANAGED_HEADER_PREFIX}\nserver {{ listen 80; }}",
                "enabled": True,
            })
        self.assertIn("unmanaged", str(ctx.exception).lower())

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    @patch("agent.app.operations.nginx._reload_nginx", new_callable=AsyncMock)
    async def test_site_deploy_rollback_on_failure(self, mock_reload, mock_test):
        # Initial managed site
        orig_content = f"{MANAGED_HEADER_PREFIX}\nserver {{ listen 80; server_name stable.com; }}"
        avail_file = os.path.join(self.avail_dir, "stable.com")
        with open(avail_file, "w") as f:
            f.write(orig_content)

        # Mock reload failure
        mock_test.return_value = (True, "ok")
        mock_reload.return_value = (False, "Service failed to reload")

        broken_content = f"{MANAGED_HEADER_PREFIX}\nserver {{ listen 8080; server_name stable.com; }}"
        res = await handle_nginx_site_deploy({
            "site_name": "stable.com",
            "config_content": broken_content,
            "enabled": True,
        })

        self.assertFalse(res["success"])
        self.assertTrue(res.get("rolled_back"))
        # Content should have reverted to original
        with open(avail_file, "r") as f:
            current = f.read()
        self.assertEqual(current, orig_content)

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    @patch("agent.app.operations.nginx._reload_nginx", new_callable=AsyncMock)
    async def test_site_enable_disable(self, mock_reload, mock_test):
        mock_test.return_value = (True, "syntax is ok")
        mock_reload.return_value = (True, "Reloaded")

        content = f"{MANAGED_HEADER_PREFIX}\nserver {{ listen 80; server_name toggle.com; }}"
        avail_file = os.path.join(self.avail_dir, "toggle.com")
        with open(avail_file, "w") as f:
            f.write(content)

        # Enable
        en_res = await handle_nginx_site_enable({"site_name": "toggle.com"})
        self.assertTrue(en_res["success"])
        self.assertTrue(os.path.islink(os.path.join(self.enabled_dir, "toggle.com")))

        # Disable
        dis_res = await handle_nginx_site_disable({"site_name": "toggle.com"})
        self.assertTrue(dis_res["success"])
        self.assertFalse(os.path.lexists(os.path.join(self.enabled_dir, "toggle.com")))

    async def test_unmanaged_site_enable_disable_rejected(self):
        """
        LOW-1 Verification:
        Verify that handle_nginx_site_enable and handle_nginx_site_disable
        reject unmanaged virtual hosts without creating or deleting symlinks.
        """
        unmanaged_file = os.path.join(self.avail_dir, "unmanaged-custom.org")
        with open(unmanaged_file, "w") as f:
            f.write("server { listen 80; server_name unmanaged-custom.org; }\n")

        # Test enable rejects unmanaged site
        with self.assertRaises(ValueError) as ctx:
            await handle_nginx_site_enable({"site_name": "unmanaged-custom.org"})
        self.assertIn("unmanaged", str(ctx.exception).lower())
        # Confirm no symlink was created
        self.assertFalse(os.path.exists(os.path.join(self.enabled_dir, "unmanaged-custom.org")))

        # Test disable rejects unmanaged site
        with self.assertRaises(ValueError) as ctx:
            await handle_nginx_site_disable({"site_name": "unmanaged-custom.org"})
        self.assertIn("unmanaged", str(ctx.exception).lower())

    @patch("agent.app.operations.nginx._run_nginx_test", new_callable=AsyncMock)
    @patch("agent.app.operations.nginx._reload_nginx", new_callable=AsyncMock)
    async def test_nginx_reload_operation(self, mock_reload, mock_test):
        mock_test.return_value = (True, "syntax ok")
        mock_reload.return_value = (True, "Reloaded successfully")

        res = await handle_nginx_reload({})
        self.assertTrue(res["success"])
        self.assertEqual(res["message"], "Reloaded successfully")

        # When test fails, reload should not run
        mock_test.return_value = (False, "Syntax error at line 5")
        mock_reload.reset_mock()
        fail_res = await handle_nginx_reload({})
        self.assertFalse(fail_res["success"])
        self.assertIn("Syntax error", fail_res["error"])
        mock_reload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
