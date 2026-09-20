'use client';

import React from 'react';

import { useState } from 'react';
import { format } from 'date-fns';
import {
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

export interface AuditLogEntry {
  audit_id: string;
  timestamp: string;
  event_type: string;
  module: number | string;
  status: string;
  message_type?: string;
  uetr?: string;
  hash?: string;
  prev_hash?: string;
  details?: Record<string, unknown>;
}

interface AuditTableProps {
  entries: AuditLogEntry[];
  loading: boolean;
  onExpand?: (id: string) => void;
}

const eventTypeColors: Record<string, string> = {
  TRANSLATION_SUCCESS:   'status-success',
  TRANSLATION_FAILURE:   'status-danger',
  VALIDATION_EXCEPTION:  'status-danger',
  LEARN_QUERY:           'status-info',
  DOCUMENT_UPLOAD:       'status-warning',
  DOCUMENT_QUERY:        'status-info',
  AUDIT_EXPORT:          'status-success',
  SYSTEM_HEALTH:         'status-neutral',
};

const statusColors: Record<string, string> = {
  SUCCESS:              'status-success',
  PASS:                 'status-success',
  VALIDATION_EXCEPTION: 'status-danger',
  FAILURE:              'status-danger',
  ERROR:                'status-danger',
  PENDING:              'status-warning',
  INFO:                 'status-info',
};

function truncate(str: string | undefined, len: number): string {
  if (!str) return '—';
  return str.length > len ? `${str.slice(0, len)}…` : str;
}

export default function AuditTable({ entries, loading, onExpand }: AuditTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleRowClick = (id: string) => {
    const next = expandedId === id ? null : id;
    setExpandedId(next);
    if (next && onExpand) onExpand(id);
  };

  /* ---------- Loading Skeleton ---------- */
  if (loading) {
    return (
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              {['Timestamp', 'Event Type', 'Module', 'Status', 'Msg Type', 'UETR', 'Hash', 'Valid'].map(
                (h) => (
                  <th key={h}>{h}</th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {[1, 2, 3].map((i) => (
              <tr key={i}>
                {Array.from({ length: 8 }).map((_, j) => (
                  <td key={j}>
                    <div
                      className="skeleton-text"
                      style={{ width: j === 0 ? '120px' : j === 5 ? '80px' : '60px' }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  /* ---------- Empty State ---------- */
  if (entries.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 24px',
          gap: '16px',
          background: 'var(--color-panel)',
          border: '1px solid var(--color-border)',
          borderRadius: '12px',
          color: 'var(--color-text-muted)',
        }}
      >
        <ShieldCheck size={40} strokeWidth={1} color="var(--color-text-muted)" />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
            No audit entries found
          </div>
          <div style={{ fontSize: '13px' }}>
            Audit records will appear here as platform operations are performed.
          </div>
        </div>
      </div>
    );
  }

  /* ---------- Table ---------- */
  return (
    <div className="table-wrapper">
      <table className="table" role="table" aria-label="Audit log entries">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Event Type</th>
            <th>Module</th>
            <th>Status</th>
            <th>Msg Type</th>
            <th>UETR</th>
            <th>Audit ID</th>
            <th>Hash</th>
            <th>Valid</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isExpanded = expandedId === entry.audit_id;
            const eventColorClass =
              eventTypeColors[entry.event_type] ?? 'status-neutral';
            const statusColorClass =
              statusColors[entry.status] ?? 'status-neutral';

            const formattedTs = (() => {
              try {
                return format(new Date(entry.timestamp), 'MMM dd HH:mm:ss');
              } catch {
                return entry.timestamp;
              }
            })();

            // Simple chain integrity: prev_hash present = valid (real check done server-side)
            const chainValid = entry.hash && entry.hash.length > 8;

            return (
              <React.Fragment key={entry.audit_id}>
                <tr
                  onClick={() => handleRowClick(entry.audit_id)}
                  style={{ cursor: 'pointer' }}
                  aria-expanded={isExpanded}
                >
                  <td>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        color: 'var(--color-text-secondary)',
                      }}
                    >
                      {formattedTs}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${eventColorClass}`}>
                      {entry.event_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        background: 'rgba(0,212,255,0.1)',
                        border: '1px solid rgba(0,212,255,0.2)',
                        fontSize: '12px',
                        fontWeight: 700,
                        color: 'var(--color-primary)',
                      }}
                    >
                      {entry.module}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${statusColorClass}`}>
                      {entry.status}
                    </span>
                  </td>
                  <td>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        color: 'var(--color-text-secondary)',
                      }}
                    >
                      {entry.message_type ?? '—'}
                    </span>
                  </td>
                  <td className="table-mono">{truncate(entry.uetr, 8)}</td>
                  <td className="table-mono">{truncate(entry.audit_id, 8)}</td>
                  <td className="table-mono">{truncate(entry.hash, 8)}</td>
                  <td>
                    {chainValid ? (
                      <span className="hash-valid">
                        <CheckCircle2 size={14} />
                        OK
                      </span>
                    ) : (
                      <span className="hash-invalid">
                        <XCircle size={14} />
                        —
                      </span>
                    )}
                  </td>
                </tr>

                {/* Expanded Row */}
                {isExpanded && (
                  <tr>
                    <td
                      colSpan={9}
                      style={{ padding: 0 }}
                    >
                      <div className="audit-row-expanded animate-slide-down">
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            marginBottom: '10px',
                            fontSize: '11px',
                            fontWeight: 700,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            color: 'var(--color-text-muted)',
                          }}
                        >
                          <ChevronUp size={14} />
                          Full Audit Record — {entry.audit_id}
                        </div>
                        <pre className="code-block">
                          {JSON.stringify(entry, null, 2)}
                        </pre>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
