import os
import signal
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.core.logging import logger

MAX_VALID_PID = 4194304


def _validate_target_pid(pid_raw: Any, proc_root: Optional[Path] = None) -> int:
    """
    Independently validates process ID inside CoreAgent.
    Rejects non-integers, floats, negative values, zero, PID 1, and CoreAgent's own PID.
    """
    if isinstance(pid_raw, bool):
        raise ValueError("PID must be an integer, not a boolean")

    if isinstance(pid_raw, int):
        pid = pid_raw
    elif isinstance(pid_raw, str) and pid_raw.strip().isdigit():
        pid = int(pid_raw.strip())
    else:
        raise ValueError(f"Invalid PID format: {pid_raw}")

    if pid < 1 or pid > MAX_VALID_PID:
        raise ValueError(f"PID {pid} out of valid range (1 to {MAX_VALID_PID})")

    # Protection for PID 1 (init/systemd)
    if pid == 1:
        raise ValueError("PID 1 (init/systemd) is protected and cannot be targeted")

    # Self-protection for CoreAgent
    my_pid = os.getpid()
    if pid == my_pid:
        raise ValueError(f"CoreAgent cannot target its own PID ({my_pid})")

    try:
        ppid = os.getppid()
        if ppid > 1 and pid == ppid:
            raise ValueError(f"CoreAgent cannot target its parent PID ({ppid})")
    except Exception:
        pass

    return pid


def _verify_process_identity(pid: int, expected_start_time_ticks: Optional[int], proc_root: Path) -> None:
    """
    TOCTOU / PID reuse protection:
    If expected start time ticks are provided, verifies that /proc/<pid>/stat exists
    and has the exact same start time ticks before executing the signal syscall.
    """
    if expected_start_time_ticks is None:
        return

    stat_file = proc_root / str(pid) / "stat"
    if not stat_file.exists():
        raise ProcessLookupError(f"Process {pid} no longer exists")

    try:
        content = stat_file.read_text(encoding="utf-8")
        rparen = content.rfind(")")
        if rparen != -1:
            fields = content[rparen + 1 :].strip().split()
            if len(fields) >= 20:
                current_start_ticks = int(fields[19])
                if current_start_ticks != expected_start_time_ticks:
                    raise ValueError(
                        f"PID reuse detected for process {pid}: start time {current_start_ticks} "
                        f"does not match expected {expected_start_time_ticks}"
                    )
    except (ProcessLookupError, FileNotFoundError):
        raise ProcessLookupError(f"Process {pid} no longer exists")
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(f"Could not verify process identity for PID {pid}: {exc}")


async def terminate_process_operation(
    payload: Dict[str, Any], proc_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Sends SIGTERM to a validated target process.
    """
    proc_path = proc_root or Path("/proc")
    raw_pid = payload.get("pid")
    expected_start_ticks = payload.get("start_time_ticks")

    pid = _validate_target_pid(raw_pid, proc_root=proc_path)
    _verify_process_identity(pid, expected_start_ticks, proc_path)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        raise ProcessLookupError(f"Process {pid} not found (may have already exited)")
    except PermissionError:
        raise PermissionError(f"Permission denied attempting to send SIGTERM to process {pid}")

    logger.info(f"Delivered SIGTERM to process {pid}")
    return {
        "success": True,
        "pid": pid,
        "operation": "terminate",
        "signal": "SIGTERM",
        "status": "signal_sent",
        "message": f"SIGTERM signal successfully delivered to process {pid}",
    }


async def kill_process_operation(
    payload: Dict[str, Any], proc_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Sends SIGKILL to a validated target process.
    """
    proc_path = proc_root or Path("/proc")
    raw_pid = payload.get("pid")
    expected_start_ticks = payload.get("start_time_ticks")

    pid = _validate_target_pid(raw_pid, proc_root=proc_path)
    _verify_process_identity(pid, expected_start_ticks, proc_path)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        raise ProcessLookupError(f"Process {pid} not found (may have already exited)")
    except PermissionError:
        raise PermissionError(f"Permission denied attempting to send SIGKILL to process {pid}")

    logger.info(f"Delivered SIGKILL to process {pid}")
    return {
        "success": True,
        "pid": pid,
        "operation": "kill",
        "signal": "SIGKILL",
        "status": "signal_sent",
        "message": f"SIGKILL signal successfully delivered to process {pid}",
    }
