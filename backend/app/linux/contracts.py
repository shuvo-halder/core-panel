from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CommandResult:
    """Structured result of command execution."""

    executable: str
    args: List[str]
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0


class ICommandRunner(ABC):
    """Abstract contract for secure command execution."""

    @abstractmethod
    async def run(
        self,
        executable: str,
        args: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1024 * 1024,
    ) -> CommandResult:
        """Run an approved executable with arguments."""
        pass


@dataclass(frozen=True)
class OSInfo:
    distribution: str
    version: str
    architecture: str
    kernel_version: str
    is_supported: bool


@dataclass(frozen=True)
class SystemIdentity:
    hostname: str
    operating_system: str
    distribution: str
    distribution_version: str
    kernel_version: str
    architecture: str
    uptime_seconds: float
    boot_time: Optional[str] = None


@dataclass(frozen=True)
class CPULoadAverage:
    load_1m: float
    load_5m: float
    load_15m: float


@dataclass(frozen=True)
class CPUInfo:
    logical_cores: int
    model_name: str
    usage_percent: float
    load_average: CPULoadAverage


@dataclass(frozen=True)
class SwapInfo:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float


@dataclass(frozen=True)
class MemoryInfo:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    free_bytes: int
    usage_percent: float
    swap: SwapInfo


@dataclass(frozen=True)
class DiskMountInfo:
    device: str
    mount_point: str
    filesystem_type: str
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float


@dataclass(frozen=True)
class NetworkInterfaceInfo:
    name: str
    state: str
    mac_address: str
    ipv4_addresses: List[str]
    ipv6_addresses: List[str]
    rx_bytes: int
    tx_bytes: int


@dataclass(frozen=True)
class ServiceInfo:
    unit: str
    description: str
    load_state: str
    active_state: str
    sub_state: str
    enabled: str
    main_pid: Optional[int] = None


@dataclass(frozen=True)
class SystemOverview:
    identity: SystemIdentity
    cpu: CPUInfo
    memory: MemoryInfo
    disks: List[DiskMountInfo]
    network: List[NetworkInterfaceInfo]
    timestamp: str


class IServiceCollector(ABC):
    """Contract for systemd service discovery and status inspection."""

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    async def list_services(self) -> List[ServiceInfo]:
        pass

    @abstractmethod
    async def get_service(self, unit: str) -> Optional[ServiceInfo]:
        pass


class ISystemInfoCollector(ABC):
    """Contract for host identification and uptime collection."""

    @abstractmethod
    def get_system_identity(self) -> SystemIdentity:
        pass


class ICPUCollector(ABC):
    """Contract for CPU specifications and real-time utilization collection."""

    @abstractmethod
    async def get_cpu_info(self) -> CPUInfo:
        pass


class IMemoryCollector(ABC):
    """Contract for RAM and swap memory collection."""

    @abstractmethod
    def get_memory_info(self) -> MemoryInfo:
        pass


class IDiskCollector(ABC):
    """Contract for local mounted filesystem statistics collection."""

    @abstractmethod
    def get_disk_mounts(self) -> List[DiskMountInfo]:
        pass


class INetworkCollector(ABC):
    """Contract for network interfaces and traffic metrics collection."""

    @abstractmethod
    def get_network_interfaces(self) -> List[NetworkInterfaceInfo]:
        pass


class IOSProvider(ABC):
    """Contract for operating system identification and inspection."""

    @abstractmethod
    def detect_os(self) -> OSInfo:
        pass


class ISystemdProvider(ABC):
    """Contract for Systemd service management (Pending Phase 10)."""

    @abstractmethod
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Pending Phase 10 implementation."""
        pass

    @abstractmethod
    async def restart_service(self, service_name: str) -> bool:
        """Pending Phase 10 implementation."""
        pass


class IPackageManager(ABC):
    """Contract for package management (Pending Phase 11)."""

    @abstractmethod
    async def is_package_installed(self, package_name: str) -> bool:
        """Pending Phase 11 implementation."""
        pass


class IFilesystemProvider(ABC):
    """Contract for safe filesystem operations (Pending Phase 18)."""

    @abstractmethod
    def resolve_safe_path(self, user_path: str, base_root: str) -> str:
        """Pending Phase 18 implementation."""
        pass


class IProcessProvider(ABC):
    """Contract for process monitoring (Pending Phase 9)."""

    @abstractmethod
    async def list_processes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Pending Phase 9 implementation."""
        pass


class ILinuxProvider(ABC):
    """Consolidated provider contract for system interaction."""

    os: IOSProvider
    runner: ICommandRunner
