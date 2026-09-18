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

