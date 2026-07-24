import { fmtConfidence, confidenceTier } from '../../utils/formatters';

interface ConfidenceBarProps {
  score: number;
}

export function ConfidenceBar({ score }: ConfidenceBarProps) {
  const tier = confidenceTier(score);
  return (
    <div className={`confidence-bar-wrap confidence-${tier}`}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: '6px',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-tertiary)',
          }}
        >
          Confidence Score
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '1.125rem',
            fontWeight: 600,
            color:
              tier === 'high'
                ? 'var(--accent-green)'
                : tier === 'mid'
                ? 'var(--accent-amber)'
                : 'var(--accent-coral)',
          }}
        >
          {fmtConfidence(score)}
        </span>
      </div>
      <div className="confidence-bar-track">
        <div
          className="confidence-bar-fill"
          style={{ width: `${Math.round(score * 100)}%` }}
          role="meter"
          aria-valuenow={Math.round(score * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confidence score: ${fmtConfidence(score)}`}
        />
      </div>
      <p
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.7rem',
          color: 'var(--text-tertiary)',
          marginTop: '6px',
        }}
      >
        {score > 0.9
          ? 'Above 90% — auto-approved by your concierge'
          : score >= 0.7
          ? 'Your approval is required before booking'
          : 'Low confidence — review carefully before approving'}
      </p>
    </div>
  );
}
