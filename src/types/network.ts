export interface IPAddressInfo {
  family: 'ipv4' | 'ipv6' | string;
  address: string;
  prefix_length?: number | null;
  scope?: string | null;
}

export interface InterfaceStats {
  rx_bytes: number;
  rx_packets: number;
  rx_errors: number;
  rx_dropped: number;
  tx_bytes: number;
  tx_packets: number;
  tx_errors: number;
  tx_dropped: number;
}

export interface InterfaceDetailInfo {
  name: string;
  index?: number | null;
  iftype: string;
  operational_state: string;
  administrative_state?: string | null;
  mtu?: number | null;
  mac_address?: string | null;
  flags: string[];
  is_loopback: boolean;
  is_virtual: boolean;
  is_physical: boolean;
  ipv4_addresses: string[];
  ipv6_addresses: string[];
  addresses: IPAddressInfo[];
  stats: InterfaceStats;
  speed_mbps?: number | null;
  duplex?: string | null;
}

export interface RouteInfo {
  destination: string;
  gateway: string;
  interface: string;
  flags: string;
  metric: number;
  family: 'ipv4' | 'ipv6' | string;
  mask?: string | null;
  is_default: boolean;
}

export interface DNSConfigInfo {
  nameservers: string[];
  search_domains: string[];
  options: string[];
  source: string;
  is_symlink: boolean;
  symlink_target?: string | null;
}

export interface NetworkOverview {
  total_interfaces: number;
  up_interfaces: number;
  down_interfaces: number;
  physical_interfaces: number;
  virtual_interfaces: number;
  loopback_interfaces: number;
  ipv4_addresses: string[];
  ipv6_addresses: string[];
  default_ipv4_route?: string | null;
  default_ipv6_route?: string | null;
  dns_servers: string[];
}
