import { ApiErrorResponse } from '../types/auth';
import { ProcessListResponse, ProcessMutationResult, ProcessSummary } from '../types/process';
import { ServiceMutationResult, ServiceSummary } from '../types/service';
import { BlockDeviceInfo, FilesystemInfo, StorageOverview } from '../types/storage';
import { DNSConfigInfo, InterfaceDetailInfo, NetworkOverview, RouteInfo } from '../types/network';
import {
  CPUInfo,
  DiskMountInfo,
  MemoryInfo,
  NetworkInterfaceInfo,
  SystemIdentity,
  SystemOverview,
} from '../types/system';

export class ApiError extends Error {
  code: string;
  statusCode: number;
  requestId?: string;

  constructor(message: string, code: string = 'UNKNOWN_ERROR', statusCode: number = 500, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.statusCode = statusCode;
    this.requestId = requestId;
  }
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api/v1') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Always send and receive HttpOnly cookies
    });

    if (response.status === 204) {
      return {} as T;
    }

    let data: any;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      if (data && typeof data === 'object' && 'error' in data) {
        const errResp = data as ApiErrorResponse;
        throw new ApiError(
          errResp.error.message || 'An error occurred',
          errResp.error.code || 'API_ERROR',
          response.status,
          errResp.error.requestId
        );
      }
      throw new ApiError(
        `Request failed with status ${response.status}`,
        'HTTP_ERROR',
        response.status
      );
    }

    return data as T;
  }

  // Authentication endpoints
  async login(username: string, password: string) {
    return this.request<{ success: boolean; user: any; effective_permissions: string[] }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  }

  async logout() {
    return this.request<{ success: boolean; message: string }>('/auth/logout', {
      method: 'POST',
    });
  }

  async getMe() {
    return this.request<{ user: any; effective_permissions: string[] }>('/auth/me', {
      method: 'GET',
    });
  }

  // Users endpoints
  async listUsers() {
    return this.request<any[]>('/users', { method: 'GET' });
  }

  async createUser(payload: { username: string; password: string; email?: string; roles?: string[]; is_active?: boolean }) {
    return this.request<any>('/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateUser(userId: string, payload: { email?: string; password?: string; roles?: string[]; is_active?: boolean }) {
    return this.request<any>(`/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteUser(userId: string) {
    return this.request<{ success: boolean; message: string }>(`/users/${userId}`, {
      method: 'DELETE',
    });
  }

  // Roles & Permissions endpoints
  async listRoles() {
    return this.request<any[]>('/roles', { method: 'GET' });
  }

  async listPermissions() {
    return this.request<any[]>('/permissions', { method: 'GET' });
  }

  // System Monitoring endpoints (Phase 3)
  async getSystemOverview(): Promise<SystemOverview> {
    return this.request<SystemOverview>('/system/overview', { method: 'GET' });
  }

  async getSystemInfo(): Promise<SystemIdentity> {
    return this.request<SystemIdentity>('/system/info', { method: 'GET' });
  }

  async getSystemCpu(): Promise<CPUInfo> {
    return this.request<CPUInfo>('/system/cpu', { method: 'GET' });
  }

  async getSystemMemory(): Promise<MemoryInfo> {
    return this.request<MemoryInfo>('/system/memory', { method: 'GET' });
  }

  async getSystemDisks(): Promise<DiskMountInfo[]> {
    return this.request<DiskMountInfo[]>('/system/disks', { method: 'GET' });
  }

  async getSystemNetwork(): Promise<NetworkInterfaceInfo[]> {
    return this.request<NetworkInterfaceInfo[]>('/system/network', { method: 'GET' });
  }

  // Linux Service Management endpoints (Phase 4)
  async listServices(): Promise<ServiceSummary[]> {
    return this.request<ServiceSummary[]>('/services', { method: 'GET' });
  }

  async getService(unit: string): Promise<ServiceSummary> {
    return this.request<ServiceSummary>(`/services/${encodeURIComponent(unit)}`, { method: 'GET' });
  }

  async startService(unit: string): Promise<ServiceMutationResult> {
    return this.request<ServiceMutationResult>(`/services/${encodeURIComponent(unit)}/start`, {
      method: 'POST',
    });
  }

  async stopService(unit: string): Promise<ServiceMutationResult> {
    return this.request<ServiceMutationResult>(`/services/${encodeURIComponent(unit)}/stop`, {
      method: 'POST',
    });
  }

  async restartService(unit: string): Promise<ServiceMutationResult> {
    return this.request<ServiceMutationResult>(`/services/${encodeURIComponent(unit)}/restart`, {
      method: 'POST',
    });
  }

  async enableService(unit: string): Promise<ServiceMutationResult> {
    return this.request<ServiceMutationResult>(`/services/${encodeURIComponent(unit)}/enable`, {
      method: 'POST',
    });
  }

  async disableService(unit: string): Promise<ServiceMutationResult> {
    return this.request<ServiceMutationResult>(`/services/${encodeURIComponent(unit)}/disable`, {
      method: 'POST',
    });
  }

  // Linux Process Management endpoints (Phase 5)
  async listProcesses(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    sort?: string;
    order?: 'asc' | 'desc';
  }): Promise<ProcessListResponse> {
    const query = new URLSearchParams();
    if (params?.page) query.append('page', params.page.toString());
    if (params?.page_size) query.append('page_size', params.page_size.toString());
    if (params?.search) query.append('search', params.search);
    if (params?.sort) query.append('sort', params.sort);
    if (params?.order) query.append('order', params.order);

    const queryString = query.toString();
    const endpoint = queryString ? `/processes?${queryString}` : '/processes';
    return this.request<ProcessListResponse>(endpoint, { method: 'GET' });
  }

  async getProcess(pid: number): Promise<ProcessSummary> {
    return this.request<ProcessSummary>(`/processes/${pid}`, { method: 'GET' });
  }

  async terminateProcess(pid: number): Promise<ProcessMutationResult> {
    return this.request<ProcessMutationResult>(`/processes/${pid}/terminate`, {
      method: 'POST',
    });
  }

  async killProcess(pid: number): Promise<ProcessMutationResult> {
    return this.request<ProcessMutationResult>(`/processes/${pid}/kill`, {
      method: 'POST',
    });
  }

  // Linux Storage & Disk Management endpoints (Phase 6)
  async getStorageOverview(): Promise<StorageOverview> {
    return this.request<StorageOverview>('/storage/overview', { method: 'GET' });
  }

  async getStorageDevices(): Promise<BlockDeviceInfo[]> {
    return this.request<BlockDeviceInfo[]>('/storage/devices', { method: 'GET' });
  }

  async getStorageFilesystems(includePseudo: boolean = false): Promise<FilesystemInfo[]> {
    const endpoint = includePseudo ? '/storage/filesystems?include_pseudo=true' : '/storage/filesystems';
    return this.request<FilesystemInfo[]>(endpoint, { method: 'GET' });
  }

  async getStorageMounts(): Promise<FilesystemInfo[]> {
    return this.request<FilesystemInfo[]>('/storage/mounts', { method: 'GET' });
  }

  // Linux Network Management endpoints (Phase 7)
  async getNetworkOverview(): Promise<NetworkOverview> {
    return this.request<NetworkOverview>('/network/overview', { method: 'GET' });
  }

  async getNetworkInterfaces(): Promise<InterfaceDetailInfo[]> {
    return this.request<InterfaceDetailInfo[]>('/network/interfaces', { method: 'GET' });
  }

  async getNetworkInterface(name: string): Promise<InterfaceDetailInfo> {
    return this.request<InterfaceDetailInfo>(`/network/interfaces/${encodeURIComponent(name)}`, {
      method: 'GET',
    });
  }

  async getNetworkRoutes(): Promise<RouteInfo[]> {
    return this.request<RouteInfo[]>('/network/routes', { method: 'GET' });
  }

  async getNetworkDNS(): Promise<DNSConfigInfo> {
    return this.request<DNSConfigInfo>('/network/dns', { method: 'GET' });
  }
}

export const apiClient = new ApiClient();
