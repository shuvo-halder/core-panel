import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from agent.app.operations.logs import handle_logs_file_read, handle_logs_journal_read, STATIC_LOG_FILE_SOURCES


class TestLogOperations(unittest.TestCase):
    def test_handle_logs_journal_read_success(self):
        """Verify handle_logs_journal_read properly executes journalctl with bounds."""
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(
            b'{"__REALTIME_TIMESTAMP":"1700000000000000","_SOURCE_REALTIME_TIMESTAMP":"1700000000000000","PRIORITY":"6","_SYSTEMD_UNIT":"sshd.service","MESSAGE":"Accepted publickey for user"}\n',
            b"",
        ))
        mock_proc.returncode = 0

        with patch("agent.app.operations.logs._resolve_journalctl_bin", return_value="/bin/journalctl"), \
             patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            res = asyncio.run(handle_logs_journal_read({
                "limit": 100,
                "unit": "sshd.service",
                "priority": "6",
            }))

            self.assertTrue(res["available"])
            self.assertEqual(len(res["entries"]), 1)
            entry = res["entries"][0]
            self.assertEqual(entry["_SYSTEMD_UNIT"], "sshd.service")
            self.assertEqual(entry["PRIORITY"], "6")
            self.assertEqual(entry["MESSAGE"], "Accepted publickey for user")

    def test_handle_logs_journal_read_not_available(self):
        """When journalctl binary is missing, return available=False gracefully without error."""
        with patch("agent.app.operations.logs._resolve_journalctl_bin", return_value=None):
            res = asyncio.run(handle_logs_journal_read({}))
            self.assertFalse(res["available"])
            self.assertTrue("not found" in res["error"] or "not available" in res["error"])

    def test_handle_logs_file_read_allowlist_enforcement(self):
        """Verify handle_logs_file_read rejects non-allowlisted file sources."""
        for bad_source in ["/etc/shadow", "../../passwd", "RANDOM"]:
            with self.assertRaises(ValueError):
                asyncio.run(handle_logs_file_read({"source_id": bad_source}))

    def test_handle_logs_file_read_safe_reading(self):
        """Verify handle_logs_file_read successfully reads tail of an allowlisted path."""
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("line 1\nline 2: Jan 15 10:00:00 myhost systemd[1]: Started User Manager\n")
            tf_path = tf.name

        try:
            with patch.dict(STATIC_LOG_FILE_SOURCES, {"TEST_LOG": [tf_path]}):
                res = asyncio.run(handle_logs_file_read({"source_id": "TEST_LOG", "max_lines": 50}))
                self.assertTrue(res["available"])
                self.assertEqual(len(res["lines"]), 2)
                self.assertEqual(res["count"], 2)
                self.assertIn("Started User Manager", res["lines"][1])
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)


if __name__ == "__main__":
    unittest.main()
