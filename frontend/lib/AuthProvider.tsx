'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  AuthUser,
  clearTokens,
  clearCookies,
  fetchCurrentUser,
  getStoredUser,
  getToken,
  login as apiLogin,
  logout as apiLogout,
  syncCookies,
} from '@/lib/auth';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isAdmin: boolean;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  isAdmin: false,
  refreshUser: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const stored = getStoredUser();
      const token = getToken();
      if (stored && token) {
        // Optimistically show stored user immediately (no flash)
        setUser(stored);
        syncCookies(stored, token);
        // Verify token is still valid with the server
        const fresh = await fetchCurrentUser().catch(() => null);
        if (fresh) {
          setUser(fresh);
          const t = getToken();
          if (t) syncCookies(fresh, t);
        } else {
          // Token expired and refresh failed
          setUser(null);
          clearTokens();
          clearCookies();
        }
      }
      setLoading(false);
    };
    init();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const u = await apiLogin(username, password);
    setUser(u);
    // syncCookies already called inside apiLogin
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    // Hard navigation clears all React state and ensures the middleware
    // sees no access_token cookie on the next request
    window.location.href = '/login';
  }, []);

  const refreshUser = useCallback(async () => {
    const fresh = await fetchCurrentUser().catch(() => null);
    if (fresh) setUser(fresh);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isAdmin: user?.role === 'admin',
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
