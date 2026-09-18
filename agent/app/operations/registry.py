import os
import platform
from typing import Any, Awaitable, Callable, Dict

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


registry = OperationRegistry()
