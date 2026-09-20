'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { format } from 'date-fns';
import { Wifi, WifiOff, Pause, Play } from 'lucide-react';

export interface TelemetryEvent {
  event_id?: string;
  event_type: string;
  module: number | string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  summary: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

interface TelemetryFeedProps {
  maxEvents?: number;
  compact?: boolean;
}

const severityConfig: Record<
  TelemetryEvent['severity'],
  { label: string; colorClass: string; color: string }
> = {
  INFO:    { label: 'INFO',    colorClass: 'status-info',    color: '#00D4FF' },
  WARNING: { label: 'WARN',   colorClass: 'status-warning',  color: '#FFB800' },
  ERROR:   { label: 'ERROR',  colorClass: 'status-danger',   color: '#FF4444' },
  SUCCESS: { label: 'OK',     colorClass: 'status-success',  color: '#00E5A0' },
};

const WS_URL =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000')
    : 'ws://localhost:8000';

export default function TelemetryFeed({
  maxEvents = 50,
  compact = false,
}: TelemetryFeedProps) {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(`${WS_URL}/ws/telemetry`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (evt) => {
        if (pausedRef.current) return;
        try {
          const data: TelemetryEvent = JSON.parse(evt.data as string);
          setEvents((prev) => [data, ...prev].slice(0, maxEvents));
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      reconnectTimer.current = setTimeout(connect, 3000);
    }
  }, [maxEvents]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  // Auto-scroll to top (newest) when not compact
  useEffect(() => {
    if (!compact && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events, compact]);

  const togglePause = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
  };

  const displayEvents = compact ? events.slice(0, 5) : events;

  return (
    <div className="telemetry-ticker">
      {/* Header */}
      <div className="telemetry-ticker-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className={`connection-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            Live Telemetry Feed
          </span>
          {connected ? (
            <span style={{ fontSize: '11px', color: 'var(--color-success)', fontFamily: 'var(--font-mono)' }}>
              CONNECTED
            </span>
          ) : (
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
              RECONNECTING...
            </span>
          )}
          <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
            {events.length} events
          </span>
        </div>

        {!compact && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {connected ? (
              <Wifi size={14} color="var(--color-success)" />
            ) : (
              <WifiOff size={14} color="var(--color-text-muted)" />
            )}
            <button
              className={`btn btn-ghost btn-sm`}
              onClick={togglePause}
              aria-label={paused ? 'Resume telemetry' : 'Pause telemetry'}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {paused ? <Play size={12} /> : <Pause size={12} />}
              {paused ? 'Resume' : 'Pause'}
            </button>
          </div>
        )}
      </div>

      {/* Events */}
      <div
        className="telemetry-ticker-body"
        ref={scrollRef}
        style={{ maxHeight: compact ? '200px' : '320px' }}
      >
        {displayEvents.length === 0 ? (
          <div
            style={{
              padding: '32px',
              textAlign: 'center',
              color: 'var(--color-text-muted)',
              fontSize: '13px',
            }}
          >
            {connected
              ? 'Waiting for telemetry events...'
              : 'Connecting to telemetry stream...'}
          </div>
        ) : (
          displayEvents.map((evt, idx) => {
            const sev = severityConfig[evt.severity] ?? severityConfig.INFO;
            const ts = (() => {
              try {
                return format(new Date(evt.timestamp), 'HH:mm:ss');
              } catch {
                return evt.timestamp;
              }
            })();

            return (
              <div key={`${evt.event_id ?? idx}-${idx}`} className="telemetry-event">
                {/* Severity */}
                <span className={`status-badge ${sev.colorClass}`}>
                  {sev.label}
                </span>

                {/* Meta */}
                <div className="telemetry-event-meta">
                  <span className="telemetry-event-type">
                    {evt.event_type}
                    {evt.module && (
                      <span
                        style={{
                          marginLeft: '8px',
                          fontSize: '11px',
                          color: 'var(--color-text-muted)',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        MOD-{evt.module}
                      </span>
                    )}
                  </span>
                  <span className="telemetry-event-summary">{evt.summary}</span>
                </div>

                {/* Timestamp */}
                <span className="telemetry-event-time">{ts}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
