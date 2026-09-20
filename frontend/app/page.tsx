'use client';

import { useEffect, useState, useRef } from 'react';
import {
  ArrowLeftRight,
  BookOpen,
  FileText,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import TelemetryFeed from '@/components/TelemetryFeed';
import AuditTable, { AuditLogEntry } from '@/components/AuditTable';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Stats {
  translations: number;
  learnQueries: number;
  documents: number;
  auditEvents: number;
}

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
  loading: boolean;
  delay?: number;
}

function useCountUp(target: number, duration = 800) {
  const [count, setCount] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease out cubic
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(ease * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);

  return count;
}

function StatCard({ label, value, icon, color, loading, delay = 0 }: StatCardProps) {
  const count = useCountUp(value);

  return (
    <div
      className="stat-card animate-slide-up"
      style={{ '--accent-color': color, animationDelay: `${delay}ms` } as React.CSSProperties}
    >
      {loading ? (
        <>
          <div className="skeleton-box" style={{ width: '40px', height: '40px', borderRadius: '10px' }} />
          <div className="skeleton-text" style={{ width: '60%', marginTop: '12px' }} />
          <div className="skeleton-text" style={{ width: '80px', height: '28px', marginTop: '8px' }} />
        </>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: `${color}18`,
                border: `1px solid ${color}35`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: color,
              }}
            >
              {icon}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--color-text-primary)', lineHeight: 1, letterSpacing: '-0.02em' }}>
              {count.toLocaleString()}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '6px', fontWeight: 500 }}>
              {label}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({ translations: 0, learnQueries: 0, documents: 0, auditEvents: 0 });
  const [loadingStats, setLoadingStats] = useState(true);
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(true);
  const [systemHealth, setSystemHealth] = useState<'nominal' | 'degraded' | 'checking'>('checking');


  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [auditRes, docsRes, healthRes] = await Promise.allSettled([
          fetch(`${API_URL}/api/v1/audit/logs?limit=5`),
          fetch(`${API_URL}/api/v1/documents/list`),
          fetch(`${API_URL}/health`),
        ]);

        let auditData: AuditLogEntry[] = [];
        let docCount = 0;

        if (auditRes.status === 'fulfilled' && auditRes.value.ok) {
          const json = await auditRes.value.json();
          auditData = Array.isArray(json) ? json : json.entries ?? json.logs ?? [];
        }
        if (docsRes.status === 'fulfilled' && docsRes.value.ok) {
          const json = await docsRes.value.json();
          docCount = Array.isArray(json) ? json.length : json.count ?? 0;
        }
        if (healthRes.status === 'fulfilled' && healthRes.value.ok) {
          setSystemHealth('nominal');
        } else {
          setSystemHealth('degraded');
        }

        setAuditEntries(auditData.slice(0, 5));
        setStats({
          translations: auditData.filter((e) =>
            e.event_type?.includes('TRANSLATION')
          ).length,
          learnQueries: auditData.filter((e) => e.event_type?.includes('LEARN')).length,
          documents: docCount,
          auditEvents: auditData.length,
        });
      } catch {
        setSystemHealth('degraded');
      } finally {
        setLoadingStats(false);
        setLoadingAudit(false);
      }
    };
    fetchAll();
  }, []);


  return (
    <main className="page-container">
      {/* Module Header */}
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Dashboard</h1>
        <p>Platform overview — live telemetry, activity stats and recent audit events.</p>
      </div>

      {/* System Health Banner */}
      {systemHealth !== 'checking' && (
        <div
          className={`system-banner ${systemHealth} animate-slide-up`}
          role="status"
          aria-live="polite"
        >
          {systemHealth === 'nominal' ? (
            <>
              <CheckCircle2 size={16} />
              SYSTEM NOMINAL — All services operational
            </>
          ) : (
            <>
              <AlertTriangle size={16} />
              SYSTEM DEGRADED — One or more services unreachable
            </>
          )}
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-4 gap-5 mb-6">
        <StatCard
          label="Total Translations"
          value={stats.translations}
          icon={<ArrowLeftRight size={20} />}
          color="#00D4FF"
          loading={loadingStats}
          delay={0}
        />
        <StatCard
          label="Learn Queries"
          value={stats.learnQueries}
          icon={<BookOpen size={20} />}
          color="#7B2FBE"
          loading={loadingStats}
          delay={80}
        />
        <StatCard
          label="Documents Indexed"
          value={stats.documents}
          icon={<FileText size={20} />}
          color="#FFB800"
          loading={loadingStats}
          delay={160}
        />
        <StatCard
          label="Audit Events"
          value={stats.auditEvents}
          icon={<ShieldCheck size={20} />}
          color="#00E5A0"
          loading={loadingStats}
          delay={240}
        />
      </div>

      {/* Live Telemetry — full width */}
      <div className="animate-slide-up delay-200" style={{ marginBottom: '24px' }}>
        <div className="section-header">Live Telemetry</div>
        <TelemetryFeed maxEvents={10} compact />
      </div>

      {/* Recent Audit Log */}
      <div className="animate-slide-up delay-400">
        <div className="section-header" style={{ marginBottom: '16px' }}>Recent Audit Log</div>
        <AuditTable entries={auditEntries} loading={loadingAudit} />
      </div>
    </main>
  );
}
