#!/usr/bin/env python3
"""
Phase 10 - Log Management & Audit Foundation
Standalone Verification and Validation Suite
Executes pure Python unit checks on log validators, source allowlists,
agent operations, LinuxLogManager abstractions, and audit log query redactions.
"""

import sys
import os
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch, MagicMock, AsyncMock

# Add workspace to path
sys.path.insert(0, os.path.abspath("."))

# Lightweight test stubs for missing fastapi/pydantic in standalone environment
if "fastapi" not in sys.modules:
    fastapi_mod = ModuleType("fastapi")
    class StatusMock:
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500
    fastapi_mod.status = StatusMock()
    fastapi_mod.Request = type("Request", (), {})
    fastapi_mod.Response = type("Response", (), {})
    fastapi_mod.APIRouter = type("APIRouter", (), {})
    fastapi_mod.Depends = lambda x: x
    fastapi_mod.Query = lambda *a, **k: None
    fastapi_mod.FastAPI = type("FastAPI", (), {})
    sys.modules["fastapi"] = fastapi_mod

    fe_mod = ModuleType("fastapi.exceptions")
    fe_mod.RequestValidationError = type("RequestValidationError", (Exception,), {})
    sys.modules["fastapi.exceptions"] = fe_mod

    fr_mod = ModuleType("fastapi.responses")
    fr_mod.JSONResponse = type("JSONResponse", (), {})
    sys.modules["fastapi.responses"] = fr_mod

    fm_mod = ModuleType("fastapi.middleware.cors")
    fm_mod.CORSMiddleware = type("CORSMiddleware", (), {})
    sys.modules["fastapi.middleware.cors"] = fm_mod

    st_mod = ModuleType("starlette.exceptions")
    st_mod.HTTPException = type("HTTPException", (Exception,), {})
    sys.modules["starlette.exceptions"] = st_mod

    pyd_mod = ModuleType("pydantic")
    pyd_mod.Field = lambda *a, **k: k.get("default", a[0] if a else None)
    class BaseModelMock:
        def __init__(self, **kwargs):
            for k, v in self.__class__.__dict__.items():
                if not k.startswith("_") and not callable(v) and not isinstance(v, property):
                    setattr(self, k, v)
            for k, v in kwargs.items():
                setattr(self, k, v)
    pyd_mod.BaseModel = BaseModelMock
    sys.modules["pydantic"] = pyd_mod

    pyds_mod = ModuleType("pydantic_settings")
    pyds_mod.BaseSettings = BaseModelMock
    pyds_mod.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = pyds_mod


def run_checks():
    print("=" * 70)
    print("PHASE 10: LOG MANAGEMENT & AUDIT FOUNDATION - VERIFICATION SUITE")
    print("=" * 70)

    # 1. Test Input Validators
    from backend.app.core.errors import BadRequestError
    from backend.app.core.validators import (
        validate_log_severity,
        validate_log_source_id,
        validate_log_unit,
        validate_log_search,
    )

    print("\n[CHECK 1] Testing Log Input Validators...")

    # Severity
    assert validate_log_severity(None) is None
    assert validate_log_severity("err") == "ERR"
    assert validate_log_severity("warning") == "WARNING"
    assert validate_log_severity("INFO") == "INFO"
    for bad_sev in ["CRITICAL", "UNKNOWN", "err; rm -rf /", "123"]:
        try:
            validate_log_severity(bad_sev)
            assert False, f"Severity {bad_sev} should have been rejected"
        except BadRequestError:
            pass
    print("  ✓ Severity validation passed (whitelist + uppercase normalization)")

    # Source ID
    assert validate_log_source_id("journal") == "JOURNAL"
    assert validate_log_source_id("syslog") == "SYSLOG"
    assert validate_log_source_id("AUTH") == "AUTH"
    for bad_src in ["/etc/shadow", "../../log", "malicious_src", ""]:
        try:
            validate_log_source_id(bad_src)
            assert False, f"Source {bad_src} should have been rejected"
        except BadRequestError:
            pass
    print("  ✓ Source ID validation passed (allowlist rejection)")

    # Systemd Unit Name
    assert validate_log_unit(None) is None
    assert validate_log_unit("nginx.service") == "nginx.service"
    assert validate_log_unit("cron.service") == "cron.service"
    for bad_unit in ["sshd; rm -rf /", "-u nginx", "daemon&whoami", "foo|bar", "invalid_no_ext"]:
        try:
            validate_log_unit(bad_unit)
            assert False, f"Unit {bad_unit} should have been rejected"
        except BadRequestError:
            pass
    print("  ✓ Unit name validation passed (shell-escape and injection-proof)")

    # Search Query
    assert validate_log_search(None) is None
    assert validate_log_search("  failed auth  ") == "failed auth"
    try:
        validate_log_search("hello\nworld\r\n")
        assert False, "Search query with newline should have been rejected"
    except BadRequestError:
        pass
    print("  ✓ Search query sanitization and newline rejection passed")

    # 2. Test Agent Operations
    print("\n[CHECK 2] Testing CoreAgent Log Operations...")
    import asyncio
    from agent.app.operations.logs import handle_logs_file_read, handle_logs_journal_read, STATIC_LOG_FILE_SOURCES

    # Reject non-allowlisted file source reads
    for bad_source in ["/etc/shadow", "../../passwd", "RANDOM"]:
        try:
            asyncio.run(handle_logs_file_read({"source_id": bad_source}))
            assert False, f"Expected ValueError for bad source {bad_source}"
        except ValueError as err:
            assert "Prohibited or unknown log source ID" in str(err)
    print("  ✓ Agent file read strictly rejects non-allowlisted / path-traversal sources")

    # Safe tail read on allowed file
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("line 1\nline 2: systemd[1]: Started User Manager for UID 1000\n")
        tf_path = tf.name

    try:
        with patch.dict(STATIC_LOG_FILE_SOURCES, {"TEST_KEY": [tf_path]}):
            res_read = asyncio.run(handle_logs_file_read({"source_id": "TEST_KEY", "max_lines": 50}))
            assert res_read["available"] is True
            assert len(res_read["lines"]) == 2
            assert "Started User Manager" in res_read["lines"][1]
        print("  ✓ Agent file read correctly reads bounded line tail")
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)

    # Journalctl handling
    with patch("agent.app.operations.logs._resolve_journalctl_bin", return_value="/bin/journalctl"), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_sub:
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(
            b'{"__REALTIME_TIMESTAMP":"1700000000000000","PRIORITY":"3","_SYSTEMD_UNIT":"cron.service","MESSAGE":"Error executing task"}\n', b""
        ))
        mock_proc.returncode = 0
        mock_sub.return_value = mock_proc

        res_j = asyncio.run(handle_logs_journal_read({"limit": 50, "unit": "cron.service", "priority": "3"}))
        assert res_j["available"] is True
        assert len(res_j["entries"]) == 1
        assert res_j["entries"][0]["PRIORITY"] == "3"
        assert res_j["entries"][0]["_SYSTEMD_UNIT"] == "cron.service"
        print("  ✓ Agent journal read executes bounded journalctl with structured output")

    # 3. Test Database Migration & Permissions
    print("\n[CHECK 3] Testing Database Migrations (Phase 10)...")
    from backend.app.db.sqlite import Database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test.db"
        test_db = Database(db_path=db_file)
        test_db.init_database()

        with test_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check permissions in db
            cursor.execute("SELECT name FROM permissions WHERE name IN ('logs.read', 'audit.read')")
            perm_names = [row["name"] for row in cursor.fetchall()]
            assert "logs.read" in perm_names, "logs.read missing from permissions table"
            assert "audit.read" in perm_names, "audit.read missing from permissions table"

            # Check role assignments
            cursor.execute(
                "SELECT permission_id FROM role_permissions WHERE role_id = 'role_admin' AND permission_id IN ('perm_logs_read', 'perm_audit_read')"
            )
            assert len(cursor.fetchall()) == 2, "admin role missing logs.read / audit.read"

            cursor.execute(
                "SELECT permission_id FROM role_permissions WHERE role_id = 'role_viewer' AND permission_id IN ('perm_logs_read', 'perm_audit_read')"
            )
            assert len(cursor.fetchall()) == 2, "viewer role missing logs.read / audit.read"
        print("  ✓ Database migration 0010_log_permissions verified: logs.read & audit.read present in RBAC")

    # 4. Test Audit Service Query & Redaction
    print("\n[CHECK 4] Testing Audit Log Redaction & Querying...")
    from backend.app.audit.service import AuditService, redact_sensitive_text
    import backend.app.audit.service as audit_module

    # Redaction checks
    raw_details = 'password="MySecretPassword123!" and token: "eyJhbGciOi..." & api_key=abc123secret'
    redacted = redact_sensitive_text(raw_details)
    assert "MySecretPassword123!" not in redacted
    assert "[REDACTED]" in redacted
    print("  ✓ Sensitive credential redaction utility verified")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "audit_test.db"
        audit_db = Database(db_path=db_file)
        audit_db.init_database()

        with patch.object(audit_module, "db", audit_db):
            test_audit = AuditService()

            # Log an event
            test_audit.log_event(
                username="admin",
                action="cron.create",
                resource_type="cron_job",
                resource_id="cron_123",
                status="SUCCESS",
                user_id=None,
                details='Created job with secret_key="123456"',
                ip_address="127.0.0.1",
            )

            events, total = test_audit.query_events(action="cron.create")
            assert total == 1
            assert len(events) == 1
            assert events[0]["username"] == "admin"
            assert events[0]["action"] == "cron.create"
            assert "123456" not in events[0]["details"]
            assert "[REDACTED]" in events[0]["details"]
            print("  ✓ Audit query with filtering and automatic payload redaction verified")

    # 5. Test LinuxLogManager Abstraction
    print("\n[CHECK 5] Testing LinuxLogManager Source Discovery & Fallback...")
    from backend.app.linux.logs import LinuxLogManager
    mgr = LinuxLogManager()

    import asyncio
    sources = asyncio.run(mgr.get_sources())
    assert len(sources) >= 5
    source_ids = [s.id for s in sources]
    assert "JOURNAL" in source_ids
    assert "SYSLOG" in source_ids
    assert "AUTH" in source_ids
    print(f"  ✓ Discovered {len(sources)} allowlisted sources: {source_ids}")

    print("\n" + "=" * 70)
    print("ALL PHASE 10 VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_checks()
