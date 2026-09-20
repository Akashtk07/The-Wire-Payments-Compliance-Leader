'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ShieldCheck, RefreshCw, Loader2, CheckCircle2, AlertCircle, ArrowLeft } from 'lucide-react';
import { verifyOtp, resendOtp } from '@/lib/auth';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN = 60; // seconds before next resend allowed

function OTPContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get('email') ?? '';
  const username = searchParams.get('username') ?? '';

  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [attemptInfo, setAttemptInfo] = useState('');
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0); // seconds
  const inputRefs = useRef<(HTMLInputElement | null)[]>(Array(OTP_LENGTH).fill(null));
  const cooldownTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  useEffect(() => {
    return () => { if (cooldownTimer.current) clearInterval(cooldownTimer.current); };
  }, []);

  const startCooldown = useCallback(() => {
    setCooldown(RESEND_COOLDOWN);
    cooldownTimer.current = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) { clearInterval(cooldownTimer.current!); return 0; }
        return c - 1;
      });
    }, 1000);
  }, []);

  const handleOtpChange = (index: number, value: string) => {
    setError('');
    const digit = value.replace(/\D/g, '').slice(-1);
    const updated = [...otp];
    updated[index] = digit;
    setOtp(updated);
    if (digit && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
    // Auto-submit when all filled
    if (digit && updated.filter(Boolean).length === OTP_LENGTH) {
      handleVerify(updated.join(''));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (!otp[index] && index > 0) {
        const updated = [...otp];
        updated[index - 1] = '';
        setOtp(updated);
        inputRefs.current[index - 1]?.focus();
      }
    }
    if (e.key === 'ArrowLeft' && index > 0) inputRefs.current[index - 1]?.focus();
    if (e.key === 'ArrowRight' && index < OTP_LENGTH - 1) inputRefs.current[index + 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    const updated = Array(OTP_LENGTH).fill('');
    pasted.split('').forEach((c, i) => { if (i < OTP_LENGTH) updated[i] = c; });
    setOtp(updated);
    // Focus last filled or last
    const lastIdx = Math.min(pasted.length, OTP_LENGTH - 1);
    inputRefs.current[lastIdx]?.focus();
    if (pasted.length === OTP_LENGTH) {
      handleVerify(pasted);
    }
  };

  const handleVerify = useCallback(async (code: string) => {
    if (code.length < OTP_LENGTH || loading) return;
    setLoading(true);
    setError('');
    try {
      const result = await verifyOtp(email, code);
      setSuccess(result.message);
      setTimeout(() => router.push('/login?verified=1'), 2000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Verification failed.';
      setError(msg);
      // Extract attempts remaining if present
      const match = msg.match(/(\d+) attempt/);
      if (match) setAttemptInfo(`${match[1]} attempt(s) remaining`);
      // Clear OTP for re-entry
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }, [email, loading, router]);

  const handleManualSubmit = () => {
    const code = otp.join('');
    if (code.length === OTP_LENGTH) handleVerify(code);
  };

  const handleResend = async () => {
    if (cooldown > 0 || resending) return;
    setResending(true);
    setError('');
    try {
      const result = await resendOtp(email);
      startCooldown();
      setAttemptInfo(`New code sent. ${result.resends_remaining} resend(s) remaining.`);
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code.');
    } finally {
      setResending(false);
    }
  };

  if (!email) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)' }}>
        Invalid verification link.{' '}
        <Link href="/register">Register again</Link>
      </div>
    );
  }

  const maskedEmail = email.replace(/(.{2})(.*)(@.*)/, '$1***$3');
  const filledCount = otp.filter(Boolean).length;

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--color-bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px', position: 'relative', overflow: 'hidden',
    }}>
      {/* Background orbs */}
      <div style={{
        position: 'fixed', top: '-200px', right: '-200px', width: '600px', height: '600px',
        background: 'var(--color-primary)', borderRadius: '50%', opacity: 0.04,
        filter: 'blur(80px)', pointerEvents: 'none',
      }} />

      <div className="animate-scale-in" style={{
        width: '100%', maxWidth: '420px',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: '20px', padding: '36px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
      }}>
        <Link href="/register" style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '24px', textDecoration: 'none',
        }}>
          <ArrowLeft size={14} /> Back to Registration
        </Link>

        {/* Icon + heading */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '16px',
            background: success
              ? 'linear-gradient(135deg, var(--color-success), #00B880)'
              : 'linear-gradient(135deg, var(--color-primary), var(--color-secondary))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: success
              ? '0 0 32px rgba(0,229,160,0.4)'
              : '0 0 32px rgba(0,212,255,0.3)',
            transition: 'all 300ms ease',
            animation: 'pulse-glow 2.5s ease-in-out infinite',
          }}>
            {success
              ? <CheckCircle2 size={28} color="#080C14" />
              : <ShieldCheck size={28} color="#080C14" />
            }
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--color-text-primary)', margin: 0 }}>
            {success ? 'Verified!' : 'Email Verification'}
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '8px', lineHeight: 1.5 }}>
            {success
              ? 'Your account is activated. Redirecting to login...'
              : <>We sent a 6-digit code to <strong style={{ color: 'var(--color-primary)' }}>{maskedEmail}</strong>.<br />Enter it below to activate your account.</>
            }
          </p>
        </div>

        {/* Success state */}
        {success && (
          <div style={{
            padding: '16px', background: 'rgba(0,229,160,0.08)', border: '1px solid rgba(0,229,160,0.3)',
            borderRadius: '12px', textAlign: 'center', fontSize: '14px', color: 'var(--color-success)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
          }}>
            <CheckCircle2 size={18} /> {success}
          </div>
        )}

        {/* OTP input */}
        {!success && (
          <>
            {error && (
              <div className="animate-slide-down" style={{
                padding: '10px 12px', marginBottom: '16px',
                background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.3)',
                borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center',
              }}>
                <AlertCircle size={14} color="var(--color-danger)" />
                <div style={{ fontSize: '13px', color: 'var(--color-danger)' }}>{error}</div>
              </div>
            )}

            {attemptInfo && !error && (
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', textAlign: 'center', marginBottom: '12px' }}>
                {attemptInfo}
              </div>
            )}

            {/* 6-digit OTP boxes */}
            <div style={{
              display: 'flex', gap: '10px', justifyContent: 'center', marginBottom: '20px',
            }}>
              {otp.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => { inputRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  onPaste={i === 0 ? handlePaste : undefined}
                  disabled={loading}
                  aria-label={`OTP digit ${i + 1}`}
                  style={{
                    width: '52px', height: '60px', borderRadius: '12px', textAlign: 'center',
                    fontSize: '24px', fontWeight: 800, fontFamily: 'var(--font-mono)',
                    background: digit ? 'rgba(0,212,255,0.08)' : 'rgba(255,255,255,0.04)',
                    border: `2px solid ${digit ? 'rgba(0,212,255,0.5)' : 'var(--color-border)'}`,
                    color: 'var(--color-primary)',
                    outline: 'none',
                    transition: 'all 150ms ease',
                    cursor: 'text',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = digit ? 'rgba(0,212,255,0.5)' : 'var(--color-border)')}
                />
              ))}
            </div>

            {/* Progress bar */}
            <div style={{ marginBottom: '16px' }}>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${(filledCount / OTP_LENGTH) * 100}%` }} />
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', textAlign: 'center', marginTop: '6px' }}>
                {filledCount}/{OTP_LENGTH} digits entered
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleManualSubmit}
              disabled={loading || filledCount < OTP_LENGTH}
              style={{ width: '100%', justifyContent: 'center', height: '48px', fontSize: '15px', fontWeight: 700, marginBottom: '12px' }}
            >
              {loading ? <><Loader2 size={18} className="animate-spin" /> Verifying...</> : <><ShieldCheck size={18} /> Verify Email</>}
            </button>

            {/* Resend */}
            <div style={{ textAlign: 'center' }}>
              <button
                onClick={handleResend}
                disabled={cooldown > 0 || resending}
                style={{
                  background: 'none', border: 'none', cursor: cooldown > 0 ? 'not-allowed' : 'pointer',
                  color: cooldown > 0 ? 'var(--color-text-muted)' : 'var(--color-primary)',
                  fontSize: '13px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '6px',
                }}
              >
                {resending
                  ? <><Loader2 size={13} className="animate-spin" /> Sending...</>
                  : cooldown > 0
                    ? `Resend in ${cooldown}s`
                    : <><RefreshCw size={13} /> Resend Code</>
                }
              </button>
            </div>

            {/* Security tip */}
            <div style={{
              marginTop: '20px', padding: '10px 14px',
              background: 'rgba(255,184,0,0.06)', border: '1px solid rgba(255,184,0,0.15)',
              borderRadius: '8px', fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: 1.5,
            }}>
              ⚠️ Never share this code with anyone. It expires in 10 minutes.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyOtpPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: '100vh', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 size={32} className="animate-spin" color="var(--color-primary)" />
      </div>
    }>
      <OTPContent />
    </Suspense>
  );
}
