from unittest.mock import AsyncMock, patch

import pytest

from agent.app.operations.registry import registry
from agent.app.operations.systemd import (
    execute_systemctl_action,
    validate_systemd_unit,
)


def test_registry_contains_systemd_operations():
    """Operation registry must expose only allowlisted systemd service handlers."""
    expected_ops = [
        "systemd.service.start",
        "systemd.service.stop",
        "systemd.service.restart",
        "systemd.service.enable",
        "systemd.service.disable",
    ]
    for op in expected_ops:
        assert registry.has_operation(op), f"Registry missing operation '{op}'"

    # Generic or arbitrary operations must be strictly forbidden
    assert not registry.has_operation("systemctl.execute")
    assert not registry.has_operation("systemd.execute")
    assert not registry.has_operation("exec.command")
    assert not registry.has_operation("agent.shell")


def test_validate_systemd_unit_defense_in_depth():
    """CoreAgent unit validation independently rejects invalid and dangerous unit names."""
    # Valid unit names
    assert validate_systemd_unit("nginx.service") == "nginx.service"
    assert validate_systemd_unit("user@1000.service") == "user@1000.service"
    assert validate_systemd_unit("systemd-journald.service") == "systemd-journald.service"
    assert validate_systemd_unit("app_worker.service") == "app_worker.service"

    # Invalid unit names
    invalid_cases = [
        "../../etc/passwd.service",
        "nginx.service;reboot",
        "nginx.service|cat",
        "nginx.socket",
        "nginx.target",
        "nginx.timer",
        "space in name.service",
        ".service",  # length < 9
        "",
        "nginx.service\n",
        "nginx.service\x00",
    ]
    for bad in invalid_cases:
        with pytest.raises(ValueError):
            validate_systemd_unit(bad)


@pytest.mark.asyncio
async def test_execute_systemctl_action_prohibits_unknown_actions():
    """CoreAgent rejects any action not in {'start', 'stop', 'restart', 'enable', 'disable'}."""
    prohibited_actions = ["mask", "edit", "cat", "is-failed", "daemon-reload", "kill"]
    for action in prohibited_actions:
        with pytest.raises(ValueError, match="Prohibited systemctl action"):
            await execute_systemctl_action(action, "nginx.service")


@pytest.mark.asyncio
async def test_execute_systemctl_action_mocked_success():
    """Tests subprocess execution without running actual host systemctl."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/bin/systemctl"):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await execute_systemctl_action("restart", "nginx.service")
            assert result["success"] is True
            assert result["operation"] == "restart"
            assert result["unit"] == "nginx.service"

            # Assert create_subprocess_exec was called with array arguments and no shell
            mock_exec.assert_called_once_with(
                "/bin/systemctl",
                "restart",
                "nginx.service",
                stdout=pytest.approx(-1),  # asyncio.subprocess.PIPE
                stderr=pytest.approx(-1),
            )


@pytest.mark.asyncio
async def test_execute_systemctl_action_mocked_failure():
    """Tests subprocess error handling when systemctl returns non-zero exit code."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"Failed to restart nginx.service: Unit not found.")
    )
    mock_proc.returncode = 5

    with patch("shutil.which", return_value="/bin/systemctl"):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Unit not found"):
                await execute_systemctl_action("restart", "nginx.service")
