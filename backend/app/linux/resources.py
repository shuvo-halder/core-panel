import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from backend.app.linux.contracts import (
    CPUInfo,
    CPULoadAverage,
    ICPUCollector,
    IMemoryCollector,
    MemoryInfo,
    SwapInfo,
)


class CPUCollector(ICPUCollector):
    """
    Collects CPU hardware metadata, multi-core load averages,
    and calculates non-blocking sampling-based CPU utilization percentages.
    """

    def __init__(self, proc_path: Optional[Path] = None):
        self.proc_path = proc_path or Path("/proc")
        self._lock = threading.Lock()
        self._last_sample: Optional[Tuple[float, int, int]] = (
            None  # (timestamp, idle_ticks, total_ticks)
        )

    def _get_cpu_ticks(self) -> Optional[Tuple[int, int]]:
        """Reads /proc/stat and returns (idle_ticks, total_ticks)."""
        stat_file = self.proc_path / "stat"
        if not stat_file.exists():
            return None

        try:
            content = stat_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("cpu "):
                    parts = line.split()[1:]
                    ticks = [int(p) for p in parts if p.isdigit()]
                    if len(ticks) >= 4:
                        # ticks order: user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
                        idle = ticks[3]
                        iowait = ticks[4] if len(ticks) > 4 else 0
                        idle_ticks = idle + iowait
                        total_ticks = sum(ticks)
                        return (idle_ticks, total_ticks)
        except Exception:
            pass

        return None

    def _get_cpu_model_name(self) -> str:
        """Parses processor model name from /proc/cpuinfo."""
        cpuinfo_file = self.proc_path / "cpuinfo"
        if not cpuinfo_file.exists():
            return "Linux Host Processor"

        try:
            content = cpuinfo_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    if key in ("model name", "hardware", "processor", "cpu model"):
                        val_str = val.strip()
                        if val_str and not val_str.isdigit():
                            return val_str
        except Exception:
            pass

        return "Linux Host Processor"

    def _get_load_average(self) -> CPULoadAverage:
        """Collects 1m, 5m, 15m load averages."""
        loadavg_file = self.proc_path / "loadavg"
        if loadavg_file.exists():
            try:
                parts = loadavg_file.read_text(encoding="utf-8").split()
                if len(parts) >= 3:
                    return CPULoadAverage(
                        load_1m=round(float(parts[0]), 2),
                        load_5m=round(float(parts[1]), 2),
                        load_15m=round(float(parts[2]), 2),
                    )
            except Exception:
                pass

        try:
            l1, l5, l15 = os.getloadavg()
            return CPULoadAverage(
                load_1m=round(l1, 2), load_5m=round(l5, 2), load_15m=round(l15, 2)
            )
        except (AttributeError, OSError):
            pass

        return CPULoadAverage(load_1m=0.0, load_5m=0.0, load_15m=0.0)

    async def _calculate_cpu_usage(self) -> float:
        """
        Calculates CPU utilization percentage using delta between consecutive snapshots.
        Uses cached sample if fresh (0.1s <= age <= 15.0s); otherwise does a quick 50ms sample.
        """
        now = time.monotonic()
        sample = self._get_cpu_ticks()
        if not sample:
            return 0.0

        current_idle, current_total = sample

        with self._lock:
            prev_sample = self._last_sample

        if prev_sample is not None:
            prev_time, prev_idle, prev_total = prev_sample
            age = now - prev_time

            # If previous sample is fresh (between 100ms and 15s old), use it directly
            if 0.1 <= age <= 15.0:
                total_delta = current_total - prev_total
                idle_delta = current_idle - prev_idle

                with self._lock:
                    self._last_sample = (now, current_idle, current_total)

                if total_delta > 0:
                    usage = (1.0 - (idle_delta / total_delta)) * 100.0
                    return max(0.0, min(100.0, round(usage, 1)))

        # Otherwise perform a bounded, non-blocking 50ms sample
        await asyncio.sleep(0.05)
        next_sample = self._get_cpu_ticks()
        next_now = time.monotonic()

        if not next_sample:
            with self._lock:
                self._last_sample = (now, current_idle, current_total)
            return 0.0

        next_idle, next_total = next_sample
        total_delta = next_total - current_total
        idle_delta = next_idle - current_idle

        with self._lock:
            self._last_sample = (next_now, next_idle, next_total)

        if total_delta > 0:
            usage = (1.0 - (idle_delta / total_delta)) * 100.0
            return max(0.0, min(100.0, round(usage, 1)))

        return 0.0

    async def get_cpu_info(self) -> CPUInfo:
        logical_cores = os.cpu_count() or 1
        model_name = self._get_cpu_model_name()
        load_avg = self._get_load_average()
        usage_percent = await self._calculate_cpu_usage()

        return CPUInfo(
            logical_cores=logical_cores,
            model_name=model_name,
            usage_percent=usage_percent,
            load_average=load_avg,
        )


class MemoryCollector(IMemoryCollector):
    """
    Collects RAM and swap memory metrics safely from /proc/meminfo.
    """

    def __init__(self, proc_path: Optional[Path] = None):
        self.proc_path = proc_path or Path("/proc")

    def _parse_meminfo(self) -> Dict[str, int]:
        mem_map: Dict[str, int] = {}
        meminfo_file = self.proc_path / "meminfo"
        if not meminfo_file.exists():
            return mem_map

        try:
            content = meminfo_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    parts = val.strip().split()
                    if parts and parts[0].isdigit():
                        mem_map[key] = int(parts[0])
        except Exception:
            pass

        return mem_map

    def get_memory_info(self) -> MemoryInfo:
        mem_map = self._parse_meminfo()

        # Values in /proc/meminfo are in kB, convert to bytes (* 1024)
        total_bytes = mem_map.get("MemTotal", 0) * 1024
        free_bytes = mem_map.get("MemFree", 0) * 1024

        if "MemAvailable" in mem_map:
            available_bytes = mem_map["MemAvailable"] * 1024
        else:
            buffers = mem_map.get("Buffers", 0) * 1024
            cached = mem_map.get("Cached", 0) * 1024
            available_bytes = free_bytes + buffers + cached

        # Cap available_bytes at total_bytes
        available_bytes = min(total_bytes, available_bytes)
        used_bytes = max(0, total_bytes - available_bytes)

        usage_percent = round((used_bytes / total_bytes) * 100.0, 1) if total_bytes > 0 else 0.0

        # Swap metrics
        swap_total_bytes = mem_map.get("SwapTotal", 0) * 1024
        swap_free_bytes = mem_map.get("SwapFree", 0) * 1024
        swap_used_bytes = max(0, swap_total_bytes - swap_free_bytes)
        swap_usage_percent = (
            round((swap_used_bytes / swap_total_bytes) * 100.0, 1) if swap_total_bytes > 0 else 0.0
        )

        swap_info = SwapInfo(
            total_bytes=swap_total_bytes,
            used_bytes=swap_used_bytes,
            free_bytes=swap_free_bytes,
            usage_percent=swap_usage_percent,
        )

        return MemoryInfo(
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            available_bytes=available_bytes,
            free_bytes=free_bytes,
            usage_percent=usage_percent,
            swap=swap_info,
        )


cpu_collector = CPUCollector()
memory_collector = MemoryCollector()
