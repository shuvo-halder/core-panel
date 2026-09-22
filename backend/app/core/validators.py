import os
import re
from typing import Any, Optional, Pattern, Set

from backend.app.core.errors import BadRequestError, ForbiddenError

# Strict regex matching valid systemd service unit names (e.g. nginx.service, user@1000.service)
SERVICE_UNIT_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9_\@\.\-]+\.service$")
PROHIBITED_CHARS_PATTERN: Pattern[str] = re.compile(r"[\s/\\;\|\&\>\<\$\`\'\"\x00\n\r\t]")

# Maximum valid Linux PID (typically 2^22 = 4194304 on 64-bit kernels)
MAX_VALID_PID = 4194304


def validate_pid(pid: Any) -> int:
    """
    Strictly validates a process ID.
    Rejects non-integers, floats, negative numbers, zero, and out-of-range values.
    """
    if isinstance(pid, bool):
        raise BadRequestError("Process ID must be an integer", code="INVALID_PID")

    if isinstance(pid, int):
        parsed_pid = pid
    elif isinstance(pid, str):
        trimmed = pid.strip()
        if not trimmed.isdigit():
            raise BadRequestError(
                f"Process ID must be a positive integer, got: '{pid}'",
                code="INVALID_PID",
            )
        try:
            parsed_pid = int(trimmed)
        except ValueError:
            raise BadRequestError(
                f"Process ID is not a valid integer: '{pid}'", code="INVALID_PID"
            )
    else:
        raise BadRequestError(
            "Process ID must be an integer or integer string", code="INVALID_PID"
        )

    if parsed_pid < 1 or parsed_pid > MAX_VALID_PID:
        raise BadRequestError(
            f"Process ID {parsed_pid} out of valid range (1 to {MAX_VALID_PID})",
            code="INVALID_PID",
        )

    return parsed_pid


def validate_not_protected_pid(pid: int, additional_protected_pids: Optional[Set[int]] = None) -> int:
    """
    Verifies that the target PID is not a protected system or control-plane process.
    PID 1 is unconditionally forbidden.
    FastAPI's own process is unconditionally forbidden.
    """
    valid_pid = validate_pid(pid)

    # PID 1 is always protected
    if valid_pid == 1:
        raise ForbiddenError(
            "PID 1 (init/systemd) is protected and cannot be targeted for termination",
            code="PROTECTED_PROCESS",
        )

    # FastAPI self-protection
    try:
        current_pid = os.getpid()
        if valid_pid == current_pid:
            raise ForbiddenError(
                f"PID {valid_pid} is the active FastAPI control plane process and cannot be targeted",
                code="PROTECTED_PROCESS",
            )
    except Exception:
        pass

    if additional_protected_pids and valid_pid in additional_protected_pids:
        raise ForbiddenError(
            f"PID {valid_pid} is a protected system or control-plane process",
            code="PROTECTED_PROCESS",
        )

    return valid_pid


def validate_service_unit_name(unit: str) -> str:
    """
    Strictly validates a systemd service unit name.
    Rejects path traversal, whitespace, shell metacharacters, and non-.service units.
    Raises BadRequestError on validation failure.
    """
    if not isinstance(unit, str):
        raise BadRequestError("Service unit must be a string", code="INVALID_SERVICE_UNIT")

    if PROHIBITED_CHARS_PATTERN.search(unit) or unit != unit.strip():
        raise BadRequestError(
            "Service unit name contains prohibited characters, control characters, or whitespace",
            code="INVALID_SERVICE_UNIT",
        )

    clean_unit = unit.strip()

    if len(clean_unit) < 9 or len(clean_unit) > 256:
        raise BadRequestError(
            "Service unit name length must be between 9 and 256 characters",
            code="INVALID_SERVICE_UNIT",
        )

    if not clean_unit.endswith(".service"):
        raise BadRequestError(
            "Only systemd .service units are supported (e.g., 'nginx.service')",
            code="INVALID_SERVICE_UNIT",
        )

    if ".." in clean_unit or "/" in clean_unit or "\\" in clean_unit:
        raise BadRequestError(
            "Service unit name cannot contain path separators or directory traversal sequences",
            code="INVALID_SERVICE_UNIT",
        )

    if not SERVICE_UNIT_PATTERN.match(clean_unit):
        raise BadRequestError(
            f"Invalid systemd service unit name: '{clean_unit}'",
            code="INVALID_SERVICE_UNIT",
        )

    return clean_unit


# Linux network interface name pattern (IFNAMSIZ typically 16 chars including null terminator)
INTERFACE_NAME_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9_\@\.\:\-]+$")


def validate_interface_name(name: Any) -> str:
    """
    Strictly validates a Linux network interface name.
    Rejects path traversal, whitespace, slashes, null bytes, shell metacharacters, and oversized strings.
    Raises BadRequestError on validation failure.
    """
    if not isinstance(name, str):
        raise BadRequestError("Interface name must be a string", code="INVALID_INTERFACE_NAME")

    clean_name = name.strip()
    if not clean_name:
        raise BadRequestError("Interface name cannot be empty", code="INVALID_INTERFACE_NAME")

    if len(clean_name) > 15:
        raise BadRequestError(
            f"Interface name exceeds Linux IFNAMSIZ limit of 15 characters: '{clean_name}'",
            code="INVALID_INTERFACE_NAME",
        )

    if PROHIBITED_CHARS_PATTERN.search(clean_name) or ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        raise BadRequestError(
            "Interface name contains prohibited characters, slashes, or path traversal",
            code="INVALID_INTERFACE_NAME",
        )

    if not INTERFACE_NAME_PATTERN.match(clean_name):
        raise BadRequestError(
            f"Invalid interface name format: '{clean_name}'",
            code="INVALID_INTERFACE_NAME",
        )

    return clean_name


# Linux package name pattern (supports Debian/RPM package names and multiarch specs like libc6:amd64)
PACKAGE_NAME_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\+\.\:\_\-]*$")


def validate_package_name(name: Any) -> str:
    """
    Strictly validates a Linux package name.
    Rejects path traversal, whitespace, slashes, null bytes, shell metacharacters, and oversized strings.
    Raises BadRequestError on validation failure.
    """
    if not isinstance(name, str):
        raise BadRequestError("Package name must be a string", code="INVALID_PACKAGE_NAME")

    clean_name = name.strip()
    if not clean_name:
        raise BadRequestError("Package name cannot be empty", code="INVALID_PACKAGE_NAME")

    if len(clean_name) > 128:
        raise BadRequestError(
            f"Package name exceeds maximum limit of 128 characters: '{clean_name}'",
            code="INVALID_PACKAGE_NAME",
        )

    if PROHIBITED_CHARS_PATTERN.search(clean_name) or ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        raise BadRequestError(
            "Package name contains prohibited characters, slashes, or path traversal",
            code="INVALID_PACKAGE_NAME",
        )

    if not PACKAGE_NAME_PATTERN.match(clean_name):
        raise BadRequestError(
            f"Invalid package name format: '{clean_name}'",
            code="INVALID_PACKAGE_NAME",
        )

    return clean_name


# Linux username pattern (POSIX standards, up to 32 characters)
CRON_USER_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9_.][a-zA-Z0-9_.-]*$")
SPECIAL_CRON_EXPRESSIONS: Set[str] = {
    "@reboot",
    "@hourly",
    "@daily",
    "@midnight",
    "@weekly",
    "@monthly",
    "@yearly",
    "@annually",
}
MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}
DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6
}


def validate_cron_username(username: Any, verify_local_account: bool = True) -> str:
    """
    Strictly validates an OS username intended for crontab ownership.
    Rejects path traversal, whitespace, slashes, null bytes, shell characters, and non-existent OS users.
    """
    if not isinstance(username, str):
        raise BadRequestError("Username must be a string", code="INVALID_CRON_USER")

    clean_user = username.strip()
    if not clean_user:
        raise BadRequestError("Username cannot be empty", code="INVALID_CRON_USER")

    if len(clean_user) > 32:
        raise BadRequestError(
            f"Username exceeds maximum Linux username length (32 chars): '{clean_user}'",
            code="INVALID_CRON_USER",
        )

    if PROHIBITED_CHARS_PATTERN.search(clean_user) or ".." in clean_user or "/" in clean_user or "\\" in clean_user:
        raise BadRequestError(
            "Username contains prohibited characters, slashes, or path traversal",
            code="INVALID_CRON_USER",
        )

    if not CRON_USER_PATTERN.match(clean_user):
        raise BadRequestError(
            f"Invalid Linux username format: '{clean_user}'",
            code="INVALID_CRON_USER",
        )

    if verify_local_account:
        try:
            import pwd
            pwd.getpwnam(clean_user)
        except (KeyError, ModuleNotFoundError):
            raise BadRequestError(
                f"User '{clean_user}' does not exist as a local operating system account",
                code="CRON_USER_NOT_FOUND",
            )

    return clean_user


def _validate_cron_field(field_val: str, min_val: int, max_val: int, name_map: Optional[dict] = None) -> None:
    """Helper to validate an individual 5-field cron schedule component."""
    if not field_val:
        raise BadRequestError("Cron field cannot be empty", code="INVALID_CRON_SCHEDULE")

    # Split by comma for lists (e.g. 1,5,10)
    subfields = field_val.split(",")
    for sub in subfields:
        sub = sub.strip()
        if not sub:
            raise BadRequestError("Invalid empty list entry in cron field", code="INVALID_CRON_SCHEDULE")

        step = None
        if "/" in sub:
            parts = sub.split("/")
            if len(parts) != 2:
                raise BadRequestError(f"Invalid step expression '{sub}'", code="INVALID_CRON_SCHEDULE")
            base, step_str = parts[0], parts[1]
            if not step_str.isdigit() or int(step_str) <= 0:
                raise BadRequestError(f"Step value must be a positive integer: '{step_str}'", code="INVALID_CRON_SCHEDULE")
            sub = base

        if sub == "*":
            continue

        if "-" in sub:
            parts = sub.split("-")
            if len(parts) != 2:
                raise BadRequestError(f"Invalid range expression '{sub}'", code="INVALID_CRON_SCHEDULE")
            start_str, end_str = parts[0].upper(), parts[1].upper()

            # Resolve named aliases if available
            start_num = name_map.get(start_str) if name_map and start_str in name_map else (int(start_str) if start_str.isdigit() else None)
            end_num = name_map.get(end_str) if name_map and end_str in name_map else (int(end_str) if end_str.isdigit() else None)

            if start_num is None or end_num is None:
                raise BadRequestError(f"Invalid range boundaries '{sub}'", code="INVALID_CRON_SCHEDULE")
            if start_num < min_val or start_num > max_val or end_num < min_val or end_num > max_val:
                raise BadRequestError(f"Range '{sub}' out of bounds ({min_val}-{max_val})", code="INVALID_CRON_SCHEDULE")
            if start_num > end_num and max_val != 7:  # DOW 7 or wraps can vary, but standard range start <= end
                raise BadRequestError(f"Range start cannot exceed end: '{sub}'", code="INVALID_CRON_SCHEDULE")
        else:
            val_str = sub.upper()
            val_num = name_map.get(val_str) if name_map and val_str in name_map else (int(val_str) if val_str.isdigit() else None)
            if val_num is None:
                raise BadRequestError(f"Invalid token '{sub}' in cron field", code="INVALID_CRON_SCHEDULE")
            if val_num < min_val or val_num > max_val:
                raise BadRequestError(f"Value '{sub}' out of bounds ({min_val}-{max_val})", code="INVALID_CRON_SCHEDULE")


def validate_cron_schedule(schedule: Any) -> str:
    """
    Validates a cron schedule string.
    Supports either standard 5-field cron or recognized special expressions (@reboot, @daily, etc.).
    """
    if not isinstance(schedule, str):
        raise BadRequestError("Cron schedule must be a string", code="INVALID_CRON_SCHEDULE")

    clean = schedule.strip()
    if not clean:
        raise BadRequestError("Cron schedule cannot be empty", code="INVALID_CRON_SCHEDULE")

    if clean.startswith("@"):
        lower = clean.lower()
        if lower not in SPECIAL_CRON_EXPRESSIONS:
            raise BadRequestError(
                f"Unsupported special cron expression: '{clean}'. Supported: {', '.join(sorted(SPECIAL_CRON_EXPRESSIONS))}",
                code="INVALID_CRON_SCHEDULE",
            )
        return lower

    fields = clean.split()
    if len(fields) != 5:
        raise BadRequestError(
            f"Cron schedule must consist of exactly 5 fields (minute hour day_of_month month day_of_week), got {len(fields)}",
            code="INVALID_CRON_SCHEDULE",
        )

    # 1. Minute (0-59)
    _validate_cron_field(fields[0], 0, 59)
    # 2. Hour (0-23)
    _validate_cron_field(fields[1], 0, 23)
    # 3. Day of month (1-31)
    _validate_cron_field(fields[2], 1, 31)
    # 4. Month (1-12 or JAN-DEC)
    _validate_cron_field(fields[3], 1, 12, MONTH_NAMES)
    # 5. Day of week (0-7, 0 & 7 = Sunday, or SUN-SAT)
    _validate_cron_field(fields[4], 0, 7, DOW_NAMES)

    return " ".join(fields)


def validate_cron_command(command: Any) -> str:
    """
    Validates a cron command string.
    Treated strictly as stored crontab data — NEVER executed by the control plane.
    Rejects null bytes, unescaped raw newlines (to prevent crontab record framing injection),
    and enforces maximum length bounds.
    """
    if not isinstance(command, str):
        raise BadRequestError("Cron command must be a string", code="INVALID_CRON_COMMAND")

    clean = command.strip()
    if not clean:
        raise BadRequestError("Cron command cannot be empty", code="INVALID_CRON_COMMAND")

    if len(clean) > 2048:
        raise BadRequestError(
            f"Cron command exceeds maximum length of 2048 characters (got {len(clean)})",
            code="INVALID_CRON_COMMAND",
        )

    if "\x00" in clean:
        raise BadRequestError("Cron command contains illegal null bytes", code="INVALID_CRON_COMMAND")

    if "\n" in clean or "\r" in clean:
        raise BadRequestError("Cron command cannot contain unescaped newline or carriage return characters", code="INVALID_CRON_COMMAND")

    return clean


def validate_cron_comment(comment: Any) -> Optional[str]:
    """Validates an optional human-readable descriptive comment attached to a cron entry."""
    if comment is None:
        return None

    if not isinstance(comment, str):
        raise BadRequestError("Cron comment must be a string", code="INVALID_CRON_COMMENT")

    clean = comment.strip()
    if not clean:
        return None

    if len(clean) > 512:
        raise BadRequestError(
            f"Cron comment exceeds maximum length of 512 characters (got {len(clean)})",
            code="INVALID_CRON_COMMENT",
        )

    if "\x00" in clean or "\n" in clean or "\r" in clean:
        raise BadRequestError("Cron comment cannot contain null bytes or newline characters", code="INVALID_CRON_COMMENT")

    return clean


# -----------------------------------------------------------------------------
# Phase 10: Log Management & Audit Validators
# -----------------------------------------------------------------------------

APPROVED_LOG_SOURCES = frozenset({
    "JOURNAL",
    "SYSLOG",
    "AUTH",
    "MESSAGES",
    "KERNEL",
    "DMESG",
    "DPKG",
    "BOOT",
    "NGINX_ACCESS",
    "NGINX_ERROR",
    "ALTERNATIVES",
})

APPROVED_LOG_SEVERITIES = frozenset({
    "EMERG",
    "ALERT",
    "CRIT",
    "ERR",
    "WARNING",
    "NOTICE",
    "INFO",
    "DEBUG",
})

LOG_SERVICE_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9_\@\.\-]+$")
LOG_UNIT_PATTERN: Pattern[str] = re.compile(
    r"^[a-zA-Z0-9_\@\.\-]+\.(service|socket|target|timer|mount|path|slice|scope)$"
)
LOG_TIMESTAMP_PATTERN: Pattern[str] = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}([T\s][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$"
)


def validate_log_source_id(source: Any) -> str:
    """
    Validates a requested log source ID against the strict internal allowlist.
    Prevents path traversal, absolute path injection, or unknown log sources.
    """
    if not isinstance(source, str):
        raise BadRequestError("Log source ID must be a string", code="INVALID_LOG_SOURCE")

    clean = source.strip().upper()
    if not clean:
        raise BadRequestError("Log source ID cannot be empty", code="INVALID_LOG_SOURCE")

    if "/" in clean or "\\" in clean or ".." in clean:
        raise BadRequestError(
            "Log source ID must be a symbolic identifier, not a file path",
            code="INVALID_LOG_SOURCE",
        )

    if clean not in APPROVED_LOG_SOURCES:
        raise BadRequestError(
            f"Unknown or prohibited log source ID: '{clean}'",
            code="INVALID_LOG_SOURCE",
        )

    return clean


def validate_log_severity(severity: Any) -> Optional[str]:
    """Validates an optional log severity level against standard syslog priorities."""
    if severity is None:
        return None

    if not isinstance(severity, str):
        raise BadRequestError("Log severity must be a string", code="INVALID_LOG_SEVERITY")

    clean = severity.strip().upper()
    if not clean:
        return None

    if clean not in APPROVED_LOG_SEVERITIES:
        raise BadRequestError(
            f"Invalid log severity: '{clean}'. Must be one of: {', '.join(sorted(APPROVED_LOG_SEVERITIES))}",
            code="INVALID_LOG_SEVERITY",
        )

    return clean


def validate_log_service(service: Any) -> Optional[str]:
    """Validates a service or daemon name filter."""
    if service is None:
        return None

    if not isinstance(service, str):
        raise BadRequestError("Service filter must be a string", code="INVALID_LOG_SERVICE")

    clean = service.strip()
    if not clean:
        return None

    if len(clean) > 64:
        raise BadRequestError(
            f"Service filter exceeds maximum length of 64 characters (got {len(clean)})",
            code="INVALID_LOG_SERVICE",
        )

    if not LOG_SERVICE_PATTERN.match(clean):
        raise BadRequestError(
            f"Invalid service filter format: '{clean}'",
            code="INVALID_LOG_SERVICE",
        )

    return clean


def validate_log_unit(unit: Any) -> Optional[str]:
    """Validates a systemd unit filter."""
    if unit is None:
        return None

    if not isinstance(unit, str):
        raise BadRequestError("Unit filter must be a string", code="INVALID_LOG_UNIT")

    clean = unit.strip()
    if not clean:
        return None

    if len(clean) > 64:
        raise BadRequestError(
            f"Unit filter exceeds maximum length of 64 characters (got {len(clean)})",
            code="INVALID_LOG_UNIT",
        )

    if not LOG_UNIT_PATTERN.match(clean):
        raise BadRequestError(
            f"Invalid unit filter format: '{clean}'. Must end in .service, .socket, etc.",
            code="INVALID_LOG_UNIT",
        )

    return clean


def validate_log_search(search: Any) -> Optional[str]:
    """
    Validates an application-level log search query.
    Enforces maximum length bounds and rejects null bytes.
    """
    if search is None:
        return None

    if not isinstance(search, str):
        raise BadRequestError("Search query must be a string", code="INVALID_LOG_SEARCH")

    clean = search.strip()
    if not clean:
        return None

    if len(clean) > 100:
        raise BadRequestError(
            f"Search query exceeds maximum length of 100 characters (got {len(clean)})",
            code="INVALID_LOG_SEARCH",
        )

    if "\x00" in clean or "\n" in clean or "\r" in clean:
        raise BadRequestError("Search query cannot contain null bytes or newline characters", code="INVALID_LOG_SEARCH")

    return clean


def validate_log_timestamp(ts: Any, param_name: str = "timestamp") -> Optional[str]:
    """Validates an ISO8601 or date-time filter string."""
    if ts is None:
        return None

    if not isinstance(ts, str):
        raise BadRequestError(f"Filter '{param_name}' must be a string", code="INVALID_LOG_TIMESTAMP")

    clean = ts.strip()
    if not clean:
        return None

    if len(clean) > 64:
        raise BadRequestError(
            f"Filter '{param_name}' exceeds maximum length of 64 characters",
            code="INVALID_LOG_TIMESTAMP",
        )

    if "\x00" in clean or "\n" in clean or "\r" in clean:
        raise BadRequestError(
            f"Filter '{param_name}' contains illegal characters",
            code="INVALID_LOG_TIMESTAMP",
        )

    if not LOG_TIMESTAMP_PATTERN.match(clean):
        raise BadRequestError(
            f"Filter '{param_name}' must be a valid ISO8601 date/time (e.g. '2026-09-21T00:00:00Z')",
            code="INVALID_LOG_TIMESTAMP",
        )

    return clean




