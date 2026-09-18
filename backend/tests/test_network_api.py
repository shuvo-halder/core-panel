import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import UserCreate
from backend.app.auth.service import auth_service
from backend.app.db.sqlite import Database
from backend.app.linux.contracts import (
    DNSConfigInfo,
    IPAddressInfo,
    InterfaceDetailInfo,
    InterfaceStats,
    NetworkOverview,
    RouteInfo,
)
from backend.app.linux.network import NetworkCollector
from backend.app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Provide an isolated, fresh SQLite database with Phase 7 migrations for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_panel.db"
        test_db = Database(db_path=test_db_path)
        monkeypatch.setattr("backend.app.db.sqlite.db", test_db)
        monkeypatch.setattr("backend.app.auth.service.db", test_db)
        monkeypatch.setattr("backend.app.audit.service.db", test_db)
        test_db.init_database()
        yield test_db


@pytest.mark.asyncio
async def test_network_endpoints_unauthenticated():
    """All /api/v1/network/* endpoints must reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/network/overview", "/network/interfaces", "/network/interfaces/eth0", "/network/routes", "/network/dns"):
            res = await client.get(f"/api/v1{path}")
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_network_viewer_and_admin_rbac(monkeypatch):
    """Users with 'network.read' (both viewer and admin) can read all network endpoints."""
    # Create test viewer user
    viewer_user = auth_service.create_user(
        UserCreate(username="testviewer", password="Password123!", role_names=["viewer"])
    )
    tokens = auth_service.create_tokens_for_user(viewer_user.id)

    # Mock network collector data
    mock_stats = InterfaceStats(
        rx_bytes=1000000,
        rx_packets=5000,
        rx_errors=0,
        rx_dropped=0,
        tx_bytes=500000,
        tx_packets=2500,
        tx_errors=0,
        tx_dropped=0,
    )

    mock_iface = InterfaceDetailInfo(
        name="eth0",
        index=2,
        iftype="ethernet",
        operational_state="up",
        administrative_state="up",
        mtu=1500,
        mac_address="52:54:00:12:34:56",
        flags=["UP", "BROADCAST", "RUNNING", "MULTICAST"],
        is_loopback=False,
        is_virtual=False,
        is_physical=True,
        ipv4_addresses=["192.168.1.100"],
        ipv6_addresses=["fe80::5054:ff:fe12:3456"],
        addresses=[
            IPAddressInfo(family="ipv4", address="192.168.1.100", prefix_length=24, scope="global"),
            IPAddressInfo(family="ipv6", address="fe80::5054:ff:fe12:3456", prefix_length=64, scope="link"),
        ],
        stats=mock_stats,
        speed_mbps=1000,
        duplex="full",
    )

    mock_overview = NetworkOverview(
        total_interfaces=2,
        up_interfaces=2,
        down_interfaces=0,
        physical_interfaces=1,
        virtual_interfaces=0,
        loopback_interfaces=1,
        ipv4_addresses=["127.0.0.1", "192.168.1.100"],
        ipv6_addresses=["::1", "fe80::5054:ff:fe12:3456"],
        default_ipv4_route="192.168.1.1 via eth0",
        default_ipv6_route=None,
        dns_servers=["1.1.1.1", "8.8.8.8"],
    )

    mock_routes = [
        RouteInfo(
            destination="0.0.0.0",
            gateway="192.168.1.1",
            interface="eth0",
            flags="UG",
            metric=100,
            family="ipv4",
            mask="0.0.0.0",
            is_default=True,
        )
    ]

    mock_dns = DNSConfigInfo(
        nameservers=["1.1.1.1", "8.8.8.8"],
        search_domains=["corp.internal"],
        options=["edns0"],
        source="systemd-resolved",
        is_symlink=True,
        symlink_target="/run/systemd/resolve/stub-resolv.conf",
    )

    monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_network_overview", lambda: mock_overview)
    monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_interface_details", lambda: [mock_iface])
    monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_interface_by_name", lambda n: mock_iface if n == "eth0" else None)
    monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_routes", lambda: mock_routes)
    monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_dns_config", lambda: mock_dns)

    headers = {"Authorization": f"Bearer {tokens.access_token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /api/v1/network/overview
        res = await client.get("/api/v1/network/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_interfaces"] == 2
        assert data["physical_interfaces"] == 1
        assert data["default_ipv4_route"] == "192.168.1.1 via eth0"
        assert "1.1.1.1" in data["dns_servers"]

        # 2. GET /api/v1/network/interfaces
        res = await client.get("/api/v1/network/interfaces", headers=headers)
        assert res.status_code == 200
        ifaces = res.json()
        assert len(ifaces) == 1
        assert ifaces[0]["name"] == "eth0"
        assert ifaces[0]["is_physical"] is True
        assert ifaces[0]["stats"]["rx_bytes"] == 1000000

        # 3. GET /api/v1/network/interfaces/eth0
        res = await client.get("/api/v1/network/interfaces/eth0", headers=headers)
        assert res.status_code == 200
        single = res.json()
        assert single["name"] == "eth0"
        assert single["mac_address"] == "52:54:00:12:34:56"
        assert single["speed_mbps"] == 1000

        # 4. GET /api/v1/network/routes
        res = await client.get("/api/v1/network/routes", headers=headers)
        assert res.status_code == 200
        r_list = res.json()
        assert len(r_list) == 1
        assert r_list[0]["destination"] == "0.0.0.0"
        assert r_list[0]["is_default"] is True

        # 5. GET /api/v1/network/dns
        res = await client.get("/api/v1/network/dns", headers=headers)
        assert res.status_code == 200
        dns_res = res.json()
        assert dns_res["nameservers"] == ["1.1.1.1", "8.8.8.8"]
        assert dns_res["source"] == "systemd-resolved"
        assert dns_res["is_symlink"] is True


@pytest.mark.asyncio
async def test_network_interface_validation_and_not_found(monkeypatch):
    """Tests interface name validation against malicious payloads and 404 behavior."""
    viewer_user = auth_service.create_user(
        UserCreate(username="validuser", password="Password123!", role_names=["viewer"])
    )
    tokens = auth_service.create_tokens_for_user(viewer_user.id)
    headers = {"Authorization": f"Bearer {tokens.access_token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid / Malicious interface names -> 400 Bad Request
        res = await client.get("/api/v1/network/interfaces/..%2F..%2Fsys", headers=headers)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INTERFACE_NAME"

        res = await client.get("/api/v1/network/interfaces/eth0%3Brm%20-rf", headers=headers)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INTERFACE_NAME"

        # Valid name but non-existent interface -> 404 Not Found
        monkeypatch.setattr("backend.app.api.v1.network.network_collector.get_interface_by_name", lambda n: None)
        res = await client.get("/api/v1/network/interfaces/eth99", headers=headers)
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "INTERFACE_NOT_FOUND"
