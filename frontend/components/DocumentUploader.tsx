'use client';

import {
  useEffect, useRef, useState, useCallback,
  DragEvent, ChangeEvent,
} from 'react';
import { Upload, FileText, CheckCircle2, XCircle, Loader2, BookOpen, Tag } from 'lucide-react';
import { authFetch } from '@/lib/auth';
import GuidelineSelector, { GuidelineVersion } from './GuidelineSelector';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface DocumentUploadResponse {
  doc_id: string;
  filename: string;
  chunks_indexed: number;
  chunks?: number;
  message?: string;
}

interface DocumentUploaderProps {
  onUploadSuccess: (doc: DocumentUploadResponse) => void;
}

type UploadState = 'idle' | 'dragging' | 'uploading' | 'success' | 'error';

const FILE_TYPE_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  pdf:  { icon: '📄', color: '#FF4444', label: 'PDF' },
  pptx: { icon: '📊', color: '#FF6B35', label: 'PPTX' },
  docx: { icon: '📝', color: '#00D4FF', label: 'DOCX' },
  xml:  { icon: '📋', color: '#00E5A0', label: 'XML' },
  txt:  { icon: '📃', color: '#8A95A8', label: 'TXT' },
};

const ACCEPTED_EXTENSIONS = Object.keys(FILE_TYPE_CONFIG);
const ACCEPTED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/xml', 'application/xml', 'text/plain',
];

const CATEGORIES = [
  'CBPR+', 'ISO 20022', 'Regulatory', 'Internal Policy', 'Draft', 'Custom',
];

export default function DocumentUploader({ onUploadSuccess }: DocumentUploaderProps) {
  const [state, setState] = useState<UploadState>('idle');
  const [progress, setProgress] = useState(0);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [result, setResult] = useState<DocumentUploadResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Version metadata state
  const [selectedVersion, setSelectedVersion] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('CBPR+');
  const [tags, setTags] = useState('');
  const [availableVersions, setAvailableVersions] = useState<GuidelineVersion[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const progressTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load available versions for dropdown
  useEffect(() => {
    authFetch(`${API_URL}/api/v1/guidelines/versions`)
      .then((r) => r.ok ? r.json() : [])
      .then((data: GuidelineVersion[]) => {
        setAvailableVersions(data);
        // Default to the first CBPR+ version
        const first = data.find((v) => v.category === 'CBPR+' && !v.is_draft);
        if (first) setSelectedVersion(first.label);
      })
      .catch(() => {});
  }, []);

  const clearProgressTimer = () => {
    if (progressTimer.current) {
      clearInterval(progressTimer.current);
      progressTimer.current = null;
    }
  };

  useEffect(() => () => clearProgressTimer(), []);

  const getFileExt = (name: string) => name.split('.').pop()?.toLowerCase() ?? '';
  const isValidFile = (file: File): boolean => {
    const ext = getFileExt(file.name);
    return ACCEPTED_EXTENSIONS.includes(ext) || ACCEPTED_MIME.some((m) => file.type.includes(m.split('/')[1]));
  };

  const simulateProgress = useCallback(() => {
    setProgress(0);
    let current = 0;
    progressTimer.current = setInterval(() => {
      current += Math.random() * 12 + 4;
      if (current >= 90) { clearProgressTimer(); setProgress(90); return; }
      setProgress(Math.min(current, 90));
    }, 150);
  }, []);

  const uploadFile = useCallback(
    async (file: File) => {
      if (!isValidFile(file)) {
        setErrorMsg(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(', ').toUpperCase()}`);
        setState('error');
        return;
      }

      setCurrentFile(file);
      setState('uploading');
      simulateProgress();

      const formData = new FormData();
      formData.append('file', file);
      formData.append('guideline_version', selectedVersion || 'Unclassified');
      formData.append('guideline_category', selectedCategory || 'Custom');
      formData.append('tags', tags);

      try {
        const res = await authFetch(`${API_URL}/api/v1/documents/upload`, {
          method: 'POST',
          body: formData,
        });

        clearProgressTimer();

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
          throw new Error(err.detail ?? 'Upload failed');
        }

        const data: DocumentUploadResponse = await res.json();
        setProgress(100);
        setResult(data);
        setState('success');
        onUploadSuccess(data);
      } catch (err) {
        clearProgressTimer();
        setProgress(0);
        setErrorMsg(err instanceof Error ? err.message : 'Upload failed');
        setState('error');
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onUploadSuccess, simulateProgress, selectedVersion, selectedCategory, tags]
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setState('idle'); const file = e.dataTransfer.files[0]; if (file) uploadFile(file); };
  const onDragOver = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setState('dragging'); };
  const onDragLeave = () => setState('idle');
  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (file) uploadFile(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const reset = () => { setState('idle'); setProgress(0); setCurrentFile(null); setResult(null); setErrorMsg(''); };

  return (
    <div>
      {/* Version Metadata — shown when idle */}
      {(state === 'idle' || state === 'dragging') && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '10px',
            marginBottom: '14px',
          }}
        >
          {/* Guideline Version dropdown */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <BookOpen size={12} /> Guideline Version
            </label>
            <select
              className="select"
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
              style={{ fontSize: '12px', height: '36px' }}
            >
              <option value="">Unclassified / Legacy</option>
              {availableVersions.map((v) => (
                <option key={v.id} value={v.label}>
                  {v.label}{v.is_draft ? ' (Draft)' : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Category */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Tag size={12} /> Category
            </label>
            <select
              className="select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{ fontSize: '12px', height: '36px' }}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div className="form-group" style={{ margin: 0, gridColumn: '1 / -1' }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Tag size={12} /> Tags (comma-separated, optional)
            </label>
            <input
              type="text"
              className="input"
              placeholder="e.g. pacs.008, mandatory-fields, agent-rules"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              style={{ fontSize: '12px', height: '36px' }}
            />
          </div>
        </div>
      )}

      {/* Drop Zone */}
      {(state === 'idle' || state === 'dragging') && (
        <div
          className={`dropzone ${state === 'dragging' ? 'drag-over' : ''}`}
          onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
          role="button" tabIndex={0} aria-label="Upload document"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
        >
          <input
            ref={fileInputRef} type="file"
            accept={ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',')}
            style={{ display: 'none' }} onChange={onFileChange} aria-hidden="true"
          />
          <div style={{
            width: '56px', height: '56px', borderRadius: '14px',
            background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '8px',
          }}>
            <Upload size={24} color="var(--color-primary)" strokeWidth={1.5} />
          </div>
          <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--color-text-primary)' }}>
            Drop file here or click to browse
          </div>
          <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            Maximum file size: 50 MB
          </div>
          {selectedVersion && (
            <div style={{
              marginTop: '8px', padding: '4px 10px', borderRadius: '999px',
              background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)',
              fontSize: '11px', color: 'var(--color-primary)', fontWeight: 600,
            }}>
              📚 Will be tagged as: {selectedVersion}
            </div>
          )}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '12px' }}>
            {Object.entries(FILE_TYPE_CONFIG).map(([ext, cfg]) => (
              <span key={ext} style={{
                padding: '4px 10px', borderRadius: '999px', fontSize: '11px',
                fontWeight: 700, letterSpacing: '0.06em',
                background: `${cfg.color}18`, border: `1px solid ${cfg.color}40`, color: cfg.color,
              }}>
                {cfg.icon} {cfg.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Uploading */}
      {state === 'uploading' && currentFile && (
        <div style={{ padding: '20px 24px', background: 'var(--color-panel)', border: '1px solid var(--color-border)', borderRadius: '12px' }} className="animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <Loader2 size={20} color="var(--color-primary)" className="animate-spin" />
            <div>
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-text-primary)' }}>
                Uploading &amp; indexing as {selectedVersion || 'Unclassified'}...
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                {currentFile.name}
              </div>
            </div>
            <div style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '14px', color: 'var(--color-primary)' }}>
              {Math.round(progress)}%
            </div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Success */}
      {state === 'success' && result && (
        <div style={{ padding: '20px 24px', background: 'rgba(0,229,160,0.06)', border: '1px solid rgba(0,229,160,0.3)', borderRadius: '12px' }} className="animate-slide-up">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <CheckCircle2 size={24} color="var(--color-success)" />
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--color-success)' }}>
                Document indexed successfully
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {result.filename}
              </div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={reset} style={{ marginLeft: 'auto' }}>
              Upload Another
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
            {[
              { label: 'Document ID', value: result.doc_id.slice(0, 8) + '...', color: 'var(--color-primary)' },
              { label: 'Chunks Created', value: String(result.chunks_indexed ?? result.chunks ?? 0), color: 'var(--color-success)' },
              { label: 'Version Tagged', value: selectedVersion || 'Unclassified', color: '#FFB800' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: '10px 14px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>{label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color, wordBreak: 'break-all' }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {state === 'error' && (
        <div style={{ padding: '20px 24px', background: 'rgba(255,68,68,0.06)', border: '1px solid rgba(255,68,68,0.3)', borderRadius: '12px' }} className="animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <XCircle size={24} color="var(--color-danger)" />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--color-danger)' }}>Upload Failed</div>
              <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>{errorMsg}</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={reset}>Try Again</button>
          </div>
        </div>
      )}
    </div>
  );
}
