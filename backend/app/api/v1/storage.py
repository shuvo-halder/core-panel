from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.linux.storage import storage_collector

router = APIRouter(prefix="/storage", tags=["Storage & Disk Management"])


class BlockDevicePartResponse(BaseModel):
    name: str
    path: str
    size_bytes: int
    filesystem: Optional[str] = None
    mount_point: Optional[str] = None
    uuid: Optional[str] = None
    label: Optional[str] = None
    is_read_only: bool = False


class BlockDeviceResponse(BaseModel):
    name: str
    path: str
    device_type: str
    size_bytes: int
    model: Optional[str] = None
    vendor: Optional[str] = None
    is_removable: bool = False
    is_read_only: bool = False
    filesystem: Optional[str] = None
    mount_point: Optional[str] = None
    label: Optional[str] = None
    uuid: Optional[str] = None
    children: List[BlockDevicePartResponse] = []


class FilesystemResponse(BaseModel):
    device: str
    mount_point: str
    fstype: str
    is_pseudo: bool
    is_read_only: bool
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    label: Optional[str] = None
    uuid: Optional[str] = None
    mount_options: Optional[str] = None


class StorageOverviewResponse(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    device_count: int
    filesystem_count: int
    mount_count: int


@router.get("/overview", response_model=StorageOverviewResponse)
async def get_storage_overview(
    _user: UserRead = Depends(require_permission("storage.read")),
) -> StorageOverviewResponse:
    """
    Returns aggregate storage capacity, utilization metrics, and device/filesystem counts.
    Requires 'storage.read' permission.
    """
    overview = storage_collector.get_storage_overview()
    return StorageOverviewResponse(
        total_bytes=overview.total_bytes,
        used_bytes=overview.used_bytes,
        available_bytes=overview.available_bytes,
        usage_percent=overview.usage_percent,
        device_count=overview.device_count,
        filesystem_count=overview.filesystem_count,
        mount_count=overview.mount_count,
    )


@router.get("/devices", response_model=List[BlockDeviceResponse])
async def get_storage_devices(
    _user: UserRead = Depends(require_permission("storage.read")),
) -> List[BlockDeviceResponse]:
    """
    Discovers physical and block devices from /sys/block and correlated partition mounts.
    Requires 'storage.read' permission.
    """
    devices = storage_collector.get_block_devices()
    return [
        BlockDeviceResponse(
            name=d.name,
            path=d.path,
            device_type=d.device_type,
            size_bytes=d.size_bytes,
            model=d.model,
            vendor=d.vendor,
            is_removable=d.is_removable,
            is_read_only=d.is_read_only,
            filesystem=d.filesystem,
            mount_point=d.mount_point,
            label=d.label,
            uuid=d.uuid,
            children=[
                BlockDevicePartResponse(
                    name=c.name,
                    path=c.path,
                    size_bytes=c.size_bytes,
                    filesystem=c.filesystem,
                    mount_point=c.mount_point,
                    uuid=c.uuid,
                    label=c.label,
                    is_read_only=c.is_read_only,
                )
                for c in d.children
            ],
        )
        for d in devices
    ]


@router.get("/filesystems", response_model=List[FilesystemResponse])
async def get_storage_filesystems(
    include_pseudo: bool = Query(
        default=False,
        description="Whether to include virtual/pseudo filesystems (tmpfs, overlay, sysfs, etc.)",
    ),
    _user: UserRead = Depends(require_permission("storage.read")),
) -> List[FilesystemResponse]:
    """
    Returns mounted filesystems with capacity, usage percentage, and mount options.
    Requires 'storage.read' permission.
    """
    filesystems = storage_collector.get_filesystems(include_pseudo=include_pseudo)
    return [
        FilesystemResponse(
            device=fs.device,
            mount_point=fs.mount_point,
            fstype=fs.fstype,
            is_pseudo=fs.is_pseudo,
            is_read_only=fs.is_read_only,
            total_bytes=fs.total_bytes,
            used_bytes=fs.used_bytes,
            available_bytes=fs.available_bytes,
            usage_percent=fs.usage_percent,
            label=fs.label,
            uuid=fs.uuid,
            mount_options=fs.mount_options,
        )
        for fs in filesystems
    ]


@router.get("/mounts", response_model=List[FilesystemResponse])
async def get_storage_mounts(
    _user: UserRead = Depends(require_permission("storage.read")),
) -> List[FilesystemResponse]:
    """
    Returns all active system mounts from /proc/mounts including pseudo filesystems.
    Requires 'storage.read' permission.
    """
    mounts = storage_collector.get_mounts()
    return [
        FilesystemResponse(
            device=m.device,
            mount_point=m.mount_point,
            fstype=m.fstype,
            is_pseudo=m.is_pseudo,
            is_read_only=m.is_read_only,
            total_bytes=m.total_bytes,
            used_bytes=m.used_bytes,
            available_bytes=m.available_bytes,
            usage_percent=m.usage_percent,
            label=m.label,
            uuid=m.uuid,
            mount_options=m.mount_options,
        )
        for m in mounts
    ]
