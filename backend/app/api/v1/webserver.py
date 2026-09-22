from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from backend.app.audit.service import audit_service
from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.linux.contracts import SiteConfig, SiteProxyConfig, SiteSSLConfig
from backend.app.linux.nginx import nginx_manager

router = APIRouter(prefix="/webserver", tags=["Web Server & Reverse Proxy Management"])


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------

class NginxOverviewResponse(BaseModel):
    installed: bool
    version: Optional[str] = None
    executable_path: Optional[str] = None
    service_active: bool
    config_path: Optional[str] = None
    sites_available_count: int
    sites_enabled_count: int
    config_valid: bool
    config_error: Optional[str] = None


class SiteProxyResponse(BaseModel):
    enabled: bool
    target: Optional[str] = None
    preserve_host: bool = True


class SiteSSLResponse(BaseModel):
    enabled: bool
    certificate: Optional[str] = None
    # We intentionally do NOT return certificate_key path or content to the frontend
    cert_exists: bool = False
    subject: Optional[str] = None
    issuer: Optional[str] = None
    not_after: Optional[str] = None
    days_remaining: Optional[int] = None


class SiteConfigResponse(BaseModel):
    name: str
    server_names: List[str]
    listen: int
    listen_ipv6: bool
    root: Optional[str] = None
    proxy: SiteProxyResponse
    ssl: SiteSSLResponse
    access_log: bool
    error_log: bool
    index: List[str]
    client_max_body_size: str
    enabled: bool
    managed: bool
    config_path: Optional[str] = None


class SiteCreateRequest(BaseModel):
    name: str = Field(..., description="Unique site identity / domain name (e.g. example.com)")
    server_names: List[str] = Field(..., min_items=1, description="List of domain names / hostnames")
    listen: int = Field(default=80, ge=1, le=65535, description="HTTP listen port")
    listen_ipv6: bool = Field(default=False, description="Whether to listen on IPv6")
    root: Optional[str] = Field(default=None, description="Absolute document root under /var/www or /srv/www")
    proxy_enabled: bool = Field(default=False, description="Enable reverse proxy mode")
    proxy_target: Optional[str] = Field(default=None, description="Upstream proxy target (e.g. http://127.0.0.1:3000)")
    proxy_preserve_host: bool = Field(default=True, description="Forward original Host header")
    ssl_enabled: bool = Field(default=False, description="Enable SSL / TLS")
    ssl_certificate: Optional[str] = Field(default=None, description="Path to SSL certificate under /etc/ssl or /etc/nginx/ssl")
    ssl_certificate_key: Optional[str] = Field(default=None, description="Path to SSL private key")
    access_log: bool = Field(default=True, description="Enable dedicated access log")
    error_log: bool = Field(default=True, description="Enable dedicated error log")
    index: List[str] = Field(default=["index.html", "index.htm"], description="Directory index filenames")
    client_max_body_size: str = Field(default="10m", description="Max body size directive (e.g. 10m, 50m)")
    enabled: bool = Field(default=True, description="Enable site upon creation")


class SiteUpdateRequest(BaseModel):
    server_names: List[str] = Field(..., min_items=1)
    listen: int = Field(default=80, ge=1, le=65535)
    listen_ipv6: bool = Field(default=False)
    root: Optional[str] = None
    proxy_enabled: bool = False
    proxy_target: Optional[str] = None
    proxy_preserve_host: bool = True
    ssl_enabled: bool = False
    ssl_certificate: Optional[str] = None
    ssl_certificate_key: Optional[str] = None
    access_log: bool = True
    error_log: bool = True
    index: List[str] = ["index.html", "index.htm"]
    client_max_body_size: str = "10m"
    enabled: bool = True


class ConfigValidationResponse(BaseModel):
    valid: bool
    output: Optional[str] = None
    error: Optional[str] = None


class ReloadResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _to_response(site: SiteConfig) -> SiteConfigResponse:
    return SiteConfigResponse(
        name=site.name,
        server_names=site.server_names,
        listen=site.listen,
        listen_ipv6=site.listen_ipv6,
        root=site.root,
        proxy=SiteProxyResponse(
            enabled=site.proxy.enabled,
            target=site.proxy.target,
            preserve_host=site.proxy.preserve_host,
        ),
        ssl=SiteSSLResponse(
            enabled=site.ssl.enabled,
            certificate=site.ssl.certificate,
            cert_exists=site.ssl.cert_exists,
            subject=site.ssl.subject,
            issuer=site.ssl.issuer,
            not_after=site.ssl.not_after,
            days_remaining=site.ssl.days_remaining,
        ),
        access_log=site.access_log,
        error_log=site.error_log,
        index=site.index,
        client_max_body_size=site.client_max_body_size,
        enabled=site.enabled,
        managed=site.managed,
        config_path=site.config_path,
    )


# -----------------------------------------------------------------------------
# Read Endpoints (Guarded by webserver.read)
# -----------------------------------------------------------------------------

@router.get("/overview", response_model=NginxOverviewResponse)
async def get_webserver_overview(
    current_user: UserRead = Depends(require_permission("webserver.read")),
) -> NginxOverviewResponse:
    """Returns Nginx binary presence, version, service status, and configuration validity."""
    st = await nginx_manager.get_status()
    return NginxOverviewResponse(
        installed=st.installed,
        version=st.version,
        executable_path=st.executable_path,
        service_active=st.service_active,
        config_path=st.config_path,
        sites_available_count=st.sites_available_count,
        sites_enabled_count=st.sites_enabled_count,
        config_valid=st.config_valid,
        config_error=st.config_error,
    )


@router.get("/sites", response_model=List[SiteConfigResponse])
async def list_sites(
    current_user: UserRead = Depends(require_permission("webserver.read")),
) -> List[SiteConfigResponse]:
    """Returns all virtual host configurations discovered in /etc/nginx/sites-available."""
    sites = await nginx_manager.list_sites()
    return [_to_response(s) for s in sites]


@router.get("/sites/{name}", response_model=SiteConfigResponse)
async def get_site(
    name: str,
    current_user: UserRead = Depends(require_permission("webserver.read")),
) -> SiteConfigResponse:
    """Returns structured configuration details for a single virtual host."""
    site = await nginx_manager.get_site(name)
    if not site:
        raise NotFoundError(f"Site '{name}' not found", code="SITE_NOT_FOUND")
    return _to_response(site)


# -----------------------------------------------------------------------------
# Mutation Endpoints (Guarded by specific webserver permissions)
# -----------------------------------------------------------------------------

@router.post("/sites", response_model=SiteConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_site(
    req: SiteCreateRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.create")),
) -> SiteConfigResponse:
    """Creates, validates, and atomically deploys a new managed Nginx virtual host."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    candidate = SiteConfig(
        name=req.name,
        server_names=req.server_names,
        listen=req.listen,
        listen_ipv6=req.listen_ipv6,
        root=req.root,
        proxy=SiteProxyConfig(
            enabled=req.proxy_enabled,
            target=req.proxy_target,
            preserve_host=req.proxy_preserve_host,
        ),
        ssl=SiteSSLConfig(
            enabled=req.ssl_enabled,
            certificate=req.ssl_certificate,
            certificate_key=req.ssl_certificate_key,
        ),
        access_log=req.access_log,
        error_log=req.error_log,
        index=req.index,
        client_max_body_size=req.client_max_body_size,
        enabled=req.enabled,
        managed=True,
    )

    created = await nginx_manager.create_site(candidate)

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="site.create",
        resource_type="webserver_site",
        resource_id=created.name,
        status="SUCCESS",
        details=f"Created site '{created.name}' (ports={created.listen}, proxy={created.proxy.enabled})",
        ip_address=client_ip,
        request_id=req_id,
    )

    return _to_response(created)


@router.put("/sites/{name}", response_model=SiteConfigResponse)
async def update_site(
    name: str,
    req: SiteUpdateRequest,
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.update")),
) -> SiteConfigResponse:
    """Atomically updates an existing managed Nginx virtual host with rollback protection."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    candidate = SiteConfig(
        name=name,
        server_names=req.server_names,
        listen=req.listen,
        listen_ipv6=req.listen_ipv6,
        root=req.root,
        proxy=SiteProxyConfig(
            enabled=req.proxy_enabled,
            target=req.proxy_target,
            preserve_host=req.proxy_preserve_host,
        ),
        ssl=SiteSSLConfig(
            enabled=req.ssl_enabled,
            certificate=req.ssl_certificate,
            certificate_key=req.ssl_certificate_key,
        ),
        access_log=req.access_log,
        error_log=req.error_log,
        index=req.index,
        client_max_body_size=req.client_max_body_size,
        enabled=req.enabled,
        managed=True,
    )

    updated = await nginx_manager.update_site(name, candidate)

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="site.update",
        resource_type="webserver_site",
        resource_id=name,
        status="SUCCESS",
        details=f"Updated site '{name}' (enabled={updated.enabled}, proxy={updated.proxy.enabled})",
        ip_address=client_ip,
        request_id=req_id,
    )

    return _to_response(updated)


@router.delete("/sites/{name}", status_code=status.HTTP_200_OK)
async def delete_site(
    name: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.delete")),
) -> Dict[str, Any]:
    """Safely removes a managed Nginx virtual host and reloads Nginx."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    await nginx_manager.delete_site(name)

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="site.delete",
        resource_type="webserver_site",
        resource_id=name,
        status="SUCCESS",
        details=f"Deleted managed site '{name}'",
        ip_address=client_ip,
        request_id=req_id,
    )

    return {"success": True, "message": f"Site '{name}' successfully deleted"}


@router.post("/sites/{name}/enable", status_code=status.HTTP_200_OK)
async def enable_site(
    name: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.enable")),
) -> Dict[str, Any]:
    """Enables an existing virtual host by creating a symlink in sites-enabled."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    await nginx_manager.enable_site(name)

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="site.enable",
        resource_type="webserver_site",
        resource_id=name,
        status="SUCCESS",
        details=f"Enabled site '{name}'",
        ip_address=client_ip,
        request_id=req_id,
    )

    return {"success": True, "message": f"Site '{name}' enabled successfully"}


@router.post("/sites/{name}/disable", status_code=status.HTTP_200_OK)
async def disable_site(
    name: str,
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.disable")),
) -> Dict[str, Any]:
    """Disables a virtual host by unlinking it from sites-enabled."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    await nginx_manager.disable_site(name)

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="site.disable",
        resource_type="webserver_site",
        resource_id=name,
        status="SUCCESS",
        details=f"Disabled site '{name}'",
        ip_address=client_ip,
        request_id=req_id,
    )

    return {"success": True, "message": f"Site '{name}' disabled successfully"}


@router.post("/validate", response_model=ConfigValidationResponse)
async def validate_candidate_config(
    req: SiteCreateRequest,
    current_user: UserRead = Depends(require_permission("webserver.create")),
) -> ConfigValidationResponse:
    """Pre-validates candidate configuration syntax with nginx -t without deploying."""
    candidate = SiteConfig(
        name=req.name,
        server_names=req.server_names,
        listen=req.listen,
        listen_ipv6=req.listen_ipv6,
        root=req.root,
        proxy=SiteProxyConfig(
            enabled=req.proxy_enabled,
            target=req.proxy_target,
            preserve_host=req.proxy_preserve_host,
        ),
        ssl=SiteSSLConfig(
            enabled=req.ssl_enabled,
            certificate=req.ssl_certificate,
            certificate_key=req.ssl_certificate_key,
        ),
        access_log=req.access_log,
        error_log=req.error_log,
        index=req.index,
        client_max_body_size=req.client_max_body_size,
        enabled=req.enabled,
        managed=True,
    )

    valid, err = await nginx_manager.validate_config(candidate)
    return ConfigValidationResponse(valid=valid, error=err)


@router.post("/reload", response_model=ReloadResponse)
async def reload_nginx(
    request: Request,
    current_user: UserRead = Depends(require_permission("webserver.reload")),
) -> ReloadResponse:
    """Safely reloads Nginx service using dedicated operation 'nginx.reload'."""
    req_id = getattr(request.state, "request_id", "req_unknown")
    client_ip = request.client.host if request.client else None

    success, err = await nginx_manager.reload()

    audit_service.log_event(
        user_id=current_user.id,
        username=current_user.username,
        action="nginx.reload",
        resource_type="webserver",
        resource_id="nginx",
        status="SUCCESS" if success else "FAILED",
        details="Nginx service reloaded successfully" if success else f"Nginx reload failed: {err}",
        ip_address=client_ip,
        request_id=req_id,
    )

    return ReloadResponse(success=success, message="Nginx reloaded successfully" if success else None, error=err)
