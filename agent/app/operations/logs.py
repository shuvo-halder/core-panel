import asyncio
import datetime
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional

logger = logging.getLogger("corepanel.agent.logs")

# Static allowlist of supported system log file paths
STATIC_LOG_FILE_SOURCES: Dict[str, List[str]] = {
    "SYSLOG": ["/var/log/syslog", "/var/log/messages"],
    "AUTH": ["/var/log/auth.log", "/var/log/secure"],
    "MESSAGES": ["/var/log/messages"],
    "KERNEL": ["/var/log/kern.log", "/var/log/dmesg"],
    "DMESG": ["/var/log/dmesg"],
    "DPKG": ["/var/log/dpkg.log"],
    "BOOT": ["/var/log/boot.log"],
    "NGINX_ACCESS": ["/var/log/nginx/access.log"],
    "NGINX_ERROR": ["/var/log/nginx/error.log"],
    "ALTERNATIVES": ["/var/log/alternatives.log"],
}

PRIORITY_MAP: Dict[str, str] = {
    "0": "EMERG",
    "1": "ALERT",
    "2": "CRIT",
    "3": "ERR",
    "4": "WARNING",
    "5": "NOTICE",
    "6": "INFO",
    "7": "DEBUG",
    "EMERG": "0",
    "ALERT": "1",
    "CRIT": "2",
    "ERR": "3",
    "WARNING": "4",
    "NOTICE": "5",
    "INFO": "6",
    "DEBUG": "7",
}

UNIT_PATTERN = re.compile(r"^[a-zA-Z0-9_\@\.\-]+\.(service|socket|target|timer|mount|path|slice|scope)$")
TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}([T\s][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$"
)


def _resolve_journalctl_bin() -> Optional[str]:
    """Finds journalctl executable from system PATH or standard binary locations."""
    found = shutil.which("journalctl")
    if found and os.path.isfile(found) and os.access(found, os.X_OK):
        return found
    for fallback in ("/usr/bin/journalctl", "/bin/journalctl"):
        if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
            return fallback
    return None


def read_file_tail(filepath: str, max_lines: int = 100, max_bytes: int = 256 * 1024) -> List[str]:
    """
    Safely reads the last N lines of a file without loading the entire file into memory.
    Uses seek from end with a byte buffer bounded to max_bytes.
    """
    if not os.path.isfile(filepath):
        return []

    try:
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return []

        bytes_to_read = min(file_size, max_bytes)
        with open(filepath, "rb") as f:
            f.seek(file_size - bytes_to_read)
            raw_data = f.read(bytes_to_read)

        text = raw_data.decode("utf-8", errors="replace")
        lines = text.splitlines()

        # If we didn't read from byte 0, the first line might be truncated
        if bytes_to_read < file_size and lines:
            lines = lines[1:]

        # Cap max line length to avoid memory bloat
        sanitized_lines = [line[:4096] for line in lines]
        return sanitized_lines[-max_lines:]
    except Exception as exc:
        logger.warning(f"Error reading tail of file {filepath}: {exc}")
        return []


async def handle_logs_journal_read(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: logs.journal.read
    Safely reads journalctl entries using fixed argument vectors and strict timeouts.
    Payload: {"limit": int, "priority": Optional[str], "unit": Optional[str], "since": Optional[str], "until": Optional[str]}
    """
    journalctl_bin = _resolve_journalctl_bin()
    if not journalctl_bin:
        return {
            "available": False,
            "entries": [],
            "error": "journalctl binary not found on host",
        }

    raw_limit = payload.get("limit", 50)
    try:
        limit = max(1, min(200, int(raw_limit)))
    except (ValueError, TypeError):
        limit = 50

    args = [journalctl_bin, "--no-pager", "--output=json", "-n", str(limit)]

    # Validate priority
    priority = payload.get("priority")
    if priority and isinstance(priority, str):
        p_clean = priority.strip().upper()
        if p_clean in PRIORITY_MAP:
            p_val = PRIORITY_MAP[p_clean]
            args.extend(["-p", p_val])

    # Validate unit
    unit = payload.get("unit")
    if unit and isinstance(unit, str):
        u_clean = unit.strip()
        if UNIT_PATTERN.match(u_clean):
            args.extend(["-u", u_clean])

    # Validate since/until
    since = payload.get("since")
    if since and isinstance(since, str) and TIMESTAMP_PATTERN.match(since.strip()):
        args.extend(["--since", since.strip()])

    until = payload.get("until")
    if until and isinstance(until, str) and TIMESTAMP_PATTERN.match(until.strip()):
        args.extend(["--until", until.strip()])

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "available": True,
                "entries": [],
                "error": "journalctl query timed out after 5.0 seconds",
            }

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            return {
                "available": True,
                "entries": [],
                "error": f"journalctl exited with code {proc.returncode}: {err_msg}",
            }

        lines = stdout.decode("utf-8", errors="replace").splitlines()
        entries: List[Dict[str, Any]] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                entries.append(data)
            except Exception:
                continue

        return {
            "available": True,
            "entries": entries,
            "count": len(entries),
        }
    except Exception as exc:
        logger.error(f"Failed to execute journalctl: {exc}")
        return {
            "available": False,
            "entries": [],
            "error": str(exc),
        }


async def handle_logs_file_read(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: logs.file.read
    Safely reads allowlisted log file entries using bounded tail reading.
    Payload: {"source_id": str, "max_lines": int}
    """
    source_id = payload.get("source_id", "").strip().upper()
    if source_id not in STATIC_LOG_FILE_SOURCES:
        raise ValueError(f"Prohibited or unknown log source ID: '{source_id}'")

    raw_lines = payload.get("max_lines", 100)
    try:
        max_lines = max(1, min(200, int(raw_lines)))
    except (ValueError, TypeError):
        max_lines = 100

    candidates = STATIC_LOG_FILE_SOURCES[source_id]
    target_path = None
    for cand in candidates:
        if os.path.isfile(cand):
            target_path = cand
            break

    if not target_path:
        return {
            "source_id": source_id,
            "available": False,
            "path": candidates[0],
            "size_bytes": 0,
            "last_modified": None,
            "lines": [],
            "message": "Log file not present on host",
        }

    try:
        stat = os.stat(target_path)
        mtime_iso = datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.timezone.utc
        ).isoformat()
        lines = read_file_tail(target_path, max_lines=max_lines)

        return {
            "source_id": source_id,
            "available": True,
            "path": target_path,
            "size_bytes": stat.st_size,
            "last_modified": mtime_iso,
            "lines": lines,
            "count": len(lines),
        }
    except Exception as exc:
        logger.warning(f"Error accessing log file '{target_path}': {exc}")
        return {
            "source_id": source_id,
            "available": False,
            "path": target_path,
            "size_bytes": 0,
            "last_modified": None,
            "lines": [],
            "error": str(exc),
        }
