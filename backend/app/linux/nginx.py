import asyncio
import datetime
import logging
import os
import re
import ssl
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.errors import AppError, BadRequestError, NotFoundError
from backend.app.core.validators import (
    validate_client_max_body_size,
    validate_listen_port,
    validate_proxy_target,
    validate_server_names,
    validate_site_name,
    validate_ssl_paths,
    validate_web_root,
)
from backend.app.ipc.client import (
    AgentExecutionError,
    AgentUnavailableError,
    IPCClient,
)
from backend.app.linux.contracts import (
    INginxManager,
    NginxStatus,
    SiteConfig,
    SiteProxyConfig,
    SiteSSLConfig,
)

logger = logging.getLogger("corepanel.linux.nginx")

# Static directory constants for Debian/Ubuntu Nginx
SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"
NGINX_CONF_PATH = "/etc/nginx/nginx.conf"

MANAGED_HEADER_PREFIX = "# MANAGED BY COREPANEL - DO NOT EDIT MANUALLY"


class LinuxNginxManager(INginxManager):
    """
    Linux Nginx Manager implementation.
    Discovers, validates, and manages virtual hosts using structured configuration models.
    Delegates all privileged operations (validation, deployment, reload) exclusively
    to CoreAgent via Unix Domain Socket IPC with strict fail-closed semantics.
    """

    def __init__(self, socket_path: str = "/run/corepanel/agent.sock"):
        self.socket_path = socket_path
        self.ipc_client = IPCClient(socket_path=socket_path)

    async def _call_agent_operation(self, op_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes CoreAgent privileged operations exclusively over Unix Domain Socket IPC.
        Production fail-closed design: If CoreAgent is unavailable or times out,
        the request immediately fails with AppError(code='IPC_UNAVAILABLE', status_code=503).
        The FastAPI process never executes privileged operations in-process.
        """
        try:
            return await self.ipc_client.execute(op_name, payload)
        except AgentUnavailableError as exc:
            logger.error(f"CoreAgent IPC unavailable for operation '{op_name}': {exc}")
            raise AppError(
                message="CoreAgent privileged daemon is unavailable",
                code="IPC_UNAVAILABLE",
                status_code=503,
            )
        except AgentExecutionError as exc:
            logger.warning(f"CoreAgent operation '{op_name}' execution error: [{exc.code}] {exc.message}")
            return {"success": False, "error": exc.message, "code": exc.code}
        except Exception as exc:
            logger.error(f"Unexpected IPC error during operation '{op_name}': {exc}")
            raise AppError(
                message="CoreAgent privileged daemon is unavailable",
                code="IPC_UNAVAILABLE",
                status_code=503,
            )

    def _generate_nginx_config(self, site: SiteConfig) -> str:
        """
        Deterministically renders an Nginx virtual host configuration file from structured parameters.
        Includes safety header, server_name directives, root / proxy_pass blocks, and SSL directives.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        server_names_str = " ".join(site.server_names)

        lines: List[str] = [
            f"{MANAGED_HEADER_PREFIX}",
            f"# Site: {site.name}",
            f"# Generated: {now_str}",
            "",
            "server {",
            f"    listen {site.listen};",
        ]

        if site.listen_ipv6:
            lines.append(f"    listen [::]:{site.listen};")

        lines.append(f"    server_name {server_names_str};")
        lines.append("")

        # SSL Configuration
        if site.ssl.enabled and site.ssl.certificate and site.ssl.certificate_key:
            lines.append("    # SSL / TLS Configuration")
            lines.append("    listen 443 ssl;")
            if site.listen_ipv6:
                lines.append("    listen [::]:443 ssl;")
            lines.append(f"    ssl_certificate {site.ssl.certificate};")
            lines.append(f"    ssl_certificate_key {site.ssl.certificate_key};")
            lines.append("    ssl_protocols TLSv1.2 TLSv1.3;")
            lines.append("    ssl_ciphers HIGH:!aNULL:!MD5;")
            lines.append("    ssl_prefer_server_ciphers on;")
            lines.append("")

        # Body size limit
        if site.client_max_body_size:
            lines.append(f"    client_max_body_size {site.client_max_body_size};")
            lines.append("")

        # Logging directives
        if site.access_log:
            lines.append(f"    access_log /var/log/nginx/{site.name}.access.log;")
        else:
            lines.append("    access_log off;")

        if site.error_log:
            lines.append(f"    error_log /var/log/nginx/{site.name}.error.log warn;")
        else:
            lines.append("    error_log /dev/null crit;")

        lines.append("")

        # Proxy Target vs Document Root
        if site.proxy.enabled and site.proxy.target:
            lines.append("    # Reverse Proxy Upstream")
            lines.append("    location / {")
            lines.append(f"        proxy_pass {site.proxy.target};")
            lines.append("        proxy_http_version 1.1;")
            lines.append("        proxy_set_header Upgrade $http_upgrade;")
            lines.append("        proxy_set_header Connection \"upgrade\";")
            if site.proxy.preserve_host:
                lines.append("        proxy_set_header Host $host;")
            else:
                lines.append("        proxy_set_header Host $proxy_host;")
            lines.append("        proxy_set_header X-Real-IP $remote_addr;")
            lines.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
            lines.append("        proxy_set_header X-Forwarded-Proto $scheme;")
            lines.append("    }")
        else:
            doc_root = site.root or "/var/www/html"
            indexes = " ".join(site.index) if site.index else "index.html index.htm"
            lines.append(f"    root {doc_root};")
            lines.append(f"    index {indexes};")
            lines.append("")
            lines.append("    location / {")
            lines.append("        try_files $uri $uri/ =404;")
            lines.append("    }")

        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def _parse_ssl_metadata(self, cert_path: Optional[str]) -> SiteSSLConfig:
        """Inspects SSL certificate metadata safely without touching private key files."""
        if not cert_path or not os.path.isfile(cert_path):
            return SiteSSLConfig(enabled=bool(cert_path), certificate=cert_path, cert_exists=False)

        try:
            cert_dict = ssl._ssl._test_decode_cert(cert_path)
            subject_parts = []
            for sub in cert_dict.get("subject", ()):
                for k, v in sub:
                    if k == "commonName":
                        subject_parts.append(v)
            subject = ", ".join(subject_parts) or cert_path

            issuer_parts = []
            for iss in cert_dict.get("issuer", ()):
                for k, v in iss:
                    if k in ("organizationName", "commonName"):
                        issuer_parts.append(v)
            issuer = ", ".join(issuer_parts) or "Unknown Issuer"

            not_after = cert_dict.get("notAfter")
            days_rem = None
            if not_after:
                try:
                    exp_sec = ssl.cert_time_to_seconds(not_after)
                    now_sec = time.time()
                    days_rem = max(0, int((exp_sec - now_sec) / 86400))
                except Exception:
                    days_rem = None

            return SiteSSLConfig(
                enabled=True,
                certificate=cert_path,
                cert_exists=True,
                subject=subject,
                issuer=issuer,
                not_after=not_after,
                days_remaining=days_rem,
            )
        except Exception as exc:
            logger.debug(f"Failed to decode certificate at '{cert_path}': {exc}")
            return SiteSSLConfig(
                enabled=True,
                certificate=cert_path,
                cert_exists=True,
                subject="Unparseable Certificate",
                issuer=None,
                not_after=None,
                days_remaining=None,
            )

    def _parse_site_file(self, site_name: str, file_path: str) -> SiteConfig:
        """Parses an existing configuration file into a structured SiteConfig object."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            content = ""

        is_managed = content.startswith(MANAGED_HEADER_PREFIX)
        enabled_link = os.path.join(SITES_ENABLED_DIR, site_name)
        is_enabled = os.path.islink(enabled_link) or os.path.exists(enabled_link)

        # Parse directives with safe regular expressions
        # server_name
        sn_match = re.search(r"server_name\s+([^;]+);", content)
        server_names = [s.strip() for s in sn_match.group(1).split()] if sn_match else [site_name]

        # listen port
        listen_match = re.search(r"listen\s+(\d+)", content)
        listen_port = int(listen_match.group(1)) if listen_match else 80

        # listen ipv6
        listen_ipv6 = bool(re.search(r"listen\s+\[::\]", content))

        # root
        root_match = re.search(r"root\s+([^;]+);", content)
        root = root_match.group(1).strip() if root_match else None

        # proxy_pass
        proxy_match = re.search(r"proxy_pass\s+([^;]+);", content)
        proxy_target = proxy_match.group(1).strip() if proxy_match else None
        proxy_enabled = bool(proxy_target)

        # SSL
        cert_match = re.search(r"ssl_certificate\s+([^;]+);", content)
        key_match = re.search(r"ssl_certificate_key\s+([^;]+);", content)
        cert_path = cert_match.group(1).strip() if cert_match else None
        key_path = key_match.group(1).strip() if key_match else None
        ssl_enabled = bool(cert_path)

        ssl_config = (
            self._parse_ssl_metadata(cert_path)
            if ssl_enabled
            else SiteSSLConfig(enabled=False)
        )
        if key_path:
            # We never expose key content, but retain the path reference for the config model
            object.__setattr__(ssl_config, "certificate_key", key_path)

        # access_log / error_log
        access_log = not bool(re.search(r"access_log\s+off;", content))
        error_log = not bool(re.search(r"error_log\s+/dev/null", content))

        # client_max_body_size
        body_match = re.search(r"client_max_body_size\s+([^;]+);", content)
        client_max_body_size = body_match.group(1).strip() if body_match else "10m"

        # index
        idx_match = re.search(r"index\s+([^;]+);", content)
        indexes = [i.strip() for i in idx_match.group(1).split()] if idx_match else ["index.html", "index.htm"]

        return SiteConfig(
            name=site_name,
            server_names=server_names,
            listen=listen_port,
            listen_ipv6=listen_ipv6,
            root=root,
            proxy=SiteProxyConfig(enabled=proxy_enabled, target=proxy_target, preserve_host=True),
            ssl=ssl_config,
            access_log=access_log,
            error_log=error_log,
            index=indexes,
            client_max_body_size=client_max_body_size,
            enabled=is_enabled,
            managed=is_managed,
            config_path=file_path,
        )

    async def get_status(self) -> NginxStatus:
        """Queries Nginx system status, version, configuration validity, and sites count."""
        res = await self._call_agent_operation("nginx.status", {})
        return NginxStatus(
            installed=res.get("installed", False),
            version=res.get("version"),
            executable_path=res.get("executable_path"),
            service_active=res.get("service_active", False),
            config_path=res.get("config_path"),
            sites_available_count=res.get("sites_available_count", 0),
            sites_enabled_count=res.get("sites_enabled_count", 0),
            config_valid=res.get("config_valid", False),
            config_error=res.get("config_output") if not res.get("config_valid", False) else None,
        )

    async def list_sites(self) -> List[SiteConfig]:
        """Discovers all virtual hosts configured in /etc/nginx/sites-available."""
        if not os.path.isdir(SITES_AVAILABLE_DIR):
            return []

        sites: List[SiteConfig] = []
        try:
            entries = sorted(os.listdir(SITES_AVAILABLE_DIR))
        except OSError as exc:
            logger.error(f"Failed to read sites-available directory: {exc}")
            return []

        for entry in entries:
            # Skip hidden files and temporary backups
            if entry.startswith(".") or entry.endswith(".bak") or entry.endswith(".tmp"):
                continue

            full_path = os.path.join(SITES_AVAILABLE_DIR, entry)
            if os.path.isfile(full_path):
                sites.append(self._parse_site_file(entry, full_path))

        return sites

    async def get_site(self, name: str) -> Optional[SiteConfig]:
        """Fetches structured configuration for a single virtual host."""
        clean_name = validate_site_name(name)
        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if not os.path.isfile(target_path):
            return None
        return self._parse_site_file(clean_name, target_path)

    async def validate_config(self, site: SiteConfig) -> Tuple[bool, Optional[str]]:
        """Generates and validates candidate configuration with nginx -t without deploying."""
        clean_name = validate_site_name(site.name)
        candidate_content = self._generate_nginx_config(site)

        res = await self._call_agent_operation(
            "nginx.config_validate",
            {"site_name": clean_name, "config_content": candidate_content},
        )
        is_valid = bool(res.get("valid", False))
        error_msg = res.get("error")
        return is_valid, error_msg

    async def create_site(self, site: SiteConfig) -> SiteConfig:
        """
        Validates, generates, and atomically deploys a new managed site configuration.
        Fails if site already exists.
        """
        clean_name = validate_site_name(site.name)
        valid_server_names = validate_server_names(site.server_names)
        valid_port = validate_listen_port(site.listen)
        valid_root = validate_web_root(site.root) if not site.proxy.enabled else None
        valid_proxy = validate_proxy_target(site.proxy.target) if site.proxy.enabled else None
        valid_body_size = validate_client_max_body_size(site.client_max_body_size)
        cert_p, key_p = validate_ssl_paths(site.ssl.certificate, site.ssl.certificate_key)

        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if os.path.exists(target_path):
            raise BadRequestError(f"Site '{clean_name}' already exists", code="SITE_ALREADY_EXISTS")

        validated_site = SiteConfig(
            name=clean_name,
            server_names=valid_server_names,
            listen=valid_port,
            listen_ipv6=site.listen_ipv6,
            root=valid_root,
            proxy=SiteProxyConfig(
                enabled=site.proxy.enabled,
                target=valid_proxy,
                preserve_host=site.proxy.preserve_host,
            ),
            ssl=SiteSSLConfig(
                enabled=site.ssl.enabled,
                certificate=cert_p,
                certificate_key=key_p,
            ),
            access_log=site.access_log,
            error_log=site.error_log,
            index=site.index,
            client_max_body_size=valid_body_size,
            enabled=site.enabled,
            managed=True,
            config_path=target_path,
        )

        config_text = self._generate_nginx_config(validated_site)

        res = await self._call_agent_operation(
            "nginx.site_deploy",
            {
                "site_name": clean_name,
                "config_content": config_text,
                "enabled": site.enabled,
            },
        )

        if not res.get("success"):
            error_msg = res.get("error", "Deployment failed")
            raise BadRequestError(f"Failed to deploy site: {error_msg}", code="SITE_DEPLOY_FAILED")

        return validated_site

    async def update_site(self, name: str, site: SiteConfig) -> SiteConfig:
        """
        Atomically updates an existing managed site configuration with rollback protection.
        Rejects modification of unmanaged sites.
        """
        clean_name = validate_site_name(name)
        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if not os.path.isfile(target_path):
            raise NotFoundError(f"Site '{clean_name}' not found", code="SITE_NOT_FOUND")

        # Check existing managed status
        existing_site = self._parse_site_file(clean_name, target_path)
        if not existing_site.managed:
            raise BadRequestError(
                f"Site '{clean_name}' is an unmanaged Nginx configuration. Overwriting is prohibited.",
                code="SITE_UNMANAGED",
            )

        valid_server_names = validate_server_names(site.server_names)
        valid_port = validate_listen_port(site.listen)
        valid_root = validate_web_root(site.root) if not site.proxy.enabled else None
        valid_proxy = validate_proxy_target(site.proxy.target) if site.proxy.enabled else None
        valid_body_size = validate_client_max_body_size(site.client_max_body_size)
        cert_p, key_p = validate_ssl_paths(site.ssl.certificate, site.ssl.certificate_key)

        updated_site = SiteConfig(
            name=clean_name,
            server_names=valid_server_names,
            listen=valid_port,
            listen_ipv6=site.listen_ipv6,
            root=valid_root,
            proxy=SiteProxyConfig(
                enabled=site.proxy.enabled,
                target=valid_proxy,
                preserve_host=site.proxy.preserve_host,
            ),
            ssl=SiteSSLConfig(
                enabled=site.ssl.enabled,
                certificate=cert_p,
                certificate_key=key_p,
            ),
            access_log=site.access_log,
            error_log=site.error_log,
            index=site.index,
            client_max_body_size=valid_body_size,
            enabled=site.enabled,
            managed=True,
            config_path=target_path,
        )

        config_text = self._generate_nginx_config(updated_site)

        res = await self._call_agent_operation(
            "nginx.site_deploy",
            {
                "site_name": clean_name,
                "config_content": config_text,
                "enabled": site.enabled,
            },
        )

        if not res.get("success"):
            error_msg = res.get("error", "Update failed")
            raise BadRequestError(f"Failed to update site: {error_msg}", code="SITE_UPDATE_FAILED")

        return updated_site

    async def delete_site(self, name: str) -> bool:
        """
        Safely removes a managed site configuration and its symlink.
        Rejects deletion of unmanaged configurations.
        """
        clean_name = validate_site_name(name)
        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if not os.path.isfile(target_path):
            raise NotFoundError(f"Site '{clean_name}' not found", code="SITE_NOT_FOUND")

        existing_site = self._parse_site_file(clean_name, target_path)
        if not existing_site.managed:
            raise BadRequestError(
                f"Site '{clean_name}' is an unmanaged Nginx configuration. Removal is prohibited.",
                code="SITE_UNMANAGED",
            )

        res = await self._call_agent_operation("nginx.site_remove", {"site_name": clean_name})
        if not res.get("success"):
            raise BadRequestError(res.get("error", "Failed to remove site"), code="SITE_REMOVE_FAILED")
        return True

    async def enable_site(self, name: str) -> bool:
        """Enables a site via controlled symlink, validates, and reloads Nginx."""
        clean_name = validate_site_name(name)
        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if not os.path.isfile(target_path):
            raise NotFoundError(f"Site '{clean_name}' not found", code="SITE_NOT_FOUND")

        existing_site = self._parse_site_file(clean_name, target_path)
        if not existing_site.managed:
            raise BadRequestError(
                f"Site '{clean_name}' is an unmanaged Nginx configuration. Enabling is prohibited.",
                code="SITE_UNMANAGED",
            )

        res = await self._call_agent_operation("nginx.site_enable", {"site_name": clean_name})
        if not res.get("success"):
            raise BadRequestError(res.get("error", "Failed to enable site"), code="SITE_ENABLE_FAILED")
        return True

    async def disable_site(self, name: str) -> bool:
        """Disables a site by removing its symlink in sites-enabled."""
        clean_name = validate_site_name(name)
        target_path = os.path.join(SITES_AVAILABLE_DIR, clean_name)
        if not os.path.isfile(target_path):
            raise NotFoundError(f"Site '{clean_name}' not found", code="SITE_NOT_FOUND")

        existing_site = self._parse_site_file(clean_name, target_path)
        if not existing_site.managed:
            raise BadRequestError(
                f"Site '{clean_name}' is an unmanaged Nginx configuration. Disabling is prohibited.",
                code="SITE_UNMANAGED",
            )

        res = await self._call_agent_operation("nginx.site_disable", {"site_name": clean_name})
        if not res.get("success"):
            raise BadRequestError(res.get("error", "Failed to disable site"), code="SITE_DISABLE_FAILED")
        return True

    async def reload(self) -> Tuple[bool, Optional[str]]:
        """Safely reloads Nginx using dedicated operation 'nginx.reload'."""
        res = await self._call_agent_operation("nginx.reload", {})
        success = bool(res.get("success", False))
        err = res.get("error")
        return success, err


# Singleton instance for FastAPI control plane
nginx_manager = LinuxNginxManager()
