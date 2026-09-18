from typing import Callable, Optional

from fastapi import Depends, Request

from backend.app.auth.models import UserRead
from backend.app.auth.service import auth_service
from backend.app.core.config import settings
from backend.app.core.errors import ForbiddenError, UnauthorizedError
from backend.app.core.logging import logger


async def get_current_user(request: Request) -> Optional[UserRead]:
    """
    Extracts and validates the current user from HttpOnly session cookie
    or standard Authorization: Bearer header.
    """
    # 1. Check HttpOnly cookie
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    # 2. Fallback to Bearer token header if cookie is not present
    if not session_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_id = auth_header.split(" ", 1)[1].strip()

    if not session_id:
        return None

    user = auth_service.get_session_user(session_id)
    return user


async def require_auth(current_user: Optional[UserRead] = Depends(get_current_user)) -> UserRead:
    """FastAPI Dependency enforcing authentication and active user status."""
    if not current_user:
        raise UnauthorizedError("Authentication credentials required")
    if not current_user.is_active:
        raise UnauthorizedError("User account is deactivated")
    return current_user


def require_permission(permission_name: str) -> Callable:
    """
    Factory creating a FastAPI dependency that verifies the user possesses
    the explicitly specified RBAC permission identifier.
    """

    async def permission_checker(current_user: UserRead = Depends(require_auth)) -> UserRead:
        if permission_name not in current_user.permissions:
            logger.warning(
                f"Authorization failure: user '{current_user.username}' ({current_user.id}) "
                f"attempted action requiring '{permission_name}'"
            )
            raise ForbiddenError(f"Access forbidden: requires '{permission_name}' permission")
        return current_user

    return permission_checker
