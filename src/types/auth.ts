export interface Permission {
  id: string;
  name: string;
  description?: string;
  resource: string;
  action: string;
  created_at: string;
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
  permissions: string[];
}

export interface User {
  id: string;
  username: string;
  email?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
  roles: string[];
  permissions: string[];
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    requestId?: string;
  };
}

export interface LoginResponse {
  success: boolean;
  user: User;
  effective_permissions: string[];
}

export interface AuthMeResponse {
  user: User;
  effective_permissions: string[];
}
