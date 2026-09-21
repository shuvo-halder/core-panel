import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.cron import router as cron_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.permissions import router as permissions_router
from backend.app.api.v1.processes import router as processes_router
from backend.app.api.v1.roles import router as roles_router
from backend.app.api.v1.services import router as services_router
from backend.app.api.v1.storage import router as storage_router
from backend.app.api.v1.network import router as network_router
from backend.app.api.v1.packages import router as packages_router
from backend.app.api.v1.system import router as system_router
from backend.app.api.v1.users import router as users_router
from backend.app.auth.service import auth_service
from backend.app.core.config import settings
from backend.app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from backend.app.core.logging import logger
from backend.app.db.sqlite import db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and graceful shutdown lifecycle."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    # Initialize SQLite database and baseline migrations
    try:
        db.init_database()
        auth_service.bootstrap_admin_if_configured()
    except Exception as exc:
        logger.error(f"Failed to initialize SQLite database: {exc}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")


def create_application() -> FastAPI:
    """Factory creating the configured FastAPI control-plane application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else ["http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    # Request ID and Request Logging Middleware
    @app.middleware("http")
    async def request_middleware(request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:10]}"
        request.state.request_id = req_id

        start_time = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = req_id

            # Log completion (excluding health check from verbose logs)
            if not request.url.path.endswith("/health"):
                logger.info(
                    f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                    extra={"request_id": req_id, "duration_ms": duration_ms},
                )
            return response
        except Exception as exc:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path}: {exc}",
                extra={"request_id": req_id, "duration_ms": duration_ms},
            )
            return await unhandled_exception_handler(request, exc)

    # Register Centralized Error Handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount API v1 Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(roles_router, prefix="/api/v1")
    app.include_router(permissions_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(services_router, prefix="/api/v1")
    app.include_router(processes_router, prefix="/api/v1")
    app.include_router(storage_router, prefix="/api/v1")
    app.include_router(network_router, prefix="/api/v1")
    app.include_router(packages_router, prefix="/api/v1")
    app.include_router(cron_router, prefix="/api/v1")

    return app


app = create_application()
