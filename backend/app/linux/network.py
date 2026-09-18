import fcntl
import os
import socket
import struct
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.linux.contracts import (
    DNSConfigInfo,
    INetworkCollector,
    IPAddressInfo,
    InterfaceDetailInfo,
    InterfaceStats,
    NetworkInterfaceInfo,
    NetworkOverview,
    RouteInfo,
)


class NetworkCollector(INetworkCollector):
    """
    Safely inspects Linux network interfaces, IP addresses, routing table, and DNS configuration.
    Uses direct read-only inspection of /sys/class/net, /proc/net/dev, /proc/net/if_inet6,
    /proc/net/route, /proc/net/ipv6_route, /etc/resolv.conf, and standard socket ioctls.
    Zero command execution, zero shell subprocesses, zero network mutation.
    """

    SIOCGIFADDR = 0x8915
    SIOCGIFNETMASK = 0x891B
    SIOCGIFFLAGS = 0x8913
    SIOCGIFMTU = 0x8921

    # Standard Linux ARPHRD device type mapping
    ARPHRD_MAP = {
        1: "ethernet",
        772: "loopback",
        768: "ipip",
        769: "ipgre",
        776: "sit",
        778: "gre",
        801: "wlan",
        512: "ppp",
        65534: "none",
    }

    # Standard Linux IFF flags bitmask mapping
    IFF_FLAGS_MAP = {
        0x1: "UP",
        0x2: "BROADCAST",
        0x4: "DEBUG",
        0x8: "LOOPBACK",
        0x10: "POINTOPOINT",
        0x20: "NOTRAILERS",
        0x40: "RUNNING",
        0x80: "NOARP",
        0x100: "PROMISC",
        0x200: "ALLMULTI",
        0x1000: "MULTICAST",
    }

    # IPv6 scope mapping
    IPV6_SCOPE_MAP = {
        0x00: "global",
        0x10: "compat",
        0x20: "link",
        0x40: "site",
        0x80: "host",
    }

    # IPv4 route flag mapping
    ROUTE_FLAGS_MAP = {
        0x0001: "U",  # Up
        0x0002: "G",  # Gateway
        0x0004: "H",  # Host
        0x0008: "R",  # Reinstate
        0x0010: "D",  # Dynamic
        0x0020: "M",  # Modified
    }

    def __init__(
        self,
        sys_net_path: Optional[Path] = None,
        proc_dev_path: Optional[Path] = None,
        proc_inet6_path: Optional[Path] = None,
        proc_route_path: Optional[Path] = None,
        proc_ipv6_route_path: Optional[Path] = None,
        resolv_conf_path: Optional[Path] = None,
    ):
        self.sys_net_path = sys_net_path or Path("/sys/class/net")
        self.proc_dev_path = proc_dev_path or Path("/proc/net/dev")
        self.proc_inet6_path = proc_inet6_path or Path("/proc/net/if_inet6")
        self.proc_route_path = proc_route_path or Path("/proc/net/route")
        self.proc_ipv6_route_path = proc_ipv6_route_path or Path("/proc/net/ipv6_route")
        self.resolv_conf_path = resolv_conf_path or Path("/etc/resolv.conf")

    def _get_detailed_traffic_stats(self) -> Dict[str, InterfaceStats]:
        """Parses /proc/net/dev for comprehensive interface packet & byte counters."""
        stats: Dict[str, InterfaceStats] = {}
        if not self.proc_dev_path.exists():
            return stats

        try:
            content = self.proc_dev_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if ":" in line:
                    iface_part, data_part = line.split(":", 1)
                    iface_name = iface_part.strip()
                    parts = data_part.split()
                    if len(parts) >= 16:
                        stats[iface_name] = InterfaceStats(
                            rx_bytes=int(parts[0]) if parts[0].isdigit() else 0,
                            rx_packets=int(parts[1]) if parts[1].isdigit() else 0,
                            rx_errors=int(parts[2]) if parts[2].isdigit() else 0,
                            rx_dropped=int(parts[3]) if parts[3].isdigit() else 0,
                            tx_bytes=int(parts[8]) if parts[8].isdigit() else 0,
                            tx_packets=int(parts[9]) if parts[9].isdigit() else 0,
                            tx_errors=int(parts[10]) if parts[10].isdigit() else 0,
                            tx_dropped=int(parts[11]) if parts[11].isdigit() else 0,
                        )
                    elif len(parts) >= 9:
                        stats[iface_name] = InterfaceStats(
                            rx_bytes=int(parts[0]) if parts[0].isdigit() else 0,
                            rx_packets=0,
                            rx_errors=0,
                            rx_dropped=0,
                            tx_bytes=int(parts[8]) if parts[8].isdigit() else 0,
                            tx_packets=0,
                            tx_errors=0,
                            tx_dropped=0,
                        )
        except Exception:
            pass

        return stats

    def _get_ipv6_address_details(self) -> Dict[str, List[IPAddressInfo]]:
        """Parses /proc/net/if_inet6 for structured IPv6 address entries."""
        ipv6_map: Dict[str, List[IPAddressInfo]] = {}
        if not self.proc_inet6_path.exists():
            return ipv6_map

        try:
            content = self.proc_inet6_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    raw_hex = parts[0]
                    prefix_len_hex = parts[2]
                    scope_hex = parts[3]
                    iface = parts[5]
                    try:
                        ip_bytes = bytes.fromhex(raw_hex)
                        formatted_ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
                        prefix_len = int(prefix_len_hex, 16)
                        scope_val = int(scope_hex, 16)
                        scope_str = self.IPV6_SCOPE_MAP.get(scope_val, f"0x{scope_val:02x}")

                        if iface not in ipv6_map:
                            ipv6_map[iface] = []

                        ipv6_map[iface].append(
                            IPAddressInfo(
                                family="ipv6",
                                address=formatted_ip,
                                prefix_length=prefix_len,
                                scope=scope_str,
                            )
                        )
                    except Exception:
                        continue
        except Exception:
            pass

        return ipv6_map

    def _get_ipv4_address_details(self, iface_name: str) -> List[IPAddressInfo]:
        """Queries IPv4 address and netmask prefix length using standard ioctls."""
        addresses: List[IPAddressInfo] = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                packed_iface = struct.pack("256s", iface_name[:15].encode("utf-8"))

                # 1. Primary IP Address
                try:
                    res_addr = fcntl.ioctl(s.fileno(), self.SIOCGIFADDR, packed_iface)
                    ip_str = socket.inet_ntoa(res_addr[20:24])
                except Exception:
                    return addresses

                # 2. Netmask -> Prefix Length
                prefix_len: Optional[int] = None
                try:
                    res_mask = fcntl.ioctl(s.fileno(), self.SIOCGIFNETMASK, packed_iface)
                    mask_str = socket.inet_ntoa(res_mask[20:24])
                    # Count 1 bits in netmask
                    mask_octets = [int(p) for p in mask_str.split(".")]
                    if len(mask_octets) == 4:
                        bin_str = "".join(f"{b:08b}" for b in mask_octets)
                        prefix_len = bin_str.count("1")
                except Exception:
                    prefix_len = None

                # Scope inference
                scope = "host" if iface_name == "lo" or ip_str.startswith("127.") else "global"

                addresses.append(
                    IPAddressInfo(
                        family="ipv4",
                        address=ip_str,
                        prefix_length=prefix_len,
                        scope=scope,
                    )
                )
        except Exception:
            pass

        return addresses

    def _decode_flags(self, flags_raw: int) -> List[str]:
        """Decodes raw Linux interface flags bitmask into human-readable flags."""
        flag_names: List[str] = []
        for bit, name in self.IFF_FLAGS_MAP.items():
            if flags_raw & bit:
                flag_names.append(name)
        return flag_names

    def get_network_interfaces(self) -> List[NetworkInterfaceInfo]:
        """Legacy interface summary for SystemOverview compatibility."""
        details = self.get_interface_details()
        return [
            NetworkInterfaceInfo(
                name=d.name,
                state=d.operational_state,
                mac_address=d.mac_address or "00:00:00:00:00:00",
                ipv4_addresses=d.ipv4_addresses,
                ipv6_addresses=d.ipv6_addresses,
                rx_bytes=d.stats.rx_bytes,
                tx_bytes=d.stats.tx_bytes,
            )
            for d in details
        ]

    def get_interface_details(self) -> List[InterfaceDetailInfo]:
        """Returns comprehensive interface details discovered via /sys/class/net and /proc."""
        traffic_map = self._get_detailed_traffic_stats()
        ipv6_map = self._get_ipv6_address_details()
        interfaces: List[InterfaceDetailInfo] = []

        if self.sys_net_path.exists():
            try:
                for iface_entry in sorted(self.sys_net_path.iterdir()):
                    if not iface_entry.is_dir() and not iface_entry.is_symlink():
                        continue

                    name = iface_entry.name

                    # Index
                    ifindex: Optional[int] = None
                    ifindex_file = iface_entry / "ifindex"
                    if ifindex_file.exists():
                        try:
                            ifindex = int(ifindex_file.read_text(encoding="utf-8").strip())
                        except Exception:
                            pass

                    # Operstate
                    operstate = "unknown"
                    operstate_file = iface_entry / "operstate"
                    if operstate_file.exists():
                        try:
                            operstate = operstate_file.read_text(encoding="utf-8").strip() or "unknown"
                        except Exception:
                            pass

                    # Address / MAC
                    mac_address: Optional[str] = None
                    addr_file = iface_entry / "address"
                    if addr_file.exists():
                        try:
                            addr_val = addr_file.read_text(encoding="utf-8").strip()
                            if addr_val:
                                mac_address = addr_val
                        except Exception:
                            pass

                    # MTU
                    mtu: Optional[int] = None
                    mtu_file = iface_entry / "mtu"
                    if mtu_file.exists():
                        try:
                            mtu = int(mtu_file.read_text(encoding="utf-8").strip())
                        except Exception:
                            pass

                    # Device Type
                    type_code = 1
                    type_file = iface_entry / "type"
                    if type_file.exists():
                        try:
                            type_code = int(type_file.read_text(encoding="utf-8").strip())
                        except Exception:
                            pass
                    iftype = self.ARPHRD_MAP.get(type_code, f"type-{type_code}")

                    # Flags
                    flags_raw = 0
                    flags_file = iface_entry / "flags"
                    if flags_file.exists():
                        try:
                            raw_txt = flags_file.read_text(encoding="utf-8").strip()
                            flags_raw = int(raw_txt, 16 if raw_txt.startswith("0x") else 10)
                        except Exception:
                            pass
                    flag_list = self._decode_flags(flags_raw)

                    # Admin state
                    admin_state = "up" if ("UP" in flag_list or (flags_raw & 0x1)) else "down"

                    # Virtual vs Physical vs Loopback
                    is_loopback = name == "lo" or "LOOPBACK" in flag_list or type_code == 772
                    try:
                        resolved_path = iface_entry.resolve().as_posix()
                        is_virtual = "/virtual/" in resolved_path or resolved_path.startswith("/sys/devices/virtual")
                    except Exception:
                        is_virtual = False

                    is_physical = not is_virtual and not is_loopback

                    # Speed & Duplex
                    speed_mbps: Optional[int] = None
                    speed_file = iface_entry / "speed"
                    if speed_file.exists():
                        try:
                            val = int(speed_file.read_text(encoding="utf-8").strip())
                            if val > 0:
                                speed_mbps = val
                        except Exception:
                            pass

                    duplex: Optional[str] = None
                    duplex_file = iface_entry / "duplex"
                    if duplex_file.exists():
                        try:
                            dup_val = duplex_file.read_text(encoding="utf-8").strip()
                            if dup_val in ("full", "half"):
                                duplex = dup_val
                        except Exception:
                            pass

                    # Statistics
                    stats = traffic_map.get(
                        name,
                        InterfaceStats(
                            rx_bytes=0,
                            rx_packets=0,
                            rx_errors=0,
                            rx_dropped=0,
                            tx_bytes=0,
                            tx_packets=0,
                            tx_errors=0,
                            tx_dropped=0,
                        ),
                    )

                    # If proc/net/dev didn't have stats, fall back to sysfs
                    if stats.rx_bytes == 0 and stats.tx_bytes == 0:
                        sys_stats_dir = iface_entry / "statistics"
                        if sys_stats_dir.exists():
                            try:
                                def _read_stat(stat_name: str) -> int:
                                    f = sys_stats_dir / stat_name
                                    if f.exists():
                                        txt = f.read_text(encoding="utf-8").strip()
                                        return int(txt) if txt.isdigit() else 0
                                    return 0

                                stats = InterfaceStats(
                                    rx_bytes=_read_stat("rx_bytes"),
                                    rx_packets=_read_stat("rx_packets"),
                                    rx_errors=_read_stat("rx_errors"),
                                    rx_dropped=_read_stat("rx_dropped"),
                                    tx_bytes=_read_stat("tx_bytes"),
                                    tx_packets=_read_stat("tx_packets"),
                                    tx_errors=_read_stat("tx_errors"),
                                    tx_dropped=_read_stat("tx_dropped"),
                                )
                            except Exception:
                                pass

                    # IP addresses
                    ipv4_objs = self._get_ipv4_address_details(name)
                    ipv6_objs = ipv6_map.get(name, [])
                    all_addrs = ipv4_objs + ipv6_objs

                    ipv4_strs = [a.address for a in ipv4_objs]
                    ipv6_strs = [a.address for a in ipv6_objs]

                    interfaces.append(
                        InterfaceDetailInfo(
                            name=name,
                            index=ifindex,
                            iftype=iftype,
                            operational_state=operstate,
                            administrative_state=admin_state,
                            mtu=mtu,
                            mac_address=mac_address,
                            flags=flag_list,
                            is_loopback=is_loopback,
                            is_virtual=is_virtual,
                            is_physical=is_physical,
                            ipv4_addresses=ipv4_strs,
                            ipv6_addresses=ipv6_strs,
                            addresses=all_addrs,
                            stats=stats,
                            speed_mbps=speed_mbps,
                            duplex=duplex,
                        )
                    )
            except Exception:
                pass

        # Sort: physical first, then virtual, loopback last
        interfaces.sort(key=lambda x: (x.is_loopback, not x.is_physical, x.name))
        return interfaces

    def get_interface_by_name(self, name: str) -> Optional[InterfaceDetailInfo]:
        """Finds a single interface by exact name."""
        for iface in self.get_interface_details():
            if iface.name == name:
                return iface
        return None

    def get_routes(self) -> List[RouteInfo]:
        """
        Parses IPv4 routing entries from /proc/net/route and IPv6 entries from /proc/net/ipv6_route.
        """
        routes: List[RouteInfo] = []

        # 1. IPv4 Routes from /proc/net/route
        if self.proc_route_path.exists():
            try:
                content = self.proc_route_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                # Skip header: Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 8:
                        iface = parts[0]
                        dest_hex = parts[1]
                        gw_hex = parts[2]
                        flags_hex = parts[3]
                        metric_val = int(parts[6]) if parts[6].isdigit() else 0
                        mask_hex = parts[7]

                        try:
                            # Convert hex to little-endian packed IPv4 address
                            dest_ip = socket.inet_ntoa(struct.pack("<L", int(dest_hex, 16)))
                            gw_ip = socket.inet_ntoa(struct.pack("<L", int(gw_hex, 16)))
                            mask_ip = socket.inet_ntoa(struct.pack("<L", int(mask_hex, 16)))

                            flags_int = int(flags_hex, 16)
                            flag_chars = "".join(
                                char for bit, char in self.ROUTE_FLAGS_MAP.items() if flags_int & bit
                            )

                            is_default = (dest_ip == "0.0.0.0" and (mask_ip in ("0.0.0.0", "0") or int(dest_hex, 16) == 0))

                            routes.append(
                                RouteInfo(
                                    destination=dest_ip,
                                    gateway=gw_ip,
                                    interface=iface,
                                    flags=flag_chars or "U",
                                    metric=metric_val,
                                    family="ipv4",
                                    mask=mask_ip,
                                    is_default=is_default,
                                )
                            )
                        except Exception:
                            continue
            except Exception:
                pass

        # 2. IPv6 Routes from /proc/net/ipv6_route
        if self.proc_ipv6_route_path.exists():
            try:
                content = self.proc_ipv6_route_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    parts = line.split()
                    if len(parts) >= 10:
                        dest_hex = parts[0]
                        dest_prefix_hex = parts[1]
                        gw_hex = parts[4]
                        metric_hex = parts[5]
                        flags_hex = parts[8]
                        iface = parts[9]

                        try:
                            dest_prefix = int(dest_prefix_hex, 16)
                            dest_bytes = bytes.fromhex(dest_hex)
                            dest_ip = socket.inet_ntop(socket.AF_INET6, dest_bytes)

                            gw_bytes = bytes.fromhex(gw_hex)
                            gw_ip = socket.inet_ntop(socket.AF_INET6, gw_bytes)

                            metric_val = int(metric_hex, 16)
                            flags_val = int(flags_hex, 16)

                            is_default = (dest_hex.strip("0") == "" and dest_prefix == 0)

                            routes.append(
                                RouteInfo(
                                    destination=f"{dest_ip}/{dest_prefix}",
                                    gateway=gw_ip,
                                    interface=iface,
                                    flags=f"0x{flags_val:04x}",
                                    metric=metric_val,
                                    family="ipv6",
                                    mask=f"/{dest_prefix}",
                                    is_default=is_default,
                                )
                            )
                        except Exception:
                            continue
            except Exception:
                pass

        # Sort: default routes first, then by interface, then destination
        routes.sort(key=lambda r: (not r.is_default, r.family != "ipv4", r.interface, r.destination))
        return routes

    def get_dns_config(self) -> DNSConfigInfo:
        """
        Parses /etc/resolv.conf and identifies nameservers, search domains, and configuration source.
        """
        nameservers: List[str] = []
        search_domains: List[str] = []
        options: List[str] = []
        source = "static / custom"
        is_symlink = False
        symlink_target: Optional[str] = None

        if self.resolv_conf_path.exists():
            try:
                is_symlink = self.resolv_conf_path.is_symlink()
                if is_symlink:
                    symlink_target = str(self.resolv_conf_path.resolve())
                    if "systemd/resolve" in symlink_target or "stub-resolv.conf" in symlink_target:
                        source = "systemd-resolved"
                    elif "NetworkManager" in symlink_target:
                        source = "NetworkManager"
                    elif "resolvconf" in symlink_target:
                        source = "resolvconf"

                content = self.resolv_conf_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#") or trimmed.startswith(";"):
                        # Check header comments for source hints
                        if "Generated by NetworkManager" in trimmed:
                            source = "NetworkManager"
                        elif "systemd-resolved" in trimmed:
                            source = "systemd-resolved"
                        elif "resolvconf" in trimmed:
                            source = "resolvconf"
                        continue

                    parts = trimmed.split()
                    if not parts:
                        continue

                    key = parts[0].lower()
                    if key == "nameserver" and len(parts) >= 2:
                        ns = parts[1]
                        if ns not in nameservers:
                            nameservers.append(ns)
                    elif key in ("search", "domain") and len(parts) >= 2:
                        for domain in parts[1:]:
                            if domain not in search_domains:
                                search_domains.append(domain)
                    elif key == "options" and len(parts) >= 2:
                        for opt in parts[1:]:
                            if opt not in options:
                                options.append(opt)
            except Exception:
                pass

        return DNSConfigInfo(
            nameservers=nameservers,
            search_domains=search_domains,
            options=options,
            source=source,
            is_symlink=is_symlink,
            symlink_target=symlink_target,
        )

    def get_network_overview(self) -> NetworkOverview:
        """Computes aggregate network metrics across interfaces, routes, and DNS."""
        interfaces = self.get_interface_details()
        routes = self.get_routes()
        dns = self.get_dns_config()

        total_interfaces = len(interfaces)
        up_interfaces = sum(1 for i in interfaces if i.operational_state == "up" or i.administrative_state == "up")
        down_interfaces = total_interfaces - up_interfaces
        physical_interfaces = sum(1 for i in interfaces if i.is_physical)
        virtual_interfaces = sum(1 for i in interfaces if i.is_virtual)
        loopback_interfaces = sum(1 for i in interfaces if i.is_loopback)

        all_ipv4: List[str] = []
        all_ipv6: List[str] = []
        for i in interfaces:
            all_ipv4.extend(i.ipv4_addresses)
            all_ipv6.extend(i.ipv6_addresses)

        default_ipv4: Optional[str] = None
        default_ipv6: Optional[str] = None
        for r in routes:
            if r.is_default:
                if r.family == "ipv4" and not default_ipv4:
                    default_ipv4 = f"{r.gateway} via {r.interface}" if r.gateway != "0.0.0.0" else f"{r.interface}"
                elif r.family == "ipv6" and not default_ipv6:
                    default_ipv6 = f"{r.gateway} via {r.interface}" if r.gateway.strip("0:") != "" else f"{r.interface}"

        return NetworkOverview(
            total_interfaces=total_interfaces,
            up_interfaces=up_interfaces,
            down_interfaces=down_interfaces,
            physical_interfaces=physical_interfaces,
            virtual_interfaces=virtual_interfaces,
            loopback_interfaces=loopback_interfaces,
            ipv4_addresses=all_ipv4,
            ipv6_addresses=all_ipv6,
            default_ipv4_route=default_ipv4,
            default_ipv6_route=default_ipv6,
            dns_servers=dns.nameservers,
        )


network_collector = NetworkCollector()
