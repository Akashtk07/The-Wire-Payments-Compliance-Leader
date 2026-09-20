'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import TopBar from '@/components/TopBar';
import { useAuth } from '@/lib/AuthProvider';

// Pages that render WITHOUT the app shell (sidebar + topbar) and WITHOUT auth
const AUTH_PATHS = ['/login', '/register', '/verify-otp'];

export default function ConditionalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();

  const isAuthPage = AUTH_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + '/')
  );

  // ── Client-side auth guard ──────────────────────────────────────────────
  // Runs AFTER the AuthProvider resolves loading (cookie/token check).
  // Prevents any protected page content from rendering for unauthenticated users.
  useEffect(() => {
    if (loading) return;           // wait until auth state is resolved
    if (isAuthPage) return;        // login/register pages are always accessible
    if (!user) {
      // No valid session — redirect to login immediately
      const redirectTo = pathname !== '/' ? `?redirect=${encodeURIComponent(pathname)}` : '';
      router.replace(`/login${redirectTo}`);
    }
  }, [loading, user, isAuthPage, pathname, router]);

  // Auth pages: render fullscreen with no sidebar/topbar, no auth check needed
  if (isAuthPage) {
    return <>{children}</>;
  }

  // ── Loading state: show blank screen while auth resolves ────────────────
  // Critical: NEVER render protected content while loading is true.
  if (loading) {
    return (
      <div style={{
        position: 'fixed', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-bg, #080C14)',
        zIndex: 9999,
      }}>
        <div style={{ textAlign: 'center' }}>
          {/* Animated logo spinner */}
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            border: '3px solid rgba(0,212,255,0.15)',
            borderTop: '3px solid #00D4FF',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 16px',
          }} />
          <p style={{
            color: 'rgba(255,255,255,0.4)', fontSize: 13,
            fontFamily: 'var(--font-inter, Inter, sans-serif)',
            letterSpacing: '0.08em',
          }}>
            Verifying session…
          </p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // ── Unauthenticated: render nothing while redirect fires ────────────────
  if (!user) {
    return null;
  }

  // ── Authenticated: render full app shell ────────────────────────────────
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <TopBar />
        <div style={{ position: 'relative', zIndex: 1 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
