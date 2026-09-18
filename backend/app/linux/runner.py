import asyncio
import os
import re
import shutil
import time
from typing import List, Optional, Set

from backend.app.core.logging import logger
from backend.app.linux.contracts import CommandResult, ICommandRunner


class SecurityError(Exception):
    """Raised when a command violates security policies."""

    pass


class CommandTimeoutError(Exception):
    """Raised when command execution exceeds timeout."""

    pass


class LinuxCommandRunner(ICommandRunner):
    """
    Secure subprocess execution engine for Linux server administration.
    Strictly forbids shell=True, enforces binary allowlisting and parameter sanity.
    """

    # Strictly approved binaries
    ALLOWED_EXECUTABLES: Set[str] = {
        "uptime",
        "uname",
        "free",
        "df",
        "cat",
        "dpkg",
        "systemctl",
        "nginx",
        "ufw",
        "which",
    }

    # Prohibited shell control characters in individual arguments
    DANGEROUS_CHAR_REGEX = re.compile(r"[`$;|&><\n\r]")

    def __init__(self, additional_allowed: Optional[Set[str]] = None):
        self.allowed_executables = set(self.ALLOWED_EXECUTABLES)
        if additional_allowed:
            self.allowed_executables.update(additional_allowed)

    def _resolve_executable(self, executable: str) -> str:
        """Validates that executable is allowlisted and resolves full path."""
        base_name = os.path.basename(executable)
        if base_name not in self.allowed_executables:
            raise SecurityError(
                f"Execution rejected: Binary '{base_name}' is not in the approved allowlist."
            )

        resolved_path = shutil.which(executable)
        if (
            not resolved_path
            or not os.path.isfile(resolved_path)
            or not os.access(resolved_path, os.X_OK)
        ):
            raise SecurityError(
                f"Execution rejected: Binary '{executable}' not found or not executable."
            )

        return resolved_path

    def _validate_args(self, args: List[str]) -> None:
        """Ensures arguments do not contain illicit control injection sequences."""
        for arg in args:
            if self.DANGEROUS_CHAR_REGEX.search(arg):
                raise SecurityError(
                    f"Execution rejected: Argument contains prohibited shell characters: {arg!r}"
                )

    async def run(
        self,
        executable: str,
        args: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1024 * 1024,
    ) -> CommandResult:
        args = args or []
        resolved_bin = self._resolve_executable(executable)
        self._validate_args(args)

        start_time = time.monotonic()
        try:
            # shell=False is enforced implicitly by create_subprocess_exec
            proc = await asyncio.create_subprocess_exec(
                resolved_bin, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
                raise CommandTimeoutError(
                    f"Command '{resolved_bin} {' '.join(args)}' timed out after {timeout_seconds}s"
                )

            duration_ms = (time.monotonic() - start_time) * 1000

            stdout_str = stdout_data[:max_output_bytes].decode("utf-8", errors="replace")
            stderr_str = stderr_data[:max_output_bytes].decode("utf-8", errors="replace")

            return CommandResult(
                executable=resolved_bin,
                args=args,
                stdout=stdout_str.strip(),
                stderr=stderr_str.strip(),
                exit_code=proc.returncode if proc.returncode is not None else -1,
                duration_ms=round(duration_ms, 2),
            )

        except (SecurityError, CommandTimeoutError):
            raise
        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(f"Execution failed for {executable}: {str(exc)}")
            return CommandResult(
                executable=resolved_bin if "resolved_bin" in locals() else executable,
                args=args,
                stdout="",
                stderr=str(exc),
                exit_code=1,
                duration_ms=round(duration_ms, 2),
            )


# Default runner instance
runner = LinuxCommandRunner()
