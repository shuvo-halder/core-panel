from typing import List

from fastapi import APIRouter, Depends, status

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import RoleCreate, RoleRead, RoleUpdate, UserRead
from backend.app.auth.service import auth_service

router = APIRouter(prefix="/roles", tags=["Roles Management"])


@router.get("", response_model=List[RoleRead])
async def list_roles(_: UserRead = Depends(require_permission("roles.read"))) -> List[RoleRead]:
    """List all system and custom roles."""
    return auth_service.list_roles()


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(payload: RoleCreate, _: UserRead = Depends(require_permission("roles.manage"))) -> RoleRead:
    """Create a new role with specific permission mappings."""
    return auth_service.create_role(payload)


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(role_id: str, _: UserRead = Depends(require_permission("roles.read"))) -> RoleRead:
    """Fetch role details by ID."""
    return auth_service.get_role_by_id(role_id)


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: str,
    payload: RoleUpdate,
    _: UserRead = Depends(require_permission("roles.manage")),
) -> RoleRead:
    """Update role name, description, or granted permissions."""
    return auth_service.update_role(role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_200_OK)
async def delete_role(
    role_id: str,
    _: UserRead = Depends(require_permission("roles.manage")),
) -> dict:
    """Delete a custom role."""
    auth_service.delete_role(role_id)
    return {"success": True, "message": f"Role '{role_id}' deleted successfully"}
