'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  FileText,
  Trash2,
  Search,
  Copy,
  ChevronDown,
  ChevronUp,
  Loader2,
  Database,
  CheckCheck,
  Info,
} from 'lucide-react';
import DocumentUploader, { DocumentUploadResponse } from '@/components/DocumentUploader';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface IndexedDocument {
  doc_id: string;
  filename: string;
  total_chunks: number;
  chunks?: number;      // alias — frontend used this previously
  uploaded_at?: string;
  file_type?: string;
}

interface SourceCitation {
  doc_id: string;
  filename?: string;
  chunk_index?: number;
  content?: string;
  score?: number;
}

interface QueryResult {
  answer: string;
  sources?: SourceCitation[];
}

const EXAMPLE_QUERIES = [
  'What are the mandatory fields for MT103?',
  'Explain the CBPR+ settlement windows',
  'What is the purpose of field 72 in SWIFT messages?',
  'How is BIC validation performed?',
  'Describe the ISO 20022 pain.001 message structure',
];

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<IndexedDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [question, setQuestion] = useState('');
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/documents/list`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(Array.isArray(data) ? data : data.documents ?? []);
      }
    } catch { /* ignore */ } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const handleUploadSuccess = (doc: DocumentUploadResponse) => {
    setDocuments((prev) => [
      {
        doc_id: doc.doc_id,
        filename: doc.filename,
        total_chunks: doc.chunks_indexed ?? doc.chunks ?? 0,
        uploaded_at: new Date().toISOString(),
      },
      ...prev,
    ]);
  };

  const handleDeleteDocument = async (docId: string) => {
    try {
      await fetch(`${API_URL}/api/v1/documents/${docId}`, { method: 'DELETE' });
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
    } catch { /* ignore */ }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setQueryLoading(true);
    setQueryResult(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/documents/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: question.trim(), top_k: 5 }),
      });
      const data = await res.json();
      setQueryResult({
        answer: data.answer ?? data.response ?? JSON.stringify(data, null, 2),
        sources: data.sources ?? data.citations ?? [],
      });
    } catch {
      setQueryResult({
        answer: '⚠️ Could not reach the document query API. Ensure the backend is running.',
        sources: [],
      });
    } finally {
      setQueryLoading(false);
    }
  };

  const copyAnswer = async () => {
    if (!queryResult?.answer) return;
    await navigator.clipboard.writeText(queryResult.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getFileTypeColor = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase();
    const colors: Record<string, string> = {
      pdf: '#FF4444', pptx: '#FF6B35', docx: '#00D4FF', xml: '#00E5A0', txt: '#8A95A8',
    };
    return colors[ext ?? ''] ?? '#8A95A8';
  };

  const getFileEmoji = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase();
    const emojis: Record<string, string> = {
      pdf: '📄', pptx: '📊', docx: '📝', xml: '📋', txt: '📃',
    };
    return emojis[ext ?? ''] ?? '📄';
  };

  return (
    <main className="page-container">
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Multi-Format Document Intelligence Layer</h1>
        <p>Upload compliance documents and query the AI-powered RAG knowledge base for instant answers.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '20px' }}>
        {/* Left: Document Management */}
        <div className="animate-slide-left">
          <div className="section-header">Document Management</div>

          {/* Uploader */}
          <div style={{ marginBottom: '20px' }}>
            <DocumentUploader onUploadSuccess={handleUploadSuccess} />
          </div>

          {/* Document List */}
          <div
            style={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(255,255,255,0.02)',
              }}
            >
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Indexed Documents
              </span>
              <span
                style={{
                  background: 'rgba(0,212,255,0.1)',
                  color: 'var(--color-primary)',
                  borderRadius: '999px',
                  padding: '2px 10px',
                  fontSize: '12px',
                  fontWeight: 700,
                  border: '1px solid rgba(0,212,255,0.2)',
                }}
              >
                {documents.length}
              </span>
            </div>

            <div style={{ maxHeight: '420px', overflowY: 'auto' }}>
              {loadingDocs ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="skeleton-row">
                    <div className="skeleton-box" style={{ width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div className="skeleton-text" style={{ width: '70%', marginBottom: '6px' }} />
                      <div className="skeleton-text" style={{ width: '40%', height: '10px' }} />
                    </div>
                  </div>
                ))
              ) : documents.length === 0 ? (
                <div
                  style={{
                    padding: '40px 20px',
                    textAlign: 'center',
                    color: 'var(--color-text-muted)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '12px',
                  }}
                >
                  <Database size={32} strokeWidth={1} />
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                      No documents indexed
                    </div>
                    <div style={{ fontSize: '12px' }}>Upload a document to begin</div>
                  </div>
                </div>
              ) : (
                documents.map((doc, idx) => (
                  <div
                    key={doc.doc_id}
                    className="doc-list-item animate-fade-in"
                    style={{ animationDelay: `${idx * 40}ms` }}
                  >
                    <div
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '8px',
                        background: `${getFileTypeColor(doc.filename)}18`,
                        border: `1px solid ${getFileTypeColor(doc.filename)}30`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '18px',
                        flexShrink: 0,
                      }}
                    >
                      {getFileEmoji(doc.filename)}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 600,
                          color: 'var(--color-text-primary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {doc.filename}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                        {(doc.total_chunks ?? doc.chunks ?? 0)} chunks · {doc.doc_id.slice(0, 8)}…
                      </div>
                    </div>
                    <button
                      className="btn btn-ghost btn-icon"
                      onClick={() => handleDeleteDocument(doc.doc_id)}
                      aria-label={`Delete ${doc.filename}`}
                      title="Delete document"
                      style={{ color: 'var(--color-danger)', opacity: 0.6 }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: RAG Query */}
        <div className="animate-slide-up delay-100">
          <div className="section-header">RAG Query Interface</div>

          <div
            style={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              overflow: 'hidden',
              marginBottom: '20px',
            }}
          >
            <form onSubmit={handleQuery} style={{ padding: '20px', borderBottom: '1px solid var(--color-border)' }}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label className="form-label" htmlFor="rag-question">
                  Ask a Question
                </label>
                <textarea
                  id="rag-question"
                  className="textarea"
                  rows={4}
                  placeholder="e.g. What are the mandatory fields for ISO 20022 pacs.008? How should BEI codes be validated?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  style={{ minHeight: '100px' }}
                />
              </div>

              <button
                type="submit"
                id="analyze-docs-btn"
                className="btn btn-primary w-full"
                disabled={queryLoading || !question.trim() || documents.length === 0}
                style={{ justifyContent: 'center' }}
                title={documents.length === 0 ? 'Upload documents first' : 'Analyze documents'}
              >
                {queryLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Analyzing Documents...
                  </>
                ) : (
                  <>
                    <Search size={16} />
                    Analyze Documents
                  </>
                )}
              </button>

              {documents.length === 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '10px', fontSize: '12px', color: 'var(--color-warning)' }}>
                  <Info size={13} />
                  Upload at least one document before querying
                </div>
              )}
            </form>

            {/* Example Queries */}
            <div style={{ padding: '16px 20px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '10px' }}>
                Example Queries
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {EXAMPLE_QUERIES.map((q, i) => (
                  <button
                    key={i}
                    className="chip"
                    onClick={() => setQuestion(q)}
                    type="button"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Answer Display */}
          {queryResult && (
            <div
              className="animate-slide-up"
              style={{
                background: 'var(--color-panel)',
                border: '1px solid var(--color-border)',
                borderRadius: '12px',
                overflow: 'hidden',
              }}
            >
              {/* Answer Header */}
              <div
                style={{
                  padding: '14px 20px',
                  borderBottom: '1px solid var(--color-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(0,229,160,0.04)',
                }}
              >
                <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-success)' }}>
                  ✦ Synthesized Answer
                </span>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={copyAnswer}
                  aria-label="Copy answer"
                >
                  {copied ? <CheckCheck size={13} color="var(--color-success)" /> : <Copy size={13} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>

              {/* Answer Body */}
              <div
                style={{
                  padding: '20px',
                  fontSize: '14px',
                  lineHeight: '1.8',
                  color: 'var(--color-text-primary)',
                  maxHeight: '400px',
                  overflowY: 'auto',
                }}
              >
                {queryResult.answer}
              </div>

              {/* Sources */}
              {queryResult.sources && queryResult.sources.length > 0 && (
                <div style={{ borderTop: '1px solid var(--color-border)' }}>
                  <button
                    style={{
                      width: '100%',
                      padding: '12px 20px',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      color: 'var(--color-text-secondary)',
                      fontSize: '12px',
                      fontWeight: 600,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                    }}
                    onClick={() => setSourcesExpanded(!sourcesExpanded)}
                    aria-expanded={sourcesExpanded}
                    aria-label="Toggle source citations"
                  >
                    <span>Source Citations ({queryResult.sources.length})</span>
                    {sourcesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>

                  {sourcesExpanded && (
                    <div
                      style={{ padding: '0 20px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}
                      className="animate-slide-down"
                    >
                      {queryResult.sources.map((src, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '12px 14px',
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid var(--color-border)',
                            borderRadius: '8px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <FileText size={13} color="var(--color-primary)" />
                            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                              {src.filename ?? src.doc_id}
                            </span>
                            {src.chunk_index !== undefined && (
                              <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                                chunk {src.chunk_index}
                              </span>
                            )}
                            {src.score !== undefined && (
                              <span
                                style={{
                                  marginLeft: 'auto',
                                  fontSize: '11px',
                                  fontFamily: 'var(--font-mono)',
                                  color: 'var(--color-success)',
                                  background: 'rgba(0,229,160,0.1)',
                                  padding: '2px 8px',
                                  borderRadius: '999px',
                                  border: '1px solid rgba(0,229,160,0.2)',
                                }}
                              >
                                {(src.score * 100).toFixed(1)}% match
                              </span>
                            )}
                          </div>
                          {src.content && (
                            <div
                              style={{
                                fontSize: '12px',
                                color: 'var(--color-text-muted)',
                                lineHeight: '1.6',
                                fontStyle: 'italic',
                              }}
                            >
                              &ldquo;{src.content.slice(0, 200)}{src.content.length > 200 ? '…' : ''}&rdquo;
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
