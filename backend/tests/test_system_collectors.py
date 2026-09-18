from pathlib import Path

import pytest

from backend.app.linux.collector import SystemCollectorService
from backend.app.linux.contracts import (
    CPUInfo,
    DiskMountInfo,
    MemoryInfo,
    NetworkInterfaceInfo,
    SystemIdentity,
    SystemOverview,
)
from backend.app.linux.filesystem import DiskCollector
from backend.app.linux.network import NetworkCollector
from backend.app.linux.resources import CPUCollector, MemoryCollector
from backend.app.linux.system_info import SystemInfoCollector


def test_system_info_collector_real():
    collector = SystemInfoCollector()
    info = collector.get_system_identity()

    assert isinstance(info, SystemIdentity)
    assert info.hostname != ""
    assert info.operating_system == "Linux"
    assert info.uptime_seconds >= 0.0
    assert info.architecture != ""


def test_system_info_collector_mock(tmp_path: Path):
    mock_proc = tmp_path / "proc"
    mock_proc.mkdir()

    (mock_proc / "uptime").write_text("12345.67 98765.43\n")
    (mock_proc / "stat").write_text("cpu  100 20 30 400 50 0 0 0 0 0\nbtime 1700000000\n")

    collector = SystemInfoCollector(proc_path=mock_proc)
    info = collector.get_system_identity()

    assert info.uptime_seconds == 12345.67
    assert info.boot_time is not None
    assert "2023" in info.boot_time or "T" in info.boot_time


@pytest.mark.asyncio
async def test_cpu_collector_real():
    collector = CPUCollector()
    cpu = await collector.get_cpu_info()

    assert isinstance(cpu, CPUInfo)
    assert cpu.logical_cores >= 1
    assert cpu.model_name != ""
    assert 0.0 <= cpu.usage_percent <= 100.0
    assert cpu.load_average.load_1m >= 0.0


@pytest.mark.asyncio
async def test_cpu_collector_mock(tmp_path: Path):
    mock_proc = tmp_path / "proc"
    mock_proc.mkdir()

    (mock_proc / "cpuinfo").write_text(
        "processor : 0\nmodel name : Intel(R) Xeon(R) Platinum 8370C\n\n"
    )
    (mock_proc / "loadavg").write_text("0.45 0.30 0.15 1/120 12345\n")
    (mock_proc / "stat").write_text("cpu  100 20 30 850 0 0 0 0 0 0\n")

    collector = CPUCollector(proc_path=mock_proc)
    cpu = await collector.get_cpu_info()

    assert cpu.model_name == "Intel(R) Xeon(R) Platinum 8370C"
    assert cpu.load_average.load_1m == 0.45
    assert cpu.load_average.load_5m == 0.30
    assert cpu.load_average.load_15m == 0.15


def test_memory_collector_real():
    collector = MemoryCollector()
    mem = collector.get_memory_info()

    assert isinstance(mem, MemoryInfo)
    assert mem.total_bytes > 0
    assert mem.available_bytes >= 0
    assert 0.0 <= mem.usage_percent <= 100.0
    assert mem.swap.total_bytes >= 0


def test_memory_collector_mock(tmp_path: Path):
    mock_proc = tmp_path / "proc"
    mock_proc.mkdir()

    meminfo_content = (
        "MemTotal:        16384000 kB\n"
        "MemFree:          4096000 kB\n"
        "MemAvailable:     8192000 kB\n"
        "Buffers:           512000 kB\n"
        "Cached:           3584000 kB\n"
        "SwapTotal:        2048000 kB\n"
        "SwapFree:         1024000 kB\n"
    )
    (mock_proc / "meminfo").write_text(meminfo_content)

    collector = MemoryCollector(proc_path=mock_proc)
    mem = collector.get_memory_info()

    assert mem.total_bytes == 16384000 * 1024
    assert mem.available_bytes == 8192000 * 1024
    assert mem.free_bytes == 4096000 * 1024
    assert mem.used_bytes == (16384000 - 8192000) * 1024
    assert mem.usage_percent == 50.0

    assert mem.swap.total_bytes == 2048000 * 1024
    assert mem.swap.free_bytes == 1024000 * 1024
    assert mem.swap.used_bytes == 1024000 * 1024
    assert mem.swap.usage_percent == 50.0


def test_disk_collector_real():
    collector = DiskCollector()
    mounts = collector.get_disk_mounts()

    assert isinstance(mounts, list)
    if mounts:
        first = mounts[0]
        assert isinstance(first, DiskMountInfo)
        assert first.mount_point != ""
        assert first.total_bytes > 0
        assert 0.0 <= first.usage_percent <= 100.0


def test_disk_collector_mock(tmp_path: Path):
    mock_proc = tmp_path / "proc"
    mock_proc.mkdir()

    mounts_content = (
        "/dev/sda1 / ext4 rw,relatime 0 0\n"
        "proc /proc proc rw 0 0\n"
        "sysfs /sys sysfs rw 0 0\n"
        "/dev/loop0 /snap/core/123 squashfs ro 0 0\n"
        "/dev/sdb1 /data ext4 rw,relatime 0 0\n"
    )
    (mock_proc / "mounts").write_text(mounts_content)

    collector = DiskCollector(mounts_path=mock_proc / "mounts")
    mounts = collector.get_disk_mounts()

    # / is valid on real system
    mount_points = [m.mount_point for m in mounts]
    assert "/" in mount_points
    assert "/proc" not in mount_points
    assert "/sys" not in mount_points
    assert "/snap/core/123" not in mount_points


def test_network_collector_real():
    collector = NetworkCollector()
    interfaces = collector.get_network_interfaces()

    assert isinstance(interfaces, list)
    if interfaces:
        first = interfaces[0]
        assert isinstance(first, NetworkInterfaceInfo)
        assert first.name != ""
        assert first.state in ("up", "down", "unknown")


def test_network_collector_mock(tmp_path: Path):
    mock_proc = tmp_path / "proc"
    mock_proc.mkdir()
    mock_sys = tmp_path / "sys" / "class" / "net"
    mock_sys.mkdir(parents=True)

    eth0_dir = mock_sys / "eth0"
    eth0_dir.mkdir()
    (eth0_dir / "operstate").write_text("up\n")
    (eth0_dir / "address").write_text("02:42:ac:11:00:02\n")

    proc_dev_content = (
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
        "  eth0: 1048576      100    0    0    0     0          0         0   524288       50    0    0    0     0       0          0\n"
    )
    (mock_proc / "dev").write_text(proc_dev_content)

    inet6_content = "fe800000000000000242acfffe110002 02 40 20 80 eth0\n"
    (mock_proc / "if_inet6").write_text(inet6_content)

    collector = NetworkCollector(
        sys_net_path=mock_sys,
        proc_dev_path=mock_proc / "dev",
        proc_inet6_path=mock_proc / "if_inet6",
    )
    interfaces = collector.get_network_interfaces()

    assert len(interfaces) == 1
    eth0 = interfaces[0]
    assert eth0.name == "eth0"
    assert eth0.state == "up"
    assert eth0.mac_address == "02:42:ac:11:00:02"
    assert eth0.rx_bytes == 1048576
    assert eth0.tx_bytes == 524288
    assert len(eth0.ipv6_addresses) == 1
    assert "fe80:" in eth0.ipv6_addresses[0]


@pytest.mark.asyncio
async def test_system_service_overview():
    service = SystemCollectorService()
    overview = await service.get_overview()

    assert isinstance(overview, SystemOverview)
    assert overview.identity.operating_system == "Linux"
    assert overview.cpu.logical_cores >= 1
    assert overview.memory.total_bytes > 0
    assert isinstance(overview.disks, list)
    assert isinstance(overview.network, list)
    assert overview.timestamp != ""
