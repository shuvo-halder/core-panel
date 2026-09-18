import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.linux.contracts import ISystemInfoCollector, SystemIdentity
from backend.app.linux.os_detect import os_provider


class SystemInfoCollector(ISystemInfoCollector):
    """
    Safely collects host identity, distribution details, and system uptime.
    Uses unprivileged /proc and standard library interfaces with no shell execution.
    """

    def __init__(self, proc_path: Optional[Path] = None, os_release_path: Optional[Path] = None):
        self.proc_path = proc_path or Path("/proc")
        self.os_release_path = os_release_path

    def _get_uptime_and_boot_time(self) -> tuple[float, Optional[str]]:
        uptime_seconds = 0.0
        boot_time_iso = None

        # Try reading /proc/uptime
        uptime_file = self.proc_path / "uptime"
        if uptime_file.exists():
            try:
                content = uptime_file.read_text(encoding="utf-8").strip()
                parts = content.split()
                if parts:
                    uptime_seconds = round(float(parts[0]), 2)
            except Exception:
                pass

        # Fallback if uptime is still 0
        if uptime_seconds <= 0.0:
            try:
                # CLOCK_BOOTTIME includes time during suspend
                uptime_seconds = round(time.clock_gettime(time.CLOCK_BOOTTIME), 2)
            except (AttributeError, OSError):
                uptime_seconds = round(time.monotonic(), 2)

        # Try reading btime from /proc/stat
        stat_file = self.proc_path / "stat"
        if stat_file.exists():
            try:
                for line in stat_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("btime "):
                        btime_sec = int(line.split()[1])
                        boot_dt = datetime.fromtimestamp(btime_sec, timezone.utc)
                        boot_time_iso = boot_dt.isoformat()
                        break
            except Exception:
                pass

        # Fallback boot_time calculation if /proc/stat btime was not found
        if not boot_time_iso and uptime_seconds > 0:
            try:
                calc_epoch = time.time() - uptime_seconds
                boot_time_iso = datetime.fromtimestamp(calc_epoch, timezone.utc).isoformat()
            except Exception:
                pass

        return uptime_seconds, boot_time_iso

    def get_system_identity(self) -> SystemIdentity:
        # Detect distribution info
        os_info = os_provider.detect_os()

        # Hostname
        try:
            hostname = socket.gethostname() or "unknown-host"
        except Exception:
            hostname = "unknown-host"

        # Uptime and boot time
        uptime_seconds, boot_time = self._get_uptime_and_boot_time()

        return SystemIdentity(
            hostname=hostname,
            operating_system=platform.system() or "Linux",
            distribution=os_info.distribution,
            distribution_version=os_info.version,
            kernel_version=os_info.kernel_version,
            architecture=os_info.architecture,
            uptime_seconds=uptime_seconds,
            boot_time=boot_time,
        )


system_info_collector = SystemInfoCollector()
