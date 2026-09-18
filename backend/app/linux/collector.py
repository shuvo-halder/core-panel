from datetime import datetime, timezone
from typing import List

from backend.app.linux.contracts import (
    CPUInfo,
    DiskMountInfo,
    MemoryInfo,
    NetworkInterfaceInfo,
    SystemIdentity,
    SystemOverview,
)
from backend.app.linux.filesystem import disk_collector
from backend.app.linux.network import network_collector
from backend.app.linux.resources import cpu_collector, memory_collector
from backend.app.linux.system_info import system_info_collector


class SystemCollectorService:
    """
    Unified coordinator service for collecting host metrics and hardware telemetry.
    Aggregates domain-specific collectors while keeping concerns decoupled.
    """

    def __init__(
        self,
        sys_info=system_info_collector,
        cpu=cpu_collector,
        mem=memory_collector,
        disk=disk_collector,
        net=network_collector,
    ):
        self.sys_info = sys_info
        self.cpu = cpu
        self.mem = mem
        self.disk = disk
        self.net = net

    def get_system_identity(self) -> SystemIdentity:
        return self.sys_info.get_system_identity()

    async def get_cpu_info(self) -> CPUInfo:
        return await self.cpu.get_cpu_info()

    def get_memory_info(self) -> MemoryInfo:
        return self.mem.get_memory_info()

    def get_disk_mounts(self) -> List[DiskMountInfo]:
        return self.disk.get_disk_mounts()

    def get_network_interfaces(self) -> List[NetworkInterfaceInfo]:
        return self.net.get_network_interfaces()

    async def get_overview(self) -> SystemOverview:
        identity = self.get_system_identity()
        cpu = await self.get_cpu_info()
        memory = self.get_memory_info()
        disks = self.get_disk_mounts()
        network = self.get_network_interfaces()
        timestamp = datetime.now(timezone.utc).isoformat()

        return SystemOverview(
            identity=identity,
            cpu=cpu,
            memory=memory,
            disks=disks,
            network=network,
            timestamp=timestamp,
        )


system_service = SystemCollectorService()
