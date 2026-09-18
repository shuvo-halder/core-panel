import re
from typing import Pattern

from backend.app.core.errors import BadRequestError

# Strict regex matching valid systemd service unit names (e.g. nginx.service, user@1000.service)
SERVICE_UNIT_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9_\@\.\-]+\.service$")
PROHIBITED_CHARS_PATTERN: Pattern[str] = re.compile(r"[\s/\\;\|\&\>\<\$\`\'\"\x00\n\r\t]")


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
