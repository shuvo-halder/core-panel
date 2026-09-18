import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.core.errors import BadRequestError
from backend.app.core.validators import validate_package_name
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    PackageDetails,
    PackageInfo,
    PackageListResult,
    PackageManagerInfo,
    PackageOverview,
    PackageUpdateInfo,
    RepositoryInfo,
)
from backend.app.linux.packages import PackageManager
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database with Phase 8 migrations for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


def test_validate_package_name():
    """Package name validator must accept standard package naming conventions and reject malicious input."""
    # Valid names
    assert validate_package_name("curl") == "curl"
    assert validate_package_name("python3-pip") == "python3-pip"
    assert validate_package_name("libc6:amd64") == "libc6:amd64"
    assert validate_package_name("libstdc++6") == "libstdc++6"
    assert validate_package_name("glibc.i686") == "glibc.i686"
    assert validate_package_name("app_daemon-1.0") == "app_daemon-1.0"

    # Invalid names
    invalid_cases = [
        "",
        " ",
        "curl; rm -rf /",
        "curl & whoami",
        "curl|bash",
        "curl`whoami`",
        "curl$(whoami)",
        "../var/lib/dpkg",
        "/etc/passwd",
        "curl\x00malicious",
        "curl\nwhoami",
        "a" * 129,
        "-invalid-start",
    ]
    for case in invalid_cases:
        with pytest.raises(BadRequestError):
            validate_package_name(case)


@pytest.mark.asyncio
async def test_package_endpoints_unauthenticated():
    """All /api/v1/packages/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in (
            "/packages/overview",
            "/packages",
            "/packages/curl",
            "/packages/repositories",
            "/packages/updates",
        ):
            res = await client.get(f"/api/v1{path}")
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_package_viewer_and_admin_rbac(monkeypatch):
    """Users with 'packages.read' (both viewer and admin) can read all package endpoints."""
    # Create test viewer user
    viewer_user = auth_service.create_user(
        UserCreate(username="testpkgviewer", password="Password123!", role_names=["viewer"])
    )
    tokens = auth_service.create_tokens_for_user(viewer_user.id)

    # Mock package manager data
    mock_overview = PackageOverview(
        manager="apt",
        family="debian",
        distribution="Debian GNU/Linux 12 (bookworm)",
        architecture="x86_64",
        installed_package_count=120,
        packages_with_updates=0,
        repository_count=2,
        manager_available=True,
        update_status_message="Package database operating in read-only mode.",
    )

    mock_list_res = PackageListResult(
        items=[
            PackageInfo(
                name="curl",
                version="7.88.1-10+deb12u5",
                architecture="amd64",
                status="installed",
                summary="command line tool for transferring data with URL syntax",
                source="curl",
                installed_size_kb=420,
            )
        ],
        total=1,
        page=1,
        page_size=50,
        total_pages=1,
    )

    mock_details = PackageDetails(
        name="curl",
        version="7.88.1-10+deb12u5",
        architecture="amd64",
        status="installed",
        summary="command line tool for transferring data with URL syntax",
        description="command line tool for transferring data with URL syntax\n Detailed description here.",
        source="curl",
        section="web",
        maintainer="Debian QA Group",
        homepage="https://curl.se/",
        installed_size_kb=420,
        dependencies=["libc6", "libcurl4", "zlib1g"],
    )

    mock_repos = [
        RepositoryInfo(
            name="bookworm (sources.list:1)",
            type="deb",
            uri="http://deb.debian.org/debian",
            enabled=True,
            distribution="bookworm",
            components=["main", "contrib"],
            source_file="/etc/apt/sources.list",
        )
    ]

    mock_updates = [
        PackageUpdateInfo(
            name="openssl",
            installed_version="3.0.11-1~deb12u1",
            candidate_version="3.0.11-1~deb12u2",
            repository="bookworm-security",
            update_available=True,
            urgency="high",
        )
    ]

    monkeypatch.setattr("backend.app.api.v1.packages.package_manager.get_overview", lambda: mock_overview)
    monkeypatch.setattr("backend.app.api.v1.packages.package_manager.list_packages", lambda **kw: mock_list_res)
    monkeypatch.setattr(
        "backend.app.api.v1.packages.package_manager.get_package_details",
        lambda name: mock_details if name == "curl" else None,
    )
    monkeypatch.setattr("backend.app.api.v1.packages.package_manager.list_repositories", lambda: mock_repos)
    monkeypatch.setattr("backend.app.api.v1.packages.package_manager.list_updates", lambda: mock_updates)

    transport = ASGITransport(app=app)
    cookies = {"access_token": tokens.access_token}

    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # 1. Overview
        res = await client.get("/api/v1/packages/overview")
        assert res.status_code == 200
        data = res.json()
        assert data["manager"] == "apt"
        assert data["installed_package_count"] == 120
        assert data["repository_count"] == 2

        # 2. List Packages
        res = await client.get("/api/v1/packages?page=1&page_size=50")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "curl"

        # 3. Get Package Details
        res = await client.get("/api/v1/packages/curl")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "curl"
        assert data["section"] == "web"
        assert len(data["dependencies"]) == 3

        # 4. Get Package Details - Not Found
        res = await client.get("/api/v1/packages/nonexistent-package-xyz")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "PACKAGE_NOT_FOUND"

        # 5. Invalid Package Name
        res = await client.get("/api/v1/packages/invalid;name")
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_PACKAGE_NAME"

        # 6. Repositories
        res = await client.get("/api/v1/packages/repositories")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["type"] == "deb"
        assert data[0]["enabled"] is True

        # 7. Updates
        res = await client.get("/api/v1/packages/updates")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "openssl"


def test_dpkg_status_parser_isolated(tmp_path):
    """PackageManager direct status file parser extracts fields correctly from RFC822 Debian status."""
    dpkg_status = tmp_path / "status"
    dpkg_status.write_text(
        """Package: bash
Status: install ok installed
Priority: required
Section: shells
Installed-Size: 7520
Maintainer: Debian QA <qa@debian.org>
Architecture: amd64
Version: 5.2.15-2+b2
Depends: debianutils (>= 5.7-1), libc6 (>= 2.36), libtinfo6 (>= 6)
Description: GNU Bourne Again SHell
 Bash is an sh-compatible command language interpreter that executes
 commands read from the standard input or from a file.
Homepage: http://www.gnu.org/software/bash/

Package: curl
Status: install ok installed
Priority: optional
Section: web
Installed-Size: 432
Maintainer: Alessandro Ghedini <ghedo@debian.org>
Architecture: amd64
Version: 7.88.1-10+deb12u5
Depends: libc6 (>= 2.34), libcurl4 (= 7.88.1-10+deb12u5), zlib1g (>= 1:1.1.4)
Description: command line tool for transferring data with URL syntax
 curl is a tool for transferring data from or to a server using URLs.
Homepage: https://curl.se/
""",
        encoding="utf-8",
    )

    os_release = tmp_path / "os-release"
    os_release.write_text(
        """PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
ID=debian
VERSION_ID="12"
""",
        encoding="utf-8",
    )

    sources_list = tmp_path / "sources.list"
    sources_list.write_text(
        """# Main Debian repository
deb http://deb.debian.org/debian bookworm main contrib non-free
deb-src http://deb.debian.org/debian bookworm main
# deb http://deb.debian.org/debian bookworm-proposed-updates main
""",
        encoding="utf-8",
    )

    mgr = PackageManager(
        os_release_paths=[os_release],
        dpkg_status_path=dpkg_status,
        apt_sources_list_path=sources_list,
        apt_sources_dir_path=tmp_path / "sources.list.d",
    )

    info = mgr.get_manager_info()
    assert info.family == "debian"
    assert info.available is True

    # Test inventory listing
    res = mgr.list_packages(page=1, page_size=10)
    assert res.total == 2
    pkg_names = [p.name for p in res.items]
    assert "bash" in pkg_names
    assert "curl" in pkg_names

    # Test details
    curl_details = mgr.get_package_details("curl")
    assert curl_details is not None
    assert curl_details.name == "curl"
    assert curl_details.version == "7.88.1-10+deb12u5"
    assert curl_details.installed_size_kb == 432
    assert "libc6 (>= 2.34)" in curl_details.dependencies
    assert curl_details.homepage == "https://curl.se/"
    assert "command line tool" in curl_details.summary

    # Test repositories
    repos = mgr.list_repositories()
    assert len(repos) == 3
    enabled_repos = [r for r in repos if r.enabled]
    disabled_repos = [r for r in repos if not r.enabled]
    assert len(enabled_repos) == 2
    assert len(disabled_repos) == 1
    assert enabled_repos[0].type == "deb"
    assert enabled_repos[0].distribution == "bookworm"
    assert "main" in enabled_repos[0].components

    # Test Overview
    overview = mgr.get_overview()
    assert overview.installed_package_count == 2
    assert overview.repository_count == 3
    assert "read-only" in overview.update_status_message.lower()
