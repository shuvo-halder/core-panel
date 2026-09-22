import asyncio
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("corepanel.agent.nginx")

# Static, locked configuration paths for Debian/Ubuntu Nginx layout
NGINX_CONF_PATH = "/etc/nginx/nginx.conf"
SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"

MANAGED_HEADER_PREFIX = "# MANAGED BY COREPANEL - DO NOT EDIT MANUALLY"
SAFE_SITE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9_\-\.]{0,251}[a-zA-Z0-9])?$")


def _resolve_nginx_bin() -> Optional[str]:
    """Finds Nginx binary from system PATH or standard binary locations."""
    found = shutil.which("nginx")
    if found and os.path.isfile(found) and os.access(found, os.X_OK):
        return found
    for fallback in ("/usr/sbin/nginx", "/usr/bin/nginx", "/sbin/nginx", "/bin/nginx"):
        if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
            return fallback
    return None


def _resolve_systemctl_bin() -> Optional[str]:
    """Finds systemctl binary from system PATH or standard binary locations."""
    found = shutil.which("systemctl")
    if found and os.path.isfile(found) and os.access(found, os.X_OK):
        return found
    for fallback in ("/bin/systemctl", "/usr/bin/systemctl"):
        if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
            return fallback
    return None


def _validate_safe_name(name: str) -> str:
    """Validates site name to strictly prevent directory traversal or invalid characters."""
    clean = str(name).strip().lower()
    if not clean or len(clean) > 253:
        raise ValueError(f"Invalid site name length: '{clean}'")
    if "/" in clean or "\\" in clean or ".." in clean or clean.startswith("-") or clean.startswith("."):
        raise ValueError(f"Prohibited characters or path traversal in site name: '{clean}'")
    if not SAFE_SITE_NAME_REGEX.match(clean):
        raise ValueError(f"Site name format invalid: '{clean}'")
    return clean


async def _run_nginx_test() -> Tuple[bool, str]:
    """
    Executes 'nginx -t' using fixed arguments and shell=False with strict timeout.
    Returns (is_valid, output_message).
    """
    nginx_bin = _resolve_nginx_bin()
    if not nginx_bin:
        return False, "Nginx binary not found on host system"

    cmd = [nginx_bin, "-t"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "nginx -t timed out after 5.0 seconds"

        out = (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()
        return proc.returncode == 0, out
    except Exception as exc:
        return False, f"Failed to run nginx -t: {exc}"


async def _reload_nginx() -> Tuple[bool, str]:
    """
    Safely reloads Nginx service using fixed commands and shell=False.
    Prefers 'systemctl reload nginx.service' where available, falling back to 'nginx -s reload'.
    """
    systemctl_bin = _resolve_systemctl_bin()
    if systemctl_bin:
        cmd = [systemctl_bin, "reload", "nginx.service"]
    else:
        nginx_bin = _resolve_nginx_bin()
        if not nginx_bin:
            return False, "Neither systemctl nor nginx binary found for reload"
        cmd = [nginx_bin, "-s", "reload"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "Nginx reload timed out after 5.0 seconds"

        if proc.returncode == 0:
            return True, "Nginx reloaded successfully"
        err = stderr.decode("utf-8", errors="replace").strip()
        return False, f"Reload exited with code {proc.returncode}: {err}"
    except Exception as exc:
        return False, f"Failed to execute reload: {exc}"


async def handle_nginx_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.status
    Gathers Nginx installation details, active service state, configuration validity, and site counts.
    """
    nginx_bin = _resolve_nginx_bin()
    installed = nginx_bin is not None
    version: Optional[str] = None

    if installed and nginx_bin:
        try:
            proc = await asyncio.create_subprocess_exec(
                nginx_bin,
                "-v",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
            ver_text = stderr.decode("utf-8", errors="replace").strip()
            # Format: nginx version: nginx/1.22.1
            m = re.search(r"nginx/([0-9\.]+)", ver_text)
            version = m.group(1) if m else ver_text
        except Exception:
            version = None

    # Service active state
    service_active = False
    systemctl_bin = _resolve_systemctl_bin()
    if systemctl_bin:
        try:
            proc = await asyncio.create_subprocess_exec(
                systemctl_bin,
                "is-active",
                "--quiet",
                "nginx.service",
            )
            await asyncio.wait_for(proc.communicate(), timeout=3.0)
            service_active = proc.returncode == 0
        except Exception:
            service_active = False
    else:
        # Check pid file or process list
        if os.path.isfile("/var/run/nginx.pid") or os.path.isfile("/run/nginx.pid"):
            service_active = True

    # Test configuration
    config_valid, config_output = await _run_nginx_test() if installed else (False, "Nginx not installed")

    # Count sites
    avail_count = 0
    if os.path.isdir(SITES_AVAILABLE_DIR):
        try:
            avail_count = len([f for f in os.listdir(SITES_AVAILABLE_DIR) if not f.startswith(".")])
        except Exception:
            avail_count = 0

    enabled_count = 0
    if os.path.isdir(SITES_ENABLED_DIR):
        try:
            enabled_count = len([f for f in os.listdir(SITES_ENABLED_DIR) if not f.startswith(".")])
        except Exception:
            enabled_count = 0

    return {
        "installed": installed,
        "version": version,
        "executable_path": nginx_bin,
        "service_active": service_active,
        "config_path": NGINX_CONF_PATH if os.path.isfile(NGINX_CONF_PATH) else None,
        "sites_available_count": avail_count,
        "sites_enabled_count": enabled_count,
        "config_valid": config_valid,
        "config_output": config_output,
    }


async def handle_nginx_config_validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.config_validate
    Safely validates candidate configuration syntax without altering active site configurations.
    Temporarily mounts candidate config into sites-enabled, runs 'nginx -t', and cleans up.
    """
    site_name = _validate_safe_name(payload.get("site_name", "test_candidate"))
    content = str(payload.get("config_content", ""))
    if not content.strip():
        return {"valid": False, "error": "Configuration content cannot be empty"}

    tmp_avail = os.path.join(SITES_AVAILABLE_DIR, f".tmp_test_{site_name}.conf")
    tmp_enabled = os.path.join(SITES_ENABLED_DIR, f".tmp_test_{site_name}.conf")

    try:
        # Write candidate file with restrictive permissions
        with open(tmp_avail, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp_avail, 0o644)

        # Create temporary symlink so nginx -t validates it
        if os.path.lexists(tmp_enabled):
            try:
                os.unlink(tmp_enabled)
            except OSError:
                pass
        os.symlink(tmp_avail, tmp_enabled)

        # Run validation
        is_valid, out = await _run_nginx_test()
        return {
            "valid": is_valid,
            "output": out,
            "error": None if is_valid else out,
        }
    except Exception as exc:
        return {"valid": False, "error": f"Candidate validation failed: {exc}"}
    finally:
        # Always clean up temporary files
        if os.path.lexists(tmp_enabled):
            try:
                os.unlink(tmp_enabled)
            except OSError:
                pass
        if os.path.exists(tmp_avail):
            try:
                os.remove(tmp_avail)
            except OSError:
                pass


async def handle_nginx_site_deploy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.site_deploy
    Atomically creates or updates an Nginx virtual host with pre-validation, backup,
    symlink management, reload, and automatic rollback on reload failure.
    """
    site_name = _validate_safe_name(payload.get("site_name", ""))
    config_content = str(payload.get("config_content", ""))
    enabled = bool(payload.get("enabled", True))

    if not config_content.strip():
        raise ValueError("Configuration content cannot be empty")

    avail_path = os.path.join(SITES_AVAILABLE_DIR, site_name)
    enabled_path = os.path.join(SITES_ENABLED_DIR, site_name)
    backup_path = os.path.join(SITES_AVAILABLE_DIR, f".{site_name}.bak")
    temp_new_path = os.path.join(SITES_AVAILABLE_DIR, f".new_{site_name}.tmp")

    # Protection: Never overwrite unmanaged configurations
    if os.path.isfile(avail_path):
        try:
            with open(avail_path, "r", encoding="utf-8", errors="replace") as f:
                existing_first_line = f.readline()
            if not existing_first_line.startswith(MANAGED_HEADER_PREFIX):
                raise ValueError(
                    f"Site '{site_name}' is an unmanaged Nginx configuration. Automatic modification is prohibited."
                )
        except OSError as exc:
            raise ValueError(f"Failed to inspect existing site config '{site_name}': {exc}")

    # 1. Pre-validation of candidate config
    val_res = await handle_nginx_config_validate({"site_name": site_name, "config_content": config_content})
    if not val_res.get("valid"):
        return {
            "success": False,
            "error": f"Nginx configuration syntax validation failed: {val_res.get('error')}",
            "rolled_back": False,
        }

    # 2. Preserve backup of existing config if present
    had_previous = os.path.isfile(avail_path)
    previous_enabled = os.path.islink(enabled_path)
    if had_previous:
        shutil.copy2(avail_path, backup_path)

    try:
        # 3. Write new config atomically using temporary file in same directory
        with open(temp_new_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        os.chmod(temp_new_path, 0o644)
        os.replace(temp_new_path, avail_path)

        # 4. Manage symlink in sites-enabled
        if enabled:
            if os.path.islink(enabled_path):
                # Verify existing link points to our site
                current_target = os.readlink(enabled_path)
                if current_target != avail_path and current_target != f"../sites-available/{site_name}":
                    os.unlink(enabled_path)
                    os.symlink(avail_path, enabled_path)
            elif not os.path.exists(enabled_path):
                os.symlink(avail_path, enabled_path)
        else:
            if os.path.lexists(enabled_path):
                os.unlink(enabled_path)

        # 5. Post-deployment test
        is_valid, test_out = await _run_nginx_test()
        if not is_valid:
            raise RuntimeError(f"Post-deployment syntax validation failed: {test_out}")

        # 6. Reload service
        reloaded, reload_msg = await _reload_nginx()
        if not reloaded:
            raise RuntimeError(f"Service reload failed: {reload_msg}")

        # Success - remove backup
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass

        return {
            "success": True,
            "site_name": site_name,
            "enabled": enabled,
            "message": "Site deployed and reloaded successfully",
        }

    except Exception as exc:
        logger.error(f"Deployment failed for site '{site_name}': {exc}. Commencing rollback...")
        # Rollback procedure
        try:
            if had_previous and os.path.exists(backup_path):
                shutil.copy2(backup_path, avail_path)
                os.remove(backup_path)
                if previous_enabled:
                    if not os.path.lexists(enabled_path):
                        os.symlink(avail_path, enabled_path)
                else:
                    if os.path.lexists(enabled_path):
                        os.unlink(enabled_path)
            else:
                # Newly created site; remove artifacts
                if os.path.exists(avail_path):
                    os.remove(avail_path)
                if os.path.lexists(enabled_path):
                    os.unlink(enabled_path)

            if os.path.exists(temp_new_path):
                os.remove(temp_new_path)

            # Re-reload to restore previous operational state
            await _reload_nginx()
        except Exception as rb_exc:
            logger.error(f"Critical error during rollback for site '{site_name}': {rb_exc}")

        return {
            "success": False,
            "error": str(exc),
            "rolled_back": True,
        }


async def handle_nginx_site_remove(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.site_remove
    Safely removes a managed site configuration and its enabled symlink.
    Refuses to delete unmanaged configuration files.
    """
    site_name = _validate_safe_name(payload.get("site_name", ""))
    avail_path = os.path.join(SITES_AVAILABLE_DIR, site_name)
    enabled_path = os.path.join(SITES_ENABLED_DIR, site_name)

    if not os.path.isfile(avail_path):
        return {"success": False, "error": f"Site configuration '{site_name}' not found"}

    # Protection: check managed header
    with open(avail_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
    if not first_line.startswith(MANAGED_HEADER_PREFIX):
        raise ValueError(
            f"Site '{site_name}' is an unmanaged Nginx configuration. Removal via control panel is prohibited."
        )

    # Backup in case reload fails
    backup_path = os.path.join(SITES_AVAILABLE_DIR, f".del_{site_name}.bak")
    shutil.copy2(avail_path, backup_path)
    had_enabled = os.path.islink(enabled_path)

    try:
        if had_enabled:
            os.unlink(enabled_path)
        os.remove(avail_path)

        is_valid, test_out = await _run_nginx_test()
        if not is_valid:
            raise RuntimeError(f"Syntax test failed after removal: {test_out}")

        reloaded, msg = await _reload_nginx()
        if not reloaded:
            raise RuntimeError(f"Reload failed after removal: {msg}")

        if os.path.exists(backup_path):
            os.remove(backup_path)

        return {"success": True, "message": f"Site '{site_name}' successfully removed"}
    except Exception as exc:
        # Rollback removal
        shutil.copy2(backup_path, avail_path)
        os.remove(backup_path)
        if had_enabled and not os.path.lexists(enabled_path):
            os.symlink(avail_path, enabled_path)
        await _reload_nginx()
        return {"success": False, "error": f"Removal failed and was rolled back: {exc}"}


async def handle_nginx_site_enable(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.site_enable
    Enables an existing site by creating a symlink in sites-enabled pointing to sites-available.
    Validates that the site is managed by CorePanel, then checks syntax with 'nginx -t' before reloading.
    """
    site_name = _validate_safe_name(payload.get("site_name", ""))
    avail_path = os.path.join(SITES_AVAILABLE_DIR, site_name)
    enabled_path = os.path.join(SITES_ENABLED_DIR, site_name)

    if not os.path.isfile(avail_path):
        return {"success": False, "error": f"Site '{site_name}' does not exist in sites-available"}

    # Protection: check managed header
    with open(avail_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
    if not first_line.startswith(MANAGED_HEADER_PREFIX):
        raise ValueError(
            f"Site '{site_name}' is an unmanaged Nginx configuration. Enabling via control panel is prohibited."
        )

    if os.path.islink(enabled_path):
        return {"success": True, "message": f"Site '{site_name}' is already enabled"}

    try:
        os.symlink(avail_path, enabled_path)
        is_valid, out = await _run_nginx_test()
        if not is_valid:
            os.unlink(enabled_path)
            return {"success": False, "error": f"Enabling site '{site_name}' causes configuration error: {out}"}

        reloaded, reload_err = await _reload_nginx()
        if not reloaded:
            os.unlink(enabled_path)
            await _reload_nginx()
            return {"success": False, "error": f"Failed to reload Nginx: {reload_err}"}

        return {"success": True, "message": f"Site '{site_name}' enabled successfully"}
    except Exception as exc:
        if os.path.lexists(enabled_path):
            try:
                os.unlink(enabled_path)
            except OSError:
                pass
        return {"success": False, "error": f"Failed to enable site: {exc}"}


async def handle_nginx_site_disable(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.site_disable
    Disables a site by removing its symlink in sites-enabled.
    Validates that the site is managed by CorePanel, then validates configuration and reloads Nginx.
    """
    site_name = _validate_safe_name(payload.get("site_name", ""))
    avail_path = os.path.join(SITES_AVAILABLE_DIR, site_name)
    enabled_path = os.path.join(SITES_ENABLED_DIR, site_name)

    if not os.path.isfile(avail_path):
        return {"success": False, "error": f"Site '{site_name}' does not exist in sites-available"}

    # Protection: check managed header
    with open(avail_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
    if not first_line.startswith(MANAGED_HEADER_PREFIX):
        raise ValueError(
            f"Site '{site_name}' is an unmanaged Nginx configuration. Disabling via control panel is prohibited."
        )

    if not os.path.lexists(enabled_path):
        return {"success": True, "message": f"Site '{site_name}' is already disabled"}

    try:
        os.unlink(enabled_path)
        is_valid, out = await _run_nginx_test()
        if not is_valid:
            # Recreate link if disabling broke configuration (e.g. dependency)
            os.symlink(avail_path, enabled_path)
            return {"success": False, "error": f"Disabling site '{site_name}' broke configuration: {out}"}

        reloaded, reload_err = await _reload_nginx()
        if not reloaded:
            os.symlink(avail_path, enabled_path)
            await _reload_nginx()
            return {"success": False, "error": f"Failed to reload Nginx: {reload_err}"}

        return {"success": True, "message": f"Site '{site_name}' disabled successfully"}
    except Exception as exc:
        return {"success": False, "error": f"Failed to disable site: {exc}"}


async def handle_nginx_reload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operation: nginx.reload
    Dedicated allowlisted operation executing strictly 'systemctl reload nginx.service'.
    Does not accept arbitrary systemctl commands or unit arguments.
    """
    is_valid, test_out = await _run_nginx_test()
    if not is_valid:
        return {
            "success": False,
            "error": f"Cannot reload: Nginx configuration test failed: {test_out}",
        }

    reloaded, msg = await _reload_nginx()
    return {
        "success": reloaded,
        "message": msg if reloaded else None,
        "error": None if reloaded else msg,
    }
