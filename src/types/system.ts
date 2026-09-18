export interface SystemIdentity {
  hostname: string;
  operating_system: string;
  distribution: string;
  distribution_version: string;
  kernel_version: string;
  architecture: string;
  uptime_seconds: number;
  boot_time?: string | null;
}

export interface CPULoadAverage {
  load_1m: number;
  load_5m: number;
  load_15m: number;
}

export interface CPUInfo {
  logical_cores: number;
  model_name: string;
  usage_percent: number;
  load_average: CPULoadAverage;
}

export interface SwapInfo {
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  usage_percent: number;
}

export interface MemoryInfo {
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  free_bytes: number;
  usage_percent: number;
  swap: SwapInfo;
}

export interface DiskMountInfo {
  device: string;
  mount_point: string;
  filesystem_type: string;
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  usage_percent: number;
}

export interface NetworkInterfaceInfo {
  name: string;
  state: string;
  mac_address: string;
  ipv4_addresses: string[];
  ipv6_addresses: string[];
  rx_bytes: number;
  tx_bytes: number;
}

export interface SystemOverview {
  identity: SystemIdentity;
  cpu: CPUInfo;
  memory: MemoryInfo;
  disks: DiskMountInfo[];
  network: NetworkInterfaceInfo[];
  timestamp: string;
}
