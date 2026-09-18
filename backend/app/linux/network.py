import fcntl
import socket
import struct
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.linux.contracts import INetworkCollector, NetworkInterfaceInfo


class NetworkCollector(INetworkCollector):
    """
    Safely inspects network interface states, addresses, and traffic statistics.
    Uses unprivileged /sys/class/net, /proc/net/dev, and standard socket syscalls.
    Zero packet sniffing, zero firewall edits, zero external shell commands.
    """

    SIOCGIFADDR = 0x8915

    def __init__(
        self,
        sys_net_path: Optional[Path] = None,
        proc_dev_path: Optional[Path] = None,
        proc_inet6_path: Optional[Path] = None,
    ):
        self.sys_net_path = sys_net_path or Path("/sys/class/net")
        self.proc_dev_path = proc_dev_path or Path("/proc/net/dev")
        self.proc_inet6_path = proc_inet6_path or Path("/proc/net/if_inet6")

    def _get_traffic_stats(self) -> Dict[str, tuple[int, int]]:
        """Parses /proc/net/dev for rx_bytes and tx_bytes per interface."""
        stats: Dict[str, tuple[int, int]] = {}
        if not self.proc_dev_path.exists():
            return stats

        try:
            content = self.proc_dev_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if ":" in line:
                    iface_part, data_part = line.split(":", 1)
                    iface_name = iface_part.strip()
                    parts = data_part.split()
                    if len(parts) >= 9:
                        rx_bytes = int(parts[0]) if parts[0].isdigit() else 0
                        tx_bytes = int(parts[8]) if parts[8].isdigit() else 0
                        stats[iface_name] = (rx_bytes, tx_bytes)
        except Exception:
            pass

        return stats

    def _get_ipv6_addresses(self) -> Dict[str, List[str]]:
        """Parses /proc/net/if_inet6 for IPv6 addresses per interface."""
        ipv6_map: Dict[str, List[str]] = {}
        if not self.proc_inet6_path.exists():
            return ipv6_map

        try:
            content = self.proc_inet6_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    raw_hex = parts[0]
                    iface = parts[5]
                    try:
                        ip_bytes = bytes.fromhex(raw_hex)
                        formatted_ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
                        if iface not in ipv6_map:
                            ipv6_map[iface] = []
                        ipv6_map[iface].append(formatted_ip)
                    except Exception:
                        continue
        except Exception:
            pass

        return ipv6_map

    def _get_ipv4_address(self, iface_name: str) -> Optional[str]:
        """Queries IPv4 address using standard SIOCGIFADDR ioctl."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                packed = struct.pack("256s", iface_name[:15].encode("utf-8"))
                result = fcntl.ioctl(s.fileno(), self.SIOCGIFADDR, packed)
                ip = socket.inet_ntoa(result[20:24])
                return ip
        except Exception:
            return None

    def get_network_interfaces(self) -> List[NetworkInterfaceInfo]:
        traffic_stats = self._get_traffic_stats()
        ipv6_stats = self._get_ipv6_addresses()
        interfaces: List[NetworkInterfaceInfo] = []

        # 1. Discover interfaces from /sys/class/net
        if self.sys_net_path.exists():
            try:
                for iface_dir in sorted(self.sys_net_path.iterdir()):
                    if not iface_dir.is_dir() and not iface_dir.is_symlink():
                        continue

                    name = iface_dir.name

                    # Operstate
                    state = "unknown"
                    operstate_file = iface_dir / "operstate"
                    if operstate_file.exists():
                        try:
                            state = operstate_file.read_text(encoding="utf-8").strip()
                        except Exception:
                            pass

                    # MAC Address
                    mac = "00:00:00:00:00:00"
                    addr_file = iface_dir / "address"
                    if addr_file.exists():
                        try:
                            mac = addr_file.read_text(encoding="utf-8").strip() or mac
                        except Exception:
                            pass

                    # Traffic Stats
                    rx_bytes, tx_bytes = traffic_stats.get(name, (0, 0))
                    if rx_bytes == 0 and tx_bytes == 0:
                        # Fallback to sysfs statistics if proc/net/dev didn't have it
                        rx_file = iface_dir / "statistics" / "rx_bytes"
                        tx_file = iface_dir / "statistics" / "tx_bytes"
                        if rx_file.exists():
                            try:
                                rx_bytes = int(rx_file.read_text(encoding="utf-8").strip())
                            except Exception:
                                pass
                        if tx_file.exists():
                            try:
                                tx_bytes = int(tx_file.read_text(encoding="utf-8").strip())
                            except Exception:
                                pass

                    # IP Addresses
                    ipv4_addrs: List[str] = []
                    ipv4 = self._get_ipv4_address(name)
                    if ipv4:
                        ipv4_addrs.append(ipv4)

                    ipv6_addrs = ipv6_stats.get(name, [])

                    interfaces.append(
                        NetworkInterfaceInfo(
                            name=name,
                            state=state,
                            mac_address=mac,
                            ipv4_addresses=ipv4_addrs,
                            ipv6_addresses=ipv6_addrs,
                            rx_bytes=rx_bytes,
                            tx_bytes=tx_bytes,
                        )
                    )
            except Exception:
                pass

        # 2. Fallback: if /sys/class/net had no interfaces, discover from /proc/net/dev
        if not interfaces and traffic_stats:
            for name, (rx, tx) in traffic_stats.items():
                ipv4_addrs = []
                ipv4 = self._get_ipv4_address(name)
                if ipv4:
                    ipv4_addrs.append(ipv4)
                ipv6_addrs = ipv6_stats.get(name, [])

                interfaces.append(
                    NetworkInterfaceInfo(
                        name=name,
                        state="up" if rx > 0 or tx > 0 else "unknown",
                        mac_address="00:00:00:00:00:00",
                        ipv4_addresses=ipv4_addrs,
                        ipv6_addresses=ipv6_addrs,
                        rx_bytes=rx,
                        tx_bytes=tx,
                    )
                )

        # Ensure loopback 'lo' is included if present, but place primary ethernet first
        interfaces.sort(key=lambda x: (x.name == "lo", x.name))
        return interfaces


network_collector = NetworkCollector()
