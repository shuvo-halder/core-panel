import asyncio
import tempfile
from pathlib import Path

import pytest

from agent.app.ipc.protocol import IPCRequest, IPCResponse
from agent.app.ipc.server import IPCServer


async def send_ipc_message(socket_path: Path, raw_msg: str) -> str:
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    writer.write(raw_msg.encode("utf-8") + b"\n")
    await writer.drain()
    response_line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return response_line.decode("utf-8").strip()


@pytest.mark.asyncio
async def test_agent_ipc_lifecycle_and_ping():
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = Path(tmpdir) / "agent.sock"
        server = IPCServer(socket_path)
        await server.start()

        try:
            req = IPCRequest(
                version=1,
                requestId="req_test_123",
                operation="agent.ping",
                payload={}
            )
            raw_res = await send_ipc_message(socket_path, req.model_dump_json())
            res = IPCResponse.model_validate_json(raw_res)

            assert res.success is True
            assert res.requestId == "req_test_123"
            assert res.data["status"] == "ready"
            assert res.data["role"] == "privileged_agent"
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_agent_ipc_rejects_unknown_operation():
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = Path(tmpdir) / "agent.sock"
        server = IPCServer(socket_path)
        await server.start()

        try:
            req = IPCRequest(
                version=1,
                requestId="req_test_unknown",
                operation="shell.execute",
                payload={"command": "whoami"}
            )
            raw_res = await send_ipc_message(socket_path, req.model_dump_json())
            res = IPCResponse.model_validate_json(raw_res)

            assert res.success is False
            assert res.error.code == "OPERATION_UNKNOWN"
        finally:
            await server.stop()


@pytest.mark.asyncio
async def test_agent_ipc_rejects_malformed_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = Path(tmpdir) / "agent.sock"
        server = IPCServer(socket_path)
        await server.start()

        try:
            raw_res = await send_ipc_message(socket_path, "{ broken json ...")
            res = IPCResponse.model_validate_json(raw_res)

            assert res.success is False
            assert res.error.code == "MALFORMED_REQUEST"
        finally:
            await server.stop()
