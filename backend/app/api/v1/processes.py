from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import BadRequestError, NotFoundError
from backend.app.core.validators import validate_not_protected_pid, validate_pid
from backend.app.ipc.client import ipc_client
from backend.app.linux.processes import process_collector

router = APIRouter(prefix="/processes", tags=["Process Management"])

ALLOWED_SORT_FIELDS = {"cpu", "memory", "pid", "name", "user", "threads", "start_time"}
ALLOWED_ORDER_VALUES = {"asc", "desc"}


class ProcessSummaryResponse(BaseModel):
    pid: int
    ppid: int
    name: str
    username: Optional[str] = None
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


class ProcessListResponse(BaseModel):
    items: List[ProcessSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProcessMutationResponse(BaseModel):
    success: bool
    pid: int
    operation: str
    signal: str
    status: str
    message: str


@router.get("", response_model=ProcessListResponse)
async def list_processes(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(default=None, max_length=100, description="Process search query"),
    sort: str = Query(default="cpu", description="Field to sort by"),
    order: str = Query(default="desc", description="Sort order: 'asc' or 'desc'"),
    _: UserRead = Depends(require_permission("processes.read")),
) -> ProcessListResponse:
    """
    Lists active host processes with CPU, memory, thread metrics, and state normalization.
    Uses unprivileged direct /proc inspection without executing shell or child commands.
    """
    clean_sort = sort.lower().strip()
    if clean_sort not in ALLOWED_SORT_FIELDS:
        raise BadRequestError(
            f"Invalid sort field '{sort}'. Allowed fields: {', '.join(sorted(ALLOWED_SORT_FIELDS))}",
            code="INVALID_SORT_FIELD",
        )

    clean_order = order.lower().strip()
    if clean_order not in ALLOWED_ORDER_VALUES:
        raise BadRequestError(
            f"Invalid order '{order}'. Allowed values: 'asc', 'desc'",
            code="INVALID_ORDER",
        )

    result = process_collector.list_processes(
        page=page,
        page_size=page_size,
        search=search,
        sort_by=clean_sort,
        order=clean_order,
    )

    items = [
        ProcessSummaryResponse(
            pid=p.pid,
            ppid=p.ppid,
            name=p.name,
            username=p.username,
            uid=p.uid,
            state=p.state,
            cpu_percent=p.cpu_percent,
            memory_rss_bytes=p.memory_rss_bytes,
            memory_vsz_bytes=p.memory_vsz_bytes,
            memory_percent=p.memory_percent,
            start_time=p.start_time,
            start_time_ticks=p.start_time_ticks,
            threads=p.threads,
            command_summary=p.command_summary,
            is_protected=p.is_protected,
        )
        for p in result.items
    ]

    return ProcessListResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/{pid}", response_model=ProcessSummaryResponse)
async def get_process(
    pid: int,
    _: UserRead = Depends(require_permission("processes.read")),
) -> ProcessSummaryResponse:
    """Retrieves metadata and metrics for a specific process ID."""
    valid_pid = validate_pid(pid)
    process = process_collector.get_process(valid_pid)

    if not process:
        raise NotFoundError(f"Process with PID {valid_pid} not found", code="PROCESS_NOT_FOUND")

    return ProcessSummaryResponse(
        pid=process.pid,
        ppid=process.ppid,
        name=process.name,
        username=process.username,
        uid=process.uid,
        state=process.state,
        cpu_percent=process.cpu_percent,
        memory_rss_bytes=process.memory_rss_bytes,
        memory_vsz_bytes=process.memory_vsz_bytes,
        memory_percent=process.memory_percent,
        start_time=process.start_time,
        start_time_ticks=process.start_time_ticks,
        threads=process.threads,
        command_summary=process.command_summary,
        is_protected=process.is_protected,
    )


async def _execute_process_mutation(
    request: Request,
    current_user: UserRead,
    pid: int,
    action: str,
    operation_name: str,
) -> ProcessMutationResponse:
    """
    Helper executing a validated process signal mutation via CoreAgent over IPC with audit logging.
    """
    valid_pid = validate_not_protected_pid(pid)
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    # Inspect process beforehand to check existence and retrieve start_time_ticks for TOCTOU verification
    existing_proc = process_collector.get_process(valid_pid)
    if not existing_proc:
        raise NotFoundError(
            f"Process with PID {valid_pid} does not exist or has already terminated",
            code="PROCESS_NOT_FOUND",
        )

    if existing_proc.is_protected:
        raise BadRequestError(
            f"Process {valid_pid} ({existing_proc.name}) is protected and cannot be signaled",
            code="PROTECTED_PROCESS",
        )

    ipc_payload = {
        "pid": valid_pid,
        "start_time_ticks": existing_proc.start_time_ticks,
    }

    try:
        result = await ipc_client.execute(
            operation=operation_name,
            payload=ipc_payload,
            request_id=req_id,
        )

        audit_service.log_event(
            user_id=current_user.id,
            username=current_user.username,
            action=f"processes.{action}",
            resource_type="process",
            resource_id=str(valid_pid),
            status="SUCCESS",
            details=f"Successfully sent signal for {action} to PID {valid_pid} ({existing_proc.name})",
            ip_address=client_ip,
            request_id=req_id,
        )

        return ProcessMutationResponse(
            success=True,
            pid=valid_pid,
            operation=action,
            signal=result.get("signal", "SIGTERM" if action == "terminate" else "SIGKILL"),
            status=result.get("status", "signal_sent"),
            message=result.get("message", f"Signal delivered to process {valid_pid}"),
        )

    except Exception as exc:
        audit_service.log_event(
            user_id=current_user.id,
            username=current_user.username,
            action=f"processes.{action}",
            resource_type="process",
            resource_id=str(valid_pid),
            status="FAILED",
            details=str(exc),
            ip_address=client_ip,
            request_id=req_id,
        )
        raise


@router.post("/{pid}/terminate", response_model=ProcessMutationResponse)
async def terminate_process(
    pid: int,
    request: Request,
    current_user: UserRead = Depends(require_permission("processes.terminate")),
) -> ProcessMutationResponse:
    """Sends SIGTERM to a validated, non-protected target process via CoreAgent."""
    return await _execute_process_mutation(
        request, current_user, pid, action="terminate", operation_name="process.terminate"
    )


@router.post("/{pid}/kill", response_model=ProcessMutationResponse)
async def kill_process(
    pid: int,
    request: Request,
    current_user: UserRead = Depends(require_permission("processes.kill")),
) -> ProcessMutationResponse:
    """Sends SIGKILL to a validated, non-protected target process via CoreAgent."""
    return await _execute_process_mutation(
        request, current_user, pid, action="kill", operation_name="process.kill"
    )
