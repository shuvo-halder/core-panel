import os
import platform
from typing import Any, Awaitable, Callable, Dict

from agent.app.operations.cron import (
    handle_cron_create,
    handle_cron_delete,
    handle_cron_list,
    handle_cron_update,
)
from agent.app.operations.processes import (
    kill_process_operation,
    terminate_process_operation,
)
from agent.app.operations.systemd import (
    handle_service_disable,
    handle_service_enable,
    handle_service_restart,
    handle_service_start,
    handle_service_stop,
)

OperationHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class OperationRegistry:
    """Registry of approved privileged operations. Strict whitelist, no arbitrary exec."""

    def __init__(self):
        self._handlers: Dict[str, OperationHandler] = {}
        self._register_default_operations()

    def register(self, name: str, handler: OperationHandler) -> None:
        self._handlers[name] = handler

    def has_operation(self, name: str) -> bool:
        return name in self._handlers

    async def execute(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.has_operation(name):
            raise ValueError(f"Unknown or prohibited operation: '{name}'")
        handler = self._handlers[name]
        return await handler(payload)

    def _register_default_operations(self) -> None:
        async def handle_ping(payload: Dict[str, Any]) -> Dict[str, Any]:
            return {"status": "ready", "role": "privileged_agent", "pid": os.getpid()}

        async def handle_system_info(payload: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            }

        self.register("agent.ping", handle_ping)
        self.register("system.info", handle_system_info)

        # Allowlisted Systemd Service Operations (Phase 4)
        self.register("systemd.service.start", handle_service_start)
        self.register("systemd.service.stop", handle_service_stop)
        self.register("systemd.service.restart", handle_service_restart)
        self.register("systemd.service.enable", handle_service_enable)
        self.register("systemd.service.disable", handle_service_disable)

        # Allowlisted Process Management Operations (Phase 5)
        self.register("process.terminate", terminate_process_operation)
        self.register("process.kill", kill_process_operation)

        # Allowlisted Scheduled Jobs / Cron Operations (Phase 9)
        self.register("cron.list", handle_cron_list)
        self.register("cron.create", handle_cron_create)
        self.register("cron.update", handle_cron_update)
        self.register("cron.delete", handle_cron_delete)


registry = OperationRegistry()
