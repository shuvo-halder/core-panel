import asyncio
import json
import os
import stat
from pathlib import Path
from typing import Optional

from agent.app.ipc.protocol import IPCError, IPCRequest, IPCResponse
from agent.app.operations.registry import registry
from backend.app.core.logging import logger


class IPCServer:
    """Unix Domain Socket IPC Server for CoreAgent privileged operations."""

    def __init__(self, socket_path: Path):
        self.socket_path = socket_path
        self._server: Optional[asyncio.Server] = None
        self._is_running = False

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break

                raw_msg = line.decode("utf-8").strip()
                if not raw_msg:
                    continue

                response = await self._process_raw_message(raw_msg)
                writer.write(response.model_dump_json().encode("utf-8") + b"\n")
                await writer.drain()
        except Exception as exc:
            logger.error(f"IPC client connection error: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_raw_message(self, raw_msg: str) -> IPCResponse:
        # Step 1: Parse JSON
        try:
            data = json.loads(raw_msg)
        except Exception:
            return IPCResponse(
                version=1,
                requestId="unknown",
                success=False,
                error=IPCError(code="MALFORMED_REQUEST", message="Invalid JSON format"),
            )

        # Step 2: Validate Schema
        try:
            req = IPCRequest.model_validate(data)
        except Exception as err:
            req_id = data.get("requestId", "unknown") if isinstance(data, dict) else "unknown"
            return IPCResponse(
                version=1,
                requestId=str(req_id),
                success=False,
                error=IPCError(
                    code="VALIDATION_ERROR", message=f"Invalid IPC request schema: {err}"
                ),
            )

        # Step 3: Check Supported Protocol Version
        if req.version != 1:
            return IPCResponse(
                version=1,
                requestId=req.requestId,
                success=False,
                error=IPCError(
                    code="UNSUPPORTED_VERSION",
                    message=f"Protocol version {req.version} not supported",
                ),
            )

        # Step 4: Execute Operation
        if not registry.has_operation(req.operation):
            logger.warning(
                f"Security Alert: Unknown operation requested: '{req.operation}' [Req: {req.requestId}]"
            )
            return IPCResponse(
                version=1,
                requestId=req.requestId,
                success=False,
                error=IPCError(
                    code="OPERATION_UNKNOWN",
                    message=f"Operation '{req.operation}' is not supported or prohibited",
                ),
            )

        try:
            result = await registry.execute(req.operation, req.payload)
            return IPCResponse(version=1, requestId=req.requestId, success=True, data=result)
        except Exception as exc:
            logger.error(f"Operation '{req.operation}' failed: {exc}")
            return IPCResponse(
                version=1,
                requestId=req.requestId,
                success=False,
                error=IPCError(code="EXECUTION_FAILED", message=str(exc)),
            )

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()

        self._server = await asyncio.start_unix_server(
            self.handle_client, path=str(self.socket_path)
        )
        # Apply restrictive permissions (0660: rw-rw----)
        try:
            os.chmod(self.socket_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
        except Exception as err:
            logger.warning(f"Could not set socket permissions: {err}")

        self._is_running = True
        logger.info(f"Privileged Agent IPC Server listening on {self.socket_path}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._is_running = False
        logger.info("Privileged Agent IPC Server stopped.")
