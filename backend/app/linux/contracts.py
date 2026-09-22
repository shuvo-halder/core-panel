from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
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
class BlockDevicePartInfo:
    name: str
    path: str
    size_bytes: int
    filesystem: Optional[str]
    mount_point: Optional[str]
    uuid: Optional[str]
    label: Optional[str]
    is_read_only: bool


@dataclass(frozen=True)
class BlockDeviceInfo:
    name: str
    path: str
    device_type: str  # disk, part, loop, rom
    size_bytes: int
    model: Optional[str]
    vendor: Optional[str]
    is_removable: bool
    is_read_only: bool
    filesystem: Optional[str]
    mount_point: Optional[str]
    label: Optional[str]
    uuid: Optional[str]
    children: List[BlockDevicePartInfo]


@dataclass(frozen=True)
class FilesystemInfo:
    device: str
    mount_point: str
    fstype: str
    is_pseudo: bool
    is_read_only: bool
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    label: Optional[str]
    uuid: Optional[str]
    mount_options: Optional[str] = None


@dataclass(frozen=True)
class StorageOverview:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    device_count: int
    filesystem_count: int
    mount_count: int


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
class IPAddressInfo:
    family: str  # "ipv4" | "ipv6"
    address: str
    prefix_length: Optional[int] = None
    scope: Optional[str] = None


@dataclass(frozen=True)
class InterfaceStats:
    rx_bytes: int
    rx_packets: int
    rx_errors: int
    rx_dropped: int
    tx_bytes: int
    tx_packets: int
    tx_errors: int
    tx_dropped: int


@dataclass(frozen=True)
class InterfaceDetailInfo:
    name: str
    index: Optional[int]
    iftype: str
    operational_state: str  # "up", "down", "unknown", "dormant"
    administrative_state: Optional[str]
    mtu: Optional[int]
    mac_address: Optional[str]
    flags: List[str]
    is_loopback: bool
    is_virtual: bool
    is_physical: bool
    ipv4_addresses: List[str]
    ipv6_addresses: List[str]
    addresses: List[IPAddressInfo]
    stats: InterfaceStats
    speed_mbps: Optional[int] = None
    duplex: Optional[str] = None


@dataclass(frozen=True)
class RouteInfo:
    destination: str
    gateway: str
    interface: str
    flags: str
    metric: int
    family: str  # "ipv4" | "ipv6"
    mask: Optional[str] = None
    is_default: bool = False


@dataclass(frozen=True)
class DNSConfigInfo:
    nameservers: List[str]
    search_domains: List[str]
    options: List[str]
    source: str
    is_symlink: bool
    symlink_target: Optional[str] = None


@dataclass(frozen=True)
class NetworkOverview:
    total_interfaces: int
    up_interfaces: int
    down_interfaces: int
    physical_interfaces: int
    virtual_interfaces: int
    loopback_interfaces: int
    ipv4_addresses: List[str]
    ipv6_addresses: List[str]
    default_ipv4_route: Optional[str]
    default_ipv6_route: Optional[str]
    dns_servers: List[str]


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


class IStorageCollector(ABC):
    """Contract for safe Linux storage discovery, block device inventory, and filesystems."""

    @abstractmethod
    def get_storage_overview(self) -> StorageOverview:
        pass

    @abstractmethod
    def get_block_devices(self) -> List[BlockDeviceInfo]:
        pass

    @abstractmethod
    def get_filesystems(self, include_pseudo: bool = False) -> List[FilesystemInfo]:
        pass

    @abstractmethod
    def get_mounts(self) -> List[FilesystemInfo]:
        pass


class INetworkCollector(ABC):
    """Contract for safe, read-only Linux network discovery, interfaces, routing, and DNS."""

    @abstractmethod
    def get_network_interfaces(self) -> List[NetworkInterfaceInfo]:
        """Legacy lightweight network interface summary used by SystemOverview."""
        pass

    @abstractmethod
    def get_interface_details(self) -> List[InterfaceDetailInfo]:
        """Detailed interface inventory with MTU, MAC, type, flags, stats, and addresses."""
        pass

    @abstractmethod
    def get_interface_by_name(self, name: str) -> Optional[InterfaceDetailInfo]:
        """Detailed information for a single specific network interface."""
        pass

    @abstractmethod
    def get_routes(self) -> List[RouteInfo]:
        """Read-only IPv4 and IPv6 routing table entries."""
        pass

    @abstractmethod
    def get_dns_config(self) -> DNSConfigInfo:
        """Read-only DNS configuration (nameservers, search domains, source)."""
        pass

    @abstractmethod
    def get_network_overview(self) -> NetworkOverview:
        """Aggregated network KPIs and summary metrics."""
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


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    name: str
    username: Optional[str]
    uid: int
    state: str
    cpu_percent: float
    memory_rss_bytes: int
    memory_vsz_bytes: int
    memory_percent: float
    start_time: str
    start_time_ticks: int
    threads: int
    command_summary: Optional[str] = None
    is_protected: bool = False


@dataclass(frozen=True)
class ProcessListResult:
    items: List[ProcessInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True)
class PackageManagerInfo:
    manager: str  # "apt" | "dpkg" | "rpm" | "dnf" | "yum" | "apk" | "pacman" | "unknown"
    family: str  # "debian" | "rhel" | "alpine" | "arch" | "unknown"
    distribution: str
    version: str
    architecture: str
    available: bool


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str
    architecture: str
    status: str  # "installed" | "config-files" | "half-installed" | "unknown"
    summary: str
    source: Optional[str] = None
    installed_size_kb: Optional[int] = None


@dataclass(frozen=True)
class PackageDetails:
    name: str
    version: str
    architecture: str
    status: str
    summary: str
    description: str
    source: Optional[str] = None
    section: Optional[str] = None
    maintainer: Optional[str] = None
    homepage: Optional[str] = None
    installed_size_kb: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepositoryInfo:
    name: str
    type: str  # "deb" | "deb-src" | "rpm" | "unknown"
    uri: str
    enabled: bool
    distribution: Optional[str] = None
    components: List[str] = field(default_factory=list)
    source_file: Optional[str] = None


@dataclass(frozen=True)
class PackageUpdateInfo:
    name: str
    installed_version: str
    candidate_version: str
    repository: Optional[str] = None
    update_available: bool = True
    urgency: Optional[str] = None


@dataclass(frozen=True)
class PackageListResult:
    items: List[PackageInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True)
class PackageOverview:
    manager: str
    family: str
    distribution: str
    architecture: str
    installed_package_count: int
    packages_with_updates: Optional[int] = None
    repository_count: int = 0
    manager_available: bool = True
    update_status_message: Optional[str] = None


class IPackageManager(ABC):
    """Contract for safe, read-only Linux package inventory, status, and repository inspection."""

    @abstractmethod
    def get_manager_info(self) -> PackageManagerInfo:
        pass

    @abstractmethod
    def get_overview(self) -> PackageOverview:
        pass

    @abstractmethod
    def list_packages(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        sort_by: str = "name",
        order: str = "asc",
    ) -> PackageListResult:
        pass

    @abstractmethod
    def get_package_details(self, name: str) -> Optional[PackageDetails]:
        pass

    @abstractmethod
    def list_repositories(self) -> List[RepositoryInfo]:
        pass

    @abstractmethod
    def list_updates(self) -> List[PackageUpdateInfo]:
        pass


class IProcessCollector(ABC):
    """Contract for safe, unprivileged Linux process discovery and metrics collection."""

    @abstractmethod
    def list_processes(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        sort_by: str = "cpu",
        order: str = "desc",
    ) -> ProcessListResult:
        pass

    @abstractmethod
    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        pass


class IProcessProvider(ABC):
    """Contract for process monitoring."""

    @abstractmethod
    async def list_processes(self, limit: int = 50) -> List[Dict[str, Any]]:
        pass


class CronSource:
    """Linux cron source identifiers."""

    USER_CRONTAB = "USER_CRONTAB"
    SYSTEM_CRONTAB = "SYSTEM_CRONTAB"
    CRON_D_DIRECTORY = "CRON_D_DIRECTORY"
    PERIODIC_DIRECTORY = "PERIODIC_DIRECTORY"


@dataclass(frozen=True)
class CronJob:
    """Structured Linux cron job representation."""

    id: str
    owner: str
    schedule: str
    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str
    command: str
    enabled: bool
    source: str
    special_expression: Optional[str] = None
    comment: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    description: Optional[str] = None
    is_editable: bool = True
    original_hash: Optional[str] = None


@dataclass(frozen=True)
class CronListResult:
    """Paginated cron job query result."""

    items: List[CronJob]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True)
class CronOverview:
    """High-level metrics for scheduled cron jobs across the Linux host."""

    total_jobs: int
    active_jobs: int
    disabled_jobs: int
    users_with_crontabs: int
    user_jobs_count: int
    system_jobs_count: int
    cron_d_jobs_count: int
    periodic_jobs_count: int
    available_sources: List[str]


class ICronManager(ABC):
    """Contract for safe Linux cron inspection and user crontab management."""

    @abstractmethod
    async def get_overview(self) -> CronOverview:
        pass

    @abstractmethod
    async def list_jobs(
        self,
        page: int = 1,
        page_size: int = 50,
        owner: Optional[str] = None,
        source: Optional[str] = None,
        enabled: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> CronListResult:
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[CronJob]:
        pass

    @abstractmethod
    async def create_job(
        self,
        owner: str,
        schedule: str,
        command: str,
        comment: Optional[str] = None,
        enabled: bool = True,
    ) -> CronJob:
        pass

    @abstractmethod
    async def update_job(
        self,
        job_id: str,
        owner: str,
        schedule: str,
        command: str,
        comment: Optional[str] = None,
        enabled: bool = True,
        expected_hash: Optional[str] = None,
    ) -> CronJob:
        pass

    @abstractmethod
    async def delete_job(
        self,
        job_id: str,
        owner: str,
        expected_hash: Optional[str] = None,
    ) -> bool:
        pass


class ILinuxProvider(ABC):
    """Consolidated provider contract for system interaction."""

    os: IOSProvider
    runner: ICommandRunner


# -----------------------------------------------------------------------------
# Phase 10: Log Management & Audit Foundation Contracts
# -----------------------------------------------------------------------------


class LogSourceType(str, Enum):
    JOURNAL = "JOURNAL"
    FILE = "FILE"


class LogSeverity(str, Enum):
    EMERG = "EMERG"
    ALERT = "ALERT"
    CRIT = "CRIT"
    ERR = "ERR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFO = "INFO"
    DEBUG = "DEBUG"


@dataclass(frozen=True)
class LogSource:
    """Represents an approved, allowlisted log source."""

    id: str
    name: str
    source_type: str  # "JOURNAL" or "FILE"
    path: Optional[str]
    available: bool
    size_bytes: Optional[int] = None
    last_modified: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class LogEntry:
    """Structured, sanitized log event."""

    id: str
    timestamp: str
    source: str
    hostname: Optional[str] = None
    service: Optional[str] = None
    unit: Optional[str] = None
    severity: str = "INFO"
    facility: Optional[str] = None
    message: str = ""
    pid: Optional[int] = None
    uid: Optional[int] = None
    boot_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class LogOverview:
    """Aggregated metrics across log sources."""

    available_sources: List[LogSource]
    journal_available: bool
    total_sources_count: int
    active_sources_count: int
    severity_counts: Dict[str, int]
    latest_timestamp: Optional[str] = None


@dataclass(frozen=True)
class LogPage:
    """Paginated collection of log entries."""

    items: List[LogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int
    source: Optional[str] = None


@dataclass(frozen=True)
class AuditLogEntry:
    """Safe read-only representation of an application audit record."""

    id: str
    user_id: Optional[str]
    username: str
    action: str
    resource_type: str
    resource_id: str
    status: str
    details: Optional[str]
    ip_address: Optional[str]
    request_id: Optional[str]
    created_at: str


@dataclass(frozen=True)
class AuditLogPage:
    """Paginated application audit log page."""

    items: List[AuditLogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


class ILogManager(ABC):
    """Abstract contract for safe Linux log discovery and read-only inspection."""

    @abstractmethod
    async def get_overview(self) -> LogOverview:
        pass

    @abstractmethod
    async def get_sources(self) -> List[LogSource]:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_log_entry(
        self, entry_id: str, source: Optional[str] = None
    ) -> Optional[LogEntry]:
        pass

