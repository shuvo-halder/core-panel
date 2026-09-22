import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.app.operations.firewall import (
    _detect_protected_ports,
    _parse_rule_target,
    _parse_ufw_output,
    handle_firewall_rule_add,
    handle_firewall_rule_delete,
    handle_firewall_status,
    handle_firewall_toggle,
    resolve_ufw_binary,
)

SAMPLE_VERBOSE_ACTIVE = """Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip
"""

SAMPLE_NUMBERED_RULES = """Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    Anywhere                  # SSH access
[ 2] 80/tcp                     ALLOW IN    Anywhere                  # HTTP
[ 3] 443                        ALLOW IN    Anywhere
[ 4] 8080/tcp                   DENY IN     192.168.1.0/24
[ 5] 3000:3010/tcp              ALLOW IN    Anywhere
[ 6] 22/tcp (v6)                ALLOW IN    Anywhere (v6)             # SSH access
[ 7] 80/tcp (v6)                ALLOW IN    Anywhere (v6)
"""

SAMPLE_VERBOSE_INACTIVE = """Status: inactive
"""


class TestFirewallOperations(unittest.IsolatedAsyncioTestCase):

    def test_parse_rule_target(self):
        port, proto, fam = _parse_rule_target("22/tcp")
        self.assertEqual(port, "22")
        self.assertEqual(proto, "tcp")
        self.assertEqual(fam, "ipv4")

        port, proto, fam = _parse_rule_target("22/tcp (v6)")
        self.assertEqual(port, "22")
        self.assertEqual(proto, "tcp")
        self.assertEqual(fam, "ipv6")

        port, proto, fam = _parse_rule_target("443")
        self.assertEqual(port, "443")
        self.assertEqual(proto, "any")
        self.assertEqual(fam, "ipv4")

        port, proto, fam = _parse_rule_target("3000:3010/udp")
        self.assertEqual(port, "3000:3010")
        self.assertEqual(proto, "udp")

    def test_parse_ufw_output_active(self):
        parsed = _parse_ufw_output(SAMPLE_VERBOSE_ACTIVE, SAMPLE_NUMBERED_RULES)
        self.assertTrue(parsed["installed"])
        self.assertTrue(parsed["active"])
        self.assertEqual(parsed["default_incoming"], "deny")
        self.assertEqual(parsed["default_outgoing"], "allow")
        self.assertEqual(parsed["default_routed"], "disabled")
        self.assertEqual(len(parsed["rules"]), 7)

        rule1 = parsed["rules"][0]
        self.assertEqual(rule1["rule_index"], 1)
        self.assertEqual(rule1["port"], "22")
        self.assertEqual(rule1["protocol"], "tcp")
        self.assertEqual(rule1["action"], "ALLOW")
        self.assertEqual(rule1["direction"], "IN")
        self.assertEqual(rule1["source"], "Anywhere")
        self.assertEqual(rule1["comment"], "SSH access")
        self.assertIn("signature", rule1)

        rule4 = parsed["rules"][3]
        self.assertEqual(rule4["action"], "DENY")
        self.assertEqual(rule4["source"], "192.168.1.0/24")

    def test_parse_ufw_output_inactive(self):
        parsed = _parse_ufw_output(SAMPLE_VERBOSE_INACTIVE, "")
        self.assertTrue(parsed["installed"])
        self.assertFalse(parsed["active"])
        self.assertEqual(len(parsed["rules"]), 0)

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value=None)
    async def test_handle_status_uninstalled(self, mock_resolve):
        res = await handle_firewall_status({})
        self.assertTrue(res["success"])
        self.assertFalse(res["installed"])
        self.assertFalse(res["active"])
        self.assertIn(22, res["management_ports"])

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("asyncio.create_subprocess_exec")
    async def test_handle_status_active(self, mock_exec, mock_resolve):
        proc_v = AsyncMock()
        proc_v.communicate.return_value = (SAMPLE_VERBOSE_ACTIVE.encode(), b"")
        proc_n = AsyncMock()
        proc_n.communicate.return_value = (SAMPLE_NUMBERED_RULES.encode(), b"")
        mock_exec.side_effect = [proc_v, proc_n]

        res = await handle_firewall_status({})
        self.assertTrue(res["success"])
        self.assertTrue(res["installed"])
        self.assertTrue(res["active"])
        self.assertEqual(len(res["rules"]), 7)

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    async def test_handle_rule_add_validation_errors(self, mock_resolve):
        # Invalid port
        res = await handle_firewall_rule_add({"port": "bad_port", "protocol": "tcp"})
        self.assertFalse(res["success"])
        self.assertIn("Invalid port", res["error"])

        # Invalid protocol
        res = await handle_firewall_rule_add({"port": "80", "protocol": "ftp"})
        self.assertFalse(res["success"])
        self.assertIn("Invalid protocol", res["error"])

        # Invalid action
        res = await handle_firewall_rule_add({"port": "80", "protocol": "tcp", "action": "forward"})
        self.assertFalse(res["success"])
        self.assertIn("Invalid action", res["error"])

        # Invalid direction
        res = await handle_firewall_rule_add({"port": "80", "protocol": "tcp", "action": "allow", "direction": "forward"})
        self.assertFalse(res["success"])
        self.assertIn("Invalid direction", res["error"])

        # Malicious comment
        res = await handle_firewall_rule_add({"port": "80", "protocol": "tcp", "comment": "test; rm -rf /"})
        self.assertFalse(res["success"])
        self.assertIn("Invalid comment", res["error"])

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    async def test_handle_rule_add_lockout_risk(self, mock_detect, mock_resolve):
        # Denying SSH port 22 incoming from any is rejected as lockout hazard
        res = await handle_firewall_rule_add({
            "port": "22",
            "protocol": "tcp",
            "action": "deny",
            "direction": "in",
            "source_ip": "any",
        })
        self.assertFalse(res["success"])
        self.assertTrue(res.get("lockout_risk"))
        self.assertIn("Lockout hazard", res["error"])

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("asyncio.create_subprocess_exec")
    async def test_handle_rule_add_success(self, mock_exec, mock_resolve):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"Rule added", b"")
        mock_exec.return_value = proc

        res = await handle_firewall_rule_add({
            "port": "8080",
            "protocol": "tcp",
            "action": "allow",
            "direction": "in",
            "source_ip": "10.0.0.0/8",
            "comment": "Internal API",
        })
        self.assertTrue(res["success"])
        # Verify fixed argv command structure
        mock_exec.assert_called_once_with(
            "/usr/sbin/ufw",
            "allow",
            "in",
            "proto",
            "tcp",
            "from",
            "10.0.0.0/8",
            "to",
            "any",
            "port",
            "8080",
            "comment",
            "Internal API",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall.handle_firewall_status")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    async def test_handle_rule_delete_signature_mismatch(self, mock_detect, mock_status, mock_resolve):
        mock_status.return_value = {
            "success": True,
            "default_incoming": "deny",
            "rules": [
                {
                    "rule_index": 1,
                    "port": "80",
                    "protocol": "tcp",
                    "action": "ALLOW",
                    "direction": "IN",
                    "source": "Anywhere",
                    "family": "ipv4",
                    "signature": "80/tcp ALLOW IN anywhere ipv4",
                }
            ],
        }

        # Request delete with different signature
        res = await handle_firewall_rule_delete({
            "rule_index": 1,
            "expected_rule_signature": "443/tcp ALLOW IN anywhere ipv4",
        })
        self.assertFalse(res["success"])
        self.assertTrue(res.get("conflict"))

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall.handle_firewall_status")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    async def test_handle_rule_delete_lockout_risk(self, mock_detect, mock_status, mock_resolve):
        # Only one SSH rule exists; deleting it is a lockout hazard
        mock_status.return_value = {
            "success": True,
            "default_incoming": "deny",
            "rules": [
                {
                    "rule_index": 1,
                    "port": "22",
                    "protocol": "tcp",
                    "action": "ALLOW",
                    "direction": "IN",
                    "source": "Anywhere",
                    "family": "ipv4",
                    "signature": "22/tcp allow in anywhere ipv4",
                }
            ],
        }

        res = await handle_firewall_rule_delete({
            "rule_index": 1,
            "expected_rule_signature": "22/tcp allow in anywhere ipv4",
        })
        self.assertFalse(res["success"])
        self.assertTrue(res.get("lockout_risk"))
        self.assertIn("only rule permitting incoming SSH", res["error"])

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall.handle_firewall_status")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    @patch("asyncio.create_subprocess_exec")
    async def test_handle_rule_delete_success(self, mock_exec, mock_detect, mock_status, mock_resolve):
        mock_status.return_value = {
            "success": True,
            "default_incoming": "deny",
            "rules": [
                {
                    "rule_index": 2,
                    "port": "80",
                    "protocol": "tcp",
                    "action": "ALLOW",
                    "direction": "IN",
                    "source": "Anywhere",
                    "family": "ipv4",
                    "signature": "80/tcp allow in anywhere ipv4",
                }
            ],
        }
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"Rule deleted", b"")
        mock_exec.return_value = proc

        res = await handle_firewall_rule_delete({
            "rule_index": 2,
            "expected_rule_signature": "80/tcp allow in anywhere ipv4",
        })
        self.assertTrue(res["success"])
        mock_exec.assert_called_once_with(
            "/usr/sbin/ufw",
            "--force",
            "delete",
            "2",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall.handle_firewall_status")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    async def test_handle_toggle_enable_lockout_risk(self, mock_detect, mock_status, mock_resolve):
        # Default incoming is deny and no rules exist -> cannot enable
        mock_status.return_value = {
            "success": True,
            "default_incoming": "deny",
            "rules": [],
        }

        res = await handle_firewall_toggle({"enable": True})
        self.assertFalse(res["success"])
        self.assertTrue(res.get("lockout_risk"))
        self.assertIn("No active rule permits incoming SSH", res["error"])

    @patch("agent.app.operations.firewall.resolve_ufw_binary", return_value="/usr/sbin/ufw")
    @patch("agent.app.operations.firewall.handle_firewall_status")
    @patch("agent.app.operations.firewall._detect_protected_ports", return_value={22})
    @patch("asyncio.create_subprocess_exec")
    async def test_handle_toggle_enable_success(self, mock_exec, mock_detect, mock_status, mock_resolve):
        mock_status.return_value = {
            "success": True,
            "default_incoming": "deny",
            "rules": [
                {
                    "rule_index": 1,
                    "port": "22",
                    "protocol": "tcp",
                    "action": "ALLOW",
                    "direction": "IN",
                }
            ],
        }
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"Firewall is active", b"")
        mock_exec.return_value = proc

        res = await handle_firewall_toggle({"enable": True})
        self.assertTrue(res["success"])
        self.assertTrue(res["active"])
        mock_exec.assert_called_once_with(
            "/usr/sbin/ufw",
            "--force",
            "enable",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )


if __name__ == "__main__":
    unittest.main()
