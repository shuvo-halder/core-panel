import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    BlockDeviceInfo,
    BlockDevicePartInfo,
    FilesystemInfo,
    StorageOverview,
)
from backend.app.linux.storage import LinuxStorageCollector
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database with Phase 6 migrations for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


@pytest.mark.asyncio
async def test_storage_endpoints_unauthenticated():
    """All /api/v1/storage/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/storage/overview", "/storage/devices", "/storage/filesystems", "/storage/mounts"):
            res = await client.get(f"/api/v1{path}")
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_storage_viewer_and_admin_rbac(monkeypatch):
    """Users with 'storage.read' (both viewer and admin) can read all storage endpoints."""
    # Create test viewer user
    viewer_user = auth_service.create_user(
        UserCreate(username="testviewer", password="Password123!", role_names=["viewer"])
    )
    tokens = auth_service.create_tokens_for_user(viewer_user.id)

    # Mock storage collector data
    mock_overview = StorageOverview(
        total_bytes=1000000000,
        used_bytes=400000000,
        available_bytes=600000000,
        usage_percent=40.0,
        device_count=1,
        filesystem_count=1,
        mount_count=1,
    )
    mock_devices = [
        BlockDeviceInfo(
            name="sda",
            path="/dev/sda",
            device_type="disk",
            size_bytes=1000000000,
            model="TestDisk",
            vendor="TestVendor",
            is_removable=False,
            is_read_only=False,
            filesystem=None,
            mount_point=None,
            label=None,
            uuid=None,
            children=[
                BlockDevicePartInfo(
                    name="sda1",
                    path="/dev/sda1",
                    size_bytes=1000000000,
                    filesystem="ext4",
                    mount_point="/",
                    uuid="1234-uuid",
                    label="root",
                    is_read_only=False,
                )
            ],
        )
    ]
    mock_fs = [
        FilesystemInfo(
            device="/dev/sda1",
            mount_point="/",
            fstype="ext4",
            is_pseudo=False,
            is_read_only=False,
            total_bytes=1000000000,
            used_bytes=400000000,
            available_bytes=600000000,
            usage_percent=40.0,
            label="root",
            uuid="1234-uuid",
            mount_options="rw,relatime",
        )
    ]

    monkeypatch.setattr(
        "backend.app.api.v1.storage.storage_collector.get_storage_overview",
        lambda: mock_overview,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.storage.storage_collector.get_block_devices",
        lambda: mock_devices,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.storage.storage_collector.get_filesystems",
        lambda include_pseudo=False: mock_fs,
    )
    monkeypatch.setattr(
        "backend.app.api.v1.storage.storage_collector.get_mounts",
        lambda: mock_fs,
    )

    transport = ASGITransport(app=app)
    cookies = {"access_token": tokens.access_token}
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # Overview
        res_overview = await client.get("/api/v1/storage/overview")
        assert res_overview.status_code == 200
        data = res_overview.json()
        assert data["total_bytes"] == 1000000000
        assert data["usage_percent"] == 40.0

        # Devices
        res_devices = await client.get("/api/v1/storage/devices")
        assert res_devices.status_code == 200
        dev_list = res_devices.json()
        assert len(dev_list) == 1
        assert dev_list[0]["name"] == "sda"
        assert len(dev_list[0]["children"]) == 1
        assert dev_list[0]["children"][0]["name"] == "sda1"

        # Filesystems
        res_fs = await client.get("/api/v1/storage/filesystems")
        assert res_fs.status_code == 200
        fs_list = res_fs.json()
        assert len(fs_list) == 1
        assert fs_list[0]["mount_point"] == "/"

        # Mounts
        res_mounts = await client.get("/api/v1/storage/mounts")
        assert res_mounts.status_code == 200
        assert len(res_mounts.json()) == 1


def test_linux_storage_collector_mounts_and_devices():
    """Test LinuxStorageCollector parsing with synthetic /proc/mounts and /sys/block."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mounts_file = tmp / "mounts"
        mounts_file.write_text(
            "/dev/sda1 / ext4 rw,relatime 0 0\n"
            "tmpfs /run tmpfs rw,nosuid,nodev 0 0\n"
            "proc /proc proc rw,nosuid,nodev,noexec 0 0\n"
            "/dev/sdb1 /mnt/data xfs ro,relatime 0 0\n",
            encoding="utf-8",
        )

        sys_block = tmp / "sys_block"
        sys_block.mkdir()

        # Create sda
        sda_dir = sys_block / "sda"
        sda_dir.mkdir()
        (sda_dir / "size").write_text("2097152\n")  # 2097152 sectors = 1 GB
        (sda_dir / "removable").write_text("0\n")
        (sda_dir / "ro").write_text("0\n")
        dev_info_dir = sda_dir / "device"
        dev_info_dir.mkdir()
        (dev_info_dir / "model").write_text("Virtual Disk\n")
        (dev_info_dir / "vendor").write_text("QEMU\n")

        # Partition sda1
        sda1_dir = sda_dir / "sda1"
        sda1_dir.mkdir()
        (sda1_dir / "partition").write_text("1\n")
        (sda1_dir / "size").write_text("2097152\n")
        (sda1_dir / "ro").write_text("0\n")

        # loop0
        loop0_dir = sys_block / "loop0"
        loop0_dir.mkdir()
        (loop0_dir / "size").write_text("102400\n")
        (loop0_dir / "ro").write_text("1\n")

        collector = LinuxStorageCollector(
            sys_block_path=sys_block,
            mounts_path=mounts_file,
            disk_by_uuid_path=tmp / "nonexistent_uuid",
            disk_by_label_path=tmp / "nonexistent_label",
        )

        # Mounts
        mounts = collector.get_mounts()
        assert len(mounts) == 4
        # Verify root mount is ext4 and not pseudo
        root_mount = next(m for m in mounts if m.mount_point == "/")
        assert root_mount.fstype == "ext4"
        assert not root_mount.is_pseudo
        assert not root_mount.is_read_only

        # Verify /proc is pseudo
        proc_mount = next(m for m in mounts if m.mount_point == "/proc")
        assert proc_mount.is_pseudo

        # Verify /mnt/data is read-only
        data_mount = next(m for m in mounts if m.mount_point == "/mnt/data")
        assert data_mount.is_read_only

        # Block devices
        devices = collector.get_block_devices()
        assert len(devices) == 2  # sda, loop0

        sda_dev = next(d for d in devices if d.name == "sda")
        assert sda_dev.device_type == "disk"
        assert sda_dev.model == "Virtual Disk"
        assert sda_dev.size_bytes == 2097152 * 512
        assert len(sda_dev.children) == 1
        assert sda_dev.children[0].name == "sda1"

        loop_dev = next(d for d in devices if d.name == "loop0")
        assert loop_dev.device_type == "loop"
        assert loop_dev.is_read_only


def test_linux_storage_collector_resilience():
    """Test collector resilience against missing directories or corrupt files."""
    collector = LinuxStorageCollector(
        sys_block_path=Path("/nonexistent_sys_block_xyz"),
        mounts_path=Path("/nonexistent_mounts_xyz"),
    )
    # Should not raise exception
    mounts = collector.get_mounts()
    assert isinstance(mounts, list)

    devices = collector.get_block_devices()
    assert isinstance(devices, list)
    assert len(devices) == 0

    overview = collector.get_storage_overview()
    assert overview.device_count == 0
