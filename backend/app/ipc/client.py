import asyncio
from typing import Any, Dict, Optional

from agent.app.ipc.protocol import IPCRequest, IPCResponse
from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.logging import logger


class AgentUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Privileged agent service is unavailable",
        code: str = "AGENT_UNAVAILABLE",
    ):
        super().__init__(message, code=code, status_code=503)


class AgentExecutionError(AppError):
    def __init__(
        self, message: str = "Privileged operation failed", code: str = "EXECUTION_FAILED"
    ):
        super().__init__(message, code=code, status_code=500)


class IPCClient:
    """Unix Domain Socket IPC Client for invoking CoreAgent privileged operations."""

    def __init__(self, socket_path: Optional[str] = None):
        self.socket_path = socket_path or str(settings.AGENT_SOCKET_PATH)

    async def execute(
        self,
        operation: str,
        payload: Dict[str, Any],
        request_id: str = "req_internal",
        timeout_seconds: float = 25.0,
    ) -> Dict[str, Any]:
        """
        Transmits a structured request over the Unix Domain Socket to CoreAgent.
        Enforces timeout and maps failures to structured domain errors.
        """
        request = IPCRequest(
            version=1,
            requestId=request_id,
            operation=operation,
            payload=payload,
        )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path), timeout=5.0
            )
        except (FileNotFoundError, ConnectionRefusedError, OSError) as conn_err:
            logger.error(f"Cannot connect to CoreAgent socket '{self.socket_path}': {conn_err}")
            raise AgentUnavailableError(
                "CoreAgent privileged daemon is not running or socket is unreachable"
            )
        except asyncio.TimeoutError:
            logger.error(f"Timed out connecting to CoreAgent socket '{self.socket_path}'")
            raise AgentUnavailableError("Connection to CoreAgent timed out")

        try:
            # Send message
            raw_msg = request.model_dump_json() + "\n"
            writer.write(raw_msg.encode("utf-8"))
            await writer.drain()

            # Read response
            line = await asyncio.wait_for(reader.readline(), timeout=timeout_seconds)
            if not line:
                raise AgentExecutionError("Empty response received from CoreAgent")

            raw_res = line.decode("utf-8").strip()
            response = IPCResponse.model_validate_json(raw_res)

            if not response.success:
                err_code = response.error.code if response.error else "EXECUTION_FAILED"
                err_msg = (
                    response.error.message
                    if response.error
                    else "Unknown failure in CoreAgent"
                )
                logger.warning(
                    f"CoreAgent returned error for '{operation}': [{err_code}] {err_msg}"
                )
                raise AgentExecutionError(f"Operation failed: {err_msg}", code=err_code)

            return response.data or {}

        except (AgentUnavailableError, AgentExecutionError):
            raise
        except asyncio.TimeoutError:
            logger.error(
                f"CoreAgent operation '{operation}' timed out after {timeout_seconds}s"
            )
            raise AgentExecutionError(
                f"CoreAgent operation '{operation}' timed out after {timeout_seconds}s",
                code="OPERATION_TIMEOUT",
            )
        except Exception as exc:
            logger.error(f"IPC error during operation '{operation}': {exc}")
            raise AgentExecutionError(f"IPC communication failure: {exc}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


ipc_client = IPCClient()
