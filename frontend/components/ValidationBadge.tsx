'use client';

import { CheckCircle2, XCircle, Loader2, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface ValidationException {
  error_code: string;
  message: string;
  action: string;
}

interface ValidationBadgeProps {
  status: 'PASS' | 'SUCCESS' | 'PARTIAL' | 'VALIDATION_EXCEPTION' | 'ERROR' | 'PENDING' | null;
  errors?: string[];
  validationException?: ValidationException | null;
}

export default function ValidationBadge({
  status,
  errors = [],
  validationException = null,
}: ValidationBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  if (status === null) return null;

  return (
    <div className="animate-slide-up" style={{ marginTop: '20px' }}>
      {/* Main Badge */}
      {(status === 'PASS' || status === 'SUCCESS') && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            background: 'rgba(0, 229, 160, 0.08)',
            border: '1px solid rgba(0, 229, 160, 0.35)',
            borderRadius: '12px',
            animation: 'pulse-glow-success 2.5s ease-in-out infinite',
          }}
        >
          <CheckCircle2
            size={28}
            color="var(--color-success)"
            strokeWidth={2}
          />
          <div>
            <div
              style={{
                fontSize: '16px',
                fontWeight: 700,
                color: 'var(--color-success)',
                letterSpacing: '0.05em',
              }}
            >
              SCHEMA VALID — PASS
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
              ISO 20022 translation completed. Message validates against CBPR+ schema.
            </div>
          </div>
        </div>
      )}

      {status === 'PARTIAL' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            background: 'rgba(255, 184, 0, 0.08)',
            border: '1px solid rgba(255, 184, 0, 0.35)',
            borderRadius: '12px',
          }}
        >
          <AlertTriangle
            size={28}
            color="var(--color-warning)"
            strokeWidth={2}
          />
          <div>
            <div
              style={{
                fontSize: '16px',
                fontWeight: 700,
                color: 'var(--color-warning)',
                letterSpacing: '0.05em',
              }}
            >
              PARTIAL TRANSLATION
            </div>
            <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
              Translation produced output with missing optional fields.
            </div>
          </div>
        </div>
      )}

      {(status === 'VALIDATION_EXCEPTION' || status === 'ERROR') && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px 24px',
              background: 'rgba(255, 68, 68, 0.08)',
              border: '1px solid rgba(255, 68, 68, 0.35)',
              borderRadius: expanded ? '12px 12px 0 0' : '12px',
              animation: 'pulse-glow-danger 2.5s ease-in-out infinite',
              cursor: 'pointer',
            }}
            onClick={() => setExpanded(!expanded)}
            role="button"
            aria-expanded={expanded}
            aria-label="Toggle validation error details"
          >
            <XCircle size={28} color="var(--color-danger)" strokeWidth={2} />
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: '16px',
                  fontWeight: 700,
                  color: 'var(--color-danger)',
                  letterSpacing: '0.05em',
                }}
              >
                VALIDATION EXCEPTION
              </div>
              {validationException && (
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-text-secondary)',
                    marginTop: '2px',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {validationException.error_code}
                </div>
              )}
            </div>
            {expanded ? (
              <ChevronUp size={18} color="var(--color-danger)" />
            ) : (
              <ChevronDown size={18} color="var(--color-danger)" />
            )}
          </div>

          {/* Expanded Detail Card */}
          {expanded && validationException && (
            <div
              className="animate-slide-down"
              style={{
                background: 'rgba(255, 68, 68, 0.04)',
                border: '1px solid rgba(255, 68, 68, 0.25)',
                borderTop: 'none',
                borderRadius: '0 0 12px 12px',
                padding: '20px 24px',
              }}
            >
              <div style={{ marginBottom: '16px' }}>
                <div
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: 'var(--color-text-muted)',
                    marginBottom: '8px',
                  }}
                >
                  Validation Exception Response
                </div>
                <pre
                  className="code-block"
                  style={{
                    color: 'var(--color-danger)',
                    fontSize: '13px',
                    lineHeight: '1.7',
                  }}
                >
{JSON.stringify(
  {
    status: 'VALIDATION_EXCEPTION',
    error_code: validationException.error_code,
    message: validationException.message,
    action: validationException.action,
  },
  null,
  2
)}
                </pre>
              </div>

              {/* Breakdown */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Error Code
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--color-danger)' }}>
                    {validationException.error_code}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Recommended Action
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-warning)' }}>
                    {validationException.action}
                  </div>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Message
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: '1.6' }}>
                    {validationException.message}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {status === 'PENDING' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 24px',
            background: 'var(--color-primary-dim)',
            border: '1px solid rgba(0, 212, 255, 0.25)',
            borderRadius: '12px',
            animation: 'pulse-glow 2s ease-in-out infinite',
          }}
        >
          <Loader2
            size={28}
            color="var(--color-primary)"
            className="animate-spin"
          />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-primary)' }}>
            Validating against CBPR+ schema...
          </div>
        </div>
      )}

      {/* Error list */}
      {errors.length > 0 && (
        <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {errors.map((err, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                padding: '8px 12px',
                background: 'rgba(255, 184, 0, 0.06)',
                border: '1px solid rgba(255, 184, 0, 0.2)',
                borderRadius: '8px',
                fontSize: '13px',
                color: 'var(--color-text-secondary)',
              }}
            >
              <AlertTriangle
                size={14}
                color="var(--color-warning)"
                style={{ flexShrink: 0, marginTop: '1px' }}
              />
              <span>
                <strong style={{ color: 'var(--color-warning)', marginRight: '6px' }}>
                  {idx + 1}.
                </strong>
                {err}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
