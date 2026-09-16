from fastapi import APIRouter, Depends, Request, Response

from backend.app.auth.dependencies import require_auth
from backend.app.auth.models import AuthMeResponse, LoginRequest, LoginResponse, UserRead
from backend.app.auth.service import auth_service
from backend.app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """
    Authenticate user credentials, establish a server-side session,
    and return user profile with HttpOnly cookie.
    """
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent")

    user, session_id = auth_service.authenticate_user(
        username=payload.username,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.is_production,
        path="/",
    )

    return LoginResponse(
        success=True,
        user=user,
        effective_permissions=user.permissions,
    )


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """Invalidate current session and clear session cookie."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_id = auth_header.split(" ", 1)[1].strip()

    if session_id:
        auth_service.revoke_session(session_id)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )
    return {"success": True, "message": "Successfully logged out"}


@router.get("/me", response_model=AuthMeResponse)
async def get_current_user_profile(current_user: UserRead = Depends(require_auth)) -> AuthMeResponse:
    """Return the authenticated user profile, roles, and effective permissions."""
    return AuthMeResponse(
        user=current_user,
        effective_permissions=current_user.permissions,
    )
