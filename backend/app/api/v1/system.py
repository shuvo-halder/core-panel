from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.linux.collector import system_service

router = APIRouter(prefix="/system", tags=["System Monitoring"])


class SystemIdentityResponse(BaseModel):
    hostname: str
    operating_system: str
    distribution: str
    distribution_version: str
    kernel_version: str
    architecture: str
    uptime_seconds: float
    boot_time: Optional[str] = None


class CPULoadAverageResponse(BaseModel):
    load_1m: float
    load_5m: float
    load_15m: float


class CPUResponse(BaseModel):
    logical_cores: int
    model_name: str
    usage_percent: float
    load_average: CPULoadAverageResponse


class SwapResponse(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float


class MemoryResponse(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    free_bytes: int
    usage_percent: float
    swap: SwapResponse


class DiskMountResponse(BaseModel):
    device: str
    mount_point: str
    filesystem_type: str
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float


class NetworkInterfaceResponse(BaseModel):
    name: str
    state: str
    mac_address: str
    ipv4_addresses: List[str]
    ipv6_addresses: List[str]
    rx_bytes: int
    tx_bytes: int


class SystemOverviewResponse(BaseModel):
    identity: SystemIdentityResponse
    cpu: CPUResponse
    memory: MemoryResponse
    disks: List[DiskMountResponse]
    network: List[NetworkInterfaceResponse]
    timestamp: str


@router.get("/overview", response_model=SystemOverviewResponse)
async def get_system_overview(
    _: UserRead = Depends(require_permission("system.read")),
) -> SystemOverviewResponse:
    """Consolidated host overview including identity, CPU, memory, disk mounts, and network."""
    overview = await system_service.get_overview()
    return overview  # FastAPI / Pydantic automatically serializes dataclass


@router.get("/info", response_model=SystemIdentityResponse)
async def get_system_info(
    _: UserRead = Depends(require_permission("system.read")),
) -> SystemIdentityResponse:
    """Operating system identity, distribution version, kernel, architecture, and uptime."""
    return system_service.get_system_identity()


@router.get("/cpu", response_model=CPUResponse)
async def get_cpu_metrics(
    _: UserRead = Depends(require_permission("system.read")),
) -> CPUResponse:
    """CPU hardware specifications, multi-core load averages, and real-time utilization."""
    return await system_service.get_cpu_info()


@router.get("/memory", response_model=MemoryResponse)
async def get_memory_metrics(
    _: UserRead = Depends(require_permission("system.read")),
) -> MemoryResponse:
    """RAM physical memory and swap utilization metrics."""
    return system_service.get_memory_info()


@router.get("/disks", response_model=List[DiskMountResponse])
async def get_disk_mounts(
    _: UserRead = Depends(require_permission("system.read")),
) -> List[DiskMountResponse]:
    """Mounted local filesystem capacities and utilization percentages."""
    return system_service.get_disk_mounts()


@router.get("/network", response_model=List[NetworkInterfaceResponse])
async def get_network_interfaces(
    _: UserRead = Depends(require_permission("system.read")),
) -> List[NetworkInterfaceResponse]:
    """Network interfaces, operational states, MAC/IP addresses, and traffic counters."""
    return system_service.get_network_interfaces()
