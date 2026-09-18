import os
import tempfile
from pathlib import Path

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.validators import validate_interface_name
from backend.app.linux.contracts import (
    DNSConfigInfo,
    IPAddressInfo,
    InterfaceDetailInfo,
    InterfaceStats,
    NetworkOverview,
    RouteInfo,
)
from backend.app.linux.network import NetworkCollector


def test_validate_interface_name():
    """Validates Linux network interface name sanitization."""
    # Valid names
    assert validate_interface_name("eth0") == "eth0"
    assert validate_interface_name("wlan0") == "wlan0"
    assert validate_interface_name("enp3s0") == "enp3s0"
    assert validate_interface_name("br0") == "br0"
    assert validate_interface_name("veth1234") == "veth1234"
    assert validate_interface_name("lo") == "lo"
    assert validate_interface_name("bond0.100") == "bond0.100"
    assert validate_interface_name("tun-vpn") == "tun-vpn"

    # Invalid names / Injection attacks
    invalid_cases = [
        "",
        "   ",
        "eth0; rm -rf /",
        "../eth0",
        "../../sys/class/net",
        "eth0/1",
        "eth$foo",
        "verylonginterfacenamethatexceeds15chars",
        "eth0\n",
        "eth0\0",
    ]
    for case in invalid_cases:
        with pytest.raises(ValidationError):
            validate_interface_name(case)


def test_network_collector_traffic_parsing():
    """Tests parsing /proc/net/dev for RX and TX byte and packet counters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proc_dev = tmp_path / "dev"
        proc_dev.write_text(
            "Inter-|   Receive                                                |  Transmit\n"
            " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
            "    lo: 1234567     890    0    0    0     0          0         0  1234567     890    0    0    0     0       0          0\n"
            "  eth0: 9876543    2100   12    3    0     0          0         0  5432100    1500    4    1    0     0       0          0\n",
            encoding="utf-8",
        )

        collector = NetworkCollector(proc_dev_path=proc_dev)
        stats = collector._get_detailed_traffic_stats()

        assert "lo" in stats
        assert stats["lo"].rx_bytes == 1234567
        assert stats["lo"].rx_packets == 890
        assert stats["lo"].tx_bytes == 1234567

        assert "eth0" in stats
        assert stats["eth0"].rx_bytes == 9876543
        assert stats["eth0"].rx_packets == 2100
        assert stats["eth0"].rx_errors == 12
        assert stats["eth0"].rx_dropped == 3
        assert stats["eth0"].tx_bytes == 5432100
        assert stats["eth0"].tx_packets == 1500
        assert stats["eth0"].tx_errors == 4
        assert stats["eth0"].tx_dropped == 1


def test_network_collector_ipv6_parsing():
    """Tests parsing /proc/net/if_inet6 for IPv6 address entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proc_inet6 = tmp_path / "if_inet6"
        # 00000000000000000000000000000001 01 80 10 80       lo
        # fe80000000000000505400fffe123456 02 40 20 80     eth0
        proc_inet6.write_text(
            "00000000000000000000000000000001 01 80 10 80       lo\n"
            "fe80000000000000505400fffe123456 02 40 20 80     eth0\n",
            encoding="utf-8",
        )

        collector = NetworkCollector(proc_inet6_path=proc_inet6)
        ipv6_map = collector._get_ipv6_address_details()

        assert "lo" in ipv6_map
        assert ipv6_map["lo"][0].address == "::1"
        assert ipv6_map["lo"][0].prefix_length == 128
        assert ipv6_map["lo"][0].family == "ipv6"

        assert "eth0" in ipv6_map
        assert ipv6_map["eth0"][0].address == "fe80::5054:ff:fe12:3456"
        assert ipv6_map["eth0"][0].prefix_length == 64
        assert ipv6_map["eth0"][0].scope == "link"


def test_network_collector_routing_table_parsing():
    """Tests parsing /proc/net/route for IPv4 routing table entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proc_route = tmp_path / "route"
        # Little-endian hex: 00000000 -> 0.0.0.0, 0101A8C0 -> 192.168.1.1, 0000FFFF -> 255.255.0.0
        proc_route.write_text(
            "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
            "eth0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
            "eth0\t0001A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
            "lo\t0000007F\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0\n",
            encoding="utf-8",
        )

        collector = NetworkCollector(proc_route_path=proc_route)
        routes = collector.get_routes()

        assert len(routes) == 3
        # First route should be the default route (sorted first)
        default_route = next(r for r in routes if r.is_default)
        assert default_route.destination == "0.0.0.0"
        assert default_route.gateway == "192.168.1.1"
        assert default_route.interface == "eth0"
        assert default_route.metric == 100
        assert default_route.is_default is True


def test_network_collector_dns_parsing():
    """Tests parsing /etc/resolv.conf for nameservers, search domains, and options."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        resolv_file = tmp_path / "resolv.conf"
        resolv_file.write_text(
            "# Generated by NetworkManager\n"
            "nameserver 1.1.1.1\n"
            "nameserver 8.8.8.8\n"
            "search corp.internal lab.local\n"
            "options timeout:2 attempts:3 edns0\n",
            encoding="utf-8",
        )

        collector = NetworkCollector(resolv_conf_path=resolv_file)
        dns = collector.get_dns_config()

        assert dns.nameservers == ["1.1.1.1", "8.8.8.8"]
        assert dns.search_domains == ["corp.internal", "lab.local"]
        assert "timeout:2" in dns.options
        assert "edns0" in dns.options
        assert dns.source == "NetworkManager"
