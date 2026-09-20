'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  ArrowLeftRight,
  BookOpen,
  FileText,
  ShieldCheck,
  Zap,
  Activity,
  Circle,
  Settings,
  ArrowRightLeft,
  Lightbulb,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import LLMConfigPanel from '@/components/LLMConfigPanel';
import { useAuth } from '@/lib/AuthProvider';

const navItems = [
  {
    href: '/',
    label: 'Dashboard',
    icon: LayoutDashboard,
    badge: '#00D4FF',
    desc: 'Home',
  },
  {
    href: '/translate',
    label: 'MT → MX Engine',
    icon: ArrowLeftRight,
    badge: '#00D4FF',
    desc: 'SWIFT MT to ISO 20022',
  },
  {
    href: '/mx-translate',
    label: 'MX → MT Engine',
    icon: ArrowRightLeft,
    badge: '#FF6B35',
    desc: 'ISO 20022 → SWIFT Reverse',
  },
  {
    href: '/learn',
    label: 'Knowledge',
    icon: BookOpen,
    badge: '#7B2FBE',
    desc: 'Interactive Learning',
  },
  {
    href: '/prompt-engineering',
    label: 'Prompt Lab',
    icon: Lightbulb,
    badge: '#A855F7',
    desc: 'Prompt Engineering',
  },
  {
    href: '/documents',
    label: 'Documents',
    icon: FileText,
    badge: '#FFB800',
    desc: 'Document Intelligence',
  },
  {
    href: '/audit',
    label: 'Audit & Telemetry',
    icon: ShieldCheck,
    badge: '#00E5A0',
    desc: 'Monitoring Framework',
  },
];

type HealthStatus = 'nominal' | 'degraded' | 'checking';

export default function Sidebar() {
  const pathname = usePathname();
  const { isAdmin } = useAuth();
  const [health, setHealth] = useState<HealthStatus>('checking');
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/health`,
          { signal: AbortSignal.timeout(3000) }
        );
        if (res.ok) {
          setHealth('nominal');
        } else {
          setHealth('degraded');
        }
      } catch {
        setHealth('degraded');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setUptime((u) => u + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <nav className="sidebar animate-slide-left" role="navigation" aria-label="Main navigation">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon" aria-hidden="true">
          <Zap size={18} color="#080C14" strokeWidth={2.5} />
        </div>
        <div className="sidebar-logo-text">
          <span className="sidebar-logo-title">Compliance Leader</span>
          <span className="sidebar-logo-subtitle">ISO 20022 Platform</span>
        </div>
      </div>

      {/* Navigation */}
      <div className="sidebar-nav">
        <div className="sidebar-section-label">Modules</div>

        {navItems.map((item, index) => {
          const Icon = item.icon;
          const isActive =
            item.href === '/'
              ? pathname === '/'
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-item ${isActive ? 'active' : ''} animate-fade-in`}
              style={{ animationDelay: `${index * 60}ms` }}
              aria-current={isActive ? 'page' : undefined}
              title={item.desc}
            >
              <span className="sidebar-item-icon">
                <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
              </span>
              <span style={{ flex: 1 }}>{item.label}</span>
              <Circle
                size={7}
                fill={item.badge}
                color={item.badge}
                className="sidebar-item-badge"
                style={{ opacity: isActive ? 1 : 0.4 }}
              />
            </Link>
          );
        })}

        {/* Admin Console — only for admins */}
        {isAdmin && (
          <>
            <div className="sidebar-section-label" style={{ marginTop: '12px' }}>Admin</div>
            <Link
              href="/admin"
              className={`sidebar-item ${pathname.startsWith('/admin') ? 'active' : ''} animate-fade-in`}
              title="Admin Console"
            >
              <span className="sidebar-item-icon">
                <Settings size={18} strokeWidth={pathname.startsWith('/admin') ? 2.2 : 1.8} />
              </span>
              <span style={{ flex: 1 }}>Admin Console</span>
              <Circle size={7} fill="#FFB800" color="#FFB800" className="sidebar-item-badge"
                style={{ opacity: pathname.startsWith('/admin') ? 1 : 0.4 }}
              />
            </Link>
          </>
        )}

        <div className="sidebar-section-label" style={{ marginTop: '16px' }}>
          System
        </div>

        <div
          style={{
            padding: '10px 12px',
            borderRadius: '10px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '8px',
            }}
          >
            <Activity size={14} color="var(--color-text-muted)" />
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Uptime
            </span>
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '13px',
              color: 'var(--color-primary)',
              letterSpacing: '0.05em',
            }}
          >
            {formatUptime(uptime)}
          </div>
        </div>

        {/* LLM Config Panel trigger */}
        <div style={{ marginTop: '10px' }}>
          <LLMConfigPanel />
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-health">
          <div
            className={`connection-dot ${health === 'nominal' ? 'connected' : 'disconnected'}`}
          />
          <span>
            {health === 'checking'
              ? 'Checking...'
              : health === 'nominal'
              ? 'System Nominal'
              : 'API Degraded'}
          </span>
        </div>
        <div className="sidebar-version">v1.1.0 · CBPR+ R2025</div>
      </div>
    </nav>
  );
}
