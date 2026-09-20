'use client';

import { useEffect, useState } from 'react';
import { Trash2, RefreshCw, FileText, BookOpen } from 'lucide-react';
import { authFetch } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface DocRecord {
  doc_id: string;
  filename: string;
  guideline_version: string;
  guideline_category: string;
  tags: string;
  total_chunks: number;
}

export default function AdminDocumentsPage() {
  const [docs, setDocs] = useState<DocRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [versionFilter, setVersionFilter] = useState('all');

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/v1/documents/list`);
      if (res.ok) {
        const data = await res.json();
        setDocs(Array.isArray(data) ? data : data.documents ?? []);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchDocs(); }, []);

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document and all its chunks from the knowledge base?')) return;
    setDeleting(docId);
    try {
      await authFetch(`${API_URL}/api/v1/documents/${docId}`, { method: 'DELETE' });
      setDocs((prev) => prev.filter((d) => d.doc_id !== docId));
    } catch {}
    setDeleting(null);
  };

  // Unique versions for filter
  const versions = ['all', ...Array.from(new Set(docs.map((d) => d.guideline_version).filter(Boolean)))];

  const filtered = docs.filter((d) => {
    const matchText = !filter || d.filename.toLowerCase().includes(filter.toLowerCase());
    const matchVer = versionFilter === 'all' || d.guideline_version === versionFilter;
    return matchText && matchVer;
  });

  const totalChunks = docs.reduce((acc, d) => acc + d.total_chunks, 0);

  return (
    <div>
      {/* Stats */}
      <div className="grid grid-4 gap-4 mb-5">
        {[
          { label: 'Total Documents', value: docs.length, color: '#FFB800' },
          { label: 'Total Chunks', value: totalChunks.toLocaleString(), color: '#00D4FF' },
          { label: 'Guideline Versions', value: versions.length - 1, color: '#7B2FBE' },
          { label: 'Filtered View', value: filtered.length, color: '#00E5A0' },
        ].map(({ label, value, color }) => (
          <div key={label} className="glass-panel" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: '22px', fontWeight: 800, color, letterSpacing: '-0.02em' }}>{value}</div>
            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px', fontWeight: 500 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', alignItems: 'center' }}>
        <input
          className="input"
          placeholder="Search by filename..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ flex: 1, maxWidth: '300px', fontSize: '13px', height: '36px' }}
        />
        <select
          className="select"
          value={versionFilter}
          onChange={(e) => setVersionFilter(e.target.value)}
          style={{ fontSize: '13px', height: '36px', minWidth: '180px' }}
        >
          {versions.map((v) => (
            <option key={v} value={v}>{v === 'all' ? 'All Versions' : v}</option>
          ))}
        </select>
        <button
          className="btn btn-ghost btn-sm"
          onClick={fetchDocs}
          style={{ gap: '6px', height: '36px' }}
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Document Table */}
      <div className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              {['Document', 'Guideline Version', 'Category', 'Tags', 'Chunks', 'Actions'].map((h) => (
                <th key={h} style={{
                  padding: '10px 14px', textAlign: 'left', fontSize: '11px',
                  fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                  color: 'var(--color-text-muted)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} style={{ padding: '12px 14px' }}>
                      <div className="skeleton-text" style={{ height: '14px', borderRadius: '4px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>
                  No documents found
                </td>
              </tr>
            ) : (
              filtered.map((doc) => (
                <tr key={doc.doc_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                  onMouseOver={(e) => (e.currentTarget as HTMLTableRowElement).style.background = 'rgba(255,255,255,0.02)'}
                  onMouseOut={(e) => (e.currentTarget as HTMLTableRowElement).style.background = 'transparent'}
                >
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileText size={14} color="#FFB800" />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.filename}
                      </span>
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                      {doc.doc_id.slice(0, 16)}...
                    </div>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: 600,
                      background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.25)',
                      color: 'var(--color-primary)',
                    }}>
                      {doc.guideline_version || 'Unclassified'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                    {doc.guideline_category || '—'}
                  </td>
                  <td style={{ padding: '12px 14px', fontSize: '11px', color: 'var(--color-text-muted)', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.tags || '—'}
                  </td>
                  <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--color-success)', fontWeight: 700 }}>
                    {doc.total_chunks.toLocaleString()}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <button
                      onClick={() => handleDelete(doc.doc_id)}
                      disabled={deleting === doc.doc_id}
                      style={{
                        padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(255,68,68,0.3)',
                        background: 'transparent', cursor: 'pointer', color: 'var(--color-danger)',
                        fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px',
                      }}
                    >
                      <Trash2 size={12} />
                      {deleting === doc.doc_id ? 'Deleting...' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
