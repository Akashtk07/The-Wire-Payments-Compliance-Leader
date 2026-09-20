'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, Loader2, ChevronDown, ChevronUp, BookOpen, Zap,
  Download, FileText, GitCompare, X, FileDown
} from 'lucide-react';
import GuidelineSelector from '@/components/GuidelineSelector';
import { authFetch } from '@/lib/auth';
import { exportAsPDF, exportAsDOCX, ChatMessage } from '@/lib/chatExport';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface LearnTopic {
  id: string;
  title: string;
  description?: string;
  category?: string;
}

interface VersionBadgeProps {
  versions: string[];
}

const QUICK_START_CARDS = [
  { icon: '💱', title: 'What is MT103?', desc: 'Explain the SWIFT MT103 Customer Credit Transfer format and its fields.' },
  { icon: '🔄', title: 'MT to MX Migration', desc: 'How does MT103 map to pacs.008 in ISO 20022 CBPR+?' },
  { icon: '🔐', title: 'UETR Generation', desc: 'What is a UETR and how is it generated per ISO 20022 standards?' },
  { icon: '📋', title: 'CBPR+ Rules', desc: 'What are the key CBPR+ compliance rules for cross-border payments?' },
  { icon: '⚠️', title: 'Validation Errors', desc: 'What causes schema validation exceptions in ISO 20022 translation?' },
  { icon: '🏦', title: 'Correspondent Banking', desc: 'Explain the role of correspondent banks in SWIFT wire transfers.' },
];

function VersionBadge({ versions }: VersionBadgeProps) {
  if (!versions || versions.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
      {versions.map((v) => (
        <span
          key={v}
          style={{
            padding: '2px 8px',
            borderRadius: '999px',
            fontSize: '10px',
            fontWeight: 700,
            letterSpacing: '0.04em',
            background: 'rgba(0,212,255,0.1)',
            border: '1px solid rgba(0,212,255,0.25)',
            color: 'var(--color-primary)',
          }}
        >
          📚 {v}
        </span>
      ))}
    </div>
  );
}

function renderMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      const code = part.slice(3, -3).replace(/^[a-z]*\n/, '');
      return (
        <pre key={i} style={{
          background: 'rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px', padding: '12px',
          fontFamily: 'var(--font-mono)', fontSize: '12px',
          color: 'var(--color-success)', overflowX: 'auto',
          margin: '8px 0', whiteSpace: 'pre-wrap',
        }}>
          {code}
        </pre>
      );
    }
    // Handle ⚠️ Changed in [VERSION] — highlight
    const changeParts = part.split(/(⚠️ Changed in [^:]+:[^\n]*)/g);
    return (
      <span key={i}>
        {changeParts.map((cp, j) => {
          if (cp.startsWith('⚠️ Changed in')) {
            return (
              <span key={j} style={{
                display: 'inline-block', padding: '3px 8px', margin: '3px 0',
                background: 'rgba(255,184,0,0.1)', border: '1px solid rgba(255,184,0,0.3)',
                borderRadius: '6px', color: '#FFB800', fontSize: '12px', fontWeight: 600,
              }}>
                {cp}
              </span>
            );
          }
          const boldParts = cp.split(/(\*\*[^*]+\*\*)/g);
          return (
            <span key={j}>
              {boldParts.map((bp, k) => {
                if (bp.startsWith('**') && bp.endsWith('**')) {
                  return <strong key={k} style={{ color: 'var(--color-text-primary)', fontWeight: 700 }}>{bp.slice(2, -2)}</strong>;
                }
                return <span key={k}>{bp}</span>;
              })}
            </span>
          );
        })}
      </span>
    );
  });
}

export default function LearnPage() {
  const [topics, setTopics] = useState<LearnTopic[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [crossVersionMode, setCrossVersionMode] = useState(false);
  const [exporting, setExporting] = useState<'pdf' | 'docx' | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const res = await authFetch(`${API_URL}/api/v1/learn/topics`);
        if (res.ok) {
          const data = await res.json();
          setTopics(Array.isArray(data) ? data : data.topics ?? []);
        }
      } catch { /* silently fail */ }
      finally { setLoadingTopics(false); }
    };
    fetchTopics();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim() || thinking) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setThinking(true);

    try {
      let endpoint = `${API_URL}/api/v1/learn`;
      let body: Record<string, unknown> = {
        query: question.trim(),
        context: context.trim() || undefined,
        selected_versions: selectedVersions.length > 0 ? selectedVersions : undefined,
        cross_version_compare: crossVersionMode && selectedVersions.length > 1,
      };

      const res = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      const answer = data.answer ?? data.response ?? data.content ?? JSON.stringify(data, null, 2);
      const sources = data.sources ?? [];

      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'ai',
        content: answer,
        timestamp: new Date(),
        sources,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      const errMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'ai',
        content: '⚠️ **Connection error** — Could not reach the Knowledge API. Please ensure the backend is running.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setThinking(false);
    }
  }, [context, thinking, selectedVersions, crossVersionMode]);

  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); sendMessage(input); };
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input); }
  };
  const handleTopicClick = (topic: LearnTopic) => {
    setSelectedTopic(topic.id);
    setInput(topic.title);
    textareaRef.current?.focus();
  };
  const handleQuickStart = (question: string) => { sendMessage(question); };

  const handleExportPDF = async () => {
    setExporting('pdf');
    try {
      await exportAsPDF({ messages, selectedVersions, sessionTitle: 'Compliance AI Chat Transcript' });
    } finally { setExporting(null); }
  };

  const handleExportDOCX = async () => {
    setExporting('docx');
    try {
      await exportAsDOCX({ messages, selectedVersions, sessionTitle: 'Compliance AI Chat Transcript' });
    } finally { setExporting(null); }
  };

  const clearChat = () => setMessages([]);

  return (
    <main className="page-container">
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Interactive Learning &amp; Domain Knowledge</h1>
        <p>AI-powered ISO 20022, SWIFT CBPR+, and regulatory compliance knowledge assistant.</p>
      </div>

      {/* Toolbar: Guideline Selector + Export */}
      <div
        className="animate-slide-up"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '16px',
          flexWrap: 'wrap',
        }}
      >
        <GuidelineSelector
          selectedVersions={selectedVersions}
          onSelectionChange={setSelectedVersions}
        />

        {/* Cross-version toggle */}
        {selectedVersions.length > 1 && (
          <button
            onClick={() => setCrossVersionMode((v) => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 12px', borderRadius: '10px', fontSize: '12px', fontWeight: 600,
              border: `1px solid ${crossVersionMode ? 'rgba(255,184,0,0.4)' : 'var(--color-border)'}`,
              background: crossVersionMode ? 'rgba(255,184,0,0.08)' : 'rgba(255,255,255,0.04)',
              color: crossVersionMode ? '#FFB800' : 'var(--color-text-secondary)',
              cursor: 'pointer', transition: 'all 150ms ease',
            }}
          >
            <GitCompare size={13} />
            Cross-version Compare {crossVersionMode ? 'ON' : 'OFF'}
          </button>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Export buttons */}
        {messages.length > 0 && (
          <>
            <button
              id="export-pdf-btn"
              onClick={handleExportPDF}
              disabled={exporting !== null}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 12px', borderRadius: '10px', fontSize: '12px', fontWeight: 600,
                border: '1px solid rgba(255,68,68,0.35)',
                background: 'rgba(255,68,68,0.06)',
                color: '#FF4444', cursor: 'pointer', transition: 'all 150ms ease',
              }}
            >
              {exporting === 'pdf' ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
              Export PDF
            </button>
            <button
              id="export-docx-btn"
              onClick={handleExportDOCX}
              disabled={exporting !== null}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 12px', borderRadius: '10px', fontSize: '12px', fontWeight: 600,
                border: '1px solid rgba(0,212,255,0.35)',
                background: 'rgba(0,212,255,0.06)',
                color: 'var(--color-primary)', cursor: 'pointer', transition: 'all 150ms ease',
              }}
            >
              {exporting === 'docx' ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />}
              Export DOCX
            </button>
            <button
              onClick={clearChat}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 10px', borderRadius: '10px', fontSize: '12px', fontWeight: 600,
                border: '1px solid var(--color-border)',
                background: 'rgba(255,255,255,0.04)',
                color: 'var(--color-text-muted)', cursor: 'pointer',
              }}
            >
              <X size={13} /> Clear
            </button>
          </>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '20px', height: 'calc(100vh - 280px)' }}>
        {/* Left Sidebar: Topics */}
        <div
          style={{
            background: 'var(--color-panel)', border: '1px solid var(--color-border)',
            borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column',
          }}
          className="animate-slide-left"
        >
          <div style={{
            padding: '14px 16px', borderBottom: '1px solid var(--color-border)',
            fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: 'var(--color-text-secondary)',
            display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0,
          }}>
            <BookOpen size={14} />
            Topics
          </div>
          <div style={{ overflowY: 'auto', flex: 1, padding: '8px' }}>
            {loadingTopics ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton-text" style={{ margin: '8px', height: '36px', borderRadius: '8px' }} />
              ))
            ) : topics.length === 0 ? (
              <div style={{ padding: '20px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                No topics available
              </div>
            ) : (
              topics.map((topic) => (
                <button
                  key={topic.id}
                  onClick={() => handleTopicClick(topic)}
                  style={{
                    width: '100%', display: 'block', padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid transparent',
                    background: selectedTopic === topic.id ? 'rgba(0,212,255,0.08)' : 'transparent',
                    borderColor: selectedTopic === topic.id ? 'rgba(0,212,255,0.2)' : 'transparent',
                    color: selectedTopic === topic.id ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                    textAlign: 'left', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
                    transition: 'all 150ms ease', lineHeight: 1.4,
                  }}
                  onMouseOver={(e) => { if (selectedTopic !== topic.id) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)'; }}
                  onMouseOut={(e) => { if (selectedTopic !== topic.id) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                >
                  {topic.title}
                </button>
              ))
            )}
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="chat-container animate-fade-in" style={{ height: '100%' }}>
          {/* Messages */}
          <div className="chat-messages">
            {/* Welcome State */}
            {messages.length === 0 && (
              <div className="animate-fade-in" style={{ padding: '20px 0' }}>
                <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                  <div style={{
                    width: '60px', height: '60px', borderRadius: '16px',
                    background: 'linear-gradient(135deg, var(--color-primary), var(--color-secondary))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 16px',
                    boxShadow: '0 0 32px rgba(0,212,255,0.3)',
                    animation: 'pulse-glow 2.5s ease-in-out infinite',
                  }}>
                    <Zap size={28} color="#080C14" />
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                    ISO 20022 Knowledge Assistant
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', maxWidth: '400px', margin: '0 auto' }}>
                    {selectedVersions.length > 0
                      ? `Active guidelines: ${selectedVersions.join(', ')}. Ask anything about these specific standards.`
                      : 'Select guideline versions above for version-specific answers, or ask anything about SWIFT/ISO 20022.'}
                  </div>
                  {selectedVersions.length > 0 && <VersionBadge versions={selectedVersions} />}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                  {QUICK_START_CARDS.map((card, i) => (
                    <div
                      key={i}
                      className="quickstart-card animate-slide-up"
                      style={{ animationDelay: `${i * 60}ms` }}
                      onClick={() => handleQuickStart(card.desc)}
                      role="button" tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleQuickStart(card.desc); }}
                      aria-label={`Ask: ${card.title}`}
                    >
                      <div className="quickstart-card-icon">{card.icon}</div>
                      <div className="quickstart-card-title">{card.title}</div>
                      <div className="quickstart-card-desc">{card.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.role}`}>
                <div className={`chat-avatar ${msg.role === 'ai' ? 'ai-avatar' : 'user-avatar'}`}>
                  {msg.role === 'ai' ? <Zap size={14} color="#080C14" /> : '👤'}
                </div>
                <div className="chat-bubble">
                  {msg.role === 'ai' ? renderMarkdown(msg.content) : msg.content}
                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {(msg.sources as any[]).slice(0, 3).map((s: any, i: number) => (
                        <span key={i} style={{
                          padding: '2px 8px', borderRadius: '999px', fontSize: '10px', fontWeight: 600,
                          background: 'rgba(0,229,160,0.08)', border: '1px solid rgba(0,229,160,0.2)',
                          color: 'var(--color-success)',
                        }}>
                          📄 {s.filename ?? s}{s.guideline_version ? ` · ${s.guideline_version}` : ''}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Version badges */}
                  {msg.role === 'ai' && selectedVersions.length > 0 && (
                    <VersionBadge versions={selectedVersions} />
                  )}
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                    {msg.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing Indicator */}
            {thinking && (
              <div className="chat-message ai animate-fade-in">
                <div className="chat-avatar ai-avatar">
                  <Zap size={14} color="#080C14" />
                </div>
                <div className="chat-bubble">
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                  {selectedVersions.length > 0 && (
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                      Searching {selectedVersions.join(', ')}...
                    </div>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Context (collapsible) */}
          {showContext && (
            <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)', background: 'rgba(0,0,0,0.2)' }}
              className="animate-slide-down"
            >
              <label className="form-label" style={{ marginBottom: '6px', display: 'block' }}>
                Additional Context (optional)
              </label>
              <textarea
                className="textarea" rows={3}
                placeholder="Paste relevant document excerpts, transaction data, or additional context..."
                value={context}
                onChange={(e) => setContext(e.target.value)}
                style={{ minHeight: '80px', resize: 'vertical', fontSize: '12px' }}
              />
            </div>
          )}

          {/* Input Area */}
          <div className="chat-input-area">
            <button
              className="btn btn-ghost btn-sm btn-icon"
              onClick={() => setShowContext(!showContext)}
              aria-label="Toggle context field"
              title="Add context"
              style={{ flexShrink: 0 }}
            >
              {showContext ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>

            <textarea
              ref={textareaRef}
              id="learn-question-input"
              className="textarea" rows={1}
              placeholder={
                selectedVersions.length > 0
                  ? `Ask about ${selectedVersions.join(', ')}... (Enter to send)`
                  : 'Ask about ISO 20022, SWIFT fields, CBPR+ rules... (Enter to send, Shift+Enter for newline)'
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={thinking}
              style={{ minHeight: '44px', maxHeight: '120px', resize: 'none', fontSize: '14px', flex: 1, borderRadius: '10px' }}
            />

            <button
              id="ask-btn"
              className="btn btn-primary"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || thinking}
              aria-label="Send question"
              style={{ flexShrink: 0, alignSelf: 'flex-end', height: '44px', width: '44px', padding: 0 }}
            >
              {thinking ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
