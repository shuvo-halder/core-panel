import os
import signal
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.app.operations.processes import (
    _validate_target_pid,
    _verify_process_identity,
    kill_process_operation,
    terminate_process_operation,
)
from agent.app.operations.registry import registry


def test_registry_contains_process_operations():
    """Operation registry must expose only allowlisted process handlers."""
    assert registry.has_operation("process.terminate")
    assert registry.has_operation("process.kill")

    # Generic or arbitrary operations must be strictly forbidden
    assert not registry.has_operation("process.signal")
    assert not registry.has_operation("process.exec")
    assert not registry.has_operation("os.kill")
    assert not registry.has_operation("agent.shell")


def test_validate_target_pid_defense_in_depth():
    """CoreAgent PID validation independently rejects invalid and dangerous PIDs."""
    # Valid PIDs
    assert _validate_target_pid(1234) == 1234
    assert _validate_target_pid("5678") == 5678

    # PID 1 is protected
    with pytest.raises(ValueError, match="PID 1"):
        _validate_target_pid(1)

    # Self PID is protected
    with pytest.raises(ValueError, match="CoreAgent cannot target its own PID"):
        _validate_target_pid(os.getpid())

    # Invalid cases
    invalid_cases = [
        0,
        -1,
        -999,
        99999999,
        "abc",
        True,
        False,
        "1; rm -rf /",
    ]
    for bad in invalid_cases:
        with pytest.raises(ValueError):
            _validate_target_pid(bad)


@pytest.mark.asyncio
async def test_terminate_process_operation_success():
    """CoreAgent sends SIGTERM to the targeted PID."""
    with patch("os.kill") as mock_kill:
        result = await terminate_process_operation({"pid": 9876})
        assert result["success"] is True
        assert result["operation"] == "terminate"
        assert result["signal"] == "SIGTERM"
        mock_kill.assert_called_once_with(9876, signal.SIGTERM)


@pytest.mark.asyncio
async def test_kill_process_operation_success():
    """CoreAgent sends SIGKILL to the targeted PID."""
    with patch("os.kill") as mock_kill:
        result = await kill_process_operation({"pid": 9876})
        assert result["success"] is True
        assert result["operation"] == "kill"
        assert result["signal"] == "SIGKILL"
        mock_kill.assert_called_once_with(9876, signal.SIGKILL)


@pytest.mark.asyncio
async def test_process_operation_nonexistent_process():
    """If process does not exist, ProcessLookupError is raised."""
    with patch("os.kill", side_effect=ProcessLookupError()):
        with pytest.raises(ProcessLookupError):
            await terminate_process_operation({"pid": 9876})


def test_process_identity_verification_toctou():
    """Verifies that start time mismatch detects PID reuse and aborts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_proc = Path(tmpdir)
        p1234 = mock_proc / "1234"
        p1234.mkdir()

        # stat file with starttime ticks = 50000 (field index 19 after comm)
        stat_line = (
            "1234 (test) S 1 1234 1234 0 -1 4194560 100 0 0 0 "
            "50 20 0 0 20 0 2 0 50000 104857600 2560 18446744073709551615"
        )
        (p1234 / "stat").write_text(stat_line)

        # Matching start time passes
        _verify_process_identity(1234, 50000, mock_proc)

        # Mismatched start time raises ValueError (PID reuse)
        with pytest.raises(ValueError, match="PID reuse detected"):
            _verify_process_identity(1234, 99999, mock_proc)
