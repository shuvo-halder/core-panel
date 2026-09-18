export interface BlockDevicePartInfo {
  name: string;
  path: string;
  size_bytes: number;
  filesystem: string | null;
  mount_point: string | null;
  uuid: string | null;
  label: string | null;
  is_read_only: boolean;
}

export interface BlockDeviceInfo {
  name: string;
  path: string;
  device_type: 'disk' | 'part' | 'loop' | 'rom' | string;
  size_bytes: number;
  model: string | null;
  vendor: string | null;
  is_removable: boolean;
  is_read_only: boolean;
  filesystem: string | null;
  mount_point: string | null;
  label: string | null;
  uuid: string | null;
  children: BlockDevicePartInfo[];
}

export interface FilesystemInfo {
  device: string;
  mount_point: string;
  fstype: string;
  is_pseudo: boolean;
  is_read_only: boolean;
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  usage_percent: number;
  label: string | null;
  uuid: string | null;
  mount_options: string | null;
}

export interface StorageOverview {
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  usage_percent: number;
  device_count: number;
  filesystem_count: number;
  mount_count: number;
}
