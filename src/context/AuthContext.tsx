import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { User } from '../types/auth';
import { apiClient, ApiError } from '../api/client';

interface AuthContextType {
  user: User | null;
  permissions: string[];
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await apiClient.getMe();
      if (res && res.user) {
        setUser(res.user);
        setPermissions(res.effective_permissions || res.user.permissions || []);
        setIsAuthenticated(true);
        setError(null);
      } else {
        setUser(null);
        setPermissions([]);
        setIsAuthenticated(false);
      }
    } catch {
      setUser(null);
      setPermissions([]);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (username: string, password: string) => {
    setError(null);
    try {
      const res = await apiClient.login(username, password);
      if (res && res.user) {
        setUser(res.user);
        setPermissions(res.effective_permissions || res.user.permissions || []);
        setIsAuthenticated(true);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Unable to authenticate. Please check your credentials.');
      }
      throw err;
    }
  };

  const logout = async () => {
    try {
      await apiClient.logout();
    } catch {
      // Continue client cleanup even if network fails
    } finally {
      setUser(null);
      setPermissions([]);
      setIsAuthenticated(false);
      setError(null);
    }
  };

  const hasPermission = (permission: string): boolean => {
    return permissions.includes(permission);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        permissions,
        isAuthenticated,
        isLoading,
        error,
        login,
        logout,
        refreshUser,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
