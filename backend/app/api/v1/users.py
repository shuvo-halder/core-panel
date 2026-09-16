from typing import List

from fastapi import APIRouter, Depends, status

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserCreate, UserRead, UserUpdate
from backend.app.auth.service import auth_service

router = APIRouter(prefix="/users", tags=["Users Management"])


@router.get("", response_model=List[UserRead])
async def list_users(_: UserRead = Depends(require_permission("users.read"))) -> List[UserRead]:
    """List all registered users, their roles, and effective permissions."""
    return auth_service.list_users()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, _: UserRead = Depends(require_permission("users.manage"))) -> UserRead:
    """Create a new user account with role assignment."""
    return auth_service.create_user(payload)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: str, _: UserRead = Depends(require_permission("users.read"))) -> UserRead:
    """Fetch user details by ID."""
    return auth_service.get_user_by_id(user_id)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    _: UserRead = Depends(require_permission("users.manage")),
) -> UserRead:
    """Update user attributes (email, password, roles, active status)."""
    return auth_service.update_user(user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: str,
    current_user: UserRead = Depends(require_permission("users.manage")),
) -> dict:
    """Delete a user account."""
    auth_service.delete_user(user_id=user_id, requesting_user_id=current_user.id)
    return {"success": True, "message": f"User '{user_id}' deleted successfully"}
