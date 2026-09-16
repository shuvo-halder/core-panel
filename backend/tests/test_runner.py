import pytest

from backend.app.linux.runner import LinuxCommandRunner, SecurityError


@pytest.mark.asyncio
async def test_runner_allowed_command():
    """Verify safe execution of an approved binary."""
    runner = LinuxCommandRunner()
    result = await runner.run("uname", ["-s"])
    assert result.is_success
    assert "Linux" in result.stdout or len(result.stdout) > 0
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_runner_rejects_unapproved_binary():
    """Verify rejection of binaries not in allowlist."""
    runner = LinuxCommandRunner()
    with pytest.raises(SecurityError) as exc_info:
        await runner.run("curl", ["https://example.com"])
    assert "not in the approved allowlist" in str(exc_info.value)


@pytest.mark.asyncio
async def test_runner_rejects_command_injection_characters():
    """Verify rejection of dangerous shell control characters in arguments."""
    runner = LinuxCommandRunner()
    dangerous_args = [
        ["-s", "; rm -rf /"],
        ["-s", "| grep Linux"],
        ["-s", "`whoami`"],
        ["-s", "$(id)"],
        ["-s", "foo && bar"],
        ["-s", "foo > /tmp/out"],
    ]
    for args in dangerous_args:
        with pytest.raises(SecurityError) as exc_info:
            await runner.run("uname", args)
        assert "prohibited shell characters" in str(exc_info.value)
