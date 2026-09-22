from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.linux.logs import log_manager

router = APIRouter(prefix="/logs", tags=["Log Management & Audit Foundation"])


class LogSourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    path: Optional[str] = None
    available: bool
    size_bytes: Optional[int] = None
    last_modified: Optional[str] = None
    description: Optional[str] = None


class LogOverviewResponse(BaseModel):
    available_sources: List[LogSourceResponse]
    journal_available: bool
    total_sources_count: int
    active_sources_count: int
    severity_counts: Dict[str, int]
    latest_timestamp: Optional[str] = None


class LogEntryResponse(BaseModel):
    id: str
    timestamp: str
    source: str
    hostname: Optional[str] = None
    service: Optional[str] = None
    unit: Optional[str] = None
    severity: str
    facility: Optional[str] = None
    message: str
    pid: Optional[int] = None
    uid: Optional[int] = None
    boot_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LogPageResponse(BaseModel):
    items: List[LogEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    source: Optional[str] = None


class AuditLogEntryResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    username: str
    action: str
    resource_type: str
    resource_id: str
    status: str
    details: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    created_at: str


class AuditLogPageResponse(BaseModel):
    items: List[AuditLogEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get(
    "/overview",
    response_model=LogOverviewResponse,
    summary="Get log management overview and metrics",
)
async def get_logs_overview(
    current_user: UserRead = Depends(require_permission("logs.read")),
) -> LogOverviewResponse:
    """Returns high-level statistics, available sources, and severity distributions."""
    overview = await log_manager.get_overview()
    return LogOverviewResponse(
        available_sources=[
            LogSourceResponse(
                id=s.id,
                name=s.name,
                source_type=s.source_type,
                path=s.path,
                available=s.available,
                size_bytes=s.size_bytes,
                last_modified=s.last_modified,
                description=s.description,
            )
            for s in overview.available_sources
        ],
        journal_available=overview.journal_available,
        total_sources_count=overview.total_sources_count,
        active_sources_count=overview.active_sources_count,
        severity_counts=overview.severity_counts,
        latest_timestamp=overview.latest_timestamp,
    )


@router.get(
    "/sources",
    response_model=List[LogSourceResponse],
    summary="List all approved log sources and their host availability",
)
async def get_log_sources(
    current_user: UserRead = Depends(require_permission("logs.read")),
) -> List[LogSourceResponse]:
    """Returns the list of allowlisted log sources with file size, presence, and modification metadata."""
    sources = await log_manager.get_sources()
    return [
        LogSourceResponse(
            id=s.id,
            name=s.name,
            source_type=s.source_type,
            path=s.path,
            available=s.available,
            size_bytes=s.size_bytes,
            last_modified=s.last_modified,
            description=s.description,
        )
        for s in sources
    ]


@router.get(
    "",
    response_model=LogPageResponse,
    summary="Query log entries with filtering and pagination",
)
async def query_logs(
    source: Optional[str] = Query(None, description="Allowlisted source ID (e.g. JOURNAL, SYSLOG, AUTH)"),
    severity: Optional[str] = Query(None, description="Syslog severity level (e.g. ERR, WARNING, INFO)"),
    service: Optional[str] = Query(None, description="Service or daemon name"),
    unit: Optional[str] = Query(None, description="Systemd unit name (e.g. nginx.service)"),
    search: Optional[str] = Query(None, description="Substring search query (max 100 characters)"),
    since: Optional[str] = Query(None, description="ISO8601 start timestamp filter"),
    until: Optional[str] = Query(None, description="ISO8601 end timestamp filter"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Entries per page (max 200)"),
    current_user: UserRead = Depends(require_permission("logs.read")),
) -> LogPageResponse:
    """Queries log records across journal and file sources with strict bounded paging and validation."""
    log_page = await log_manager.query_logs(
        source=source,
        severity=severity,
        service=service,
        unit=unit,
        search=search,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )

    return LogPageResponse(
        items=[
            LogEntryResponse(
                id=item.id,
                timestamp=item.timestamp,
                source=item.source,
                hostname=item.hostname,
                service=item.service,
                unit=item.unit,
                severity=item.severity,
                facility=item.facility,
                message=item.message,
                pid=item.pid,
                uid=item.uid,
                boot_id=item.boot_id,
                metadata=item.metadata,
            )
            for item in log_page.items
        ],
        total=log_page.total,
        page=log_page.page,
        page_size=log_page.page_size,
        total_pages=log_page.total_pages,
        source=log_page.source,
    )


@router.get(
    "/audit",
    response_model=AuditLogPageResponse,
    summary="Query control-plane application audit logs",
)
async def query_audit_logs(
    user_id: Optional[str] = Query(None, description="User ID filter"),
    username: Optional[str] = Query(None, description="Username filter"),
    action: Optional[str] = Query(None, description="Action filter (e.g. cron.create, service.restart)"),
    resource_type: Optional[str] = Query(None, description="Resource type filter"),
    status: Optional[str] = Query(None, description="Execution status filter (SUCCESS or FAILED)"),
    search: Optional[str] = Query(None, description="Substring search query"),
    since: Optional[str] = Query(None, description="ISO8601 start timestamp filter"),
    until: Optional[str] = Query(None, description="ISO8601 end timestamp filter"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Entries per page (max 100)"),
    current_user: UserRead = Depends(require_permission("audit.read")),
) -> AuditLogPageResponse:
    """Queries security and mutation audit records recorded by the control plane with automatic redaction."""
    events, total = audit_service.query_events(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        status=status,
        search=search,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    return AuditLogPageResponse(
        items=[
            AuditLogEntryResponse(
                id=ev["id"],
                user_id=ev["user_id"],
                username=ev["username"],
                action=ev["action"],
                resource_type=ev["resource_type"],
                resource_id=ev["resource_id"],
                status=ev["status"],
                details=ev["details"],
                ip_address=ev["ip_address"],
                request_id=ev["request_id"],
                created_at=ev["created_at"],
            )
            for ev in events
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{id}",
    response_model=LogEntryResponse,
    summary="Get single log entry by identifier",
)
async def get_log_entry(
    id: str,
    source: Optional[str] = Query(None, description="Optional source ID"),
    current_user: UserRead = Depends(require_permission("logs.read")),
) -> LogEntryResponse:
    """Fetches a specific log record by its deterministic identifier."""
    entry = await log_manager.get_log_entry(id, source=source)
    if not entry:
        raise NotFoundError(f"Log entry '{id}' not found", code="LOG_ENTRY_NOT_FOUND")

    return LogEntryResponse(
        id=entry.id,
        timestamp=entry.timestamp,
        source=entry.source,
        hostname=entry.hostname,
        service=entry.service,
        unit=entry.unit,
        severity=entry.severity,
        facility=entry.facility,
        message=entry.message,
        pid=entry.pid,
        uid=entry.uid,
        boot_id=entry.boot_id,
        metadata=entry.metadata,
    )
