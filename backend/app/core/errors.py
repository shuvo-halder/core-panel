from typing import Any, Optional

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.config import settings
from backend.app.core.logging import logger


class AppError(Exception):
    """Base application domain exception."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(message, code=code, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN"):
        super().__init__(message, code=code, status_code=status.HTTP_403_FORBIDDEN)


class BadRequestError(AppError):
    def __init__(self, message: str = "Invalid request", code: str = "INVALID_REQUEST"):
        super().__init__(message, code=code, status_code=status.HTTP_400_BAD_REQUEST)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(message, code=code, status_code=status.HTTP_409_CONFLICT)


def format_error_response(code: str, message: str, request_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id,
            }
        }
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        f"Domain error {exc.code}: {exc.message}",
        extra={"request_id": request_id}
    )
    return format_error_response(exc.code, exc.message, request_id, exc.status_code)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    error_msg = "; ".join([f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()])
    logger.info(
        f"Validation error: {error_msg}",
        extra={"request_id": request_id}
    )
    return format_error_response("VALIDATION_ERROR", f"Invalid parameters: {error_msg}", request_id, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR"
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return format_error_response(code, str(exc.detail), request_id, exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"request_id": request_id}
    )

    # In production, never expose raw Python exception/traceback
    message = "An unexpected internal server error occurred" if settings.is_production else str(exc)
    return format_error_response("INTERNAL_SERVER_ERROR", message, request_id, status.HTTP_500_INTERNAL_SERVER_ERROR)
