from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth.dependencies import require_permission
from backend.app.auth.models import UserRead
from backend.app.core.errors import NotFoundError
from backend.app.core.validators import validate_interface_name
from backend.app.linux.network import network_collector

router = APIRouter(prefix="/network", tags=["Network Management"])


class IPAddressResponse(BaseModel):
    family: str
    address: str
    prefix_length: Optional[int] = None
    scope: Optional[str] = None


class InterfaceStatsResponse(BaseModel):
    rx_bytes: int
    rx_packets: int
    rx_errors: int
    rx_dropped: int
    tx_bytes: int
    tx_packets: int
    tx_errors: int
    tx_dropped: int


class InterfaceDetailResponse(BaseModel):
    name: str
    index: Optional[int] = None
    iftype: str
    operational_state: str
    administrative_state: Optional[str] = None
    mtu: Optional[int] = None
    mac_address: Optional[str] = None
    flags: List[str] = []
    is_loopback: bool
    is_virtual: bool
    is_physical: bool
    ipv4_addresses: List[str] = []
    ipv6_addresses: List[str] = []
    addresses: List[IPAddressResponse] = []
    stats: InterfaceStatsResponse
    speed_mbps: Optional[int] = None
    duplex: Optional[str] = None


class RouteResponse(BaseModel):
    destination: str
    gateway: str
    interface: str
    flags: str
    metric: int
    family: str
    mask: Optional[str] = None
    is_default: bool = False


class DNSConfigResponse(BaseModel):
    nameservers: List[str] = []
    search_domains: List[str] = []
    options: List[str] = []
    source: str
    is_symlink: bool
    symlink_target: Optional[str] = None


class NetworkOverviewResponse(BaseModel):
    total_interfaces: int
    up_interfaces: int
    down_interfaces: int
    physical_interfaces: int
    virtual_interfaces: int
    loopback_interfaces: int
    ipv4_addresses: List[str] = []
    ipv6_addresses: List[str] = []
    default_ipv4_route: Optional[str] = None
    default_ipv6_route: Optional[str] = None
    dns_servers: List[str] = []


@router.get(
    "/overview",
    response_model=NetworkOverviewResponse,
    summary="Get aggregated network overview",
    description="Retrieves high-level summary KPIs and default routes.",
)
async def get_network_overview(
    _current_user: UserRead = Depends(require_permission("network.read")),
) -> NetworkOverviewResponse:
    overview = network_collector.get_network_overview()
    return NetworkOverviewResponse(
        total_interfaces=overview.total_interfaces,
        up_interfaces=overview.up_interfaces,
        down_interfaces=overview.down_interfaces,
        physical_interfaces=overview.physical_interfaces,
        virtual_interfaces=overview.virtual_interfaces,
        loopback_interfaces=overview.loopback_interfaces,
        ipv4_addresses=overview.ipv4_addresses,
        ipv6_addresses=overview.ipv6_addresses,
        default_ipv4_route=overview.default_ipv4_route,
        default_ipv6_route=overview.default_ipv6_route,
        dns_servers=overview.dns_servers,
    )


@router.get(
    "/interfaces",
    response_model=List[InterfaceDetailResponse],
    summary="List all network interfaces",
    description="Discovers and details physical, virtual, and loopback network interfaces with stats and IP addresses.",
)
async def get_network_interfaces(
    _current_user: UserRead = Depends(require_permission("network.read")),
) -> List[InterfaceDetailResponse]:
    details = network_collector.get_interface_details()
    return [
        InterfaceDetailResponse(
            name=d.name,
            index=d.index,
            iftype=d.iftype,
            operational_state=d.operational_state,
            administrative_state=d.administrative_state,
            mtu=d.mtu,
            mac_address=d.mac_address,
            flags=d.flags,
            is_loopback=d.is_loopback,
            is_virtual=d.is_virtual,
            is_physical=d.is_physical,
            ipv4_addresses=d.ipv4_addresses,
            ipv6_addresses=d.ipv6_addresses,
            addresses=[
                IPAddressResponse(
                    family=a.family,
                    address=a.address,
                    prefix_length=a.prefix_length,
                    scope=a.scope,
                )
                for a in d.addresses
            ],
            stats=InterfaceStatsResponse(
                rx_bytes=d.stats.rx_bytes,
                rx_packets=d.stats.rx_packets,
                rx_errors=d.stats.rx_errors,
                rx_dropped=d.stats.rx_dropped,
                tx_bytes=d.stats.tx_bytes,
                tx_packets=d.stats.tx_packets,
                tx_errors=d.stats.tx_errors,
                tx_dropped=d.stats.tx_dropped,
            ),
            speed_mbps=d.speed_mbps,
            duplex=d.duplex,
        )
        for d in details
    ]


@router.get(
    "/interfaces/{name}",
    response_model=InterfaceDetailResponse,
    summary="Get single interface details",
    description="Retrieves full telemetry, statistics, and IP addresses for a validated interface name.",
)
async def get_network_interface_by_name(
    name: str,
    _current_user: UserRead = Depends(require_permission("network.read")),
) -> InterfaceDetailResponse:
    validated_name = validate_interface_name(name)
    d = network_collector.get_interface_by_name(validated_name)
    if not d:
        raise NotFoundError(
            f"Network interface '{validated_name}' not found",
            code="INTERFACE_NOT_FOUND",
        )

    return InterfaceDetailResponse(
        name=d.name,
        index=d.index,
        iftype=d.iftype,
        operational_state=d.operational_state,
        administrative_state=d.administrative_state,
        mtu=d.mtu,
        mac_address=d.mac_address,
        flags=d.flags,
        is_loopback=d.is_loopback,
        is_virtual=d.is_virtual,
        is_physical=d.is_physical,
        ipv4_addresses=d.ipv4_addresses,
        ipv6_addresses=d.ipv6_addresses,
        addresses=[
            IPAddressResponse(
                family=a.family,
                address=a.address,
                prefix_length=a.prefix_length,
                scope=a.scope,
            )
            for a in d.addresses
        ],
        stats=InterfaceStatsResponse(
            rx_bytes=d.stats.rx_bytes,
            rx_packets=d.stats.rx_packets,
            rx_errors=d.stats.rx_errors,
            rx_dropped=d.stats.rx_dropped,
            tx_bytes=d.stats.tx_bytes,
            tx_packets=d.stats.tx_packets,
            tx_errors=d.stats.tx_errors,
            tx_dropped=d.stats.tx_dropped,
        ),
        speed_mbps=d.speed_mbps,
        duplex=d.duplex,
    )


@router.get(
    "/routes",
    response_model=List[RouteResponse],
    summary="Get Linux routing table",
    description="Retrieves read-only IPv4 and IPv6 routing entries.",
)
async def get_network_routes(
    _current_user: UserRead = Depends(require_permission("network.read")),
) -> List[RouteResponse]:
    routes = network_collector.get_routes()
    return [
        RouteResponse(
            destination=r.destination,
            gateway=r.gateway,
            interface=r.interface,
            flags=r.flags,
            metric=r.metric,
            family=r.family,
            mask=r.mask,
            is_default=r.is_default,
        )
        for r in routes
    ]


@router.get(
    "/dns",
    response_model=DNSConfigResponse,
    summary="Get DNS configuration",
    description="Retrieves DNS nameservers, search domains, and resolver source.",
)
async def get_dns_config(
    _current_user: UserRead = Depends(require_permission("network.read")),
) -> DNSConfigResponse:
    dns = network_collector.get_dns_config()
    return DNSConfigResponse(
        nameservers=dns.nameservers,
        search_domains=dns.search_domains,
        options=dns.options,
        source=dns.source,
        is_symlink=dns.is_symlink,
        symlink_target=dns.symlink_target,
    )
