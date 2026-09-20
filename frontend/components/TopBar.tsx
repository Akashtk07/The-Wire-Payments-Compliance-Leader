'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ChevronRight, LogOut, User, Shield } from 'lucide-react';
import { useAuth } from '@/lib/AuthProvider';

const routeLabels: Record<string, string> = {
  '/': 'Command Center',
  '/translate': 'TX Engine',
  '/learn': 'Knowledge',
  '/documents': 'Documents',
  '/audit': 'Audit & Telemetry',
  '/admin': 'Admin Console',
  '/admin/users': 'User Management',
  '/admin/documents': 'Document Control',
  '/admin/guidelines': 'Guideline Registry',
};

export default function TopBar() {
  const pathname = usePathname();
  const { user, logout, isAdmin } = useAuth();
  const [time, setTime] = useState('');
  const [date, setDate] = useState('');
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
      setDate(
        now.toLocaleDateString('en-US', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const currentLabel = routeLabels[pathname] ?? 'Module';

  return (
    <header className="topbar" role="banner">
      {/* Breadcrumb */}
      <div className="topbar-breadcrumb">
        <span>The Compliance Leader</span>
        <ChevronRight size={14} color="var(--color-text-muted)" />
        <span className="topbar-breadcrumb-active">{currentLabel}</span>
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <span
          style={{
            fontSize: '12px',
            color: 'var(--color-text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {date}
        </span>
        <div className="topbar-clock" aria-live="polite" aria-label="Current time">
          {time || '00:00:00'}
        </div>

        {/* User menu */}
        {user && (
          <div style={{ position: 'relative' }}>
            <button
              id="user-menu-btn"
              onClick={() => setShowUserMenu((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid var(--color-border)',
                background: 'rgba(255,255,255,0.04)',
                cursor: 'pointer',
                transition: 'all 150ms ease',
              }}
              onMouseOver={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)'; }}
              onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)'; }}
            >
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  background: isAdmin
                    ? 'linear-gradient(135deg, #FFB800, #FF6B35)'
                    : 'linear-gradient(135deg, var(--color-primary), var(--color-secondary))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isAdmin ? <Shield size={12} color="#080C14" /> : <User size={12} color="#080C14" />}
              </div>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-primary)', lineHeight: 1 }}>
                  {user.username}
                </div>
                <div style={{ fontSize: '10px', color: isAdmin ? '#FFB800' : 'var(--color-primary)', marginTop: '1px', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                  {user.role}
                </div>
              </div>
            </button>

            {showUserMenu && (
              <div
                className="animate-scale-in"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  right: 0,
                  background: 'var(--color-panel)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '12px',
                  padding: '8px',
                  minWidth: '180px',
                  boxShadow: '0 16px 40px rgba(0,0,0,0.4)',
                  zIndex: 100,
                }}
                onMouseLeave={() => setShowUserMenu(false)}
              >
                <div
                  style={{
                    padding: '8px 10px',
                    borderBottom: '1px solid var(--color-border)',
                    marginBottom: '4px',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                    {user.username}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    {user.email}
                  </div>
                </div>
                <button
                  id="logout-btn"
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: 'var(--color-danger)',
                    fontSize: '13px',
                    fontWeight: 600,
                    transition: 'background 150ms ease',
                  }}
                  onMouseOver={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,68,68,0.08)'; }}
                  onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
