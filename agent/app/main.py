import asyncio
import signal

from agent.app.ipc.server import IPCServer
from backend.app.core.config import settings


async def run_agent() -> None:
    socket_path = settings.AGENT_SOCKET_PATH
    server = IPCServer(socket_path)
    await server.start()

    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass
