import asyncio
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.errors import AppError, NotFoundError
from backend.app.core.validators import (
    APPROVED_LOG_SEVERITIES,
    APPROVED_LOG_SOURCES,
    validate_log_search,
    validate_log_service,
    validate_log_severity,
    validate_log_source_id,
    validate_log_timestamp,
    validate_log_unit,
)
from backend.app.ipc.client import IPCClient
from backend.app.linux.contracts import (
    ILogManager,
    LogEntry,
    LogOverview,
    LogPage,
    LogSeverity,
    LogSource,
    LogSourceType,
)

logger = logging.getLogger("corepanel.linux.logs")

# Static allowlist of supported log sources
APPROVED_LOG_SOURCE_METADATA: Dict[str, Dict[str, Any]] = {
    "JOURNAL": {
        "name": "Systemd Journal",
        "source_type": LogSourceType.JOURNAL.value,
        "paths": [],
        "description": "Centralized systemd binary journal for services and kernel",
    },
    "SYSLOG": {
        "name": "System Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/syslog", "/var/log/messages"],
        "description": "Standard Linux syslog messages and daemon activity",
    },
    "AUTH": {
        "name": "Authentication Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/auth.log", "/var/log/secure"],
        "description": "User authentication, SSH logins, and sudo activity",
    },
    "KERNEL": {
        "name": "Kernel Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/kern.log", "/var/log/dmesg"],
        "description": "Linux kernel ring buffer and driver diagnostics",
    },
    "DPKG": {
        "name": "Package Manager Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/dpkg.log"],
        "description": "Debian and Ubuntu package installation and update history",
    },
    "BOOT": {
        "name": "Boot Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/boot.log"],
        "description": "System hardware initialization and boot service messages",
    },
    "NGINX_ACCESS": {
        "name": "Nginx Access Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/nginx/access.log"],
        "description": "Nginx web server HTTP access request log",
    },
    "NGINX_ERROR": {
        "name": "Nginx Error Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/nginx/error.log"],
        "description": "Nginx web server error and diagnostic messages",
    },
    "ALTERNATIVES": {
        "name": "Alternatives Log",
        "source_type": LogSourceType.FILE.value,
        "paths": ["/var/log/alternatives.log"],
        "description": "System update-alternatives symlink updates log",
    },
}

JOURNAL_PRIORITY_TO_SEVERITY = {
    0: LogSeverity.EMERG.value,
    1: LogSeverity.ALERT.value,
    2: LogSeverity.CRIT.value,
    3: LogSeverity.ERR.value,
    4: LogSeverity.WARNING.value,
    5: LogSeverity.NOTICE.value,
    6: LogSeverity.INFO.value,
    7: LogSeverity.DEBUG.value,
}

# Standard syslog pattern: MMM DD HH:MM:SS hostname service[pid]: message
SYSLOG_REGEX = re.compile(
    r"^([A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+([a-zA-Z0-9_\.\-]+)\s+([a-zA-Z0-9_\.\-\@]+)(?:\[(\d+)\])?:\s*(.*)$"
)

# RFC5424 timestamp pattern: YYYY-MM-DDTHH:MM:SS...
RFC5424_REGEX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}))\s+([a-zA-Z0-9_\.\-]+)\s+([a-zA-Z0-9_\.\-\@]+)(?:\[(\d+)\])?:\s*(.*)$"
)

# Dpkg log pattern: YYYY-MM-DD HH:MM:SS action package version ...
DPKG_REGEX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([a-z]+)\s+(.*)$"
)


def compute_log_id(source: str, timestamp: str, line_idx: int, message: str) -> str:
    """Computes a deterministic, collision-resistant identifier for a log entry."""
    seed = f"{source}:{timestamp}:{line_idx}:{message[:120]}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"log_{source.lower()}_{digest}"


def derive_severity_from_text(text: str) -> str:
    """Heuristically infers syslog severity from log message keywords if unlabelled."""
    lower = text.lower()
    if any(k in lower for k in ("emerg", "panic", "fatal")):
        return LogSeverity.EMERG.value
    if any(k in lower for k in ("alert", "crit", "critical")):
        return LogSeverity.CRIT.value
    if any(k in lower for k in ("error", "err", "fail", "failed", "failure", "exception")):
        return LogSeverity.ERR.value
    if any(k in lower for k in ("warn", "warning")):
        return LogSeverity.WARNING.value
    if any(k in lower for k in ("notice")):
        return LogSeverity.NOTICE.value
    if any(k in lower for k in ("debug", "trace")):
        return LogSeverity.DEBUG.value
    return LogSeverity.INFO.value


def parse_syslog_timestamp(raw_ts: str) -> str:
    """Parses 'MMM DD HH:MM:SS' into an ISO8601 string using current year."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        parsed = datetime.datetime.strptime(f"{now.year} {raw_ts}", "%Y %b %d %H:%M:%S")
        # Handle year boundary if log is from end of previous year
        if parsed > now + datetime.timedelta(days=1):
            parsed = parsed.replace(year=now.year - 1)
        return parsed.replace(tzinfo=datetime.timezone.utc).isoformat()
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_file_tail_bounded(filepath: str, max_lines: int = 150, max_bytes: int = 256 * 1024) -> List[str]:
    """
    Safely reads the tail of a file without loading the entire file into memory.
    Enforces maximum line lengths and byte bounds.
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

        if bytes_to_read < file_size and lines:
            lines = lines[1:]

        sanitized = [line[:4096] for line in lines if line.strip()]
        return sanitized[-max_lines:]
    except Exception as exc:
        logger.warning(f"Failed to read file tail for {filepath}: {exc}")
        return []


class LinuxLogManager(ILogManager):
    """
    Production-grade Linux Log Manager implementing ILogManager.
    Enforces strict read-only bounded access, allowlisted sources,
    safe IPC delegation when privileged, and rich structured parsing.
    """

    def __init__(self, ipc_client: Optional[IPCClient] = None):
        self.ipc_client = ipc_client or IPCClient()

    def _is_journal_supported(self) -> bool:
        """Checks if journalctl binary is available on the host system."""
        found = shutil.which("journalctl")
        if found:
            return True
        for fb in ("/usr/bin/journalctl", "/bin/journalctl"):
            if os.path.isfile(fb) and os.access(fb, os.X_OK):
                return True
        return False

    def _resolve_source_path(self, source_id: str) -> Tuple[Optional[str], bool, int, Optional[str]]:
        """Resolves existing path, accessibility, size, and modification time for a file source."""
        meta = APPROVED_LOG_SOURCE_METADATA.get(source_id)
        if not meta or meta["source_type"] != LogSourceType.FILE.value:
            return None, False, 0, None

        candidates = meta.get("paths", [])
        for p in candidates:
            if os.path.isfile(p):
                try:
                    stat = os.stat(p)
                    mtime = datetime.datetime.fromtimestamp(
                        stat.st_mtime, tz=datetime.timezone.utc
                    ).isoformat()
                    return p, True, stat.st_size, mtime
                except Exception:
                    return p, False, 0, None

        # None exist; return first candidate as reference path
        return (candidates[0] if candidates else None), False, 0, None

    async def get_sources(self) -> List[LogSource]:
        """Discovers all allowlisted log sources and reports their current availability."""
        sources: List[LogSource] = []

        # 1. Systemd Journal
        journal_avail = self._is_journal_supported()
        sources.append(
            LogSource(
                id="JOURNAL",
                name=APPROVED_LOG_SOURCE_METADATA["JOURNAL"]["name"],
                source_type=LogSourceType.JOURNAL.value,
                path=None,
                available=journal_avail,
                size_bytes=None,
                last_modified=None,
                description=APPROVED_LOG_SOURCE_METADATA["JOURNAL"]["description"],
            )
        )

        # 2. File sources
        for s_id, meta in APPROVED_LOG_SOURCE_METADATA.items():
            if meta["source_type"] != LogSourceType.FILE.value:
                continue

            path, available, size, mtime = self._resolve_source_path(s_id)
            sources.append(
                LogSource(
                    id=s_id,
                    name=meta["name"],
                    source_type=meta["source_type"],
                    path=path,
                    available=available,
                    size_bytes=size if available else None,
                    last_modified=mtime if available else None,
                    description=meta["description"],
                )
            )

        return sources

    async def get_overview(self) -> LogOverview:
        """Returns consolidated metrics across all log sources."""
        sources = await self.get_sources()
        journal_avail = any(s.id == "JOURNAL" and s.available for s in sources)
        active_count = sum(1 for s in sources if s.available)

        # Fetch recent entries to calculate severity distributions and latest timestamp
        sample_page = await self.query_logs(page=1, page_size=100)

        severity_counts: Dict[str, int] = {
            LogSeverity.EMERG.value: 0,
            LogSeverity.ALERT.value: 0,
            LogSeverity.CRIT.value: 0,
            LogSeverity.ERR.value: 0,
            LogSeverity.WARNING.value: 0,
            LogSeverity.NOTICE.value: 0,
            LogSeverity.INFO.value: 0,
            LogSeverity.DEBUG.value: 0,
        }

        latest_ts: Optional[str] = None
        for item in sample_page.items:
            if item.severity in severity_counts:
                severity_counts[item.severity] += 1
            if not latest_ts or item.timestamp > latest_ts:
                latest_ts = item.timestamp

        return LogOverview(
            available_sources=sources,
            journal_available=journal_avail,
            total_sources_count=len(sources),
            active_sources_count=active_count,
            severity_counts=severity_counts,
            latest_timestamp=latest_ts,
        )

    async def _fetch_journal_entries(
        self,
        limit: int = 100,
        priority: Optional[str] = None,
        unit: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[LogEntry]:
        """Reads entries from journalctl either directly or via CoreAgent IPC."""
        if not self._is_journal_supported():
            return []

        entries_raw: List[Dict[str, Any]] = []

        # Try IPC if available
        ipc_worked = False
        try:
            resp = await self.ipc_client.execute(
                "logs.journal.read",
                {
                    "limit": limit,
                    "priority": priority,
                    "unit": unit,
                    "since": since,
                    "until": until,
                },
                timeout_seconds=6.0,
            )
            if resp.get("available") and "entries" in resp:
                entries_raw = resp["entries"]
                ipc_worked = True
        except Exception:
            ipc_worked = False

        if not ipc_worked:
            # Direct execution fallback if journalctl exists
            journalctl_bin = shutil.which("journalctl") or "/usr/bin/journalctl"
            args = [journalctl_bin, "--no-pager", "--output=json", "-n", str(limit)]
            if priority:
                args.extend(["-p", priority])
            if unit:
                args.extend(["-u", unit])
            if since:
                args.extend(["--since", since])
            if until:
                args.extend(["--until", until])

            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                if proc.returncode == 0:
                    for line in stdout.decode("utf-8", errors="replace").splitlines():
                        if line.strip():
                            try:
                                entries_raw.append(json.loads(line.strip()))
                            except Exception:
                                continue
            except Exception as exc:
                logger.warning(f"Direct journalctl read failed: {exc}")
                return []

        # Parse raw JSON journal entries into LogEntry objects
        parsed_entries: List[LogEntry] = []
        for idx, item in enumerate(entries_raw):
            raw_msg = str(item.get("MESSAGE", ""))
            raw_ts = item.get("__REALTIME_TIMESTAMP")
            if raw_ts:
                try:
                    ts_sec = int(raw_ts) / 1000000.0
                    iso_ts = datetime.datetime.fromtimestamp(
                        ts_sec, tz=datetime.timezone.utc
                    ).isoformat()
                except Exception:
                    iso_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            else:
                iso_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

            raw_prio = item.get("PRIORITY")
            try:
                prio_int = int(raw_prio) if raw_prio is not None else 6
                sev = JOURNAL_PRIORITY_TO_SEVERITY.get(prio_int, LogSeverity.INFO.value)
            except Exception:
                sev = LogSeverity.INFO.value

            service = item.get("_COMM") or item.get("SYSLOG_IDENTIFIER")
            unit_val = item.get("_SYSTEMD_UNIT")
            hostname = item.get("_HOSTNAME")
            pid_raw = item.get("_PID")
            uid_raw = item.get("_UID")
            boot_id = item.get("_BOOT_ID")

            pid = int(pid_raw) if pid_raw and str(pid_raw).isdigit() else None
            uid = int(uid_raw) if uid_raw and str(uid_raw).isdigit() else None

            entry_id = compute_log_id("JOURNAL", iso_ts, idx, raw_msg)
            parsed_entries.append(
                LogEntry(
                    id=entry_id,
                    timestamp=iso_ts,
                    source="JOURNAL",
                    hostname=hostname,
                    service=service,
                    unit=unit_val,
                    severity=sev,
                    facility=item.get("SYSLOG_FACILITY"),
                    message=raw_msg,
                    pid=pid,
                    uid=uid,
                    boot_id=boot_id,
                    metadata={"transport": item.get("_TRANSPORT")},
                )
            )

        return parsed_entries

    async def _fetch_file_entries(self, source_id: str, max_lines: int = 150) -> List[LogEntry]:
        """Reads and parses raw lines from an allowlisted file source."""
        path, available, _, _ = self._resolve_source_path(source_id)
        if not path:
            return []

        lines: List[str] = []

        # If readable locally by control plane
        if available and os.access(path, os.R_OK):
            lines = read_file_tail_bounded(path, max_lines=max_lines)
        else:
            # Delegate to CoreAgent IPC for root-only files (e.g. /var/log/auth.log)
            try:
                resp = await self.ipc_client.execute(
                    "logs.file.read",
                    {"source_id": source_id, "max_lines": max_lines},
                    timeout_seconds=5.0,
                )
                if resp.get("available") and "lines" in resp:
                    lines = resp["lines"]
            except Exception as exc:
                logger.warning(f"CoreAgent IPC file read failed for {source_id}: {exc}")
                return []

        parsed: List[LogEntry] = []
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Try RFC5424
            m = RFC5424_REGEX.match(line_str)
            if m:
                ts, host, srv, pid_str, msg = m.groups()
                pid = int(pid_str) if pid_str and pid_str.isdigit() else None
                entry_id = compute_log_id(source_id, ts, idx, msg)
                sev = derive_severity_from_text(msg)
                parsed.append(
                    LogEntry(
                        id=entry_id,
                        timestamp=ts,
                        source=source_id,
                        hostname=host,
                        service=srv,
                        unit=f"{srv}.service" if srv else None,
                        severity=sev,
                        message=msg,
                        pid=pid,
                    )
                )
                continue

            # Try standard syslog
            m = SYSLOG_REGEX.match(line_str)
            if m:
                raw_ts, host, srv, pid_str, msg = m.groups()
                iso_ts = parse_syslog_timestamp(raw_ts)
                pid = int(pid_str) if pid_str and pid_str.isdigit() else None
                entry_id = compute_log_id(source_id, iso_ts, idx, msg)
                sev = derive_severity_from_text(msg)
                parsed.append(
                    LogEntry(
                        id=entry_id,
                        timestamp=iso_ts,
                        source=source_id,
                        hostname=host,
                        service=srv,
                        unit=f"{srv}.service" if srv else None,
                        severity=sev,
                        message=msg,
                        pid=pid,
                    )
                )
                continue

            # Try dpkg format: YYYY-MM-DD HH:MM:SS action package version ...
            m = DPKG_REGEX.match(line_str)
            if m:
                raw_ts, action_name, rest = m.groups()
                try:
                    dt = datetime.datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=datetime.timezone.utc
                    )
                    iso_ts = dt.isoformat()
                except Exception:
                    iso_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                full_msg = f"{action_name} {rest}"
                entry_id = compute_log_id(source_id, iso_ts, idx, full_msg)
                sev = derive_severity_from_text(full_msg)
                parsed.append(
                    LogEntry(
                        id=entry_id,
                        timestamp=iso_ts,
                        source=source_id,
                        service="dpkg",
                        severity=sev,
                        message=full_msg,
                    )
                )
                continue

            # Fallback raw line
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            entry_id = compute_log_id(source_id, now_iso, idx, line_str)
            sev = derive_severity_from_text(line_str)
            parsed.append(
                LogEntry(
                    id=entry_id,
                    timestamp=now_iso,
                    source=source_id,
                    severity=sev,
                    message=line_str,
                )
            )

        return parsed

    async def query_logs(
        self,
        source: Optional[str] = None,
        severity: Optional[str] = None,
        service: Optional[str] = None,
        unit: Optional[str] = None,
        search: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LogPage:
        """
        Queries log entries with structured filtering, search, and pagination.
        Enforces maximum bounds and security validations on all inputs.
        """
        page = max(1, page)
        page_size = max(1, min(200, page_size))

        target_source = validate_log_source_id(source) if source else None
        target_sev = validate_log_severity(severity) if severity else None
        target_svc = validate_log_service(service) if service else None
        target_unit = validate_log_unit(unit) if unit else None
        target_search = validate_log_search(search) if search else None
        target_since = validate_log_timestamp(since, "since") if since else None
        target_until = validate_log_timestamp(until, "until") if until else None

        all_entries: List[LogEntry] = []

        if target_source == "JOURNAL":
            all_entries = await self._fetch_journal_entries(
                limit=page_size * 4,
                priority=target_sev,
                unit=target_unit,
                since=target_since,
                until=target_until,
            )
        elif target_source and target_source in APPROVED_LOG_SOURCE_METADATA:
            all_entries = await self._fetch_file_entries(target_source, max_lines=page_size * 4)
        else:
            # Query all available sources concurrently
            tasks = []
            if self._is_journal_supported():
                tasks.append(
                    self._fetch_journal_entries(
                        limit=50,
                        priority=target_sev,
                        unit=target_unit,
                        since=target_since,
                        until=target_until,
                    )
                )

            # File sources
            for s_id in APPROVED_LOG_SOURCE_METADATA:
                if s_id != "JOURNAL":
                    path, avail, _, _ = self._resolve_source_path(s_id)
                    if avail:
                        tasks.append(self._fetch_file_entries(s_id, max_lines=50))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, list):
                        all_entries.extend(res)

        # In-memory filtering
        filtered: List[LogEntry] = []
        search_lower = target_search.lower() if target_search else None

        for entry in all_entries:
            if target_sev and entry.severity.upper() != target_sev:
                continue
            if target_svc and (not entry.service or entry.service.lower() != target_svc.lower()):
                continue
            if target_unit and (not entry.unit or entry.unit.lower() != target_unit.lower()):
                continue
            if target_since and entry.timestamp < target_since:
                continue
            if target_until and entry.timestamp > target_until:
                continue
            if search_lower:
                msg_match = search_lower in entry.message.lower()
                srv_match = bool(entry.service and search_lower in entry.service.lower())
                unit_match = bool(entry.unit and search_lower in entry.unit.lower())
                host_match = bool(entry.hostname and search_lower in entry.hostname.lower())
                if not (msg_match or srv_match or unit_match or host_match):
                    continue

            filtered.append(entry)

        # Sort newest first
        filtered.sort(key=lambda x: x.timestamp, reverse=True)

        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

        offset = (page - 1) * page_size
        paginated_items = filtered[offset : offset + page_size]

        return LogPage(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            source=target_source,
        )

    async def get_log_entry(
        self, entry_id: str, source: Optional[str] = None
    ) -> Optional[LogEntry]:
        """Finds a specific log entry by its deterministic identifier."""
        # Query recent logs and match entry_id
        page = await self.query_logs(source=source, page=1, page_size=200)
        for item in page.items:
            if item.id == entry_id:
                return item
        return None


log_manager = LinuxLogManager()
