from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.core.validators import validate_service_unit_name
from backend.app.ipc.client import ipc_client
from backend.app.linux.services import service_collector

router = APIRouter(prefix="/services", tags=["Service Management"])


class ServiceSummaryResponse(BaseModel):
    unit: str
    description: str
    load_state: str
    active_state: str
    sub_state: str
    enabled: str
    main_pid: Optional[int] = None


class ServiceMutationResponse(BaseModel):
    success: bool
    operation: str
    unit: str
    message: str
    service: Optional[ServiceSummaryResponse] = None


@router.get("", response_model=List[ServiceSummaryResponse])
async def list_services(
    _: UserRead = Depends(require_permission("services.read")),
) -> List[ServiceSummaryResponse]:
    """Lists all discovered systemd .service units and their current runtime/enablement state."""
    services = await service_collector.list_services()
    return [
        ServiceSummaryResponse(
            unit=s.unit,
            description=s.description,
            load_state=s.load_state,
            active_state=s.active_state,
            sub_state=s.sub_state,
            enabled=s.enabled,
            main_pid=s.main_pid,
        )
        for s in services
    ]


@router.get("/{unit}", response_model=ServiceSummaryResponse)
async def get_service_details(
    unit: str,
    _: UserRead = Depends(require_permission("services.read")),
) -> ServiceSummaryResponse:
    """Inspects details for a specific validated .service unit."""
    clean_unit = validate_service_unit_name(unit)
    service = await service_collector.get_service(clean_unit)
    if not service:
        raise NotFoundError(f"Service unit '{clean_unit}' not found or inaccessible")

    return ServiceSummaryResponse(
        unit=service.unit,
        description=service.description,
        load_state=service.load_state,
        active_state=service.active_state,
        sub_state=service.sub_state,
        enabled=service.enabled,
        main_pid=service.main_pid,
    )


async def _execute_service_mutation(
    request: Request,
    current_user: UserRead,
    unit: str,
    action: str,
    operation_name: str,
) -> ServiceMutationResponse:
    """Helper executing a validated service mutation via CoreAgent with full audit logging."""
    clean_unit = validate_service_unit_name(unit)
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    try:
        # Transmit structured request to privileged CoreAgent over IPC
        result = await ipc_client.execute(
            operation=operation_name,
            payload={"unit": clean_unit},
            request_id=req_id,
        )

        # Audit successful mutation
        audit_service.log_event(
            user_id=current_user.id,
            username=current_user.username,
            action=f"services.{action}",
            resource_type="service",
            resource_id=clean_unit,
            status="SUCCESS",
            details=f"Successfully executed {action} on {clean_unit}",
            ip_address=client_ip,
            request_id=req_id,
        )

        # Retrieve refreshed service status if available
        refreshed_status: Optional[ServiceSummaryResponse] = None
        try:
            s = await service_collector.get_service(clean_unit)
            if s:
                refreshed_status = ServiceSummaryResponse(
                    unit=s.unit,
                    description=s.description,
                    load_state=s.load_state,
                    active_state=s.active_state,
                    sub_state=s.sub_state,
                    enabled=s.enabled,
                    main_pid=s.main_pid,
                )
        except Exception:
            pass

        return ServiceMutationResponse(
            success=True,
            operation=action,
            unit=clean_unit,
            message=result.get("message", f"Service '{clean_unit}' {action} completed successfully"),
            service=refreshed_status,
        )

    except Exception as exc:
        # Audit failed mutation
        audit_service.log_event(
            user_id=current_user.id,
            username=current_user.username,
            action=f"services.{action}",
            resource_type="service",
            resource_id=clean_unit,
            status="FAILED",
            details=str(exc),
            ip_address=client_ip,
            request_id=req_id,
        )
        raise


@router.post("/{unit}/start", response_model=ServiceMutationResponse)
async def start_service(
    unit: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("services.start")),
) -> ServiceMutationResponse:
    """Starts a validated systemd service via CoreAgent."""
    return await _execute_service_mutation(
        request, current_user, unit, action="start", operation_name="systemd.service.start"
    )


@router.post("/{unit}/stop", response_model=ServiceMutationResponse)
async def stop_service(
    unit: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("services.stop")),
) -> ServiceMutationResponse:
    """Stops a validated systemd service via CoreAgent."""
    return await _execute_service_mutation(
        request, current_user, unit, action="stop", operation_name="systemd.service.stop"
    )


@router.post("/{unit}/restart", response_model=ServiceMutationResponse)
async def restart_service(
    unit: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("services.restart")),
) -> ServiceMutationResponse:
    """Restarts a validated systemd service via CoreAgent."""
    return await _execute_service_mutation(
        request, current_user, unit, action="restart", operation_name="systemd.service.restart"
    )


@router.post("/{unit}/enable", response_model=ServiceMutationResponse)
async def enable_service(
    unit: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("services.enable")),
) -> ServiceMutationResponse:
    """Enables a validated systemd service to start at boot via CoreAgent."""
    return await _execute_service_mutation(
        request, current_user, unit, action="enable", operation_name="systemd.service.enable"
    )


@router.post("/{unit}/disable", response_model=ServiceMutationResponse)
async def disable_service(
    unit: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("services.disable")),
) -> ServiceMutationResponse:
    """Disables a validated systemd service from starting at boot via CoreAgent."""
    return await _execute_service_mutation(
        request, current_user, unit, action="disable", operation_name="systemd.service.disable"
    )
