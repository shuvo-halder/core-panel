from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.linux.cron import cron_manager

router = APIRouter(prefix="/cron", tags=["Scheduled Jobs / Cron Management"])


class CronJobResponse(BaseModel):
    id: str
    owner: str
    schedule: str
    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str
    special_expression: Optional[str] = None
    command: str
    comment: Optional[str] = None
    enabled: bool
    source: str
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    description: Optional[str] = None
    is_editable: bool
    original_hash: Optional[str] = None


class CronListResponse(BaseModel):
    items: List[CronJobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CronOverviewResponse(BaseModel):
    total_jobs: int
    active_jobs: int
    disabled_jobs: int
    users_with_crontabs: int
    user_jobs_count: int
    system_jobs_count: int
    cron_d_jobs_count: int
    periodic_jobs_count: int
    available_sources: List[str]


class CronEligibleUserResponse(BaseModel):
    username: str
    uid: int
    gid: int
    home: str
    shell: str


class CronJobCreateRequest(BaseModel):
    owner: str = Field(..., description="Target OS username owning the crontab entry")
    schedule: str = Field(..., description="5-field cron schedule or special expression (@daily, etc.)")
    command: str = Field(..., description="The command/script path to execute via cron")
    comment: Optional[str] = Field(None, description="Optional descriptive note attached to this job")
    enabled: bool = Field(True, description="Whether this job is active or commented out")


class CronJobUpdateRequest(BaseModel):
    owner: str = Field(..., description="Target OS username owning the crontab entry")
    schedule: str = Field(..., description="5-field cron schedule or special expression (@daily, etc.)")
    command: str = Field(..., description="The command/script path to execute via cron")
    comment: Optional[str] = Field(None, description="Optional descriptive note attached to this job")
    enabled: bool = Field(True, description="Whether this job is active or commented out")
    expected_hash: Optional[str] = Field(None, description="Hash fingerprint for optimistic concurrency verification")


class CronJobDeleteRequest(BaseModel):
    owner: str = Field(..., description="Target OS username owning the crontab entry")
    expected_hash: Optional[str] = Field(None, description="Hash fingerprint for optimistic concurrency verification")


class CronJobMutationResponse(BaseModel):
    success: bool
    operation: str
    job: CronJobResponse
    message: str


class CronJobDeleteResponse(BaseModel):
    success: bool
    operation: str
    deleted_id: str
    owner: str
    message: str


# -----------------------------------------------------------------------------
# Read Endpoints (Guarded by cron.read)
# -----------------------------------------------------------------------------

@router.get("/overview", response_model=CronOverviewResponse)
async def get_cron_overview(
    _: UserRead = Depends(require_permission("cron.read")),
) -> CronOverviewResponse:
    """Retrieves aggregated metrics for scheduled jobs across all discovered sources."""
    overview = await cron_manager.get_overview()
    return CronOverviewResponse(
        total_jobs=overview.total_jobs,
        active_jobs=overview.active_jobs,
        disabled_jobs=overview.disabled_jobs,
        users_with_crontabs=overview.users_with_crontabs,
        user_jobs_count=overview.user_jobs_count,
        system_jobs_count=overview.system_jobs_count,
        cron_d_jobs_count=overview.cron_d_jobs_count,
        periodic_jobs_count=overview.periodic_jobs_count,
        available_sources=overview.available_sources,
    )


@router.get("/users", response_model=List[CronEligibleUserResponse])
async def list_cron_eligible_users(
    _: UserRead = Depends(require_permission("cron.read")),
) -> List[CronEligibleUserResponse]:
    """Lists local OS user accounts that are eligible to possess user crontabs."""
    users = cron_manager.list_eligible_users()
    return [CronEligibleUserResponse(**u) for u in users]


@router.get("/jobs", response_model=CronListResponse)
async def list_cron_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    owner: Optional[str] = Query(None, description="Filter by OS username"),
    source: Optional[str] = Query(None, description="Filter by source (USER_CRONTAB, etc.)"),
    enabled: Optional[bool] = Query(None, description="Filter by active/disabled status"),
    search: Optional[str] = Query(None, description="Search term across commands, comments, or schedules"),
    _: UserRead = Depends(require_permission("cron.read")),
) -> CronListResponse:
    """Returns a filtered, paginated list of discovered cron jobs."""
    result = await cron_manager.list_jobs(
        page=page,
        page_size=page_size,
        owner=owner,
        source=source,
        enabled=enabled,
        search=search,
    )
    return CronListResponse(
        items=[
            CronJobResponse(
                id=j.id,
                owner=j.owner,
                schedule=j.schedule,
                minute=j.minute,
                hour=j.hour,
                day_of_month=j.day_of_month,
                month=j.month,
                day_of_week=j.day_of_week,
                special_expression=j.special_expression,
                command=j.command,
                comment=j.comment,
                enabled=j.enabled,
                source=j.source,
                source_file=j.source_file,
                line_number=j.line_number,
                description=j.description,
                is_editable=j.is_editable,
                original_hash=j.original_hash,
            )
            for j in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/jobs/{job_id}", response_model=CronJobResponse)
async def get_cron_job_details(
    job_id: str,
    _: UserRead = Depends(require_permission("cron.read")),
) -> CronJobResponse:
    """Retrieves full details of a specific cron job."""
    job = await cron_manager.get_job(job_id)
    if not job:
        raise NotFoundError(f"Cron job '{job_id}' not found")

    return CronJobResponse(
        id=job.id,
        owner=job.owner,
        schedule=job.schedule,
        minute=job.minute,
        hour=job.hour,
        day_of_month=job.day_of_month,
        month=job.month,
        day_of_week=job.day_of_week,
        special_expression=job.special_expression,
        command=job.command,
        comment=job.comment,
        enabled=job.enabled,
        source=job.source,
        source_file=job.source_file,
        line_number=job.line_number,
        description=job.description,
        is_editable=job.is_editable,
        original_hash=job.original_hash,
    )


# -----------------------------------------------------------------------------
# Mutation Endpoints (Guarded by cron.create, cron.update, cron.delete)
# -----------------------------------------------------------------------------

@router.post("/jobs", response_model=CronJobMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_cron_job(
    req: CronJobCreateRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("cron.create")),
) -> CronJobMutationResponse:
    """Creates a new cron job entry in the specified user's crontab."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    created = await cron_manager.create_job(
        owner=req.owner,
        schedule=req.schedule,
        command=req.command,
        comment=req.comment,
        enabled=req.enabled,
    )

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="cron.create",
        resource_type="cron_job",
        resource_id=created.id,
        status="SUCCESS",
        details=f"Created cron job for owner='{created.owner}' with schedule='{created.schedule}'",
        ip_address=client_ip,
        request_id=req_id,
    )

    return CronJobMutationResponse(
        success=True,
        operation="create",
        job=CronJobResponse(
            id=created.id,
            owner=created.owner,
            schedule=created.schedule,
            minute=created.minute,
            hour=created.hour,
            day_of_month=created.day_of_month,
            month=created.month,
            day_of_week=created.day_of_week,
            special_expression=created.special_expression,
            command=created.command,
            comment=created.comment,
            enabled=created.enabled,
            source=created.source,
            source_file=created.source_file,
            line_number=created.line_number,
            description=created.description,
            is_editable=created.is_editable,
            original_hash=created.original_hash,
        ),
        message=f"Cron job successfully created for user '{created.owner}'",
    )


@router.put("/jobs/{job_id}", response_model=CronJobMutationResponse)
async def update_cron_job(
    job_id: str,
    req: CronJobUpdateRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("cron.update")),
) -> CronJobMutationResponse:
    """Updates an existing cron job with optimistic concurrency conflict detection."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    updated = await cron_manager.update_job(
        job_id=job_id,
        owner=req.owner,
        schedule=req.schedule,
        command=req.command,
        comment=req.comment,
        enabled=req.enabled,
        expected_hash=req.expected_hash,
    )

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="cron.update",
        resource_type="cron_job",
        resource_id=job_id,
        status="SUCCESS",
        details=f"Updated cron job for owner='{updated.owner}' with schedule='{updated.schedule}'",
        ip_address=client_ip,
        request_id=req_id,
    )

    return CronJobMutationResponse(
        success=True,
        operation="update",
        job=CronJobResponse(
            id=updated.id,
            owner=updated.owner,
            schedule=updated.schedule,
            minute=updated.minute,
            hour=updated.hour,
            day_of_month=updated.day_of_month,
            month=updated.month,
            day_of_week=updated.day_of_week,
            special_expression=updated.special_expression,
            command=updated.command,
            comment=updated.comment,
            enabled=updated.enabled,
            source=updated.source,
            source_file=updated.source_file,
            line_number=updated.line_number,
            description=updated.description,
            is_editable=updated.is_editable,
            original_hash=updated.original_hash,
        ),
        message=f"Cron job '{job_id}' successfully updated",
    )


@router.delete("/jobs/{job_id}", response_model=CronJobDeleteResponse)
async def delete_cron_job(
    job_id: str,
    owner: str = Query(..., description="Target OS username owning the crontab entry"),
    expected_hash: Optional[str] = Query(None, description="Optional concurrency hash fingerprint"),
    request: Request = None,
    current_user: UserRead = Depends(require_permission("cron.delete")),
) -> CronJobDeleteResponse:
    """Safely deletes an identified cron job from the user's crontab."""
    req_id = getattr(request.state, "request_id", "req_unknown") if request else "req_unknown"
    client_ip = request.client.host if request and request.client else None

    await cron_manager.delete_job(
        job_id=job_id,
        owner=owner,
        expected_hash=expected_hash,
    )

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="cron.delete",
        resource_type="cron_job",
        resource_id=job_id,
        status="SUCCESS",
        details=f"Deleted cron job '{job_id}' from owner='{owner}' crontab",
        ip_address=client_ip,
        request_id=req_id,
    )

    return CronJobDeleteResponse(
        success=True,
        operation="delete",
        deleted_id=job_id,
        owner=owner,
        message=f"Cron job '{job_id}' successfully deleted",
    )
