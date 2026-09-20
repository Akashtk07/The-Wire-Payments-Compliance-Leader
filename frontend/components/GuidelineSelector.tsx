'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { ChevronDown, Check, AlertTriangle, BookOpen, Plus, X } from 'lucide-react';
import { authFetch } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface GuidelineVersion {
  id: string;
  label: string;
  year: number;
  category: string;
  is_draft: boolean;
  description: string;
}

interface GuidelineSelectorProps {
  selectedVersions: string[];
  onSelectionChange: (versions: string[]) => void;
  compact?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  'CBPR+': '#00D4FF',
  'ISO 20022': '#7B2FBE',
  'Regulatory': '#FFB800',
  'Custom': '#00E5A0',
};

export default function GuidelineSelector({
  selectedVersions,
  onSelectionChange,
  compact = false,
}: GuidelineSelectorProps) {
  const [versions, setVersions] = useState<GuidelineVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await authFetch(`${API_URL}/api/v1/guidelines/versions`);
        if (res.ok) {
          const data: GuidelineVersion[] = await res.json();
          setVersions(data);

          // Restore from localStorage
          const stored = localStorage.getItem('selected_guideline_versions');
          if (stored) {
            const parsed: string[] = JSON.parse(stored);
            const valid = parsed.filter((v) => data.some((d) => d.label === v));
            if (valid.length > 0) {
              onSelectionChange(valid);
              return;
            }
          }
          // Default to CBPR+ R2025 — the current mandatory standard
          const r2025 = data.find((d) => d.label === 'CBPR+ R2025');
          if (r2025) onSelectionChange([r2025.label]);
        }
      } catch {}
      finally { setLoading(false); }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist to localStorage
  useEffect(() => {
    if (selectedVersions.length > 0) {
      localStorage.setItem('selected_guideline_versions', JSON.stringify(selectedVersions));
    }
  }, [selectedVersions]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const toggle = useCallback((label: string) => {
    const next = selectedVersions.includes(label)
      ? selectedVersions.filter((v) => v !== label)
      : [...selectedVersions, label];
    onSelectionChange(next);
  }, [selectedVersions, onSelectionChange]);

  const selectAll = () => onSelectionChange(versions.map((v) => v.label));
  const clearAll = () => onSelectionChange([]);

  // Group by category
  const groups: Record<string, GuidelineVersion[]> = {};
  for (const v of versions) {
    const cat = v.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(v);
  }

  const hasSelection = selectedVersions.length > 0;
  const buttonLabel = hasSelection
    ? selectedVersions.length === 1
      ? selectedVersions[0]
      : `${selectedVersions.length} versions selected`
    : 'Select Guideline Versions';

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      {/* Trigger button */}
      <button
        id="guideline-selector-btn"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: compact ? '6px 12px' : '8px 14px',
          borderRadius: '10px',
          border: `1px solid ${hasSelection ? 'rgba(0,212,255,0.4)' : 'var(--color-border)'}`,
          background: hasSelection ? 'rgba(0,212,255,0.06)' : 'rgba(255,255,255,0.04)',
          cursor: 'pointer',
          color: hasSelection ? 'var(--color-primary)' : 'var(--color-text-secondary)',
          fontSize: '13px',
          fontWeight: 600,
          transition: 'all 150ms ease',
          whiteSpace: 'nowrap',
          minWidth: compact ? 'auto' : '220px',
        }}
      >
        <BookOpen size={14} />
        <span style={{ flex: 1, textAlign: 'left' }}>
          {loading ? 'Loading versions...' : buttonLabel}
        </span>
        <ChevronDown
          size={14}
          style={{
            transition: 'transform 150ms ease',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="animate-scale-in"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            zIndex: 200,
            background: 'var(--color-panel)',
            border: '1px solid var(--color-border)',
            borderRadius: '14px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            width: '320px',
            maxHeight: '480px',
            overflowY: 'auto',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                Guideline Versions
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                {selectedVersions.length} of {versions.length} selected
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={selectAll}
                style={{ fontSize: '11px', color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
              >
                All
              </button>
              <span style={{ color: 'var(--color-border)' }}>·</span>
              <button
                onClick={clearAll}
                style={{ fontSize: '11px', color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
              >
                Clear
              </button>
            </div>
          </div>

          {/* Version groups */}
          {Object.entries(groups).map(([category, items]) => (
            <div key={category}>
              <div
                style={{
                  padding: '8px 16px 4px',
                  fontSize: '10px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: CATEGORY_COLORS[category] ?? 'var(--color-text-muted)',
                }}
              >
                {category}
              </div>
              {items.map((v) => {
                const isSelected = selectedVersions.includes(v.label);
                return (
                  <button
                    key={v.id}
                    onClick={() => toggle(v.label)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      padding: '8px 16px',
                      border: 'none',
                      background: isSelected ? 'rgba(0,212,255,0.06)' : 'transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background 100ms ease',
                    }}
                    onMouseOver={(e) => {
                      if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
                    }}
                    onMouseOut={(e) => {
                      if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    }}
                  >
                    {/* Checkbox */}
                    <div
                      style={{
                        width: '16px',
                        height: '16px',
                        borderRadius: '4px',
                        border: `1.5px solid ${isSelected ? 'var(--color-primary)' : 'var(--color-border)'}`,
                        background: isSelected ? 'var(--color-primary)' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '2px',
                        transition: 'all 150ms ease',
                      }}
                    >
                      {isSelected && <Check size={10} color="#080C14" strokeWidth={3} />}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: isSelected ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                          {v.label}
                        </span>
                        {v.label === 'CBPR+ R2025' && (
                          <span style={{
                            fontSize: '9px', fontWeight: 700, letterSpacing: '0.06em',
                            padding: '2px 6px', borderRadius: '4px',
                            background: 'rgba(0,229,160,0.12)', color: 'var(--color-success)',
                            border: '1px solid rgba(0,229,160,0.35)', textTransform: 'uppercase',
                          }}>
                            Current
                          </span>
                        )}
                        {v.is_draft && (
                          <span style={{
                            fontSize: '9px', fontWeight: 700, letterSpacing: '0.06em',
                            padding: '2px 6px', borderRadius: '4px',
                            background: 'rgba(255,184,0,0.12)', color: '#FFB800',
                            border: '1px solid rgba(255,184,0,0.3)', textTransform: 'uppercase',
                          }}>
                            Draft
                          </span>
                        )}
                        {v.year > 0 && (
                          <span style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>
                            {v.year}
                          </span>
                        )}
                      </div>
                      {v.description && (
                        <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px', lineHeight: 1.4 }}>
                          {v.description.length > 80 ? v.description.slice(0, 80) + '…' : v.description}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* Cross-version warning note */}
      {selectedVersions.length > 1 && (
        <div
          className="animate-slide-up"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: open ? '340px' : '0',
            zIndex: 100,
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            padding: '10px 14px',
            background: 'rgba(255,184,0,0.06)',
            border: '1px solid rgba(255,184,0,0.25)',
            borderRadius: '10px',
            maxWidth: '280px',
            pointerEvents: 'none',
          }}
        >
          <AlertTriangle size={13} color="#FFB800" style={{ marginTop: '2px', flexShrink: 0 }} />
          <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
            <strong style={{ color: '#FFB800' }}>Multi-version mode:</strong> AI will highlight rule changes between selected versions using{' '}
            <strong>⚠️ Changed in [VERSION]</strong> notation.
          </span>
        </div>
      )}
    </div>
  );
}
