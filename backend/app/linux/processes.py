import os
import pwd
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from backend.app.core.logging import logger
from backend.app.linux.contracts import IProcessCollector, ProcessInfo, ProcessListResult

STATE_MAPPING: Dict[str, str] = {
    "R": "running",
    "S": "sleeping",
    "D": "disk_sleep",
    "Z": "zombie",
    "T": "stopped",
    "t": "stopped",
    "X": "dead",
    "x": "dead",
    "K": "wakekill",
    "W": "waking",
    "P": "parked",
    "I": "idle",
}


class LinuxProcessCollector(IProcessCollector):
    """
    Unprivileged, high-performance Linux process collector.
    Directly inspects /proc files with zero external subprocess calls.
    Maintains bounded thread-safe caches for UID resolution and CPU utilization.
    """

    def __init__(self, proc_path: Optional[Path] = None):
        self.proc_path = proc_path or Path("/proc")
        self._uid_cache: Dict[int, Optional[str]] = {}
        self._cpu_cache: Dict[Tuple[int, int], Tuple[float, int, int]] = {}
        self._cpu_lock = threading.Lock()
        self._last_cache_cleanup = time.monotonic()
        self._page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        self._clk_tck = (
            os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") and hasattr(os, "sysconf_names") and "SC_CLK_TCK" in os.sysconf_names else 100
        )

    def _get_system_total_ticks_and_btime(self) -> Tuple[int, int]:
        """Reads /proc/stat for system-wide CPU ticks and boot epoch time."""
        stat_file = self.proc_path / "stat"
        total_ticks = 0
        btime = 0

        if stat_file.exists():
            try:
                content = stat_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("cpu "):
                        parts = line.split()[1:]
                        ticks = [int(p) for p in parts if p.isdigit()]
                        total_ticks = sum(ticks)
                    elif line.startswith("btime "):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            btime = int(parts[1])
            except Exception:
                pass

        if btime == 0:
            btime = int(time.time() - (self._get_uptime() or 0))

        return total_ticks, btime

    def _get_uptime(self) -> float:
        """Reads /proc/uptime."""
        uptime_file = self.proc_path / "uptime"
        if uptime_file.exists():
            try:
                parts = uptime_file.read_text(encoding="utf-8").split()
                if parts:
                    return float(parts[0])
            except Exception:
                pass
        return 0.0

    def _get_total_memory_bytes(self) -> int:
        """Reads MemTotal from /proc/meminfo."""
        meminfo_file = self.proc_path / "meminfo"
        if meminfo_file.exists():
            try:
                for line in meminfo_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            return int(parts[1]) * 1024
            except Exception:
                pass
        return 1024 * 1024 * 1024  # 1GB default fallback to prevent division by zero

    def _resolve_username(self, uid: int) -> Optional[str]:
        """Resolves UID to system username with in-memory caching."""
        if uid in self._uid_cache:
            return self._uid_cache[uid]

        try:
            name = pwd.getpwuid(uid).pw_name
            self._uid_cache[uid] = name
            return name
        except (KeyError, Exception):
            self._uid_cache[uid] = str(uid)
            return str(uid)

    def _get_protected_pids(self) -> Set[int]:
        """Returns set of known critical PIDs that must not be terminated."""
        protected = {1}
        try:
            protected.add(os.getpid())
            ppid = os.getppid()
            if ppid > 1:
                protected.add(ppid)
        except Exception:
            pass
        return protected

    def _clean_stale_cpu_cache(self, current_time: float) -> None:
        """Removes entries older than 60 seconds from CPU cache to avoid unbounded growth."""
        if current_time - self._last_cache_cleanup > 60.0:
            with self._cpu_lock:
                stale_keys = [
                    k for k, v in self._cpu_cache.items() if current_time - v[0] > 60.0
                ]
                for k in stale_keys:
                    self._cpu_cache.pop(k, None)
                self._last_cache_cleanup = current_time

    def _read_process_info(
        self,
        pid: int,
        system_total_ticks: int,
        btime: int,
        total_mem_bytes: int,
        uptime_sec: float,
        protected_pids: Set[int],
    ) -> Optional[ProcessInfo]:
        """
        Parses process metadata from /proc/<pid>/stat, /proc/<pid>/status, and /proc/<pid>/cmdline.
        Handles processes disappearing gracefully.
        """
        pid_dir = self.proc_path / str(pid)
        stat_file = pid_dir / "stat"

        if not stat_file.exists():
            return None

        try:
            stat_content = stat_file.read_text(encoding="utf-8")
        except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
            return None

        # Parse /proc/<pid>/stat
        # comm can contain spaces and parentheses: e.g. "(Web Content)"
        lparen = stat_content.find("(")
        rparen = stat_content.rfind(")")
        if lparen == -1 or rparen == -1 or rparen <= lparen:
            return None

        name = stat_content[lparen + 1 : rparen]
        fields_after_comm = stat_content[rparen + 1 :].strip().split()
        if len(fields_after_comm) < 22:
            return None

        raw_state = fields_after_comm[0]
        state = STATE_MAPPING.get(raw_state, "unknown")

        try:
            ppid = int(fields_after_comm[1])
            utime = int(fields_after_comm[11])
            stime = int(fields_after_comm[12])
            threads = int(fields_after_comm[17])
            starttime_ticks = int(fields_after_comm[19])
            vsize = int(fields_after_comm[20])
            rss_pages = int(fields_after_comm[21])
        except (ValueError, IndexError):
            return None

        proc_ticks = utime + stime
        rss_bytes = rss_pages * self._page_size

        # Parse /proc/<pid>/status for exact Uid and VmRSS if available
        status_file = pid_dir / "status"
        uid = 0
        if status_file.exists():
            try:
                for line in status_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("Uid:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            uid = int(parts[1])
                    elif line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            rss_bytes = int(parts[1]) * 1024
                    elif line.startswith("VmSize:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            vsize = int(parts[1]) * 1024
            except Exception:
                pass

        username = self._resolve_username(uid)

        # Calculate Memory percentage
        memory_percent = round((rss_bytes / total_mem_bytes) * 100.0, 2) if total_mem_bytes > 0 else 0.0

        # Calculate Start Time ISO
        start_seconds_after_boot = starttime_ticks / (self._clk_tck or 100)
        start_timestamp_epoch = btime + start_seconds_after_boot
        try:
            start_time_iso = datetime.fromtimestamp(start_timestamp_epoch, timezone.utc).isoformat()
        except Exception:
            start_time_iso = datetime.now(timezone.utc).isoformat()

        # Calculate CPU Percentage with bounded sampling cache
        now_ts = time.monotonic()
        cache_key = (pid, starttime_ticks)
        cpu_percent = 0.0

        with self._cpu_lock:
            if cache_key in self._cpu_cache:
                last_ts, last_proc_ticks, last_sys_ticks = self._cpu_cache[cache_key]
                time_delta = now_ts - last_ts
                sys_delta = system_total_ticks - last_sys_ticks
                proc_delta = proc_ticks - last_proc_ticks

                if sys_delta > 0:
                    cpu_percent = round((proc_delta / sys_delta) * 100.0, 2)
                elif time_delta > 0.05:
                    proc_time_sec = proc_delta / (self._clk_tck or 100)
                    cpu_percent = round((proc_time_sec / time_delta) * 100.0, 2)

                self._cpu_cache[cache_key] = (now_ts, proc_ticks, system_total_ticks)
            else:
                # First time seeing this PID: calculate lifetime average CPU utilization
                proc_age_sec = uptime_sec - start_seconds_after_boot
                if proc_age_sec > 0.1:
                    total_proc_sec = proc_ticks / (self._clk_tck or 100)
                    cpu_percent = round((total_proc_sec / proc_age_sec) * 100.0, 2)
                self._cpu_cache[cache_key] = (now_ts, proc_ticks, system_total_ticks)

        cpu_percent = max(0.0, min(cpu_percent, 100.0 * (os.cpu_count() or 1)))

        # Parse /proc/<pid>/cmdline safely (sanitized, truncated)
        command_summary: Optional[str] = None
        cmdline_file = pid_dir / "cmdline"
        if cmdline_file.exists():
            try:
                cmd_data = cmdline_file.read_bytes()
                if cmd_data:
                    # null-byte separated arguments
                    parts = cmd_data.decode("utf-8", errors="replace").split("\x00")
                    sanitized_parts = [p.strip() for p in parts if p.strip()]
                    if sanitized_parts:
                        full_cmd = " ".join(sanitized_parts)
                        # Truncate command line for privacy and performance
                        command_summary = full_cmd[:128] + ("..." if len(full_cmd) > 128 else "")
            except Exception:
                pass

        if not command_summary:
            command_summary = f"[{name}]"

        is_protected = pid in protected_pids or pid == 1

        return ProcessInfo(
            pid=pid,
            ppid=ppid,
            name=name,
            username=username,
            uid=uid,
            state=state,
            cpu_percent=cpu_percent,
            memory_rss_bytes=rss_bytes,
            memory_vsz_bytes=vsize,
            memory_percent=memory_percent,
            start_time=start_time_iso,
            start_time_ticks=starttime_ticks,
            threads=threads,
            command_summary=command_summary,
            is_protected=is_protected,
        )

    def list_processes(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        sort_by: str = "cpu",
        order: str = "desc",
    ) -> ProcessListResult:
        """
        Discovers all active processes in /proc, applies optional search filtering,
        sorts by allowlisted field, and returns a paginated slice.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 200))

        system_total_ticks, btime = self._get_system_total_ticks_and_btime()
        total_mem_bytes = self._get_total_memory_bytes()
        uptime_sec = self._get_uptime()
        protected_pids = self._get_protected_pids()

        self._clean_stale_cpu_cache(time.monotonic())

        all_processes: List[ProcessInfo] = []

        if self.proc_path.exists():
            try:
                for entry in self.proc_path.iterdir():
                    if entry.is_dir() and entry.name.isdigit():
                        pid = int(entry.name)
                        p_info = self._read_process_info(
                            pid=pid,
                            system_total_ticks=system_total_ticks,
                            btime=btime,
                            total_mem_bytes=total_mem_bytes,
                            uptime_sec=uptime_sec,
                            protected_pids=protected_pids,
                        )
                        if p_info:
                            all_processes.append(p_info)
            except Exception as exc:
                logger.error(f"Error enumerating processes in {self.proc_path}: {exc}")

        # Search filter
        if search and search.strip():
            term = search.strip().lower()
            all_processes = [
                p
                for p in all_processes
                if term in str(p.pid)
                or term in p.name.lower()
                or (p.username and term in p.username.lower())
                or (p.command_summary and term in p.command_summary.lower())
            ]

        # Sorting whitelist
        reverse = order.lower() == "desc"
        sort_key_map = {
            "cpu": lambda p: p.cpu_percent,
            "memory": lambda p: p.memory_rss_bytes,
            "pid": lambda p: p.pid,
            "name": lambda p: p.name.lower(),
            "user": lambda p: (p.username or "").lower(),
            "threads": lambda p: p.threads,
            "start_time": lambda p: p.start_time_ticks,
        }

        key_fn = sort_key_map.get(sort_by.lower(), lambda p: p.cpu_percent)
        all_processes.sort(key=key_fn, reverse=reverse)

        total = len(all_processes)
        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = all_processes[start_idx:end_idx]

        return ProcessListResult(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        """Retrieves details for a single validated PID."""
        system_total_ticks, btime = self._get_system_total_ticks_and_btime()
        total_mem_bytes = self._get_total_memory_bytes()
        uptime_sec = self._get_uptime()
        protected_pids = self._get_protected_pids()

        return self._read_process_info(
            pid=pid,
            system_total_ticks=system_total_ticks,
            btime=btime,
            total_mem_bytes=total_mem_bytes,
            uptime_sec=uptime_sec,
            protected_pids=protected_pids,
        )


process_collector = LinuxProcessCollector()
