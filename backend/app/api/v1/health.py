from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import settings

router = APIRouter(tags=["System"])


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class VersionResponse(BaseModel):
    name: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Lightweight health check endpoint.
    Guaranteed fast response; executes zero expensive subshell or OS inspection commands.
    """
    return HealthResponse(
        status="ok", version=settings.APP_VERSION, timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    """Application and environment version details."""
    return VersionResponse(
        name=settings.APP_NAME, version=settings.APP_VERSION, environment=settings.ENVIRONMENT
    )
