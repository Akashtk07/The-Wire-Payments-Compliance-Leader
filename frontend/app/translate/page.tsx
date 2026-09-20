'use client';

import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import {
  ArrowRight, Copy, Download, Loader2, RefreshCw,
  CheckCheck, Code2, FileInput, ToggleLeft, ToggleRight,
  AlertTriangle, Shield, Zap, Info,
} from 'lucide-react';
import ValidationBadge from '@/components/ValidationBadge';
import { xml } from '@codemirror/lang-xml';
import { oneDark } from '@codemirror/theme-one-dark';

const CodeMirror = dynamic(
  () => import('@uiw/react-codemirror').then((m) => m.default),
  { ssr: false }
);

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── All supported MT types (both CBPR+ and LYNX) ──────────────────────────
const MT_TYPES = [
  // CBPR+ standard types
  { value: 'MT103',        label: 'MT103 — Customer Credit Transfer',           scheme: 'CBPR+', target: 'pacs.008.001.08' },
  { value: 'MT103STP',     label: 'MT103 STP — Straight Through Processing',    scheme: 'CBPR+', target: 'pacs.008.001.08' },
  { value: 'MT202',        label: 'MT202 — FI-to-FI Credit Transfer (CORE)',    scheme: 'CBPR+', target: 'pacs.009.001.08' },
  { value: 'MT202COV',     label: 'MT202 COV — Cover Payment',                  scheme: 'CBPR+', target: 'pacs.009.001.08' },
  { value: 'MT204',        label: 'MT204 — Financial Market Direct Debit',      scheme: 'CBPR+', target: 'pacs.009.001.08' },
  // Return messages
  { value: 'MT103RETURN',  label: 'MT103 RETURN — Customer Payment Return',     scheme: 'CBPR+', target: 'pacs.004.001.09' },
  { value: 'MT202RETURN',  label: 'MT202 RETURN — FI Payment Return (CBPR+)',   scheme: 'CBPR+', target: 'pacs.004.001.09' },
  // LYNX Canadian domestic types
  { value: 'MT205',        label: 'MT205 — Canadian Domestic FI Transfer 🍁',   scheme: 'LYNX',  target: 'pacs.009.001.08' },
  { value: 'MT205COV',     label: 'MT205 COV — Canadian Cover Payment 🍁',      scheme: 'LYNX',  target: 'pacs.009.001.08' },
  { value: 'MT205RETURN',  label: 'MT205 RETURN — LYNX Payment Return 🍁',      scheme: 'LYNX',  target: 'pacs.004.001.09' },
];

interface TranslationResult {
  status: 'PASS' | 'SUCCESS' | 'PARTIAL' | 'VALIDATION_EXCEPTION' | 'ERROR';
  xml_output?: string;
  iso20022_xml?: string;
  uetr?: string;
  message_type_mapped?: string;
  audit_id?: string;
  timestamp?: string;
  errors?: string[];
  validation_exception?: {
    error_code: string;
    message: string;
    action: string;
  };
}

// ── Full-featured sample messages ─────────────────────────────────────────
const SAMPLES: Record<string, string> = {
  MT103: `{1:F01DEUTDEBB1XXX0000000000}{2:I103BNPAFRPPXXXXN}{3:{108:MT103SAMPLE}{121:eb1e6758-7116-4176-b538-7eb43ff895f3}}{4:
:20:REF20260523001
:23B:CRED
:32A:260523USD50000,00
:50K:/12345678
ACME CORPORATION
123 MAIN STREET
NEW YORK NY 10001
:52A:DEUTDEDB
:57A:BNPAFRPP
:59:/DE89370400440532013000
HANS MUELLER GMBH
HAUPTSTRASSE 1
10115 BERLIN
:70:PAYMENT FOR SERVICES INV-2023-456
:71A:SHA
-}{5:{CHK:ABCDEF012345}}`,

  MT103STP: `{1:F01CITIUS33XXXX0000000000}{2:I103BARCGB22XXXXN}{3:{119:STP}{121:cdd4e105-00c3-4593-83ee-63c3ce0bb66a}}{4:
:20:STP20260523001
:23B:CRED
:32A:260523GBP25000,00
:50A:CITIUS33
:52A:CITIUS33
:57A:BARCGB22
:59A:BARCGB22
:71A:OUR
-}{5:{CHK:ABCDEF012345}}`,

  MT202: `{1:F01CHASUS33XXXX0000000000}{2:I202DEUTDEBB1XXXN}{3:{121:3efecd64-ff91-4811-ad77-3ee74cbc4e7e}}{4:
:20:CHASREF20260523
:21:RELATED20260523
:32A:260523USD100000,00
:52A:CHASUS33
:57A:DEUTDEBB
:58A:DEUTDEBB
-}{5:{CHK:ABCDEF012345}}`,

  MT202COV: `{1:F01BNPAFRPPXXXX0000000000}{2:I202CHASUS33XXXXN}{3:{119:COV}{121:55f635c9-15bd-4454-a984-f6ad92db21b3}}{4:
:20:COVREF20260523
:21:UNDERLYING001
:32A:260523EUR75000,00
:52A:BNPAFRPP
:57A:CHASUS33
:58A:CHASUS33
:50K:/FR7630006000011234567890189
JEAN DUPONT
12 RUE DE LA PAIX
75001 PARIS
:59:/US12345678901234
JOHN DOE INC
100 BROADWAY
NEW YORK NY
-}{5:{CHK:ABCDEF012345}}`,

  MT204: `{1:F01MARKDEFFXXXX0000000000}{2:I204DEUTDEBB1XXXN}{3:{121:b58eea24-980f-488d-9d49-8ba5d8bca52b}}{4:
:20:DD20260523001
:19:EUR500000,00
:25:DE89370400440532013000
:30:260523
-}{5:{CHK:ABCDEF012345}}`,

  MT103RETURN: `{1:F01BNPAFRPPXXXX0000000000}{2:I103DEUTDEBB1XXXN}{3:{121:f8ce4d75-8605-46b4-9e72-6630f0f80cd3}}{4:
:20:RET20260523001
:21:REF20260523001
:32A:260523USD50000,00
:52A:BNPAFRPP
:58A:DEUTDEBB
:72:/RETN/AC04 Account Closed
-}{5:{CHK:ABCDEF012345}}`,

  MT202RETURN: `{1:F01DEUTDEBB1XXX0000000000}{2:I202CHASUS33XXXXN}{3:{121:ea1a9e6f-4d9a-4d5b-8299-f0f9c97e932e}}{4:
:20:RET202-20260523
:21:CHASREF20260523
:32A:260523USD100000,00
:52A:DEUTDEBB
:58A:CHASUS33
:72:/RETN/DUPL Duplicate Payment
-}{5:{CHK:ABCDEF012345}}`,

  MT205: `{1:F01ROYCCAT2XXXX0000000000}{2:I205TDOMCATTXXXXN}{3:{121:7a4906e0-3106-4c52-9f9a-52eeb8b05299}}{4:
:20:LYNX20260523001
:21:RELATED20260523
:32A:260523CAD200000,00
:52A:ROYCCAT2
:57A:TDOMCATT
:58A:TDOMCATT
-}{5:{CHK:ABCDEF012345}}`,

  MT205COV: `{1:F01ROYCCAT2XXXX0000000000}{2:I205BOFMCAM2XXXXN}{3:{119:COV}{121:763cbdb0-1bd0-41af-82d2-f58006c3d464}}{4:
:20:COVLYNX20260523
:21:UNDERLYING002
:32A:260523CAD150000,00
:52A:ROYCCAT2
:57A:BOFMCAM2
:58A:BOFMCAM2
:50K:/CA59007700016306002005
MAPLE LEAF CORP
100 KING STREET W
TORONTO ON M5X 1A9
:59:/CA21000000011234567891
CANUCK INDUSTRIES
200 BAY STREET
TORONTO ON
-}{5:{CHK:ABCDEF012345}}`,

  MT205RETURN: `{1:F01TDOMCATTXXXX0000000000}{2:I205ROYCCAT2XXXXN}{3:{121:fce61f2c-9b9d-4e81-b474-edb74ee31d4c}}{4:
:20:RETLYNX20260523
:21:LYNX20260523001
:32A:260523CAD200000,00
:52A:TDOMCATT
:58A:ROYCCAT2
:72:/RETN/AC04 Account Closed
-}{5:{CHK:ABCDEF012345}}`,
};

export default function TranslatePage() {
  const [msgType, setMsgType] = useState('MT103');
  const [rawInput, setRawInput] = useState('');
  const [outputXml, setOutputXml] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [result, setResult] = useState<TranslationResult | null>(null);
  const [copied, setCopied] = useState(false);
  // Full translation mode: skips strict CBPR+ validation, forces XML output even with warnings
  const [fullMode, setFullMode] = useState(false);

  const selectedType = MT_TYPES.find((t) => t.value === msgType) ?? MT_TYPES[0];

  const translate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawInput.trim()) return;
    setLoading(true);
    setResult(null);
    setOutputXml('');

    try {
      const body: Record<string, unknown> = {
        source_type: msgType,
        mt_raw: rawInput,
      };
      // Full mode: tell backend to skip validation and force output
      if (fullMode) body.force_output = true;

      const res = await fetch(`${API_URL}/api/v1/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data: TranslationResult = await res.json();
      setResult(data);

      const xmlOut = data.xml_output ?? data.iso20022_xml ?? '';
      if (xmlOut) {
        setOutputXml(xmlOut);
      } else if (data.status === 'VALIDATION_EXCEPTION' || data.status === 'ERROR') {
        setOutputXml('');
      } else {
        setOutputXml(JSON.stringify(data, null, 2));
      }
    } catch {
      setResult({
        status: 'ERROR',
        validation_exception: {
          error_code: 'NETWORK_ERROR',
          message: 'Could not reach the translation API. Is the backend running?',
          action: 'Verify the backend is running on port 8000.',
        },
      });
    } finally {
      setLoading(false);
    }
  };

  const loadSample = async () => {
    setLoadingSample(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/translate/sample/${msgType}`);
      if (res.ok) {
        const data = await res.json();
        setRawInput(data.sample_mt ?? data.sample ?? data.raw_message ?? JSON.stringify(data));
      } else {
        setRawInput(SAMPLES[msgType] ?? SAMPLES.MT103);
      }
    } catch {
      setRawInput(SAMPLES[msgType] ?? SAMPLES.MT103);
    } finally {
      setLoadingSample(false);
    }
  };

  const copyToClipboard = async () => {
    if (!outputXml) return;
    await navigator.clipboard.writeText(outputXml);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadXml = () => {
    if (!outputXml) return;
    const blob = new Blob([outputXml], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `iso20022_${msgType}_${Date.now()}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setRawInput('');
    setOutputXml('');
    setResult(null);
  };

  const isLynx = selectedType.scheme === 'LYNX';
  const isPartial = result?.status === 'PARTIAL';
  const isSuccess = result?.status === 'PASS' || result?.status === 'SUCCESS';

  return (
    <main className="page-container">
      {/* Header */}
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Transaction Translation &amp; Validation Engine</h1>
        <p>
          Deterministic MT→MX translation with full{' '}
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '5px',
            padding: '2px 8px', borderRadius: '5px',
            background: isLynx ? 'rgba(255,184,0,0.12)' : 'rgba(0,229,160,0.12)',
            color: isLynx ? 'var(--color-warning)' : 'var(--color-success)',
            border: `1px solid ${isLynx ? 'rgba(255,184,0,0.3)' : 'rgba(0,229,160,0.3)'}`,
            fontSize: '12px', fontWeight: 700, letterSpacing: '0.05em',
          }}>
            {isLynx ? '🍁 LYNX' : 'CBPR+ R2025'}
          </span>{' '}
          compliance — UETR generation, hybrid PostalAddress, ChrgBr = SHAR enforcement,
          XSD validation and immutable audit trail.
        </p>
      </div>

      {/* Mode Controls Row */}
      <div className="animate-fade-in" style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        marginBottom: '20px', flexWrap: 'wrap',
      }}>
        {/* Translation Mode Switch */}
        <button
          id="full-mode-toggle"
          onClick={() => setFullMode((v) => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 18px', borderRadius: '10px', cursor: 'pointer',
            border: `1px solid ${fullMode ? 'rgba(0,212,255,0.4)' : 'rgba(255,255,255,0.1)'}`,
            background: fullMode ? 'rgba(0,212,255,0.08)' : 'var(--color-panel)',
            color: fullMode ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            transition: 'all 0.2s ease', fontWeight: 600, fontSize: '13px',
          }}
          title={fullMode
            ? 'Full mode: forces XML output even when validation warnings exist'
            : 'Partial mode: strict CBPR+ validation — halts on errors'}
        >
          {fullMode ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
          {fullMode ? 'Full Translation Mode' : 'Partial (Strict) Mode'}
        </button>

        {/* Mode Info Badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '8px 14px', borderRadius: '8px', fontSize: '12px',
          background: fullMode ? 'rgba(0,212,255,0.05)' : 'rgba(255,184,0,0.05)',
          border: `1px solid ${fullMode ? 'rgba(0,212,255,0.2)' : 'rgba(255,184,0,0.2)'}`,
          color: fullMode ? 'var(--color-primary)' : 'var(--color-warning)',
        }}>
          {fullMode ? <Zap size={13} /> : <Shield size={13} />}
          {fullMode
            ? 'Generates ISO 20022 XML even with validation warnings — suitable for testing'
            : 'Strict: halts on CBPR+ rule violations — suitable for production'}
        </div>

        {/* Scheme indicator */}
        <div style={{
          marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px',
          padding: '8px 14px', borderRadius: '8px', fontSize: '12px', fontWeight: 700,
          background: isLynx ? 'rgba(255,184,0,0.08)' : 'rgba(0,229,160,0.08)',
          border: `1px solid ${isLynx ? 'rgba(255,184,0,0.25)' : 'rgba(0,229,160,0.25)'}`,
          color: isLynx ? 'var(--color-warning)' : 'var(--color-success)',
        }}>
          <Info size={13} />
          {isLynx ? '🍁 LYNX Scheme' : 'CBPR+ Scheme'} → {selectedType.target}
        </div>
      </div>

      {/* Split Pane */}
      <div className="split-pane animate-slide-up">
        {/* Left: MT Input */}
        <div className="split-pane-panel">
          <div className="split-pane-header">
            <div className="split-pane-header-title">
              <FileInput size={16} />
              MT Input
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={loadSample}
                disabled={loadingSample}
                aria-label="Load sample message"
              >
                {loadingSample ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                {loadingSample ? 'Loading...' : 'Load Sample'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={reset} aria-label="Clear inputs">
                Clear
              </button>
            </div>
          </div>

          <div style={{ padding: '16px', flex: '0 0 auto' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="source-msg-type">
                Source Message Type
              </label>
              <select
                id="source-msg-type"
                className="select"
                value={msgType}
                onChange={(e) => {
                  setMsgType(e.target.value);
                  setResult(null);
                  setOutputXml('');
                  setRawInput('');
                }}
              >
                <optgroup label="── CBPR+ Standard ──────────────────">
                  {MT_TYPES.filter((t) => t.scheme === 'CBPR+' && !t.value.includes('RETURN')).map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
                <optgroup label="── CBPR+ Returns ───────────────────">
                  {MT_TYPES.filter((t) => t.scheme === 'CBPR+' && t.value.includes('RETURN')).map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
                <optgroup label="── LYNX Canadian Domestic 🍁 ────────">
                  {MT_TYPES.filter((t) => t.scheme === 'LYNX').map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>

          <div className="split-pane-body" style={{ padding: '0 16px', flex: 1, overflow: 'hidden' }}>
            <textarea
              id="mt-raw-input"
              className="textarea"
              style={{
                height: '100%', resize: 'none', fontSize: '12px',
                minHeight: '320px', borderRadius: '8px', fontFamily: 'var(--font-mono)',
              }}
              placeholder={`Paste raw ${msgType} message here...`}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              spellCheck={false}
              aria-label="Raw MT message input"
            />
          </div>

          <div style={{ padding: '16px', borderTop: '1px solid var(--color-border)', flexShrink: 0 }}>
            <form onSubmit={translate}>
              <button
                type="submit"
                id="translate-btn"
                className="btn btn-primary btn-lg w-full"
                disabled={loading || !rawInput.trim()}
                style={{ justifyContent: 'center', fontSize: '15px' }}
              >
                {loading ? (
                  <><Loader2 size={18} className="animate-spin" /> Translating &amp; Validating...</>
                ) : (
                  <>{msgType} → {selectedType.target} <ArrowRight size={18} /></>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right: XML Output */}
        <div className="split-pane-panel">
          <div className="split-pane-header">
            <div className="split-pane-header-title">
              <Code2 size={16} />
              ISO 20022 XML Output
              {isPartial && (
                <span style={{
                  fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                  background: 'rgba(255,184,0,0.15)', color: 'var(--color-warning)',
                  border: '1px solid rgba(255,184,0,0.3)', fontWeight: 700,
                }}>PARTIAL</span>
              )}
            </div>
            {outputXml && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-ghost btn-sm" onClick={copyToClipboard} aria-label="Copy XML">
                  {copied ? <CheckCheck size={12} color="var(--color-success)" /> : <Copy size={12} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={downloadXml} aria-label="Download XML">
                  <Download size={12} />
                  Download .xml
                </button>
              </div>
            )}
          </div>

          <div className="split-pane-body" style={{ overflow: 'hidden' }}>
            {outputXml ? (
              <CodeMirror
                value={outputXml}
                extensions={[xml()]}
                theme={oneDark}
                readOnly
                style={{ height: '100%', fontSize: '13px', overflow: 'auto' }}
                basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: false }}
              />
            ) : (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', height: '100%', gap: '16px',
                color: 'var(--color-text-muted)', padding: '40px', textAlign: 'center',
              }}>
                <Code2 size={40} strokeWidth={1} />
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
                    ISO 20022 XML will appear here
                  </div>
                  <div style={{ fontSize: '13px' }}>
                    Select a message type, load a sample, and click Translate
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Validation Badge */}
      <ValidationBadge
        status={loading ? 'PENDING' : (result?.status ?? null) as any}
        validationException={result?.validation_exception ?? null}
        errors={result?.errors}
      />

      {/* PARTIAL Status — show XML warnings inline */}
      {isPartial && result?.errors && result.errors.length > 0 && (
        <div className="animate-slide-up" style={{
          marginTop: '16px', padding: '16px 20px',
          background: 'rgba(255,184,0,0.05)', border: '1px solid rgba(255,184,0,0.25)',
          borderRadius: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <AlertTriangle size={16} color="var(--color-warning)" />
            <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--color-warning)', letterSpacing: '0.04em' }}>
              PARTIAL TRANSLATION — {result.errors.length} VALIDATION WARNING{result.errors.length > 1 ? 'S' : ''}
            </span>
            {outputXml && (
              <span style={{
                marginLeft: 'auto', fontSize: '11px', padding: '2px 8px',
                background: 'rgba(0,212,255,0.1)', color: 'var(--color-primary)',
                borderRadius: '4px', border: '1px solid rgba(0,212,255,0.25)',
              }}>
                XML generated with warnings
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {result.errors.map((err, i) => (
              <div key={i} style={{
                padding: '8px 12px', borderRadius: '6px', fontSize: '12px',
                fontFamily: 'var(--font-mono)', lineHeight: 1.5,
                background: 'rgba(255,184,0,0.06)', border: '1px solid rgba(255,184,0,0.15)',
                color: 'var(--color-text-secondary)',
              }}>
                <span style={{ color: 'var(--color-warning)', fontWeight: 700 }}>#{i + 1}</span>{' '}{err}
              </div>
            ))}
          </div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--color-text-muted)' }}>
            💡 Switch to <strong style={{ color: 'var(--color-primary)' }}>Full Translation Mode</strong> above to suppress strict validation and always generate XML output.
          </div>
        </div>
      )}

      {/* Success Metadata */}
      {(isSuccess || isPartial) && result?.uetr && (
        <div className="animate-slide-up" style={{ marginTop: '20px' }}>
          <div className="section-header">Translation Metadata</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '16px', alignItems: 'start' }}>
            <div>
              <div style={{
                fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600,
                letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px',
              }}>
                UETR — Unique End-to-End Transaction Reference
              </div>
              <div className="uetr-display">
                <span>{result.uetr}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => navigator.clipboard.writeText(result.uetr!)}
                  aria-label="Copy UETR"
                ><Copy size={13} /></button>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginTop: '16px' }}>
            {[
              { label: 'Source MT Type', value: msgType, color: 'var(--color-primary)' },
              { label: 'Target MX Type', value: selectedType.target, color: 'var(--color-secondary)' },
              { label: 'Audit ID', value: result.audit_id ? result.audit_id.slice(0, 14) + '…' : '—', color: 'var(--color-text-secondary)' },
              { label: 'Timestamp', value: result.timestamp ? new Date(result.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString(), color: 'var(--color-text-secondary)' },
            ].map((item) => (
              <div key={item.label} style={{
                padding: '14px 16px', background: 'var(--color-panel)',
                border: '1px solid var(--color-border)', borderRadius: '10px',
              }}>
                <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px' }}>
                  {item.label}
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: item.color, wordBreak: 'break-all' }}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hard Error Card */}
      {(result?.status === 'VALIDATION_EXCEPTION' || result?.status === 'ERROR') && result.validation_exception && (
        <div className="animate-slide-up" style={{
          marginTop: '20px', padding: '20px 24px',
          background: 'rgba(255,68,68,0.05)', border: '1px solid rgba(255,68,68,0.25)', borderRadius: '12px',
        }}>
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-danger)', marginBottom: '12px', letterSpacing: '0.05em' }}>
            TRANSLATION FAILED — VALIDATION EXCEPTION
          </div>
          <pre className="code-block" style={{ color: 'var(--color-danger)', fontSize: '12px' }}>
{JSON.stringify({
  error_code: result.validation_exception.error_code,
  message: result.validation_exception.message,
  action: result.validation_exception.action,
}, null, 2)}
          </pre>
        </div>
      )}

      {/* Message Type Reference Table */}
      <div className="animate-slide-up" style={{ marginTop: '28px' }}>
        <div className="section-header">Supported Message Types — Full Mapping Table</div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{
            width: '100%', borderCollapse: 'collapse',
            fontSize: '12px', fontFamily: 'var(--font-mono)',
          }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['MT Type', 'Scheme', 'ISO 20022 Target', 'Description'].map((h) => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.05em', fontSize: '11px', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MT_TYPES.map((t) => (
                <tr
                  key={t.value}
                  onClick={() => { setMsgType(t.value); setResult(null); setOutputXml(''); setRawInput(''); }}
                  style={{
                    borderBottom: '1px solid var(--color-border)',
                    background: msgType === t.value ? 'rgba(0,212,255,0.05)' : 'transparent',
                    cursor: 'pointer', transition: 'background 0.15s',
                  }}
                >
                  <td style={{ padding: '10px 14px', color: 'var(--color-primary)', fontWeight: 700 }}>{t.value}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      padding: '2px 7px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                      background: t.scheme === 'LYNX' ? 'rgba(255,184,0,0.1)' : 'rgba(0,229,160,0.1)',
                      color: t.scheme === 'LYNX' ? 'var(--color-warning)' : 'var(--color-success)',
                    }}>{t.scheme}</span>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-secondary)' }}>{t.target}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-sans)', fontSize: '12px' }}>{t.label.split(' — ')[1] ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
