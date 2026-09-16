from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CommandResult:
    """Structured result of command execution."""
    executable: str
    args: List[str]
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0


class ICommandRunner(ABC):
    """Abstract contract for secure command execution."""

    @abstractmethod
    async def run(
        self,
        executable: str,
        args: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1024 * 1024
    ) -> CommandResult:
        """Run an approved executable with arguments."""
        pass


@dataclass(frozen=True)
class OSInfo:
    distribution: str
    version: str
    architecture: str
    kernel_version: str
    is_supported: bool


class IOSProvider(ABC):
    """Contract for operating system identification and inspection."""

    @abstractmethod
    def detect_os(self) -> OSInfo:
        pass


class ISystemdProvider(ABC):
    """Contract for Systemd service management (Pending Phase 10)."""

    @abstractmethod
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Pending Phase 10 implementation."""
        pass

    @abstractmethod
    async def restart_service(self, service_name: str) -> bool:
        """Pending Phase 10 implementation."""
        pass


class IPackageManager(ABC):
    """Contract for package management (Pending Phase 11)."""

    @abstractmethod
    async def is_package_installed(self, package_name: str) -> bool:
        """Pending Phase 11 implementation."""
        pass


class IFilesystemProvider(ABC):
    """Contract for safe filesystem operations (Pending Phase 18)."""

    @abstractmethod
    def resolve_safe_path(self, user_path: str, base_root: str) -> str:
        """Pending Phase 18 implementation."""
        pass


class IProcessProvider(ABC):
    """Contract for process monitoring (Pending Phase 9)."""

    @abstractmethod
    async def list_processes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Pending Phase 9 implementation."""
        pass


class ILinuxProvider(ABC):
    """Consolidated provider contract for system interaction."""
    os: IOSProvider
    runner: ICommandRunner
