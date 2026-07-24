import { useEffect, useRef, useState } from 'react';
import type { ReasoningStep } from '../types';
import { fmtStepName, fmtTime } from '../utils/formatters';

interface ReasoningTraceProps {
  steps: ReasoningStep[];
  isLive?: boolean;
}

// Stream steps in one-by-one for the teleprinter effect
export function ReasoningTrace({ steps, isLive = false }: ReasoningTraceProps) {
  const [visibleCount, setVisibleCount] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevStepLen = useRef(0);

  useEffect(() => {
    if (steps.length === prevStepLen.current) return;

    // When we have more steps, stream each new one in with a delay
    let i = prevStepLen.current;
    prevStepLen.current = steps.length;

    const interval = setInterval(() => {
      i++;
      setVisibleCount(i);
      if (i >= steps.length) {
        clearInterval(interval);
      }
    }, 350);

    return () => clearInterval(interval);
  }, [steps]);

  // Auto-scroll to bottom as steps appear
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [visibleCount]);

  const shown = steps.slice(0, visibleCount);

  return (
    <div className="reasoning-trace" role="log" aria-label="Agent reasoning trace" aria-live="polite">
      <div className="trace-header">
        <span className="trace-title">▸ Agent Reasoning Log</span>
        {isLive && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--accent-amber)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: 'var(--accent-amber)',
                display: 'inline-block',
                animation: 'pulse-dot 1.5s infinite',
              }}
            />
            LIVE
          </span>
        )}
      </div>

      {shown.length === 0 && (
        <div className="trace-empty">
          <div style={{ marginBottom: '8px', opacity: 0.4 }}>◌</div>
          Waiting for agent to begin…
          {isLive && <span className="trace-cursor" />}
        </div>
      )}

      {shown.map((step, idx) => (
        <TraceStep
          key={`${step.step_name}-${idx}`}
          step={step}
          index={idx}
          isLast={idx === shown.length - 1}
          isLive={isLive}
        />
      ))}

      {isLive && shown.length > 0 && shown.length < steps.length && (
        <div style={{ padding: '8px 0', color: 'var(--text-tertiary)' }}>
          <span className="trace-cursor" />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

interface TraceStepProps {
  step: ReasoningStep;
  index: number;
  isLast: boolean;
  isLive: boolean;
}

function TraceStep({ step, index, isLast, isLive }: TraceStepProps) {
  const output = typeof step.output === 'string'
    ? step.output
    : JSON.stringify(step.output);

  return (
    <div className={`trace-step ${isLast && isLive ? 'active' : ''}`}>
      <span className="trace-step-num">{String(index + 1).padStart(2, '0')}</span>
      <span className="trace-step-name">{fmtStepName(step.step_name)}</span>
      <span className="trace-step-time">{fmtTime(step.timestamp)}</span>
      <span className="trace-step-desc" title={output}>
        {output}
        {isLast && isLive && <span className="trace-cursor" />}
      </span>
    </div>
  );
}
