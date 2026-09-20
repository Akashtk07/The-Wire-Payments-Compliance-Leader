'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Zap, Eye, EyeOff, ShieldCheck, Lock, User, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/AuthProvider';
import { clearCookies, clearTokens } from '@/lib/auth';

function LoginContent() {
  const { login: authLogin, user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect') ?? '/';
  const verified = searchParams.get('verified') === '1';
  const unauthorized = searchParams.get('unauthorized') === '1';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [unverifiedEmail, setUnverifiedEmail] = useState('');

  useEffect(() => {
    // If already logged in, redirect immediately
    if (!loading && user) {
      window.location.href = redirect;
    }
  }, [user, loading, redirect]);

  useEffect(() => {
    // On mount, if there's NO valid stored user, clear any stale cookies
    // so the middleware doesn't get confused by expired tokens
    if (!loading && !user) {
      clearCookies();
      clearTokens();
    }
  }, [loading, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please enter your username and password.');
      return;
    }
    setError('');
    setUnverifiedEmail('');
    setSubmitting(true);
    try {
      await authLogin(username.trim(), password);
      // Hard navigation ensures the new SameSite=Lax cookie is included
      // in the next request so the middleware doesn't loop back to login
      window.location.href = redirect;
    } catch (err: any) {
      if (err?.code === 'EMAIL_NOT_VERIFIED') {
        setUnverifiedEmail(err.email ?? '');
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : 'Login failed.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return null;

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--color-bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px', position: 'relative', overflow: 'hidden',
    }}>
      {/* Background orbs */}
      <div className="bg-orb bg-orb-1" aria-hidden="true" />
      <div className="bg-orb bg-orb-2" aria-hidden="true" />

      {/* Login Card */}
      <div className="animate-scale-in" style={{
        width: '100%', maxWidth: '420px',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: '20px', padding: '40px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.5)',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '16px',
            background: 'linear-gradient(135deg, var(--color-primary), var(--color-secondary))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 0 40px rgba(0,212,255,0.3)',
            animation: 'pulse-glow 3s ease-in-out infinite',
          }}>
            <Zap size={28} color="#080C14" strokeWidth={2.5} />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>
            Compliance Leader
          </div>
          <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            ISO 20022 · SWIFT CBPR+ Enterprise Platform
          </div>
        </div>

        {/* Verified success banner */}
        {verified && (
          <div className="animate-slide-down" style={{
            display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px',
            background: 'rgba(0,229,160,0.08)', border: '1px solid rgba(0,229,160,0.3)',
            borderRadius: '10px', marginBottom: '16px', fontSize: '13px', color: 'var(--color-success)',
          }}>
            <CheckCircle2 size={15} />
            Email verified! You can now sign in.
          </div>
        )}

        {/* Unauthorized banner */}
        {unauthorized && (
          <div className="animate-slide-down" style={{
            display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px',
            background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.3)',
            borderRadius: '10px', marginBottom: '16px', fontSize: '13px', color: 'var(--color-danger)',
          }}>
            <AlertCircle size={15} />
            Administrator access required for that page.
          </div>
        )}

        {/* Security badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px',
          background: 'rgba(0,229,160,0.06)', border: '1px solid rgba(0,229,160,0.2)',
          borderRadius: '10px', marginBottom: '24px',
        }}>
          <ShieldCheck size={14} color="var(--color-success)" />
          <span style={{ fontSize: '12px', color: 'var(--color-success)', fontWeight: 600 }}>
            Secure · Authenticated Access Only
          </span>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Username */}
          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label className="form-label" htmlFor="login-username">Username or Email</label>
            <div style={{ position: 'relative' }}>
              <User size={16} style={{
                position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)', pointerEvents: 'none',
              }} />
              <input
                id="login-username"
                type="text"
                className="input"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setError(''); }}
                autoComplete="username"
                disabled={submitting}
                style={{ paddingLeft: '38px' }}
              />
            </div>
          </div>

          {/* Password */}
          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label className="form-label" htmlFor="login-password">Password</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{
                position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)', pointerEvents: 'none',
              }} />
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                className="input"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(''); }}
                autoComplete="current-password"
                disabled={submitting}
                style={{ paddingLeft: '38px', paddingRight: '44px' }}
              />
              <button type="button" onClick={() => setShowPassword((v) => !v)}
                style={{
                  position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-text-muted)', padding: '4px', display: 'flex',
                }}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="animate-slide-down" style={{
              padding: '10px 14px', background: 'rgba(255,68,68,0.08)',
              border: '1px solid rgba(255,68,68,0.3)', borderRadius: '8px',
              fontSize: '13px', color: 'var(--color-danger)', marginBottom: '16px',
              display: 'flex', flexDirection: 'column', gap: '6px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <AlertCircle size={14} /> {error}
              </div>
              {unverifiedEmail && (
                <Link
                  href={`/verify-otp?email=${encodeURIComponent(unverifiedEmail)}`}
                  style={{ fontSize: '12px', color: 'var(--color-primary)', fontWeight: 600 }}
                >
                  → Verify your email now
                </Link>
              )}
            </div>
          )}

          {/* Submit */}
          <button
            id="login-btn"
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
            style={{ width: '100%', justifyContent: 'center', height: '48px', fontSize: '15px', fontWeight: 700 }}
          >
            {submitting
              ? <><Loader2 size={18} className="animate-spin" /> Authenticating...</>
              : 'Sign In →'
            }
          </button>
        </form>

        {/* Register link */}
        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'var(--color-text-muted)' }}>
          Don&apos;t have an account?{' '}
          <Link href="/register" style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
            Register
          </Link>
        </div>

        {/* Compliance footer */}
        <div style={{
          marginTop: '20px', padding: '10px 14px',
          background: 'rgba(255,184,0,0.05)', border: '1px solid rgba(255,184,0,0.1)',
          borderRadius: '8px', fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: 1.5,
          textAlign: 'center',
        }}>
          🏦 Authorised access only. All sessions are monitored and audited.
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
