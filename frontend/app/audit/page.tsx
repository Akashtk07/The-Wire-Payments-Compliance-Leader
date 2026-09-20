'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Download,
  Filter,
  RefreshCw,
  Shield,
  Info,
  ChevronLeft,
  ChevronRight,
  Lock,
} from 'lucide-react';
import TelemetryFeed from '@/components/TelemetryFeed';
import AuditTable, { AuditLogEntry } from '@/components/AuditTable';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const PAGE_SIZE = 10;

const EVENT_TYPES = [
  'ALL',
  'TRANSLATION_SUCCESS',
  'TRANSLATION_FAILURE',
  'VALIDATION_EXCEPTION',
  'LEARN_QUERY',
  'DOCUMENT_UPLOAD',
  'DOCUMENT_QUERY',
  'AUDIT_EXPORT',
  'SYSTEM_HEALTH',
];

export default function AuditPage() {
  // Audit log state
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState('ALL');
  const [moduleFilter, setModuleFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Export
  const [exporting, setExporting] = useState(false);
  const [lastExport, setLastExport] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      if (eventTypeFilter !== 'ALL') params.set('event_type', eventTypeFilter);
      if (moduleFilter) params.set('module', moduleFilter);
      if (searchText) params.set('search', searchText);
      if (dateFrom) params.set('from', dateFrom);
      if (dateTo) params.set('to', dateTo);

      const res = await fetch(`${API_URL}/api/v1/audit/logs?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        const list: AuditLogEntry[] = Array.isArray(data)
          ? data
          : data.entries ?? data.logs ?? [];
        setEntries(list);
        setTotal(data.total ?? list.length);
      }
    } catch { /* ignore */ } finally {
      setLoadingLogs(false);
    }
  }, [page, eventTypeFilter, moduleFilter, searchText, dateFrom, dateTo]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/audit/export`);
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const cd = res.headers.get('content-disposition');
        const filename = cd?.match(/filename="?([^"]+)"?/)?.[1] ?? `audit_export_${Date.now()}.json`;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        setLastExport(new Date().toLocaleString());
      }
    } catch { /* ignore */ } finally {
      setExporting(false);
    }
  };

  const applyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const resetFilters = () => {
    setEventTypeFilter('ALL');
    setModuleFilter('');
    setSearchText('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="page-container">
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Audit Logging &amp; Telemetry Monitoring Framework</h1>
        <p>
          Real-time telemetry stream, immutable tamper-evident audit log, and SHA-256 hash chain
          integrity verification for full regulatory compliance.
        </p>
      </div>

      {/* === SECTION 1: Live Telemetry === */}
      <div className="animate-slide-up mb-6">
        <div className="section-header" style={{ marginBottom: '16px' }}>
          Live Telemetry Stream
        </div>
        <TelemetryFeed maxEvents={50} />
      </div>

      {/* === SECTION 2: Audit Log Explorer === */}
      <div className="animate-slide-up delay-200 mb-6">
        <div className="section-header" style={{ marginBottom: '16px' }}>
          Audit Log Explorer
        </div>

        {/* Filter Bar */}
        <div className="audit-grid mb-4">
          <form className="audit-filter-bar" onSubmit={applyFilters}>
            {/* Event Type */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '0 0 180px' }}>
              <label className="form-label" htmlFor="filter-event-type">Event Type</label>
              <select
                id="filter-event-type"
                className="select"
                value={eventTypeFilter}
                onChange={(e) => setEventTypeFilter(e.target.value)}
                style={{ maxWidth: '180px' }}
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t === 'ALL' ? 'All Events' : t.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>

            {/* Module */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '0 0 100px' }}>
              <label className="form-label" htmlFor="filter-module">Module</label>
              <input
                id="filter-module"
                type="number"
                min={1}
                max={4}
                className="input"
                placeholder="1–4"
                value={moduleFilter}
                onChange={(e) => setModuleFilter(e.target.value)}
                style={{ maxWidth: '100px' }}
              />
            </div>

            {/* Date From */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '0 0 160px' }}>
              <label className="form-label" htmlFor="filter-date-from">From Date</label>
              <input
                id="filter-date-from"
                type="date"
                className="input"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                style={{ maxWidth: '160px', colorScheme: 'dark' }}
              />
            </div>

            {/* Date To */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '0 0 160px' }}>
              <label className="form-label" htmlFor="filter-date-to">To Date</label>
              <input
                id="filter-date-to"
                type="date"
                className="input"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                style={{ maxWidth: '160px', colorScheme: 'dark' }}
              />
            </div>

            {/* Search */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: '160px' }}>
              <label className="form-label" htmlFor="filter-search">Search</label>
              <input
                id="filter-search"
                type="text"
                className="input"
                placeholder="UETR, audit ID, message..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', flexShrink: 0 }}>
              <button type="submit" className="btn btn-primary btn-sm">
                <Filter size={13} />
                Filter
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={resetFilters}
                aria-label="Reset filters"
              >
                <RefreshCw size={13} />
                Reset
              </button>
            </div>
          </form>
        </div>

        {/* Table */}
        <AuditTable entries={entries} loading={loadingLogs} />

        {/* Pagination */}
        {!loadingLogs && total > 0 && (
          <div className="pagination">
            <button
              className="page-btn"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              aria-label="Previous page"
            >
              <ChevronLeft size={14} />
            </button>

            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const pageNum = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
              return (
                <button
                  key={pageNum}
                  className={`page-btn ${pageNum === page ? 'active' : ''}`}
                  onClick={() => setPage(pageNum)}
                  aria-current={pageNum === page ? 'page' : undefined}
                >
                  {pageNum}
                </button>
              );
            })}

            <button
              className="page-btn"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              aria-label="Next page"
            >
              <ChevronRight size={14} />
            </button>

            <span style={{ marginLeft: 'auto', color: 'var(--color-text-muted)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
              {entries.length} of {total} entries · Page {page}/{totalPages}
            </span>
          </div>
        )}
      </div>

      {/* === SECTION 3: Export Controls === */}
      <div className="animate-slide-up delay-400">
        <div className="section-header" style={{ marginBottom: '16px' }}>
          Export Controls
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Export Button Card */}
          <div
            style={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  background: 'rgba(0,229,160,0.1)',
                  border: '1px solid rgba(0,229,160,0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Lock size={20} color="var(--color-success)" />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--color-text-primary)' }}>
                  Tamper-Evident Bundle
                </div>
                <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                  Full audit log with SHA-256 hash chain
                </div>
              </div>
            </div>

            <button
              id="export-audit-btn"
              className="btn btn-success"
              onClick={handleExport}
              disabled={exporting}
              style={{ justifyContent: 'center' }}
            >
              {exporting ? (
                <>
                  <Shield size={16} className="animate-spin" />
                  Generating Bundle...
                </>
              ) : (
                <>
                  <Download size={16} />
                  Export Tamper-Evident Bundle
                </>
              )}
            </button>

            {lastExport && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  color: 'var(--color-success)',
                  background: 'rgba(0,229,160,0.08)',
                  border: '1px solid rgba(0,229,160,0.2)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                }}
              >
                <Shield size={13} />
                Last exported: {lastExport}
              </div>
            )}
          </div>

          {/* Info Callout */}
          <div className="callout" style={{ alignSelf: 'start' }}>
            <div className="callout-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={16} />
              SHA-256 Hash Chain Integrity
            </div>
            <p>
              Every audit record in The Compliance Leader is cryptographically linked to the previous
              entry using SHA-256 hashing. Each record stores:
            </p>
            <ul style={{ marginTop: '10px', paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '6px', listStyle: 'disc' }}>
              <li><strong>hash</strong> — SHA-256 digest of this record&apos;s content</li>
              <li><strong>prev_hash</strong> — Hash of the preceding record, forming the chain</li>
              <li><strong>audit_id</strong> — Immutable UUID assigned at creation</li>
            </ul>
            <p style={{ marginTop: '10px' }}>
              Any tampering with historical records breaks the chain, providing forensic proof of
              integrity for compliance auditors, regulators, and counterparty verification.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
