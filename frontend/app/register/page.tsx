'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, UserPlus, CheckCircle2, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';
import { register } from '@/lib/auth';

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'One uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
  { label: 'One lowercase letter', test: (p: string) => /[a-z]/.test(p) },
  { label: 'One digit', test: (p: string) => /\d/.test(p) },
  { label: 'One special character (!@#$%^&*...)', test: (p: string) => /[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]/.test(p) },
];

export default function RegisterPage() {
  const router = useRouter();

  const [form, setForm] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<string[]>([]);
  const [passwordFocused, setPasswordFocused] = useState(false);

  const passwordRules = PASSWORD_RULES.map((r) => ({
    ...r,
    passed: r.test(form.password),
  }));
  const allRulesPassed = passwordRules.every((r) => r.passed);
  const passwordsMatch = form.password === form.confirmPassword && form.confirmPassword !== '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldErrors([]);

    if (!allRulesPassed) {
      setError('Password does not meet all requirements.');
      return;
    }
    if (!passwordsMatch) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const result = await register({
        username: form.username.trim().toLowerCase(),
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim() || undefined,
      });

      // Redirect to OTP verification, passing email via query param
      router.push(`/verify-otp?email=${encodeURIComponent(form.email.trim())}&username=${encodeURIComponent(form.username)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Registration failed.';
      if (msg.includes('\n')) {
        setFieldErrors(msg.split('\n'));
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const setField = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [field]: e.target.value }));
    setError('');
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background orbs */}
      <div style={{
        position: 'fixed', top: '-200px', right: '-200px', width: '600px', height: '600px',
        background: 'var(--color-secondary)', borderRadius: '50%', opacity: 0.04,
        filter: 'blur(80px)', pointerEvents: 'none',
      }} />
      <div style={{
        position: 'fixed', bottom: '-150px', left: '-150px', width: '500px', height: '500px',
        background: 'var(--color-primary)', borderRadius: '50%', opacity: 0.04,
        filter: 'blur(80px)', pointerEvents: 'none',
      }} />

      <div className="animate-scale-in" style={{
        width: '100%',
        maxWidth: '480px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '20px',
        padding: '36px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
      }}>
        {/* Back to login */}
        <Link href="/login" style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          fontSize: '13px', color: 'var(--color-text-muted)',
          marginBottom: '24px', textDecoration: 'none',
          transition: 'color 150ms',
        }}>
          <ArrowLeft size={14} /> Back to Login
        </Link>

        {/* Header */}
        <div style={{ marginBottom: '28px' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'linear-gradient(135deg, var(--color-primary), var(--color-secondary))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '16px',
            boxShadow: '0 0 24px rgba(0,212,255,0.3)',
          }}>
            <UserPlus size={22} color="#080C14" />
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--color-text-primary)', margin: 0 }}>
            Create Account
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '6px' }}>
            You'll receive a 6-digit OTP to verify your email.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Global error */}
          {(error || fieldErrors.length > 0) && (
            <div className="animate-slide-down" style={{
              padding: '12px 14px', marginBottom: '16px',
              background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.3)',
              borderRadius: '10px', display: 'flex', gap: '10px', alignItems: 'flex-start',
            }}>
              <AlertCircle size={16} color="var(--color-danger)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                {error && <div style={{ fontSize: '13px', color: 'var(--color-danger)' }}>{error}</div>}
                {fieldErrors.map((e, i) => (
                  <div key={i} style={{ fontSize: '12px', color: 'var(--color-danger)', marginTop: '2px' }}>• {e}</div>
                ))}
              </div>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Full Name (optional)</label>
            <input
              className="input"
              type="text"
              placeholder="John Doe"
              value={form.full_name}
              onChange={setField('full_name')}
              autoComplete="name"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Username *</label>
            <input
              className="input"
              type="text"
              placeholder="john_doe"
              value={form.username}
              onChange={setField('username')}
              required
              autoComplete="username"
              pattern="^[a-zA-Z0-9_.-]+$"
              title="Letters, numbers, underscore, hyphen, dot"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email Address *</label>
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={setField('email')}
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password *</label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                placeholder="Create a strong password"
                value={form.password}
                onChange={setField('password')}
                onFocus={() => setPasswordFocused(true)}
                onBlur={() => setPasswordFocused(false)}
                required
                autoComplete="new-password"
                style={{ paddingRight: '44px' }}
              />
              <button type="button" onClick={() => setShowPassword((v) => !v)}
                style={{
                  position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-text-muted)', padding: '4px',
                }}>
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Password strength checklist */}
            {(passwordFocused || form.password) && (
              <div style={{
                marginTop: '8px', padding: '10px 12px',
                background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)',
                borderRadius: '8px',
              }}>
                {passwordRules.map((rule, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '7px',
                    fontSize: '11px', marginBottom: i < passwordRules.length - 1 ? '4px' : 0,
                    color: rule.passed ? 'var(--color-success)' : 'var(--color-text-muted)',
                    transition: 'color 200ms',
                  }}>
                    <CheckCircle2 size={11} strokeWidth={rule.passed ? 2.5 : 1.5}
                      color={rule.passed ? 'var(--color-success)' : 'var(--color-text-muted)'} />
                    {rule.label}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label className="form-label">Confirm Password *</label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showConfirm ? 'text' : 'password'}
                placeholder="Repeat your password"
                value={form.confirmPassword}
                onChange={setField('confirmPassword')}
                required
                autoComplete="new-password"
                style={{
                  paddingRight: '44px',
                  borderColor: form.confirmPassword
                    ? passwordsMatch ? 'var(--color-success)' : 'var(--color-danger)'
                    : undefined,
                }}
              />
              <button type="button" onClick={() => setShowConfirm((v) => !v)}
                style={{
                  position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-text-muted)', padding: '4px',
                }}>
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {form.confirmPassword && !passwordsMatch && (
              <div style={{ fontSize: '11px', color: 'var(--color-danger)', marginTop: '4px' }}>
                Passwords do not match
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', height: '48px', fontSize: '15px', fontWeight: 700 }}
          >
            {loading ? <><Loader2 size={18} className="animate-spin" /> Creating account...</> : <><UserPlus size={18} /> Create Account</>}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'var(--color-text-muted)' }}>
          Already have an account?{' '}
          <Link href="/login" style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
            Sign in
          </Link>
        </div>

        {/* Compliance notice */}
        <div style={{
          marginTop: '20px', padding: '10px 14px',
          background: 'rgba(255,184,0,0.06)', border: '1px solid rgba(255,184,0,0.15)',
          borderRadius: '8px', fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: 1.5,
        }}>
          🏦 Access to this system is restricted to authorised personnel only.
          Unauthorised use is prohibited and subject to applicable laws.
        </div>
      </div>
    </div>
  );
}
