'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2, BookOpen, RefreshCw } from 'lucide-react';
import { authFetch } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface GuidelineVersionRecord {
  id: string;
  label: string;
  year: number;
  category: string;
  is_draft: boolean;
  description: string;
  created_at: string | null;
  created_by: string;
}

const CATEGORIES = ['CBPR+', 'ISO 20022', 'Regulatory', 'Internal Policy', 'Custom'];
const CATEGORY_COLORS: Record<string, string> = {
  'CBPR+': '#00D4FF', 'ISO 20022': '#7B2FBE', 'Regulatory': '#FFB800',
  'Internal Policy': '#00E5A0', 'Custom': '#8A95A8',
};

export default function AdminGuidelinesPage() {
  const [versions, setVersions] = useState<GuidelineVersionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ label: '', year: new Date().getFullYear(), category: 'CBPR+', is_draft: false, description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/v1/guidelines/versions`);
      if (res.ok) setVersions(await res.json());
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchVersions(); }, []);

  const handleCreate = async () => {
    if (!form.label.trim()) { setError('Label is required'); return; }
    setSubmitting(true);
    setError('');
    try {
      const res = await authFetch(`${API_URL}/api/v1/guidelines/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err?.detail?.message ?? 'Failed to create version');
      }
      setShowForm(false);
      setForm({ label: '', year: new Date().getFullYear(), category: 'CBPR+', is_draft: false, description: '' });
      fetchVersions();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, label: string) => {
    if (!confirm(`Remove "${label}" from the registry? Documents tagged with this version will keep the tag but the version won't appear in the dropdown.`)) return;
    setDeleting(id);
    try {
      await authFetch(`${API_URL}/api/v1/guidelines/versions/${id}`, { method: 'DELETE' });
      setVersions((prev) => prev.filter((v) => v.id !== id));
    } catch {}
    setDeleting(null);
  };

  const fmt = (d: string | null) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

  // Group by category
  const groups: Record<string, GuidelineVersionRecord[]> = {};
  for (const v of versions) {
    const cat = v.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(v);
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div className="section-header" style={{ margin: 0 }}>
          Guideline Registry ({versions.length} versions)
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-ghost btn-sm" onClick={fetchVersions} style={{ gap: '6px' }}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button
            id="add-version-btn"
            className="btn btn-primary btn-sm"
            onClick={() => { setShowForm((v) => !v); setError(''); }}
            style={{ gap: '6px' }}
          >
            <Plus size={14} /> Add Version
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="glass-panel animate-slide-down" style={{ padding: '20px', marginBottom: '16px' }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '16px' }}>
            New Guideline Version
          </div>
          {error && (
            <div style={{ padding: '8px 12px', background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.3)', borderRadius: '8px', fontSize: '13px', color: 'var(--color-danger)', marginBottom: '12px' }}>
              {error}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Label *</label>
              <input className="input" placeholder="e.g. CBPR+ R2027" value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} style={{ fontSize: '13px', height: '36px' }} />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Year</label>
              <input className="input" type="number" value={form.year} onChange={(e) => setForm((f) => ({ ...f, year: parseInt(e.target.value) }))} style={{ fontSize: '13px', height: '36px' }} />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Category</label>
              <select className="select" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} style={{ fontSize: '13px', height: '36px' }}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="form-label">Description</label>
            <input className="input" placeholder="Brief description of this guideline version" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ fontSize: '13px', height: '36px' }} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
            <input type="checkbox" checked={form.is_draft} onChange={(e) => setForm((f) => ({ ...f, is_draft: e.target.checked }))} />
            Mark as Draft
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={submitting} style={{ gap: '6px' }}>
              {submitting ? 'Creating...' : <><Plus size={13} /> Create Version</>}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Version groups */}
      {loading ? (
        <div className="glass-panel" style={{ padding: '20px' }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton-text" style={{ margin: '10px 0', height: '52px', borderRadius: '8px' }} />
          ))}
        </div>
      ) : (
        Object.entries(groups).map(([category, items]) => (
          <div key={category} style={{ marginBottom: '16px' }}>
            <div style={{
              fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
              color: CATEGORY_COLORS[category] ?? 'var(--color-text-muted)',
              marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: CATEGORY_COLORS[category] ?? 'var(--color-text-muted)' }} />
              {category} ({items.length})
            </div>
            <div className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
              {items.map((v, idx) => (
                <div key={v.id} style={{
                  display: 'flex', alignItems: 'center', gap: '14px',
                  padding: '12px 16px',
                  borderBottom: idx < items.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  transition: 'background 150ms',
                }}
                  onMouseOver={(e) => (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.02)'}
                  onMouseOut={(e) => (e.currentTarget as HTMLDivElement).style.background = 'transparent'}
                >
                  <div style={{
                    width: '36px', height: '36px', borderRadius: '8px', flexShrink: 0,
                    background: `${CATEGORY_COLORS[category] ?? '#8A95A8'}18`,
                    border: `1px solid ${CATEGORY_COLORS[category] ?? '#8A95A8'}35`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: CATEGORY_COLORS[category] ?? '#8A95A8',
                  }}>
                    <BookOpen size={16} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-primary)' }}>{v.label}</span>
                      {v.is_draft && (
                        <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: 'rgba(255,184,0,0.12)', color: '#FFB800', border: '1px solid rgba(255,184,0,0.3)', textTransform: 'uppercase' }}>
                          Draft
                        </span>
                      )}
                      {v.year > 0 && (
                        <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>· {v.year}</span>
                      )}
                    </div>
                    {v.description && (
                      <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                        {v.description}
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', textAlign: 'right', flexShrink: 0 }}>
                    <div>Added {fmt(v.created_at)}</div>
                    <div>by {v.created_by}</div>
                  </div>
                  <button
                    onClick={() => handleDelete(v.id, v.label)}
                    disabled={deleting === v.id || v.created_by === 'system'}
                    title={v.created_by === 'system' ? 'System versions cannot be deleted' : 'Remove version'}
                    style={{
                      padding: '6px', borderRadius: '6px', border: '1px solid rgba(255,68,68,0.3)',
                      background: 'transparent', cursor: v.created_by === 'system' ? 'not-allowed' : 'pointer',
                      color: v.created_by === 'system' ? 'var(--color-text-muted)' : 'var(--color-danger)',
                      opacity: v.created_by === 'system' ? 0.4 : 1, flexShrink: 0,
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
