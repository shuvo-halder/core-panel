from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.linux.contracts import FirewallRuleCreate
from backend.app.linux.firewall import LinuxFirewallManager

router = APIRouter(prefix="/firewall", tags=["Firewall Management"])
firewall_manager = LinuxFirewallManager()


# -----------------------------------------------------------------------------
# Pydantic Request & Response Schemas
# -----------------------------------------------------------------------------

class FirewallRuleResponse(BaseModel):
    rule_index: int
    port: str
    protocol: str
    action: str
    direction: str
    source: str
    family: str
    comment: Optional[str] = None
    signature: Optional[str] = None


class FirewallStatusResponse(BaseModel):
    installed: bool
    active: bool
    default_incoming: str
    default_outgoing: str
    default_routed: str
    rules: List[FirewallRuleResponse]
    management_ports: List[int]


class FirewallRuleCreateRequest(BaseModel):
    port: str = Field(..., description="Single port (e.g. '80') or port range (e.g. '3000:3010')")
    protocol: str = Field(default="tcp", description="Protocol: 'tcp', 'udp', or 'any'")
    action: str = Field(default="allow", description="Action: 'allow' or 'deny'")
    direction: str = Field(default="in", description="Direction: 'in' or 'out'")
    source_ip: str = Field(default="any", description="Source IP, CIDR network, or 'any'")
    comment: Optional[str] = Field(default=None, max_length=64, description="Optional brief description")


class FirewallRuleDeleteRequest(BaseModel):
    expected_rule_signature: Optional[str] = Field(
        default=None,
        description="Signature of the rule expected at this index to prevent concurrency conflicts",
    )


class FirewallToggleRequest(BaseModel):
    enable: bool = Field(..., description="True to enable firewall, False to disable")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_permission("firewall.read"))],
    summary="Get firewall status and active rules",
)
async def get_firewall_status() -> Dict[str, Any]:
    """Inspects firewall daemon state, default policies, and parsed active rules."""
    status_obj = await firewall_manager.get_status()
    return {
        "success": True,
        "data": {
            "installed": status_obj.installed,
            "active": status_obj.active,
            "default_incoming": status_obj.default_incoming,
            "default_outgoing": status_obj.default_outgoing,
            "default_routed": status_obj.default_routed,
            "rules": [
                {
                    "rule_index": r.rule_index,
                    "port": r.port,
                    "protocol": r.protocol,
                    "action": r.action,
                    "direction": r.direction,
                    "source": r.source,
                    "family": r.family,
                    "comment": r.comment,
                    "signature": r.signature,
                }
                for r in status_obj.rules
            ],
            "management_ports": status_obj.management_ports,
        },
    }


@router.post(
    "/rules",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Add a new firewall rule",
)
async def add_firewall_rule(
    rule_req: FirewallRuleCreateRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("firewall.manage")),
) -> Dict[str, Any]:
    """Validates and creates a new packet filtering rule with anti-lockout protection."""
    rule_dto = FirewallRuleCreate(
        port=rule_req.port,
        protocol=rule_req.protocol,
        action=rule_req.action,
        direction=rule_req.direction,
        source_ip=rule_req.source_ip,
        comment=rule_req.comment,
    )

    result = await firewall_manager.add_rule(rule_dto)

    audit_service.log_event(
        user_id=current_user.id,
        action="firewall.rule_add",
        resource=f"port:{rule_req.port}/{rule_req.protocol}",
        details={
            "port": rule_req.port,
            "protocol": rule_req.protocol,
            "action": rule_req.action,
            "direction": rule_req.direction,
            "source_ip": rule_req.source_ip,
            "comment": rule_req.comment,
        },
        ip_address=request.client.host if request.client else None,
    )

    return {
        "success": True,
        "message": f"Firewall rule added: {rule_req.action} {rule_req.direction} {rule_req.port}/{rule_req.protocol}",
        "data": result,
    }


@router.delete(
    "/rules/{rule_index}",
    response_model=Dict[str, Any],
    summary="Delete a firewall rule by index",
)
async def delete_firewall_rule(
    rule_index: int,
    request: Request,
    expected_rule_signature: Optional[str] = Query(
        None, description="Expected rule signature to prevent index-shift race conditions"
    ),
    current_user: UserRead = Depends(require_permission("firewall.manage")),
) -> Dict[str, Any]:
    """Safely deletes a firewall rule by index with signature concurrency verification and lockout prevention."""
    result = await firewall_manager.delete_rule(
        rule_index=rule_index,
        expected_signature=expected_rule_signature,
    )

    audit_service.log_event(
        user_id=current_user.id,
        action="firewall.rule_delete",
        resource=f"rule:{rule_index}",
        details={
            "rule_index": rule_index,
            "expected_signature": expected_rule_signature,
        },
        ip_address=request.client.host if request.client else None,
    )

    return {
        "success": True,
        "message": f"Firewall rule #{rule_index} deleted successfully",
        "data": result,
    }


@router.post(
    "/toggle",
    response_model=Dict[str, Any],
    summary="Enable or disable the firewall",
)
async def toggle_firewall(
    toggle_req: FirewallToggleRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("firewall.manage")),
) -> Dict[str, Any]:
    """Enables or disables packet filtering. Enforces pre-enable SSH lockout verification."""
    result = await firewall_manager.toggle_firewall(enable=toggle_req.enable)

    audit_service.log_event(
        user_id=current_user.id,
        action="firewall.toggle",
        resource="firewall",
        details={"enable": toggle_req.enable},
        ip_address=request.client.host if request.client else None,
    )

    action_str = "enabled" if toggle_req.enable else "disabled"
    return {
        "success": True,
        "active": toggle_req.enable,
        "message": f"Firewall {action_str} successfully",
        "data": result,
    }
