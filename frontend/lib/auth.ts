'use client';

/**
 * Auth helpers — token storage, API call wrappers, user state.
 * Industry-grade: auto-refresh, cookie sync, secure logout.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role: 'admin' | 'analyst';
  must_change_password?: boolean;
  is_verified?: boolean;
}

// ---------------------------------------------------------------------------
// Token management (localStorage + cookies for middleware)
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

export function clearTokens(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('current_user');
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('current_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser): void {
  localStorage.setItem('current_user', JSON.stringify(user));
}

/**
 * Sync tokens into HTTP-only-like cookies so the Next.js middleware (edge runtime)
 * can read them. SameSite=Strict prevents CSRF.
 */
export function syncCookies(user: AuthUser, token: string): void {
  const secure = window.location.protocol === 'https:';
  // SameSite=Lax (not Strict) so cookies are sent on top-level navigations
  // e.g. router.replace('/learn') — Strict blocks this, causing redirect loop
  const baseOpts = `path=/;SameSite=Lax${secure ? ';Secure' : ''}`;
  const days7 = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toUTCString();
  document.cookie = `access_token=${token};${baseOpts};expires=${days7}`;
  document.cookie = `user_role=${user.role};${baseOpts};expires=${days7}`;
  document.cookie = `username=${user.username};${baseOpts};expires=${days7}`;
}

export function clearCookies(): void {
  const past = 'Thu, 01 Jan 1970 00:00:00 UTC';
  document.cookie = `access_token=;path=/;expires=${past}`;
  document.cookie = `user_role=;path=/;expires=${past}`;
  document.cookie = `username=;path=/;expires=${past}`;
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export async function register(payload: RegisterPayload): Promise<{
  message: string;
  email: string;
  expires_in_minutes: number;
}> {
  const res = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Password policy violations
    if (data?.detail?.violations) {
      throw new Error(data.detail.violations.join('\n'));
    }
    throw new Error(data?.detail?.message ?? data?.detail ?? 'Registration failed.');
  }
  return data;
}

// ---------------------------------------------------------------------------
// OTP Verification
// ---------------------------------------------------------------------------

export async function verifyOtp(email: string, otp: string): Promise<{ message: string; username: string }> {
  const res = await fetch(`${API_URL}/api/v1/auth/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail?.message ?? data?.detail ?? 'OTP verification failed.');
  }
  return data;
}

export async function resendOtp(email: string): Promise<{ message: string; resends_remaining: number }> {
  const res = await fetch(`${API_URL}/api/v1/auth/resend-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail?.message ?? data?.detail ?? 'Failed to resend OTP.');
  }
  return data;
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Locked account — include retry info
    if (res.status === 423) {
      const secs = data?.detail?.retry_after_seconds ?? 1800;
      const mins = Math.ceil(secs / 60);
      throw new Error(`Account locked. Try again in ${mins} minute(s).`);
    }
    // Email not verified — include email so UI can redirect to OTP page
    if (data?.detail?.error === 'EMAIL_NOT_VERIFIED') {
      const err: any = new Error(data.detail.message ?? 'Email not verified.');
      err.email = data.detail.email;
      err.code = 'EMAIL_NOT_VERIFIED';
      throw err;
    }
    throw new Error(data?.detail?.message ?? data?.detail ?? 'Login failed.');
  }

  setTokens(data.access_token, data.refresh_token);
  setStoredUser(data.user);
  syncCookies(data.user, data.access_token);
  return data.user;
}

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

export async function logout(): Promise<void> {
  const token = getToken();
  if (token) {
    await fetch(`${API_URL}/api/v1/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  clearTokens();
  clearCookies();
}

// ---------------------------------------------------------------------------
// Fetch current user profile
// ---------------------------------------------------------------------------

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return null;

  const res = await fetch(`${API_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    // Try refresh
    const refreshed = await tryRefresh();
    if (!refreshed) {
      clearTokens();
      clearCookies();
      return null;
    }
    // Retry with new token
    const res2 = await fetch(`${API_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res2.ok) { clearTokens(); clearCookies(); return null; }
    const user: AuthUser = await res2.json();
    setStoredUser(user);
    syncCookies(user, getToken()!);
    return user;
  }

  const user: AuthUser = await res.json();
  setStoredUser(user);
  syncCookies(user, token);
  return user;
}

// ---------------------------------------------------------------------------
// Authenticated fetch wrapper (with auto-refresh)
// ---------------------------------------------------------------------------

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getToken()}`;
      return fetch(url, { ...options, headers });
    }
    clearTokens();
    clearCookies();
    if (typeof window !== 'undefined') window.location.href = '/login';
  }

  return res;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    const existingRefresh = localStorage.getItem('refresh_token') ?? '';
    setTokens(data.access_token, existingRefresh);
    // Re-sync cookie
    const user = getStoredUser();
    if (user) syncCookies(user, data.access_token);
    return true;
  } catch {
    return false;
  }
}
