import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Patterns to redact from logs
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "secret",
    "secret_key",
    "authorization",
    "cookie",
    "private_key",
    "ssh_key",
}

SENSITIVE_REGEX = re.compile(
    r'(?i)(password|token|secret|authorization|key|cookie)["\']?\s*[:=]\s*["\']?([^"\'\s&]+)',
    re.IGNORECASE,
)


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON without leaking sensitive information."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": self._sanitize_message(record.getMessage()),
        }

        # Include request ID if attached to record
        if hasattr(record, "request_id"):
            log_entry["requestId"] = getattr(record, "request_id")

        if hasattr(record, "duration_ms"):
            log_entry["durationMs"] = getattr(record, "duration_ms")

        if record.exc_info and not getattr(record, "suppress_trace", False):
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)

    def _sanitize_message(self, msg: str) -> str:
        # Redact known sensitive string patterns
        return SENSITIVE_REGEX.sub(r"\1: [REDACTED]", msg)


def setup_logger(name: str = "corepanel") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logger()
