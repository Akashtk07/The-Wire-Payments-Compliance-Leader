'use client';

import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  Settings,
  X,
  ChevronDown,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Zap,
  RefreshCw,
  History,
  Key,
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Model {
  id: string;
  label: string;
}

interface ProviderModels {
  [provider: string]: Model[];
}

interface CurrentConfig {
  provider: string;
  model: string;
  api_key_preview: string | null;
  api_key_set: boolean;
  ollama_base_url: string;
  available_providers: string[];
  available_models: Model[];
}

interface HistoryEntry {
  change_id: string;
  timestamp: string;
  provider: string;
  model: string;
  api_key_preview: string | null;
  changed_by: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  gemini: '✦ Google Gemini',
  groq:   '⚡ Groq',
  openai: '◆ OpenAI',
  ollama: '◉ Ollama (Local)',
};

const PROVIDER_COLORS: Record<string, string> = {
  gemini: '#4285F4',
  groq:   '#F55036',
  openai: '#10A37F',
  ollama: '#FFB800',
};

export default function LLMConfigPanel() {
  const [mounted, setMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [tab, setTab] = useState<'config' | 'history'>('config');

  // Config state
  const [currentConfig, setCurrentConfig] = useState<CurrentConfig | null>(null);
  const [allModels, setAllModels]         = useState<ProviderModels>({});
  const [history, setHistory]             = useState<HistoryEntry[]>([]);

  // Form state
  const [selectedProvider, setSelectedProvider] = useState('gemini');
  const [selectedModel, setSelectedModel]       = useState('');
  const [apiKey, setApiKey]                     = useState('');
  const [ollamaUrl, setOllamaUrl]               = useState('http://localhost:11434');
  const [showKey, setShowKey]                   = useState(false);

  // Status
  const [saving, setSaving]       = useState(false);
  const [testing, setTesting]     = useState(false);
  const [testResult, setTestResult]   = useState<{ status: string; message: string } | null>(null);
  const [saveResult, setSaveResult]   = useState<{ ok: boolean; msg: string } | null>(null);

  // Portal requires the component to be mounted on the client
  useEffect(() => { setMounted(true); }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const [cfgRes, modelsRes, histRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/llm-config`),
        fetch(`${API_URL}/api/v1/llm-config/models`),
        fetch(`${API_URL}/api/v1/llm-config/history`),
      ]);
      if (cfgRes.ok) {
        const cfg: CurrentConfig = await cfgRes.json();
        setCurrentConfig(cfg);
        setSelectedProvider(cfg.provider);
        setSelectedModel(cfg.model);
        setOllamaUrl(cfg.ollama_base_url);
      }
      if (modelsRes.ok) {
        const data = await modelsRes.json();
        setAllModels(data.providers);
      }
      if (histRes.ok) {
        const data = await histRes.json();
        setHistory(data.history);
      }
    } catch { /* backend may be starting */ }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchConfig();
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen, fetchConfig]);

  // Auto-select first model when provider changes
  useEffect(() => {
    if (allModels[selectedProvider]?.length) {
      const models = allModels[selectedProvider];
      if (!models.find((m) => m.id === selectedModel)) {
        setSelectedModel(models[0].id);
      }
    }
  }, [selectedProvider, allModels, selectedModel]);

  const handleSave = async () => {
    setSaving(true);
    setSaveResult(null);
    setTestResult(null);
    try {
      const body: Record<string, string> = {
        provider: selectedProvider,
        model: selectedModel,
      };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      if (selectedProvider === 'ollama') body.ollama_base_url = ollamaUrl;

      const res = await fetch(`${API_URL}/api/v1/llm-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setCurrentConfig(data.config);
        setApiKey('');
        setSaveResult({
          ok: true,
          msg: `Switched to ${PROVIDER_LABELS[selectedProvider]} · ${selectedModel}`,
        });
        const histRes = await fetch(`${API_URL}/api/v1/llm-config/history`);
        if (histRes.ok) setHistory((await histRes.json()).history);
      } else {
        setSaveResult({ ok: false, msg: data.detail?.message ?? 'Update failed.' });
      }
    } catch {
      setSaveResult({ ok: false, msg: 'Network error — backend unreachable.' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/llm-config/test`, { method: 'POST' });
      const data = await res.json();
      setTestResult({ status: data.status, message: data.message });
    } catch {
      setTestResult({ status: 'error', message: 'Network error — backend unreachable.' });
    } finally {
      setTesting(false);
    }
  };

  const models = allModels[selectedProvider] ?? [];
  const activeColor = PROVIDER_COLORS[currentConfig?.provider ?? 'gemini'] ?? '#00D4FF';

  // -------------------------------------------------------------------------
  // Portal modal (renders at body level, not inside sidebar DOM)
  // -------------------------------------------------------------------------
  const modal = isOpen && mounted ? createPortal(
    <>
      {/* Backdrop */}
      <div
        onClick={() => setIsOpen(false)}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.72)',
          backdropFilter: 'blur(6px)',
          WebkitBackdropFilter: 'blur(6px)',
          zIndex: 9998,
          animation: 'llmFadeIn 0.15s ease',
        }}
      />

      {/* Panel — centered over the ENTIRE viewport */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="LLM Configuration"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '540px',
          maxWidth: 'calc(100vw - 32px)',
          maxHeight: '88vh',
          overflowY: 'auto',
          background: 'var(--color-surface)',
          border: '1px solid rgba(255,255,255,0.14)',
          borderRadius: '18px',
          boxShadow: '0 32px 96px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.05)',
          zIndex: 9999,
          animation: 'llmSlideUp 0.22s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '22px 26px 18px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          position: 'sticky', top: 0,
          background: 'var(--color-surface)',
          borderRadius: '18px 18px 0 0',
          zIndex: 1,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px', height: '40px', borderRadius: '12px',
              background: `linear-gradient(135deg, ${activeColor}30, ${activeColor}10)`,
              border: `1px solid ${activeColor}50`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: `0 4px 16px ${activeColor}20`,
            }}>
              <Zap size={20} color={activeColor} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '16px', color: 'var(--color-text-primary)', letterSpacing: '-0.01em' }}>
                LLM Configuration
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Switch providers · models · API keys in real-time
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            aria-label="Close"
            style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px', cursor: 'pointer', color: 'var(--color-text-secondary)',
              padding: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { (e.currentTarget).style.background = 'rgba(255,255,255,0.12)'; (e.currentTarget).style.color = 'var(--color-text-primary)'; }}
            onMouseLeave={(e) => { (e.currentTarget).style.background = 'rgba(255,255,255,0.06)'; (e.currentTarget).style.color = 'var(--color-text-secondary)'; }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Active config banner */}
        {currentConfig && (
          <div style={{ padding: '14px 26px 0' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
              padding: '10px 16px', borderRadius: '12px',
              background: `${activeColor}12`, border: `1px solid ${activeColor}30`,
            }}>
              <div style={{
                width: '9px', height: '9px', borderRadius: '50%',
                background: activeColor, flexShrink: 0,
                boxShadow: `0 0 8px ${activeColor}`,
              }} />
              <span style={{ fontSize: '12px', color: activeColor, fontWeight: 700, letterSpacing: '0.04em' }}>
                ACTIVE:
              </span>
              <span style={{ fontSize: '13px', color: 'var(--color-text-primary)', fontWeight: 600 }}>
                {PROVIDER_LABELS[currentConfig.provider]} · {currentConfig.model}
              </span>
              {currentConfig.api_key_preview && (
                <span style={{
                  fontSize: '11px', color: 'var(--color-text-muted)',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex', alignItems: 'center', gap: '4px',
                }}>
                  <Key size={10} /> {currentConfig.api_key_preview}
                </span>
              )}
              {!currentConfig.api_key_set && currentConfig.provider !== 'ollama' && (
                <span style={{
                  fontSize: '11px', color: '#FF6B6B', fontWeight: 700,
                  background: 'rgba(255,107,107,0.12)', padding: '2px 8px',
                  borderRadius: '4px', border: '1px solid rgba(255,107,107,0.25)',
                }}>
                  ⚠ No API key
                </span>
              )}
            </div>
          </div>
        )}

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '4px', padding: '16px 26px 0' }}>
          {(['config', 'history'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '8px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer',
                fontSize: '13px', fontWeight: 600, transition: 'all 0.15s',
                background: tab === t ? 'rgba(255,255,255,0.1)' : 'transparent',
                color: tab === t ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
                display: 'flex', alignItems: 'center', gap: '7px',
              }}
            >
              {t === 'config' ? <Settings size={13} /> : <History size={13} />}
              {t === 'config' ? 'Configure' : `History (${history.length})`}
            </button>
          ))}
        </div>

        <div style={{ padding: '18px 26px 28px' }}>
          {tab === 'config' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

              {/* Provider selector */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
                  Provider
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '9px' }}>
                  {Object.entries(PROVIDER_LABELS).map(([key, label]) => {
                    const color = PROVIDER_COLORS[key];
                    const isSelected = selectedProvider === key;
                    return (
                      <button
                        key={key}
                        id={`provider-btn-${key}`}
                        onClick={() => { setSelectedProvider(key); setSaveResult(null); setTestResult(null); }}
                        style={{
                          padding: '12px 14px', borderRadius: '12px', cursor: 'pointer',
                          border: isSelected ? `1.5px solid ${color}70` : '1px solid rgba(255,255,255,0.08)',
                          background: isSelected ? `${color}18` : 'rgba(255,255,255,0.03)',
                          color: isSelected ? color : 'var(--color-text-muted)',
                          fontSize: '13px', fontWeight: isSelected ? 700 : 500,
                          textAlign: 'left', transition: 'all 0.15s',
                          boxShadow: isSelected ? `0 4px 16px ${color}25` : 'none',
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Model selector */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
                  Model
                </label>
                <div style={{ position: 'relative' }}>
                  <select
                    id="llm-model-select"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    style={{
                      width: '100%', padding: '11px 40px 11px 16px', borderRadius: '12px',
                      border: '1px solid rgba(255,255,255,0.12)',
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--color-text-primary)', fontSize: '13px', cursor: 'pointer',
                      appearance: 'none', outline: 'none',
                    }}
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id} style={{ background: '#0D1421' }}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={15} style={{
                    position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)',
                    color: 'var(--color-text-muted)', pointerEvents: 'none',
                  }} />
                </div>
              </div>

              {/* API key input */}
              {selectedProvider !== 'ollama' && (
                <div>
                  <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
                    API Key{' '}
                    <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 'normal' }}>
                      {currentConfig?.provider === selectedProvider && currentConfig.api_key_set
                        ? '(leave blank to keep current)'
                        : '(required)'}
                    </span>
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="llm-api-key-input"
                      type={showKey ? 'text' : 'password'}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={
                        selectedProvider === 'gemini' ? 'AIzaSy...' :
                        selectedProvider === 'groq'   ? 'gsk_...' :
                        selectedProvider === 'openai' ? 'sk-...' : ''
                      }
                      autoComplete="off"
                      style={{
                        width: '100%', padding: '11px 48px 11px 16px', borderRadius: '12px',
                        border: '1px solid rgba(255,255,255,0.12)',
                        background: 'rgba(255,255,255,0.05)',
                        color: 'var(--color-text-primary)', fontSize: '13px', outline: 'none',
                        fontFamily: 'var(--font-mono)', boxSizing: 'border-box',
                        transition: 'border-color 0.15s',
                      }}
                      onFocus={(e) => { e.currentTarget.style.borderColor = PROVIDER_COLORS[selectedProvider]; }}
                      onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; }}
                    />
                    <button
                      onClick={() => setShowKey((v) => !v)}
                      style={{
                        position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--color-text-muted)', padding: '4px',
                        display: 'flex', alignItems: 'center',
                      }}
                    >
                      {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
              )}

              {/* Ollama URL */}
              {selectedProvider === 'ollama' && (
                <div>
                  <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
                    Ollama Server URL
                  </label>
                  <input
                    type="text"
                    value={ollamaUrl}
                    onChange={(e) => setOllamaUrl(e.target.value)}
                    placeholder="http://localhost:11434"
                    style={{
                      width: '100%', padding: '11px 16px', borderRadius: '12px',
                      border: '1px solid rgba(255,255,255,0.12)',
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--color-text-primary)', fontSize: '13px', outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              )}

              {/* Save result */}
              {saveResult && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px',
                  borderRadius: '12px',
                  background: saveResult.ok ? 'rgba(0,229,160,0.1)' : 'rgba(255,107,107,0.1)',
                  border: `1px solid ${saveResult.ok ? 'rgba(0,229,160,0.3)' : 'rgba(255,107,107,0.3)'}`,
                }}>
                  {saveResult.ok
                    ? <CheckCircle2 size={15} color="#00E5A0" />
                    : <AlertTriangle size={15} color="#FF6B6B" />}
                  <span style={{ fontSize: '13px', color: saveResult.ok ? '#00E5A0' : '#FF6B6B', fontWeight: 600 }}>
                    {saveResult.msg}
                  </span>
                </div>
              )}

              {/* Test result */}
              {testResult && (
                <div style={{
                  display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '12px 16px',
                  borderRadius: '12px',
                  background: testResult.status === 'ok' ? 'rgba(0,229,160,0.1)' : 'rgba(255,107,107,0.1)',
                  border: `1px solid ${testResult.status === 'ok' ? 'rgba(0,229,160,0.3)' : 'rgba(255,107,107,0.3)'}`,
                }}>
                  {testResult.status === 'ok'
                    ? <CheckCircle2 size={15} color="#00E5A0" style={{ flexShrink: 0, marginTop: '1px' }} />
                    : <AlertTriangle size={15} color="#FF6B6B" style={{ flexShrink: 0, marginTop: '1px' }} />}
                  <span style={{ fontSize: '13px', color: testResult.status === 'ok' ? '#00E5A0' : '#FF6B6B', fontWeight: 500, lineHeight: 1.5 }}>
                    {testResult.message}
                  </span>
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                <button
                  id="llm-test-btn"
                  onClick={handleTest}
                  disabled={testing}
                  style={{
                    flex: 1, padding: '12px', borderRadius: '12px', cursor: testing ? 'not-allowed' : 'pointer',
                    border: '1px solid rgba(255,255,255,0.12)',
                    background: 'rgba(255,255,255,0.05)',
                    color: 'var(--color-text-secondary)', fontSize: '13px', fontWeight: 600,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                    opacity: testing ? 0.6 : 1, transition: 'all 0.15s',
                  }}
                >
                  <RefreshCw size={13} style={{ animation: testing ? 'spin 0.8s linear infinite' : 'none' }} />
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
                <button
                  id="llm-apply-btn"
                  onClick={handleSave}
                  disabled={saving}
                  style={{
                    flex: 2, padding: '12px', borderRadius: '12px',
                    cursor: saving ? 'not-allowed' : 'pointer',
                    border: 'none',
                    background: `linear-gradient(135deg, ${PROVIDER_COLORS[selectedProvider]}, ${PROVIDER_COLORS[selectedProvider]}cc)`,
                    color: '#fff', fontSize: '13px', fontWeight: 800,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                    opacity: saving ? 0.7 : 1, transition: 'all 0.15s',
                    boxShadow: `0 6px 20px ${PROVIDER_COLORS[selectedProvider]}45`,
                    letterSpacing: '0.01em',
                  }}
                >
                  ⚡ {saving ? 'Applying...' : 'Apply Configuration'}
                </button>
              </div>
            </div>

          ) : (
            /* History tab */
            <div>
              {history.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)', fontSize: '13px' }}>
                  <History size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                  No configuration changes yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {history.map((entry, idx) => {
                    const color = PROVIDER_COLORS[entry.provider] ?? '#00D4FF';
                    return (
                      <div
                        key={entry.change_id}
                        style={{
                          padding: '13px 16px', borderRadius: '12px',
                          background: idx === 0 ? `${color}12` : 'rgba(255,255,255,0.03)',
                          border: `1px solid ${idx === 0 ? color + '35' : 'rgba(255,255,255,0.07)'}`,
                          transition: 'all 0.15s',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '5px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {idx === 0 && (
                              <span style={{ fontSize: '9px', fontWeight: 800, color: color, background: `${color}20`, padding: '2px 6px', borderRadius: '4px', letterSpacing: '0.08em' }}>
                                CURRENT
                              </span>
                            )}
                            <span style={{ fontSize: '13px', fontWeight: 700, color: color }}>
                              {PROVIDER_LABELS[entry.provider] ?? entry.provider}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--color-text-muted)' }}>
                            <Clock size={10} />
                            {new Date(entry.timestamp).toLocaleString()}
                          </div>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                          <span>
                            Model:{' '}
                            <span style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                              {entry.model}
                            </span>
                          </span>
                          {entry.api_key_preview && (
                            <span>
                              Key:{' '}
                              <span style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                                {entry.api_key_preview}
                              </span>
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Global animation keyframes for the portal */}
      <style>{`
        @keyframes llmFadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes llmSlideUp {
          from { opacity: 0; transform: translate(-50%, -47%); }
          to   { opacity: 1; transform: translate(-50%, -50%); }
        }
      `}</style>
    </>,
    document.body
  ) : null;

  // -------------------------------------------------------------------------
  // Sidebar trigger button
  // -------------------------------------------------------------------------
  return (
    <>
      <button
        id="llm-config-trigger"
        onClick={() => setIsOpen(true)}
        title="LLM Configuration"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          padding: '10px 12px',
          borderRadius: '10px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          color: 'var(--color-text-muted)',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 600,
          letterSpacing: '0.04em',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
          e.currentTarget.style.color = 'var(--color-text-primary)';
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
          e.currentTarget.style.color = 'var(--color-text-muted)';
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
        }}
      >
        <Settings size={14} />
        <span style={{ flex: 1, textAlign: 'left', textTransform: 'uppercase' }}>LLM Config</span>
        {currentConfig && (
          <span style={{
            fontSize: '10px',
            padding: '2px 7px',
            borderRadius: '5px',
            background: `${PROVIDER_COLORS[currentConfig.provider] ?? '#00D4FF'}22`,
            color: PROVIDER_COLORS[currentConfig.provider] ?? '#00D4FF',
            border: `1px solid ${PROVIDER_COLORS[currentConfig.provider] ?? '#00D4FF'}40`,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontWeight: 700,
          }}>
            {currentConfig.provider}
          </span>
        )}
      </button>

      {/* Portal-mounted modal */}
      {modal}
    </>
  );
}
