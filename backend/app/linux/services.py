import os
import shutil
from typing import Dict, List, Optional

from backend.app.core.errors import AppError, NotFoundError
from backend.app.core.logging import logger
from backend.app.core.validators import validate_service_unit_name
from backend.app.linux.contracts import ICommandRunner, IServiceCollector, ServiceInfo
from backend.app.linux.runner import runner as default_runner


class ServiceManagerUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Systemd service manager is not available on this host",
        code: str = "SERVICE_MANAGER_UNAVAILABLE",
    ):
        super().__init__(message, code=code, status_code=503)


class LinuxServiceCollector(IServiceCollector):
    """
    Unprivileged systemd service collector for discovering and inspecting .service units.
    Uses structured unprivileged systemctl queries with fallback handling.
    """

    def __init__(self, command_runner: Optional[ICommandRunner] = None):
        self.runner = command_runner or default_runner

    def is_available(self) -> bool:
        """Checks if systemctl and systemd runtime directory exist."""
        has_systemctl = shutil.which("systemctl") is not None
        has_systemd_dir = os.path.exists("/run/systemd/system")
        return bool(has_systemctl and has_systemd_dir)

    async def list_services(self) -> List[ServiceInfo]:
        """
        Lists all systemd .service units in O(1) subprocess calls without N+1 queries.
        Filters out non-.service units (sockets, targets, mounts, devices, etc.).
        """
        if not shutil.which("systemctl"):
            logger.info("systemctl not available; returning empty service list")
            return []

        # 1. Query unit files for enablement state: systemctl list-unit-files --type=service
        enabled_map: Dict[str, str] = {}
        try:
            res_files = await self.runner.run(
                "systemctl",
                ["list-unit-files", "--type=service", "--no-pager", "--plain", "--no-legend"],
                timeout_seconds=10.0,
            )
            if res_files.is_success:
                for line in res_files.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].endswith(".service"):
                        enabled_map[parts[0]] = parts[1]
        except Exception as exc:
            logger.warning(f"Failed to query systemctl list-unit-files: {exc}")

        # 2. Query active/loaded units: systemctl list-units --type=service --all
        services: Dict[str, ServiceInfo] = {}
        try:
            res_units = await self.runner.run(
                "systemctl",
                ["list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend"],
                timeout_seconds=10.0,
            )
            if res_units.is_success:
                for line in res_units.stdout.splitlines():
                    parts = line.split(maxsplit=4)
                    if len(parts) >= 4:
                        unit_name = parts[0].strip()
                        # Handle dot prefix or special markers if present
                        if unit_name.startswith("●"):
                            # If systemctl prefixed with bullet point
                            parts = line.replace("●", " ").split(maxsplit=4)
                            if len(parts) < 4:
                                continue
                            unit_name = parts[0].strip()

                        if not unit_name.endswith(".service"):
                            continue

                        load_state = parts[1]
                        active_state = parts[2]
                        sub_state = parts[3]
                        description = parts[4] if len(parts) > 4 else ""
                        enabled_state = enabled_map.get(unit_name, "unknown")

                        services[unit_name] = ServiceInfo(
                            unit=unit_name,
                            description=description,
                            load_state=load_state,
                            active_state=active_state,
                            sub_state=sub_state,
                            enabled=enabled_state,
                            main_pid=None,
                        )
        except Exception as exc:
            logger.warning(f"Failed to query systemctl list-units: {exc}")

        # 3. Include any unit files that weren't listed in active units
        for unit_name, enabled_state in enabled_map.items():
            if unit_name not in services:
                services[unit_name] = ServiceInfo(
                    unit=unit_name,
                    description="",
                    load_state="loaded",
                    active_state="inactive",
                    sub_state="dead",
                    enabled=enabled_state,
                    main_pid=None,
                )

        return sorted(list(services.values()), key=lambda s: s.unit)

    async def get_service(self, unit: str) -> Optional[ServiceInfo]:
        """
        Inspects details for a single validated .service unit using fixed property list.
        Never exposes arbitrary systemctl show parameters.
        """
        clean_unit = validate_service_unit_name(unit)

        if not shutil.which("systemctl"):
            return None

        # Fixed, restricted properties
        properties = "Id,Description,LoadState,ActiveState,SubState,UnitFileState,MainPID"
        res = await self.runner.run(
            "systemctl",
            ["show", clean_unit, f"--property={properties}", "--no-pager"],
            timeout_seconds=10.0,
        )

        if not res.is_success or not res.stdout:
            return None

        prop_dict: Dict[str, str] = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                prop_dict[k.strip()] = v.strip()

        unit_id = prop_dict.get("Id", clean_unit)
        if not unit_id or unit_id == "":
            unit_id = clean_unit

        load_state = prop_dict.get("LoadState", "unknown")
        if load_state == "not-found" and prop_dict.get("ActiveState") == "inactive":
            # Unit does not exist
            raise NotFoundError(f"Service unit '{clean_unit}' not found on system")

        active_state = prop_dict.get("ActiveState", "unknown")
        sub_state = prop_dict.get("SubState", "unknown")
        enabled_state = prop_dict.get("UnitFileState", "unknown")
        description = prop_dict.get("Description", "")

        main_pid_val: Optional[int] = None
        main_pid_str = prop_dict.get("MainPID")
        if main_pid_str and main_pid_str.isdigit():
            pid_int = int(main_pid_str)
            if pid_int > 0:
                main_pid_val = pid_int

        return ServiceInfo(
            unit=clean_unit,
            description=description,
            load_state=load_state,
            active_state=active_state,
            sub_state=sub_state,
            enabled=enabled_state,
            main_pid=main_pid_val,
        )


service_collector = LinuxServiceCollector()
