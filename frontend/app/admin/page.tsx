'use client';

import { useEffect, useState } from 'react';
import { Users, FileText, BookOpen, AlertTriangle, CheckCircle2, Activity, HardDrive, Cpu } from 'lucide-react';
import { authFetch } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface PlatformStats {
  users: { total: number; active: number; admin: number; analyst: number };
  documents: { total_docs: number; total_chunks: number };
  guideline_versions: number;
  timestamp: string;
}

interface SystemInfo {
  platform: string;
  python_version: string;
  app_version: string;
  llm_provider: string;
  storage: { chroma_db_mb: number; uploads_mb: number; uploads_count: number };
  paths: { upload_dir: string; chroma_dir: string; audit_dir: string };
}

interface ModuleHealth {
  status: 'healthy' | 'degraded';
  detail: string;
}

interface HealthData {
  status: string;
  version: string;
  modules: Record<string, ModuleHealth>;
}

function StatCard({
  label, value, sub, icon, color,
}: { label: string; value: string | number; sub?: string; icon: React.ReactNode; color: string }) {
  return (
    <div className="stat-card animate-slide-up" style={{ '--accent-color': color } as React.CSSProperties}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '10px',
          background: `${color}18`, border: `1px solid ${color}35`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', color,
        }}>
          {icon}
        </div>
      </div>
      <div style={{ marginTop: '12px' }}>
        <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--color-text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>
          {value}
        </div>
        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '6px', fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>{sub}</div>}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [statsRes, systemRes, healthRes] = await Promise.allSettled([
          authFetch(`${API_URL}/api/v1/admin/stats`),
          authFetch(`${API_URL}/api/v1/admin/system`),
          fetch(`${API_URL}/health`),
        ]);

        if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
          setStats(await statsRes.value.json());
        }
        if (systemRes.status === 'fulfilled' && systemRes.value.ok) {
          setSystem(await systemRes.value.json());
        }
        if (healthRes.status === 'fulfilled' && healthRes.value.ok) {
          setHealth(await healthRes.value.json());
        }
      } catch {}
      setLoading(false);
    };
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, []);

  const moduleColors: Record<string, string> = {
    translate: '#00D4FF', learn: '#7B2FBE', documents: '#FFB800',
    audit: '#00E5A0', telemetry: '#FF6B35',
  };

  return (
    <div>
      {/* Stats Row */}
      <div className="grid grid-4 gap-5 mb-6">
        <StatCard label="Total Users" value={stats?.users.total ?? '—'} sub={`${stats?.users.active ?? 0} active`} icon={<Users size={18} />} color="#00D4FF" />
        <StatCard label="Documents Indexed" value={stats?.documents.total_docs ?? '—'} sub={`${stats?.documents.total_chunks ?? 0} chunks`} icon={<FileText size={18} />} color="#FFB800" />
        <StatCard label="Guideline Versions" value={stats?.guideline_versions ?? '—'} icon={<BookOpen size={18} />} color="#7B2FBE" />
        <StatCard label="Admins / Analysts" value={stats ? `${stats.users.admin}/${stats.users.analyst}` : '—'} icon={<Users size={18} />} color="#00E5A0" />
      </div>

      <div className="grid grid-2 gap-5 mb-6">
        {/* Module Health */}
        <div>
          <div className="section-header">Module Health</div>
          <div className="glass-panel" style={{ padding: '16px' }}>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-text" style={{ margin: '8px 0', height: '36px', borderRadius: '8px' }} />
              ))
            ) : health ? (
              Object.entries(health.modules).map(([name, mod]) => (
                <div key={name} style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '10px 12px', borderRadius: '8px', marginBottom: '4px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <div style={{
                    width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
                    background: mod.status === 'healthy' ? 'var(--color-success)' : 'var(--color-danger)',
                    boxShadow: mod.status === 'healthy' ? '0 0 6px var(--color-success)' : '0 0 6px var(--color-danger)',
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', textTransform: 'capitalize' }}>{name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '1px', fontFamily: 'var(--font-mono)' }}>{mod.detail}</div>
                  </div>
                  <div style={{
                    fontSize: '10px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase',
                    background: mod.status === 'healthy' ? 'rgba(0,229,160,0.1)' : 'rgba(255,68,68,0.1)',
                    color: mod.status === 'healthy' ? 'var(--color-success)' : 'var(--color-danger)',
                    border: `1px solid ${mod.status === 'healthy' ? 'rgba(0,229,160,0.3)' : 'rgba(255,68,68,0.3)'}`,
                  }}>
                    {mod.status}
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-muted)', fontSize: '13px' }}>
                Could not fetch health data
              </div>
            )}
          </div>
        </div>

        {/* System Info */}
        <div>
          <div className="section-header">System Information</div>
          <div className="glass-panel" style={{ padding: '16px' }}>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton-text" style={{ margin: '8px 0', height: '28px', borderRadius: '6px' }} />
              ))
            ) : system ? (
              [
                { label: 'App Version', value: system.app_version, icon: <Activity size={12} /> },
                { label: 'Platform', value: `${system.platform} · Python ${system.python_version}`, icon: <Cpu size={12} /> },
                { label: 'LLM Provider', value: system.llm_provider.toUpperCase(), icon: <Activity size={12} /> },
                { label: 'ChromaDB Size', value: `${system.storage.chroma_db_mb} MB`, icon: <HardDrive size={12} /> },
                { label: 'Uploads Storage', value: `${system.storage.uploads_mb} MB · ${system.storage.uploads_count} files`, icon: <HardDrive size={12} /> },
              ].map(({ label, value, icon }) => (
                <div key={label} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 10px', borderRadius: '6px', marginBottom: '4px',
                  background: 'rgba(255,255,255,0.02)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-muted)', fontSize: '12px' }}>
                    {icon} {label}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-text-primary)', fontWeight: 600 }}>
                    {value}
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-muted)', fontSize: '13px' }}>
                Could not fetch system info
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Storage paths */}
      {system && (
        <div>
          <div className="section-header">Storage Paths</div>
          <div className="glass-panel" style={{ padding: '16px' }}>
            {[
              { label: 'Upload Directory', value: system.paths.upload_dir },
              { label: 'ChromaDB Directory', value: system.paths.chroma_dir },
              { label: 'Audit Log Directory', value: system.paths.audit_dir },
            ].map(({ label, value }) => (
              <div key={label} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 10px', borderRadius: '6px', marginBottom: '4px',
                background: 'rgba(255,255,255,0.02)',
              }}>
                <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-text-muted)' }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
