import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from backend.app.core.logging import logger
from backend.app.linux.contracts import (
    BlockDeviceInfo,
    BlockDevicePartInfo,
    FilesystemInfo,
    IStorageCollector,
    StorageOverview,
)


class LinuxStorageCollector(IStorageCollector):
    """
    Safe Linux storage, block device, and filesystem telemetry collector.
    Discovers block devices from /sys/block, mounts from /proc/mounts,
    and filesystem metrics from statvfs.
    """

    PSEUDO_FSTYPES: Set[str] = {
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
        "rpc_pipefs",
        "none",
        "overlay",
        "tmpfs",
        "squashfs",
    }

    def __init__(
        self,
        sys_block_path: Optional[Path] = None,
        mounts_path: Optional[Path] = None,
        disk_by_uuid_path: Optional[Path] = None,
        disk_by_label_path: Optional[Path] = None,
    ):
        self.sys_block_path = sys_block_path or Path("/sys/block")
        self.mounts_path = mounts_path or Path("/proc/mounts")
        self.disk_by_uuid_path = disk_by_uuid_path or Path("/dev/disk/by-uuid")
        self.disk_by_label_path = disk_by_label_path or Path("/dev/disk/by-label")

    def _get_device_id_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Safely builds device_path -> uuid and device_path -> label mappings
        by resolving symlinks in /dev/disk/by-uuid and /dev/disk/by-label.
        """
        uuid_map: Dict[str, str] = {}
        label_map: Dict[str, str] = {}

        if self.disk_by_uuid_path.exists() and self.disk_by_uuid_path.is_dir():
            try:
                for entry in self.disk_by_uuid_path.iterdir():
                    try:
                        resolved = entry.resolve()
                        uuid_map[str(resolved)] = entry.name
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
            except (PermissionError, FileNotFoundError, OSError):
                pass

        if self.disk_by_label_path.exists() and self.disk_by_label_path.is_dir():
            try:
                for entry in self.disk_by_label_path.iterdir():
                    try:
                        resolved = entry.resolve()
                        label_map[str(resolved)] = entry.name
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
            except (PermissionError, FileNotFoundError, OSError):
                pass

        return uuid_map, label_map

    def get_mounts(self) -> List[FilesystemInfo]:
        """
        Reads /proc/mounts (or fallback) and collects all mounted filesystems with statvfs metrics.
        """
        uuid_map, label_map = self._get_device_id_maps()
        mounts: List[FilesystemInfo] = []
        seen_mount_points: Set[str] = set()

        if not self.mounts_path.exists():
            # Fallback to root mount if /proc/mounts is missing
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
                    FilesystemInfo(
                        device="/dev/root",
                        mount_point="/",
                        fstype="ext4",
                        is_pseudo=False,
                        is_read_only=False,
                        total_bytes=total_bytes,
                        used_bytes=used_bytes,
                        available_bytes=available_bytes,
                        usage_percent=usage_percent,
                        label=None,
                        uuid=None,
                        mount_options="rw",
                    )
                ]
            except Exception:
                return []

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
                options = parts[3] if len(parts) > 3 else ""

                if mount_point in seen_mount_points:
                    continue

                is_ro = "ro" in options.split(",")
                is_pseudo = (
                    fstype in self.PSEUDO_FSTYPES
                    or device == "none"
                    or device.startswith("cgroup")
                    or not device.startswith("/dev/")
                )

                total_bytes = 0
                used_bytes = 0
                available_bytes = 0
                usage_percent = 0.0

                try:
                    stat = os.statvfs(mount_point)
                    total_bytes = stat.f_blocks * stat.f_frsize
                    free_bytes = stat.f_bfree * stat.f_frsize
                    available_bytes = stat.f_bavail * stat.f_frsize
                    used_bytes = max(0, total_bytes - free_bytes)
                    usage_percent = (
                        round((used_bytes / total_bytes) * 100.0, 1) if total_bytes > 0 else 0.0
                    )
                except (PermissionError, FileNotFoundError, OSError):
                    pass

                uuid = uuid_map.get(device)
                label = label_map.get(device)

                mounts.append(
                    FilesystemInfo(
                        device=device,
                        mount_point=mount_point,
                        fstype=fstype,
                        is_pseudo=is_pseudo,
                        is_read_only=is_ro,
                        total_bytes=total_bytes,
                        used_bytes=used_bytes,
                        available_bytes=available_bytes,
                        usage_percent=usage_percent,
                        label=label,
                        uuid=uuid,
                        mount_options=options,
                    )
                )
                seen_mount_points.add(mount_point)
        except Exception as exc:
            logger.warning(f"Failed reading mounts from {self.mounts_path}: {exc}")

        # Sort mounts: root first, then by mount point
        mounts.sort(key=lambda m: (0 if m.mount_point == "/" else 1, len(m.mount_point), m.mount_point))
        return mounts

    def get_filesystems(self, include_pseudo: bool = False) -> List[FilesystemInfo]:
        """
        Returns list of mounted filesystems.
        If include_pseudo is False, filters out virtual/pseudo filesystems and zero-size entries.
        """
        all_mounts = self.get_mounts()
        if include_pseudo:
            return all_mounts

        return [
            m
            for m in all_mounts
            if not m.is_pseudo
            and not m.mount_point.startswith("/snap")
            and not m.device.startswith("/dev/loop")
            and m.total_bytes > 0
        ]

    def get_block_devices(self) -> List[BlockDeviceInfo]:
        """
        Discovers physical block devices and partitions from /sys/block.
        Correlates each device with active mounts and filesystem metadata.
        """
        devices: List[BlockDeviceInfo] = []
        if not self.sys_block_path.exists() or not self.sys_block_path.is_dir():
            return devices

        uuid_map, label_map = self._get_device_id_maps()
        mounts_by_device: Dict[str, FilesystemInfo] = {m.device: m for m in self.get_mounts()}

        try:
            for dev_entry in sorted(self.sys_block_path.iterdir(), key=lambda e: e.name):
                if not dev_entry.is_dir():
                    continue

                dev_name = dev_entry.name
                dev_path = f"/dev/{dev_name}"

                # Read size in 512-byte sectors
                size_bytes = 0
                size_file = dev_entry / "size"
                if size_file.exists():
                    try:
                        size_sectors = int(size_file.read_text().strip())
                        size_bytes = size_sectors * 512
                    except (ValueError, OSError):
                        size_bytes = 0

                # Determine device type
                if dev_name.startswith("loop"):
                    dev_type = "loop"
                elif dev_name.startswith("sr") or dev_name.startswith("cdrom"):
                    dev_type = "rom"
                elif (dev_entry / "partition").exists():
                    dev_type = "part"
                else:
                    dev_type = "disk"

                # Read removable flag
                is_removable = False
                removable_file = dev_entry / "removable"
                if removable_file.exists():
                    try:
                        is_removable = removable_file.read_text().strip() == "1"
                    except OSError:
                        pass

                # Read read-only flag
                is_ro = False
                ro_file = dev_entry / "ro"
                if ro_file.exists():
                    try:
                        is_ro = ro_file.read_text().strip() == "1"
                    except OSError:
                        pass

                # Read model and vendor
                model: Optional[str] = None
                vendor: Optional[str] = None
                model_file = dev_entry / "device" / "model"
                if model_file.exists():
                    try:
                        model = model_file.read_text().strip()
                    except OSError:
                        pass

                vendor_file = dev_entry / "device" / "vendor"
                if vendor_file.exists():
                    try:
                        vendor = vendor_file.read_text().strip()
                    except OSError:
                        pass

                # Discover child partitions
                children: List[BlockDevicePartInfo] = []
                try:
                    for child_entry in sorted(dev_entry.iterdir(), key=lambda e: e.name):
                        if not child_entry.is_dir():
                            continue
                        # A partition subdirectory inside /sys/block/<dev> typically starts with the dev name and contains a 'partition' file
                        if child_entry.name.startswith(dev_name) and (child_entry / "partition").exists():
                            part_name = child_entry.name
                            part_path = f"/dev/{part_name}"
                            part_size_bytes = 0
                            part_size_file = child_entry / "size"
                            if part_size_file.exists():
                                try:
                                    part_size_bytes = int(part_size_file.read_text().strip()) * 512
                                except (ValueError, OSError):
                                    part_size_bytes = 0

                            part_ro = False
                            part_ro_file = child_entry / "ro"
                            if part_ro_file.exists():
                                try:
                                    part_ro = part_ro_file.read_text().strip() == "1"
                                except OSError:
                                    pass

                            part_mount = mounts_by_device.get(part_path)
                            part_fs = part_mount.fstype if part_mount else None
                            part_mp = part_mount.mount_point if part_mount else None
                            part_uuid = uuid_map.get(part_path)
                            part_label = label_map.get(part_path)

                            children.append(
                                BlockDevicePartInfo(
                                    name=part_name,
                                    path=part_path,
                                    size_bytes=part_size_bytes,
                                    filesystem=part_fs,
                                    mount_point=part_mp,
                                    uuid=part_uuid,
                                    label=part_label,
                                    is_read_only=part_ro,
                                )
                            )
                except (PermissionError, OSError):
                    pass

                # Direct mount info if device itself is mounted without partitions
                dev_mount = mounts_by_device.get(dev_path)
                dev_fs = dev_mount.fstype if dev_mount else None
                dev_mp = dev_mount.mount_point if dev_mount else None
                dev_uuid = uuid_map.get(dev_path)
                dev_label = label_map.get(dev_path)

                devices.append(
                    BlockDeviceInfo(
                        name=dev_name,
                        path=dev_path,
                        device_type=dev_type,
                        size_bytes=size_bytes,
                        model=model,
                        vendor=vendor,
                        is_removable=is_removable,
                        is_read_only=is_ro,
                        filesystem=dev_fs,
                        mount_point=dev_mp,
                        label=dev_label,
                        uuid=dev_uuid,
                        children=children,
                    )
                )
        except Exception as exc:
            logger.warning(f"Error enumerating block devices from {self.sys_block_path}: {exc}")

        return devices

    def get_storage_overview(self) -> StorageOverview:
        """
        Calculates high-level aggregated storage capacity and utilization metrics.
        """
        filesystems = self.get_filesystems(include_pseudo=False)
        all_mounts = self.get_mounts()
        devices = self.get_block_devices()

        total_bytes = 0
        used_bytes = 0
        available_bytes = 0

        # Avoid double-counting when multiple mount points map to the same device
        seen_devices: Set[str] = set()
        for fs in filesystems:
            if fs.device not in seen_devices:
                total_bytes += fs.total_bytes
                used_bytes += fs.used_bytes
                available_bytes += fs.available_bytes
                seen_devices.add(fs.device)

        usage_percent = (
            round((used_bytes / total_bytes) * 100.0, 1) if total_bytes > 0 else 0.0
        )

        return StorageOverview(
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            available_bytes=available_bytes,
            usage_percent=usage_percent,
            device_count=len([d for d in devices if d.device_type == "disk"]),
            filesystem_count=len(filesystems),
            mount_count=len(all_mounts),
        )


storage_collector = LinuxStorageCollector()
