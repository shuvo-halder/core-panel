import platform
from pathlib import Path
from typing import Dict, Optional

from backend.app.linux.contracts import IOSProvider, OSInfo

SUPPORTED_OS_MATRIX = {
    ("ubuntu", "22.04"),
    ("ubuntu", "24.04"),
    ("debian", "12"),
}


def parse_os_release(content: str) -> Dict[str, str]:
    """Parse standard /etc/os-release key-value pairs."""
    data = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            # Strip quotes
            val = val.strip("\"'")
            data[key.strip()] = val
    return data


class OSProvider(IOSProvider):
    """
    Read-only Operating System Detection.
    Inspects /etc/os-release and kernel platform safely without side effects.
    """

    def __init__(self, os_release_path: Optional[Path] = None):
        self.os_release_path = os_release_path or Path("/etc/os-release")

    def detect_os(self) -> OSInfo:
        distro = "unknown"
        version = "unknown"

        if self.os_release_path.exists():
            try:
                content = self.os_release_path.read_text(encoding="utf-8")
                parsed = parse_os_release(content)
                distro = parsed.get("ID", "unknown").lower()
                version = parsed.get("VERSION_ID", "unknown").strip()
            except Exception:
                pass

        arch = platform.machine() or "x86_64"
        kernel = platform.release() or "unknown"

        # Check if matched in supported matrix
        is_supported = (distro, version) in SUPPORTED_OS_MATRIX

        return OSInfo(
            distribution=distro,
            version=version,
            architecture=arch,
            kernel_version=kernel,
            is_supported=is_supported
        )


os_provider = OSProvider()
