#!/usr/bin/env python3
"""
Phase 9 - Scheduled Jobs / Cron Management Foundation
Standalone Verification and Validation Suite
Executes pure Python unit checks on cron validators, schedule translation,
and crontab parsing to ensure bulletproof security and functionality.
"""

import sys
import os
from types import ModuleType

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
    pyd_mod.Field = lambda *a, **k: a[0] if a else None
    pyd_mod.BaseModel = type("BaseModel", (), {})
    sys.modules["pydantic"] = pyd_mod

    pyds_mod = ModuleType("pydantic_settings")
    pyds_mod.BaseSettings = type("BaseSettings", (), {})
    pyds_mod.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = pyds_mod

from backend.app.core.validators import (
    validate_cron_username,
    validate_cron_schedule,
    validate_cron_command,
    validate_cron_comment,
)
from backend.app.core.errors import BadRequestError
from backend.app.linux.cron import translate_cron_schedule_to_human
from agent.app.operations.cron import (
    _parse_crontab_lines,
    _compute_job_hash,
    _compute_job_id,
)


def run_tests():
    passed = 0
    failed = 0

    def assert_eq(actual, expected, desc):
        nonlocal passed, failed
        if actual == expected:
            passed += 1
            print(f"  [PASS] {desc}")
        else:
            failed += 1
            print(f"  [FAIL] {desc}: expected {expected!r}, got {actual!r}")

    def assert_raises(func, *args, desc=""):
        nonlocal passed, failed
        try:
            func(*args)
            failed += 1
            print(f"  [FAIL] {desc}: expected exception but none raised")
        except BadRequestError:
            passed += 1
            print(f"  [PASS] {desc}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {desc}: expected BadRequestError, got {type(e).__name__}: {e}")

    print("=== TEST SUITE 1: CRON USERNAME VALIDATION ===")
    assert_eq(validate_cron_username("root"), "root", "Accepts standard local user 'root'")
    assert_raises(validate_cron_username, "", desc="Rejects empty username")
    assert_raises(validate_cron_username, "root; rm -rf /", desc="Rejects semicolon injection")
    assert_raises(validate_cron_username, "../root", desc="Rejects path traversal")
    assert_raises(validate_cron_username, "root\x00evil", desc="Rejects null byte")
    assert_raises(validate_cron_username, "-root", desc="Rejects leading dash")
    assert_raises(validate_cron_username, "nonexistent_os_user_xyz999", desc="Rejects non-existent OS account")

    print("\n=== TEST SUITE 2: CRON SCHEDULE VALIDATION ===")
    assert_eq(validate_cron_schedule("* * * * *"), "* * * * *", "Accepts '* * * * *'")
    assert_eq(validate_cron_schedule("*/5 * * * *"), "*/5 * * * *", "Accepts step expression '*/5 * * * *'")
    assert_eq(validate_cron_schedule("0 2 * * *"), "0 2 * * *", "Accepts '0 2 * * *'")
    assert_eq(validate_cron_schedule("30 3 * * 0"), "30 3 * * 0", "Accepts '30 3 * * 0'")
    assert_eq(validate_cron_schedule("0 0 1 1 *"), "0 0 1 1 *", "Accepts '0 0 1 1 *'")
    assert_eq(validate_cron_schedule("15,45 8-17 * * 1-5"), "15,45 8-17 * * 1-5", "Accepts range & list expression")

    # Specials
    for spec in ["@reboot", "@daily", "@hourly", "@weekly", "@monthly", "@yearly", "@annually"]:
        assert_eq(validate_cron_schedule(spec), spec, f"Accepts special '{spec}'")

    # Invalids
    assert_raises(validate_cron_schedule, "* * *", desc="Rejects 3 fields (too few)")
    assert_raises(validate_cron_schedule, "* * * * * *", desc="Rejects 6 fields (too many)")
    assert_raises(validate_cron_schedule, "60 * * * *", desc="Rejects minute 60")
    assert_raises(validate_cron_schedule, "* 24 * * *", desc="Rejects hour 24")
    assert_raises(validate_cron_schedule, "* * 32 * *", desc="Rejects day-of-month 32")
    assert_raises(validate_cron_schedule, "* * * 13 *", desc="Rejects month 13")
    assert_raises(validate_cron_schedule, "* * * * 8", desc="Rejects day-of-week 8")
    assert_raises(validate_cron_schedule, "@invalid_special", desc="Rejects invalid special keyword")
    assert_raises(validate_cron_schedule, "; rm -rf /", desc="Rejects shell command injection in schedule")

    print("\n=== TEST SUITE 3: CRON COMMAND VALIDATION ===")
    assert_eq(validate_cron_command("/usr/local/bin/backup.sh"), "/usr/local/bin/backup.sh", "Accepts script path")
    assert_eq(validate_cron_command("python3 /opt/app/run.py --flag"), "python3 /opt/app/run.py --flag", "Accepts complex command args")
    assert_raises(validate_cron_command, "", desc="Rejects empty command")
    assert_raises(validate_cron_command, "/bin/echo 1\n* * * * * /bin/evil", desc="Rejects newline injection in command")
    assert_raises(validate_cron_command, "/bin/echo 1\r* * * * * /bin/evil", desc="Rejects carriage-return injection in command")
    assert_raises(validate_cron_command, "/bin/echo\x00/bin/evil", desc="Rejects null byte in command")

    print("\n=== TEST SUITE 4: CRON COMMENT VALIDATION ===")
    assert_eq(validate_cron_comment("Daily backup"), "Daily backup", "Accepts standard single line comment")
    assert_eq(validate_cron_comment(None), None, "Accepts None comment")
    assert_raises(validate_cron_comment, "Note 1\n* * * * * /bin/evil", desc="Rejects newline injection in comment")

    print("\n=== TEST SUITE 5: SCHEDULE HUMAN TRANSLATION ===")
    assert_eq(translate_cron_schedule_to_human("@reboot"), "Run once at system startup", "Translates @reboot")
    assert_eq(translate_cron_schedule_to_human("@daily"), "Every day at midnight (00:00)", "Translates @daily")
    assert_eq(translate_cron_schedule_to_human("* * * * *"), "Every minute", "Translates '* * * * *'")
    assert_eq(translate_cron_schedule_to_human("*/5 * * * *"), "Every 5 minutes", "Translates '*/5 * * * *'")
    assert_eq(translate_cron_schedule_to_human("0 * * * *"), "Every hour at minute 0", "Translates '0 * * * *'")
    assert_eq(translate_cron_schedule_to_human("0 0 * * *"), "Daily at 00:00", "Translates '0 0 * * *'")
    assert_eq(translate_cron_schedule_to_human("30 3 * * 0"), "Every Sunday at 03:30", "Translates '30 3 * * 0'")

    print("\n=== TEST SUITE 6: CRONTAB CONTENT PARSING & IDENTIFICATION ===")
    sample_crontab = """# Sample crontab header
MAILTO=admin@example.com
SHELL=/bin/bash

# Run database backup every night at 2 AM
0 2 * * * /usr/local/bin/backup-db.sh > /dev/null 2>&1

# Disabled log rotation
# 0 4 * * * /usr/sbin/logrotate /etc/logrotate.conf

# Reboot task
@reboot /usr/local/bin/startup-notification.sh
"""
    jobs = _parse_crontab_lines(sample_crontab, owner="root", source="USER_CRONTAB")
    assert_eq(len(jobs), 3, "Parsed exactly 3 jobs (including 1 disabled)")
    assert_eq(jobs[0]["enabled"], True, "First job is enabled")
    assert_eq(jobs[0]["schedule"], "0 2 * * *", "First job schedule is '0 2 * * *'")
    assert_eq(jobs[0]["command"], "/usr/local/bin/backup-db.sh > /dev/null 2>&1", "First job command matched")
    assert_eq(jobs[0]["comment"], "Run database backup every night at 2 AM", "First job extracted preceding comment")

    assert_eq(jobs[1]["enabled"], False, "Second job correctly detected as disabled (# 0 4 * * *)")
    assert_eq(jobs[1]["schedule"], "0 4 * * *", "Second job schedule is '0 4 * * *'")

    assert_eq(jobs[2]["enabled"], True, "Third job is enabled")
    assert_eq(jobs[2]["schedule"], "@reboot", "Third job schedule is @reboot")

    # Hash fingerprints
    assert_eq(len(jobs[0]["original_hash"]), 16, "Job has 16-char SHA-256 fingerprint")
    assert_eq(jobs[0]["id"].startswith("cron_"), True, "Job ID has standard cron_ prefix")

    print(f"\n==========================================")
    print(f"VERIFICATION SUMMARY: {passed} PASSED, {failed} FAILED")
    print(f"==========================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
