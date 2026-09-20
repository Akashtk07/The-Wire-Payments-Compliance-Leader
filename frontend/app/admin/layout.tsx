'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/AuthProvider';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Settings, Users, FileText, BookOpen, LayoutDashboard } from 'lucide-react';

const adminNav = [
  { href: '/admin', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/admin/users', label: 'User Management', icon: Users },
  { href: '/admin/documents', label: 'Document Control', icon: FileText },
  { href: '/admin/guidelines', label: 'Guideline Registry', icon: BookOpen },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isAdmin, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !isAdmin) {
      router.replace('/');
    }
  }, [isAdmin, loading, router]);

  if (loading || !isAdmin) return null;

  return (
    <main className="page-container">
      {/* Admin header */}
      <div className="module-header animate-fade-in" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px', height: '32px', borderRadius: '8px',
            background: 'linear-gradient(135deg, #FFB800, #FF6B35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Settings size={16} color="#080C14" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: 'var(--color-text-primary)' }}>
              Admin Console
            </h1>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              Full platform control — administrator access only
            </p>
          </div>
        </div>
      </div>

      {/* Admin sub-navigation */}
      <div style={{
        display: 'flex', gap: '4px', marginBottom: '20px',
        background: 'var(--color-panel)', border: '1px solid var(--color-border)',
        borderRadius: '12px', padding: '6px',
      }}>
        {adminNav.map(({ href, label, icon: Icon, exact }) => {
          const isActive = exact ? pathname === href : pathname.startsWith(href) && pathname !== '/admin';
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '7px 14px', borderRadius: '8px', fontSize: '13px', fontWeight: 600,
                textDecoration: 'none', transition: 'all 150ms ease',
                background: active ? 'rgba(255,184,0,0.1)' : 'transparent',
                border: `1px solid ${active ? 'rgba(255,184,0,0.3)' : 'transparent'}`,
                color: active ? '#FFB800' : 'var(--color-text-secondary)',
              }}
            >
              <Icon size={14} />
              {label}
            </Link>
          );
        })}
      </div>

      {children}
    </main>
  );
}
