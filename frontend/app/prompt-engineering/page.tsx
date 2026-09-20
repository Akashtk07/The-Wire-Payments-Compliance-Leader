'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Brain,
  Send,
  Loader2,
  Copy,
  CheckCheck,
  ChevronRight,
  Sparkles,
  Lightbulb,
  AlertTriangle,
  BookOpen,
  Zap,
  Link2,
  LayoutGrid,
  Database,
  Target,
  ThumbsDown,
  Building2,
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Topic {
  id: string;
  title: string;
  icon: string;
  badge_color: string;
  short_desc: string;
  description: string;
  technique_tags: string[];
}

interface Example {
  id: string;
  title: string;
  technique: string;
  prompt?: string;
  bad_prompt?: string;
  good_prompt?: string;
  system_prompt?: string;
  expected_answer_hint?: string;
  why_better?: string;
  anti_pattern_name?: string;
  problem?: string;
  fix?: string;
  is_template?: boolean;
  template_vars?: string[];
}

const TOPIC_ICONS: Record<string, React.ReactNode> = {
  intro: <Brain size={18} />,
  zero_shot: <Target size={18} />,
  few_shot: <LayoutGrid size={18} />,
  chain_of_thought: <Link2 size={18} />,
  role_prompting: <Sparkles size={18} />,
  structured_output: <BookOpen size={18} />,
  rag_prompting: <Database size={18} />,
  anti_patterns: <AlertTriangle size={18} />,
  financial_domain: <Building2 size={18} />,
};

export default function PromptEngineeringPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [activeTopic, setActiveTopic] = useState<string>('intro');
  const [examples, setExamples] = useState<Example[]>([]);
  const [activeExampleId, setActiveExampleId] = useState<string | null>(null);
  const [tryPrompt, setTryPrompt] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [llmResponse, setLlmResponse] = useState('');
  const [llmLoading, setLlmLoading] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [modelUsed, setModelUsed] = useState('');
  const responseRef = useRef<HTMLDivElement>(null);

  // Load topics on mount
  useEffect(() => {
    fetch(`${API_URL}/api/v1/prompts/topics`)
      .then((r) => r.json())
      .then((d) => setTopics(d.topics ?? []))
      .catch(() => {});
  }, []);

  // Load examples when topic changes
  useEffect(() => {
    if (!activeTopic) return;
    fetch(`${API_URL}/api/v1/prompts/examples/${activeTopic}`)
      .then((r) => r.json())
      .then((d) => {
        setExamples(d.examples ?? []);
        setActiveExampleId(null);
        setTryPrompt('');
        setSystemPrompt('');
        setLlmResponse('');
      })
      .catch(() => setExamples([]));
  }, [activeTopic]);

  const currentTopic = topics.find((t) => t.id === activeTopic);

  const sendToLLM = async () => {
    if (!tryPrompt.trim()) return;
    setLlmLoading(true);
    setLlmResponse('');

    try {
      const res = await fetch(`${API_URL}/api/v1/prompts/try`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: tryPrompt,
          technique: currentTopic?.technique_tags?.[0] ?? null,
          topic_id: activeTopic,
          system_prompt: systemPrompt || null,
        }),
      });
      const data = await res.json();
      setLlmResponse(data.response ?? JSON.stringify(data, null, 2));
      setModelUsed(data.model_used ?? '');
      setTimeout(() => responseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);
    } catch (err) {
      setLlmResponse('⚠️ Could not connect to LLM. Is the backend running?');
    } finally {
      setLlmLoading(false);
    }
  };

  const loadExample = (ex: Example) => {
    const promptText = ex.good_prompt ?? ex.prompt ?? '';
    setTryPrompt(promptText);
    setSystemPrompt(ex.system_prompt ?? '');
    setActiveExampleId(ex.id);
    setLlmResponse('');
  };

  const copyText = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const renderMarkdown = (text: string) => {
    if (!text) return null;
    const lines = text.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('```')) return null;
      if (line.startsWith('#')) {
        const level = line.match(/^#+/)?.[0].length ?? 1;
        const content = line.replace(/^#+\s*/, '');
        return <div key={i} style={{ fontWeight: 700, fontSize: level === 1 ? '16px' : '14px', color: 'var(--color-text-primary)', marginTop: '12px', marginBottom: '4px' }}>{content}</div>;
      }
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return <div key={i} style={{ paddingLeft: '16px', color: 'var(--color-text-secondary)', lineHeight: '1.7', fontSize: '13px' }}>• {line.slice(2)}</div>;
      }
      if (/^\d+\./.test(line)) {
        return <div key={i} style={{ paddingLeft: '16px', color: 'var(--color-text-secondary)', lineHeight: '1.7', fontSize: '13px' }}>{line}</div>;
      }
      if (!line.trim()) return <br key={i} />;
      return <div key={i} style={{ color: 'var(--color-text-secondary)', lineHeight: '1.7', fontSize: '13px' }}>{line}</div>;
    });
  };

  return (
    <main className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* Header */}
      <div className="module-header animate-fade-in">
        <h1 className="gradient-text">Prompt Engineering Lab</h1>
        <p>
          Master the art of communicating with AI — from Zero-Shot to Chain-of-Thought, Role Prompting,
          and RAG-augmented techniques. All examples use{' '}
          <span style={{ color: '#00D4FF', fontWeight: 700 }}>CBPR+</span> and{' '}
          <span style={{ color: '#FFB800', fontWeight: 700 }}>LYNX</span> domain context.
          Try prompts live with the{' '}
          <span style={{ color: '#A855F7', fontWeight: 700 }}>↓ Try It Live</span> panel.
        </p>
      </div>

      <div className="animate-slide-up" style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 0 }}>
        {/* Sidebar: Topics */}
        <div style={{
          width: '240px', flexShrink: 0,
          background: 'var(--color-panel)', borderRadius: '12px',
          border: '1px solid var(--color-border)', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--color-border)', fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Topics ({topics.length})
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {topics.map((topic) => (
              <button
                key={topic.id}
                id={`topic-${topic.id}`}
                onClick={() => setActiveTopic(topic.id)}
                style={{
                  width: '100%', padding: '12px 16px',
                  display: 'flex', alignItems: 'center', gap: '10px',
                  background: activeTopic === topic.id ? `${topic.badge_color}15` : 'transparent',
                  borderLeft: `3px solid ${activeTopic === topic.id ? topic.badge_color : 'transparent'}`,
                  border: 'none',
                  borderRight: 'none', borderTop: 'none', borderBottom: '1px solid var(--color-border)',
                  cursor: 'pointer', textAlign: 'left',
                  transition: 'all 0.15s',
                  borderLeftColor: activeTopic === topic.id ? topic.badge_color : 'transparent',
                  borderLeftWidth: '3px',
                  borderLeftStyle: 'solid',
                }}
              >
                <span style={{ fontSize: '18px', flexShrink: 0 }}>{topic.icon}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: activeTopic === topic.id ? topic.badge_color : 'var(--color-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {topic.title}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {topic.short_desc}
                  </div>
                </div>
                {activeTopic === topic.id && <ChevronRight size={12} style={{ marginLeft: 'auto', flexShrink: 0, color: topic.badge_color }} />}
              </button>
            ))}
          </div>
        </div>

        {/* Main content area */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>

          {/* Topic header */}
          {currentTopic && (
            <div style={{ padding: '20px 24px', background: 'var(--color-panel)', borderRadius: '12px', border: `1px solid ${currentTopic.badge_color}30` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <span style={{ fontSize: '28px' }}>{currentTopic.icon}</span>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text-primary)', margin: 0 }}>{currentTopic.title}</h2>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap' }}>
                    {currentTopic.technique_tags.map((tag) => (
                      <span key={tag} style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '10px', fontWeight: 700, letterSpacing: '0.04em', background: `${currentTopic.badge_color}20`, border: `1px solid ${currentTopic.badge_color}40`, color: currentTopic.badge_color }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: '1.7', margin: 0 }}>{currentTopic.description}</p>
            </div>
          )}

          {/* Examples */}
          {examples.length > 0 && (
            <div>
              <div className="section-header">Examples — Click to Load into Try It Live</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {examples.map((ex) => (
                  <div
                    key={ex.id}
                    style={{
                      padding: '16px 20px',
                      background: 'var(--color-panel)',
                      border: `1px solid ${activeExampleId === ex.id ? (currentTopic?.badge_color ?? 'var(--color-primary)') : 'var(--color-border)'}`,
                      borderRadius: '12px',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)' }}>{ex.title}</span>
                        <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '10px', fontWeight: 700, background: 'rgba(168,85,247,0.15)', border: '1px solid rgba(168,85,247,0.3)', color: '#A855F7' }}>{ex.technique}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => copyText(ex.good_prompt ?? ex.prompt ?? '', ex.id + '-copy')}
                          id={`copy-example-${ex.id}`}
                        >
                          {copied === ex.id + '-copy' ? <CheckCheck size={12} color="var(--color-success)" /> : <Copy size={12} />}
                          Copy
                        </button>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => loadExample(ex)}
                          id={`load-example-${ex.id}`}
                          style={{ fontSize: '11px' }}
                        >
                          <Zap size={12} /> Try It
                        </button>
                      </div>
                    </div>

                    {/* Anti-pattern: show bad vs good */}
                    {ex.bad_prompt && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '8px' }}>
                        <div>
                          <div style={{ fontSize: '10px', fontWeight: 700, color: '#FF4444', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>❌ Bad Prompt</div>
                          <pre style={{ background: 'rgba(255,68,68,0.05)', border: '1px solid rgba(255,68,68,0.2)', borderRadius: '8px', padding: '10px', fontSize: '11px', color: '#FF4444', whiteSpace: 'pre-wrap', margin: 0 }}>
                            {ex.bad_prompt}
                          </pre>
                        </div>
                        <div>
                          <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-success)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>✅ Engineered Prompt</div>
                          <pre style={{ background: 'rgba(0,229,160,0.05)', border: '1px solid rgba(0,229,160,0.2)', borderRadius: '8px', padding: '10px', fontSize: '11px', color: 'var(--color-success)', whiteSpace: 'pre-wrap', margin: 0 }}>
                            {ex.good_prompt}
                          </pre>
                        </div>
                      </div>
                    )}

                    {/* Standard prompt display */}
                    {!ex.bad_prompt && (ex.prompt ?? ex.good_prompt) && (
                      <div>
                        {ex.system_prompt && (
                          <div style={{ marginBottom: '8px' }}>
                            <div style={{ fontSize: '10px', fontWeight: 700, color: '#A855F7', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>🎭 System Role Prompt</div>
                            <pre style={{ background: 'rgba(168,85,247,0.05)', border: '1px solid rgba(168,85,247,0.2)', borderRadius: '8px', padding: '10px', fontSize: '11px', color: '#A855F7', whiteSpace: 'pre-wrap', margin: 0 }}>
                              {ex.system_prompt}
                            </pre>
                          </div>
                        )}
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          {ex.is_template ? '📋 Template (Replace {VARS} before sending)' : '💬 Prompt'}
                        </div>
                        <pre style={{ background: 'rgba(0,212,255,0.04)', border: '1px solid var(--color-border)', borderRadius: '8px', padding: '10px', fontSize: '11px', color: 'var(--color-text-secondary)', whiteSpace: 'pre-wrap', margin: 0 }}>
                          {ex.prompt ?? ex.good_prompt}
                        </pre>
                      </div>
                    )}

                    {/* Hints */}
                    {(ex.expected_answer_hint ?? ex.why_better ?? ex.fix) && (
                      <div style={{ marginTop: '10px', padding: '8px 12px', background: 'rgba(0,212,255,0.05)', borderRadius: '8px', borderLeft: '3px solid var(--color-primary)' }}>
                        <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {ex.why_better ? '💡 Why Better' : ex.fix ? '🔧 Fix' : '📝 Expected Answer Hint'}
                        </span>
                        <p style={{ margin: '4px 0 0', fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: '1.6' }}>
                          {ex.why_better ?? ex.fix ?? ex.expected_answer_hint}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Try It Live Panel */}
          <div style={{ background: 'var(--color-panel)', borderRadius: '12px', border: '1px solid rgba(168,85,247,0.3)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(168,85,247,0.05)' }}>
              <Sparkles size={16} color="#A855F7" />
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#A855F7' }}>Try It Live</span>
              {modelUsed && (
                <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Model: {modelUsed}
                </span>
              )}
            </div>
            <div style={{ padding: '16px 20px' }}>
              {/* System prompt (optional) */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: '6px' }}>
                  System / Role Prompt (optional)
                </label>
                <textarea
                  id="system-prompt-input"
                  className="textarea"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="e.g. Act as a senior CBPR+ compliance officer with 15 years of experience..."
                  style={{ minHeight: '60px', fontSize: '12px', resize: 'vertical' }}
                />
              </div>

              {/* Main prompt */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: '6px' }}>
                  Your Prompt
                </label>
                <textarea
                  id="try-prompt-input"
                  className="textarea"
                  value={tryPrompt}
                  onChange={(e) => setTryPrompt(e.target.value)}
                  placeholder="Type or paste a prompt here, or click 'Try It' on any example above..."
                  style={{ minHeight: '120px', fontSize: '12px', resize: 'vertical' }}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendToLLM(); } }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                  Press Ctrl+Enter to send
                </span>
                <button
                  id="send-prompt-btn"
                  className="btn btn-primary"
                  onClick={sendToLLM}
                  disabled={llmLoading || !tryPrompt.trim()}
                  style={{ background: 'linear-gradient(135deg, #A855F7, #7C3AED)' }}
                >
                  {llmLoading ? (
                    <><Loader2 size={16} className="animate-spin" /> Thinking...</>
                  ) : (
                    <><Send size={16} /> Send Prompt</>
                  )}
                </button>
              </div>

              {/* LLM Response */}
              {(llmLoading || llmResponse) && (
                <div ref={responseRef} style={{ marginTop: '16px', padding: '16px', background: 'rgba(168,85,247,0.04)', border: '1px solid rgba(168,85,247,0.2)', borderRadius: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#A855F7', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      🤖 LLM Response
                    </span>
                    {llmResponse && (
                      <button className="btn btn-ghost btn-sm" onClick={() => copyText(llmResponse, 'llm-resp')} id="copy-llm-response-btn">
                        {copied === 'llm-resp' ? <CheckCheck size={12} color="var(--color-success)" /> : <Copy size={12} />}
                        Copy
                      </button>
                    )}
                  </div>
                  {llmLoading ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-muted)', fontSize: '13px' }}>
                      <Loader2 size={14} className="animate-spin" color="#A855F7" />
                      Generating response...
                    </div>
                  ) : (
                    <div style={{ fontSize: '13px', lineHeight: '1.7' }}>
                      {renderMarkdown(llmResponse)}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
