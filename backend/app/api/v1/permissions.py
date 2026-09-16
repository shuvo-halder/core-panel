from typing import List

from fastapi import APIRouter, Depends

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import PermissionRead, UserRead
from backend.app.auth.service import auth_service

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("", response_model=List[PermissionRead])
async def list_permissions(_: UserRead = Depends(require_permission("roles.read"))) -> List[PermissionRead]:
    """List all available system permissions."""
    raw_perms = auth_service.list_permissions()
    return [PermissionRead(**p) for p in raw_perms]
