import tempfile
from pathlib import Path

from backend.app.linux.os_detect import OSProvider, parse_os_release

UBUNTU_22_RELEASE = """
NAME="Ubuntu"
VERSION="22.04.4 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.4 LTS"
VERSION_ID="22.04"
"""

UBUNTU_24_RELEASE = """
NAME="Ubuntu"
VERSION="24.04 LTS (Noble Numbat)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 24.04 LTS"
VERSION_ID="24.04"
"""

DEBIAN_12_RELEASE = """
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
VERSION="12 (bookworm)"
VERSION_CODENAME=bookworm
ID=debian
"""

UNSUPPORTED_FEDORA_RELEASE = """
NAME="Fedora Linux"
VERSION="39 (Server Edition)"
ID=fedora
VERSION_ID="39"
"""


def test_parse_os_release():
    parsed = parse_os_release(UBUNTU_22_RELEASE)
    assert parsed["ID"] == "ubuntu"
    assert parsed["VERSION_ID"] == "22.04"


def test_detect_supported_ubuntu_22():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(UBUNTU_22_RELEASE)
        f.flush()
        provider = OSProvider(os_release_path=Path(f.name))
        info = provider.detect_os()
        assert info.distribution == "ubuntu"
        assert info.version == "22.04"
        assert info.is_supported is True


def test_detect_supported_ubuntu_24():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(UBUNTU_24_RELEASE)
        f.flush()
        provider = OSProvider(os_release_path=Path(f.name))
        info = provider.detect_os()
        assert info.distribution == "ubuntu"
        assert info.version == "24.04"
        assert info.is_supported is True


def test_detect_supported_debian_12():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(DEBIAN_12_RELEASE)
        f.flush()
        provider = OSProvider(os_release_path=Path(f.name))
        info = provider.detect_os()
        assert info.distribution == "debian"
        assert info.version == "12"
        assert info.is_supported is True


def test_detect_unsupported_distribution():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(UNSUPPORTED_FEDORA_RELEASE)
        f.flush()
        provider = OSProvider(os_release_path=Path(f.name))
        info = provider.detect_os()
        assert info.distribution == "fedora"
        assert info.version == "39"
        assert info.is_supported is False
