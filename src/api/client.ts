import { ApiErrorResponse } from '../types/auth';

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
}

export const apiClient = new ApiClient();
