import asyncio
import os
import re
import shutil
from typing import Any, Dict

from backend.app.core.logging import logger

SERVICE_UNIT_PATTERN = re.compile(r"^[a-zA-Z0-9_\@\.\-]+\.service$")
PROHIBITED_CHARS_PATTERN = re.compile(r"[\s/\\;\|\&\>\<\$\`\'\"\x00\n\r\t]")

ALLOWED_SYSTEMD_ACTIONS = {"start", "stop", "restart", "enable", "disable"}


def validate_systemd_unit(unit: str) -> str:
    """
    Independent validation within CoreAgent (Defense-in-Depth).
    Strictly validates systemd service unit name before execution.
    """
    if not isinstance(unit, str):
        raise ValueError("Invalid unit name: must be a string")

    if PROHIBITED_CHARS_PATTERN.search(unit) or unit != unit.strip():
        raise ValueError("Invalid unit: prohibited shell metacharacters, control chars, or whitespace detected")

    clean_unit = unit.strip()

    if len(clean_unit) < 9 or len(clean_unit) > 256:
        raise ValueError("Invalid unit name length: must be between 9 and 256 characters")

    if not clean_unit.endswith(".service"):
        raise ValueError("Invalid unit: only .service units are supported")

    if ".." in clean_unit or "/" in clean_unit or "\\" in clean_unit:
        raise ValueError("Invalid unit: directory traversal or path separators prohibited")

    if not SERVICE_UNIT_PATTERN.match(clean_unit):
        raise ValueError(f"Invalid unit name format: '{clean_unit}'")

    return clean_unit


def resolve_systemctl() -> str:
    """Resolves and verifies systemctl binary location."""
    systemctl_bin = shutil.which("systemctl")
    if not systemctl_bin:
        for fallback in ("/bin/systemctl", "/usr/bin/systemctl"):
            if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
                systemctl_bin = fallback
                break

    if not systemctl_bin:
        raise RuntimeError("systemctl binary not found or not executable on host system")

    return systemctl_bin


async def execute_systemctl_action(
    action: str, unit: str, timeout_seconds: float = 20.0
) -> Dict[str, Any]:
    """
    Executes an allowlisted systemctl action on a validated service unit.
    Strictly forbids shell=True and uses direct array arguments.
    """
    if action not in ALLOWED_SYSTEMD_ACTIONS:
        raise ValueError(f"Prohibited systemctl action: '{action}'")

    valid_unit = validate_systemd_unit(unit)
    systemctl_bin = resolve_systemctl()

    logger.info(f"CoreAgent executing: {systemctl_bin} {action} {valid_unit}")

    # Explicit array parameters with shell=False
    args = [action, valid_unit]
    try:
        proc = await asyncio.create_subprocess_exec(
            systemctl_bin,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(
                f"systemctl {action} {valid_unit} timed out after {timeout_seconds}s"
            )

        stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            error_msg = stderr_str or stdout_str or f"Exited with code {proc.returncode}"
            logger.warning(
                f"systemctl {action} {valid_unit} failed (exit {proc.returncode}): {error_msg}"
            )
            raise RuntimeError(f"Service operation failed: {error_msg}")

        return {
            "unit": valid_unit,
            "operation": action,
            "success": True,
            "exit_code": 0,
            "message": f"Successfully performed '{action}' on {valid_unit}",
        }

    except (ValueError, RuntimeError, TimeoutError):
        raise
    except Exception as exc:
        logger.error(f"Unexpected error executing systemctl {action} {valid_unit}: {exc}")
        raise RuntimeError(f"Internal systemctl execution failure: {exc}")


async def handle_service_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    unit = payload.get("unit", "")
    return await execute_systemctl_action("start", unit)


async def handle_service_stop(payload: Dict[str, Any]) -> Dict[str, Any]:
    unit = payload.get("unit", "")
    return await execute_systemctl_action("stop", unit)


async def handle_service_restart(payload: Dict[str, Any]) -> Dict[str, Any]:
    unit = payload.get("unit", "")
    return await execute_systemctl_action("restart", unit)


async def handle_service_enable(payload: Dict[str, Any]) -> Dict[str, Any]:
    unit = payload.get("unit", "")
    return await execute_systemctl_action("enable", unit)


async def handle_service_disable(payload: Dict[str, Any]) -> Dict[str, Any]:
    unit = payload.get("unit", "")
    return await execute_systemctl_action("disable", unit)
