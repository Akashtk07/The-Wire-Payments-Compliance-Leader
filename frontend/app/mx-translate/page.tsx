'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import {
  ArrowLeftRight,
  Copy,
  Download,
  Loader2,
  RefreshCw,
  CheckCheck,
  FileCode,
  FileInput,
  ArrowRightLeft,
  Shield,
  Zap,
} from 'lucide-react';
import { xml } from '@codemirror/lang-xml';
import { oneDark } from '@codemirror/theme-one-dark';

const CodeMirror = dynamic(
  () => import('@uiw/react-codemirror').then((m) => m.default),
  { ssr: false }
);

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const PACS_TYPES = [
  { value: 'pacs.008.001.08', label: 'pacs.008 — FI-to-FI Customer Credit Transfer (MT103 equivalent)' },
  { value: 'pacs.009.001.08', label: 'pacs.009 — FI-to-FI Credit Transfer CORE/COV (MT202/MT205)' },
  { value: 'pacs.004.001.09', label: 'pacs.004 — Payment Return (MT103RETURN / MT202RETURN)' },
];

const SCHEME_OPTIONS = [
  { value: 'CBPR+', label: 'CBPR+ (Global Cross-Border, SWIFT FINplus)', color: '#00D4FF' },
  { value: 'LYNX', label: 'LYNX (Canada Domestic, Payments Canada)', color: '#FFB800' },
];

const SAMPLE_KEY_MAP: Record<string, Record<string, string>> = {
  'pacs.008.001.08': { 'CBPR+': 'pacs008/CBPR+', 'LYNX': 'pacs008/LYNX' },
  'pacs.009.001.08': { 'CBPR+': 'pacs009-core/CBPR+', 'LYNX': 'pacs009-core/LYNX' },
  'pacs.009.001.08-cov': { 'CBPR+': 'pacs009-cov/CBPR+', 'LYNX': 'pacs009-cov/LYNX' },
  'pacs.004.001.09': { 'CBPR+': 'pacs004/CBPR+', 'LYNX': 'pacs004/LYNX' },
};

interface MXTranslateResult {
  status: string;
  source_type: string;
  target_mt_type: string;
  scheme: string;
  variant: string;
  mt_raw?: string;
  uetr?: string;
  audit_id?: string;
  timestamp?: string;
  detail?: { error: string; message: string };
}

interface CoverResult {
  status: string;
  scheme: string;
  pacs009cov_xml?: string;
  cover_uetr?: string;
  original_uetr?: string;
  uetr_rule?: string;
  audit_id?: string;
  timestamp?: string;
  detail?: { error: string; message: string };
}

type Mode = 'mx-to-mt' | 'pacs008-to-cover';

export default function MXTranslatePage() {
  const [mode, setMode] = useState<Mode>('mx-to-mt');
  const [pacsType, setPacsType] = useState('pacs.008.001.08');
  const [scheme, setScheme] = useState('CBPR+');
  const [xmlInput, setXmlInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [result, setResult] = useState<MXTranslateResult | null>(null);
  const [coverResult, setCoverResult] = useState<CoverResult | null>(null);
  const [copied, setCopied] = useState(false);

  const schemeColor = SCHEME_OPTIONS.find((s) => s.value === scheme)?.color ?? '#00D4FF';

  const translate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!xmlInput.trim()) return;
    setLoading(true);
    setResult(null);
    setCoverResult(null);

    try {
      if (mode === 'mx-to-mt') {
        const res = await fetch(`${API_URL}/api/v1/mx-translate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            xml_content: xmlInput,
            source_type: pacsType,
            scheme,
          }),
        });
        const data: MXTranslateResult = await res.json();
        setResult(data);
      } else {
        const res = await fetch(`${API_URL}/api/v1/mx-translate/cover`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pacs008_xml: xmlInput, scheme }),
        });
        const data: CoverResult = await res.json();
        setCoverResult(data);
      }
    } catch {
      setResult({
        status: 'ERROR',
        source_type: pacsType,
        target_mt_type: '',
        scheme,
        variant: '',
        detail: {
          error: 'NETWORK_ERROR',
          message: 'Could not reach the translation API. Is the backend running?',
        },
      });
    } finally {
      setLoading(false);
    }
  };

  const loadSample = async () => {
    setLoadingSample(true);
    try {
      const sampleKey = SAMPLE_KEY_MAP[pacsType]?.[scheme] ?? `pacs008/${scheme}`;
      const [keyPart, schemePart] = sampleKey.split('/');
      const res = await fetch(`${API_URL}/api/v1/mx-translate/sample/${keyPart}/${schemePart}`);
      if (res.ok) {
        const data = await res.json();
        setXmlInput(data.sample_xml ?? '');
      }
    } catch {
      /* ignore */
    } finally {
      setLoadingSample(false);
    }
  };

  const copyOutput = async () => {
    const text = result?.mt_raw ?? coverResult?.pacs009cov_xml ?? '';
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadOutput = () => {
    if (result?.mt_raw) {
      const blob = new Blob([result.mt_raw], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.target_mt_type}_${Date.now()}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } else if (coverResult?.pacs009cov_xml) {
      const blob = new Blob([coverResult.pacs009cov_xml], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pacs009cov_${Date.now()}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const outputContent = result?.mt_raw ?? coverResult?.pacs009cov_xml ?? '';
  const isSuccess = result?.status === 'SUCCESS' || coverResult?.status === 'SUCCESS';
  const isError = result?.status === 'ERROR' || coverResult?.status === 'ERROR';

  return (
    <main className="page-container">
      {/* Header */}
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">MX → MT Reverse Translation Engine</h1>
        <p>
          Convert ISO 20022 XML messages back to raw SWIFT MT strings. Supports{' '}
          <span style={{ color: '#00D4FF', fontWeight: 700 }}>CBPR+</span> and{' '}
          <span style={{ color: '#FFB800', fontWeight: 700 }}>Canada LYNX</span> schemes —
          automatically routing pacs.009 CORE to MT202 (CBPR+) or{' '}
          <span style={{ color: '#FFB800', fontWeight: 700 }}>MT205</span> (LYNX).
          Also converts pacs.008 → pacs.009COV cover payments.
        </p>
      </div>

      {/* Mode selector */}
      <div className="animate-slide-up" style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {[
          { id: 'mx-to-mt' as Mode, label: 'MX → MT String', icon: '📤', desc: 'ISO 20022 XML → SWIFT message' },
          { id: 'pacs008-to-cover' as Mode, label: 'pacs.008 → Cover', icon: '🔄', desc: 'Direct to Cover (pacs.009COV)' },
        ].map((m) => (
          <button
            key={m.id}
            onClick={() => { setMode(m.id); setResult(null); setCoverResult(null); }}
            id={`mode-${m.id}`}
            style={{
              padding: '12px 20px',
              borderRadius: '10px',
              border: `2px solid ${mode === m.id ? 'var(--color-primary)' : 'var(--color-border)'}`,
              background: mode === m.id ? 'rgba(0,212,255,0.1)' : 'var(--color-panel)',
              color: mode === m.id ? 'var(--color-primary)' : 'var(--color-text-secondary)',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 600,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              alignItems: 'flex-start',
              transition: 'all 0.2s',
            }}
          >
            <span>{m.icon} {m.label}</span>
            <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--color-text-muted)' }}>{m.desc}</span>
          </button>
        ))}
      </div>

      {/* Scheme selector + LYNX badge */}
      <div className="animate-slide-up" style={{ display: 'flex', gap: '10px', marginBottom: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Scheme:</span>
        {SCHEME_OPTIONS.map((s) => (
          <button
            key={s.value}
            id={`scheme-${s.value.toLowerCase()}`}
            onClick={() => setScheme(s.value)}
            style={{
              padding: '8px 16px',
              borderRadius: '999px',
              border: `2px solid ${scheme === s.value ? s.color : 'var(--color-border)'}`,
              background: scheme === s.value ? `${s.color}20` : 'transparent',
              color: scheme === s.value ? s.color : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 700,
              transition: 'all 0.2s',
              letterSpacing: '0.02em',
            }}
          >
            {s.label}
          </button>
        ))}
        {scheme === 'LYNX' && (
          <span style={{
            padding: '4px 12px', borderRadius: '999px',
            background: 'rgba(255,184,0,0.15)', border: '1px solid rgba(255,184,0,0.4)',
            color: '#FFB800', fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em',
          }}>
            ⚡ pacs.009 → MT205 mode active
          </span>
        )}
      </div>

      {/* Split pane */}
      <div className="split-pane animate-slide-up">
        {/* Left: XML Input */}
        <div className="split-pane-panel">
          <div className="split-pane-header">
            <div className="split-pane-header-title">
              <FileInput size={16} />
              {mode === 'mx-to-mt' ? 'ISO 20022 XML Input' : 'pacs.008 XML Input'}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-ghost btn-sm" onClick={loadSample} disabled={loadingSample} id="load-sample-btn">
                {loadingSample ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                {loadingSample ? 'Loading...' : 'Load Sample'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setXmlInput(''); setResult(null); setCoverResult(null); }}>
                Clear
              </button>
            </div>
          </div>

          {mode === 'mx-to-mt' && (
            <div style={{ padding: '16px', flex: '0 0 auto' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="pacs-type">Source Message Type</label>
                <select
                  id="pacs-type"
                  className="select"
                  value={pacsType}
                  onChange={(e) => { setPacsType(e.target.value); setResult(null); }}
                >
                  {PACS_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="split-pane-body" style={{ padding: '0 16px', flex: 1, overflow: 'hidden' }}>
            <CodeMirror
              value={xmlInput}
              onChange={setXmlInput}
              extensions={[xml()]}
              theme={oneDark}
              style={{ height: '100%', fontSize: '12px', overflow: 'auto', minHeight: '300px' }}
              basicSetup={{ lineNumbers: true, foldGutter: true }}
              placeholder={`Paste ISO 20022 XML here...\n\nExample: <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">...</Document>`}
            />
          </div>

          <div style={{ padding: '16px', borderTop: '1px solid var(--color-border)', flexShrink: 0 }}>
            <form onSubmit={translate}>
              <button
                type="submit"
                id="translate-mx-btn"
                className="btn btn-primary btn-lg w-full"
                disabled={loading || !xmlInput.trim()}
                style={{ justifyContent: 'center', fontSize: '15px', background: `linear-gradient(135deg, ${schemeColor}, var(--color-primary))` }}
              >
                {loading ? (
                  <><Loader2 size={18} className="animate-spin" /> Translating...</>
                ) : (
                  <>{mode === 'mx-to-mt' ? 'Translate MX → MT' : 'Create Cover Payment'}<ArrowLeftRight size={18} /></>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right: Output */}
        <div className="split-pane-panel">
          <div className="split-pane-header">
            <div className="split-pane-header-title">
              <FileCode size={16} />
              {mode === 'mx-to-mt' ? 'SWIFT MT Output' : 'pacs.009 COV Output'}
              {isSuccess && result?.target_mt_type && (
                <span style={{
                  marginLeft: '8px', padding: '2px 10px', borderRadius: '999px',
                  background: `${schemeColor}25`, border: `1px solid ${schemeColor}60`,
                  color: schemeColor, fontSize: '11px', fontWeight: 700,
                }}>
                  {result.target_mt_type}
                </span>
              )}
            </div>
            {outputContent && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-ghost btn-sm" onClick={copyOutput} id="copy-output-btn">
                  {copied ? <CheckCheck size={12} color="var(--color-success)" /> : <Copy size={12} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={downloadOutput}>
                  <Download size={12} />
                  Download
                </button>
              </div>
            )}
          </div>

          <div className="split-pane-body" style={{ overflow: 'hidden' }}>
            {outputContent ? (
              <CodeMirror
                value={outputContent}
                extensions={coverResult ? [xml()] : []}
                theme={oneDark}
                readOnly
                style={{ height: '100%', fontSize: '12px', overflow: 'auto' }}
                basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: false }}
              />
            ) : (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', height: '100%', gap: '16px',
                color: 'var(--color-text-muted)', padding: '40px', textAlign: 'center',
              }}>
                <ArrowRightLeft size={48} strokeWidth={1} />
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
                    {mode === 'mx-to-mt' ? 'SWIFT MT string will appear here' : 'pacs.009 COV XML will appear here'}
                  </div>
                  <div style={{ fontSize: '13px' }}>
                    Paste ISO 20022 XML and click Translate
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Result metadata */}
      {isSuccess && (
        <div className="animate-slide-up" style={{ marginTop: '20px' }}>
          <div className="section-header">Translation Result</div>

          {/* UETR display */}
          {(result?.uetr || coverResult?.original_uetr) && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px' }}>
                UETR — Unique End-to-End Transaction Reference
              </div>
              <div className="uetr-display">
                <span>{result?.uetr ?? coverResult?.original_uetr}</span>
                <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(result?.uetr ?? coverResult?.original_uetr ?? '')}>
                  <Copy size={13} />
                </button>
              </div>
              {coverResult?.cover_uetr && (
                <div style={{ marginTop: '8px' }}>
                  <div style={{ fontSize: '11px', color: '#FFB800', fontWeight: 600, marginBottom: '4px' }}>Cover Leg UETR ({coverResult.uetr_rule})</div>
                  <div className="uetr-display" style={{ borderColor: 'rgba(255,184,0,0.4)' }}>
                    <span>{coverResult.cover_uetr}</span>
                    <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(coverResult.cover_uetr ?? '')}>
                      <Copy size={13} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Metadata grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
            {[
              result && { label: 'Target MT Type', value: result.target_mt_type, color: schemeColor },
              result && { label: 'Variant', value: result.variant, color: 'var(--color-text-secondary)' },
              result && { label: 'Scheme', value: result.scheme, color: schemeColor },
              (result || coverResult) && { label: 'Audit ID', value: (result?.audit_id ?? coverResult?.audit_id ?? '').slice(0, 16) + '…', color: 'var(--color-text-muted)' },
              (result || coverResult) && {
                label: 'Timestamp',
                value: new Date((result?.timestamp ?? coverResult?.timestamp ?? '')).toLocaleTimeString(),
                color: 'var(--color-text-muted)',
              },
            ].filter(Boolean).map((item: any) => (
              <div key={item.label} style={{ padding: '14px 16px', background: 'var(--color-panel)', border: '1px solid var(--color-border)', borderRadius: '10px' }}>
                <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px' }}>{item.label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error display */}
      {isError && (
        <div className="animate-slide-up" style={{ marginTop: '20px', padding: '20px 24px', background: 'rgba(255,68,68,0.05)', border: '1px solid rgba(255,68,68,0.25)', borderRadius: '12px' }}>
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-danger)', marginBottom: '12px' }}>
            TRANSLATION FAILED
          </div>
          <pre className="code-block" style={{ color: 'var(--color-danger)', fontSize: '12px' }}>
            {JSON.stringify(result?.detail ?? coverResult?.detail ?? { error: 'UNKNOWN' }, null, 2)}
          </pre>
        </div>
      )}

      {/* Scheme info card */}
      <div className="animate-slide-up" style={{ marginTop: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {[
          {
            scheme: 'CBPR+', color: '#00D4FF',
            items: ['pacs.008 → MT103', 'pacs.009 CORE → MT202', 'pacs.009 COV → MT202COV', 'pacs.004 (pacs.008 return) → MT103RETURN', 'pacs.004 (pacs.009 return) → MT202RETURN'],
          },
          {
            scheme: 'LYNX 🍁', color: '#FFB800',
            items: ['pacs.008 → MT103', 'pacs.009 CORE → MT205', 'pacs.009 COV → MT205COV', 'pacs.004 (any) → MT205RETURN', 'UETR: COV carries SAME UETR as pacs.008'],
          },
        ].map((s) => (
          <div key={s.scheme} style={{ padding: '16px 20px', background: 'var(--color-panel)', border: `1px solid ${s.color}30`, borderRadius: '12px' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: s.color, marginBottom: '12px', letterSpacing: '0.04em' }}>
              {s.scheme} Translation Rules
            </div>
            <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: '1.8' }}>
              {s.items.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </main>
  );
}
