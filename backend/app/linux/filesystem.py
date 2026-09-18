import os
from pathlib import Path
from typing import List, Optional, Set

from backend.app.linux.contracts import DiskMountInfo, IDiskCollector


class DiskCollector(IDiskCollector):
    """
    Safely inspects mounted local filesystems using /proc/mounts and os.statvfs.
    Excludes pseudo-filesystems, virtual device trees, and duplicate mount paths.
    """

    IGNORED_FSTYPES: Set[str] = {
        "proc",
        "sysfs",
        "devpts",
        "devtmpfs",
        "cgroup",
        "cgroup2",
        "pstore",
        "bpf",
        "tracefs",
        "securityfs",
        "configfs",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "debugfs",
        "nsfs",
        "ramfs",
        "autofs",
        "binfmt_misc",
        "squashfs",
        "rpc_pipefs",
        "none",
    }

    def __init__(self, mounts_path: Optional[Path] = None):
        self.mounts_path = mounts_path or Path("/proc/mounts")

    def get_disk_mounts(self) -> List[DiskMountInfo]:
        if not self.mounts_path.exists():
            # Fallback to root filesystem only if /proc/mounts is missing
            try:
                stat = os.statvfs("/")
                total_bytes = stat.f_blocks * stat.f_frsize
                free_bytes = stat.f_bfree * stat.f_frsize
                available_bytes = stat.f_bavail * stat.f_frsize
                used_bytes = max(0, total_bytes - free_bytes)
                usage_percent = (
                    round((used_bytes / total_bytes) * 100.0, 1) if total_bytes > 0 else 0.0
                )
                return [
                    DiskMountInfo(
                        device="/dev/root",
                        mount_point="/",
                        filesystem_type="ext4",
                        total_bytes=total_bytes,
                        used_bytes=used_bytes,
                        available_bytes=available_bytes,
                        usage_percent=usage_percent,
                    )
                ]
            except Exception:
                return []

        mounts: List[DiskMountInfo] = []
        seen_mount_points: Set[str] = set()

        try:
            content = self.mounts_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split()
                if len(parts) < 3:
                    continue

                device = parts[0]
                mount_point = parts[1]
                fstype = parts[2]

                # Filter out ignored pseudo filesystems
                if fstype in self.IGNORED_FSTYPES:
                    continue

                # Filter out read-only snap mounts
                if mount_point.startswith("/snap") or device.startswith("/dev/loop"):
                    continue

                # Skip duplicate mount points
                if mount_point in seen_mount_points:
                    continue

                try:
                    stat = os.statvfs(mount_point)
                    total_bytes = stat.f_blocks * stat.f_frsize
                    if total_bytes <= 0:
                        continue

                    free_bytes = stat.f_bfree * stat.f_frsize
                    available_bytes = stat.f_bavail * stat.f_frsize
                    used_bytes = max(0, total_bytes - free_bytes)
                    usage_percent = (
                        round((used_bytes / total_bytes) * 100.0, 1) if total_bytes > 0 else 0.0
                    )

                    mounts.append(
                        DiskMountInfo(
                            device=device,
                            mount_point=mount_point,
                            filesystem_type=fstype,
                            total_bytes=total_bytes,
                            used_bytes=used_bytes,
                            available_bytes=available_bytes,
                            usage_percent=usage_percent,
                        )
                    )
                    seen_mount_points.add(mount_point)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except Exception:
            pass

        # Sort mounts by mount point path length (/ first)
        mounts.sort(key=lambda m: (len(m.mount_point), m.mount_point))
        return mounts


disk_collector = DiskCollector()
