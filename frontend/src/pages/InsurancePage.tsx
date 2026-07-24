import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../store/auth';
import { getInsuranceClaims } from '../api/endpoints';
import { InsuranceStatusBadge } from '../components/ui/Badge';
import { LoadingCenter } from '../components/ui/Spinner';
import { DataErrorState } from '../components/ui/DataState';
import { fmtPrice, fmtDate } from '../utils/formatters';

// Insurance eligibility rules (for the info panel)
const ELIGIBILITY_RULES = [
  { tier: 'Premium', cancellation: 'Eligible — up to $10,000', delay: 'Eligible if delay > 6 hrs — up to $500' },
  { tier: 'Mid-Tier', cancellation: 'Not eligible', delay: 'Eligible if delay > 12 hrs — up to $300' },
  { tier: 'Entry',   cancellation: 'Not eligible', delay: 'Not eligible' },
];

export function InsurancePage() {
  const { token, userId, user } = useAuth();

  const { data: claims, isLoading, error, refetch } = useQuery({
    queryKey: ['insurance', userId],
    queryFn: () => getInsuranceClaims(userId!, token!),
    enabled: !!token && !!userId,
  });

  if (isLoading) return <LoadingCenter label="Loading insurance claims…" />;

  if (error) {
    return (
      <div className="page-container">
        <DataErrorState
          title="Insurance records are temporarily unavailable"
          error={error}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const list = claims ?? [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Insurance Claims</h1>
        <p className="page-subtitle">
          Insurance eligibility is determined automatically when a disruption is detected.
        </p>
      </div>

      {/* Eligibility reference table */}
      <div className="card mb-6">
        <h3 style={{ marginBottom: 'var(--space-4)', fontSize: '0.9375rem' }}>
          Coverage by card tier
          {user && (
            <span
              className="mono"
              style={{ fontSize: '0.75rem', color: 'var(--accent-amber)', marginLeft: '12px' }}
            >
              You: {user.card_tier.toUpperCase()}
            </span>
          )}
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="ins-table">
            <thead>
              <tr>
                <th>Card Tier</th>
                <th>Cancellation</th>
                <th>Delay</th>
              </tr>
            </thead>
            <tbody>
              {ELIGIBILITY_RULES.map((row) => {
                const isYours = user &&
                  ((row.tier === 'Premium' && user.card_tier === 'premium') ||
                   (row.tier === 'Mid-Tier' && user.card_tier === 'mid') ||
                   (row.tier === 'Entry' && user.card_tier === 'entry'));
                return (
                  <tr key={row.tier} style={isYours ? { background: 'var(--accent-amber-muted)' } : undefined}>
                    <td>
                      <span style={isYours ? { color: 'var(--accent-amber)', fontWeight: 600 } : {}}>
                        {row.tier}
                        {isYours && (
                          <span
                            className="mono"
                            style={{ fontSize: '0.65rem', marginLeft: '6px', color: 'var(--accent-amber)' }}
                          >
                            ← you
                          </span>
                        )}
                      </span>
                    </td>
                    <td style={row.cancellation === 'Not eligible' ? { color: 'var(--text-tertiary)' } : { color: 'var(--accent-green)' }}>
                      {row.cancellation}
                    </td>
                    <td style={row.delay === 'Not eligible' ? { color: 'var(--text-tertiary)' } : { color: 'var(--accent-green)' }}>
                      {row.delay}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Claims list */}
      <h2 style={{ fontSize: '1rem', marginBottom: 'var(--space-4)', color: 'var(--text-secondary)' }}>
        Your claims
      </h2>

      {list.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">◈</div>
          <div className="empty-state-title">No claims on file</div>
          <p className="empty-state-desc">
            Insurance claim records will appear here when a covered disruption is detected.
          </p>
        </div>
      ) : (
        <div className="stack">
          {list.map((claim) => (
            <div key={claim.id} className="card">
              <div className="row-between mb-4">
                <InsuranceStatusBadge status={claim.status} />
                {claim.created_at && (
                  <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                    {fmtDate(claim.created_at)}
                  </span>
                )}
              </div>

              <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
                <div>
                  <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Claim type
                  </div>
                  <div style={{ color: claim.claim_type ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                    {claim.claim_type
                      ? claim.claim_type.charAt(0).toUpperCase() + claim.claim_type.slice(1)
                      : '—'}
                  </div>
                </div>
                <div>
                  <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Eligible amount
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '1.125rem',
                      fontWeight: 700,
                      color: claim.eligible ? 'var(--accent-green)' : 'var(--text-tertiary)',
                    }}
                  >
                    {claim.eligible && claim.amount != null ? fmtPrice(claim.amount) : 'Not eligible'}
                  </div>
                </div>
              </div>

              {claim.status === 'eligible' && (
                <div
                  style={{
                    marginTop: 'var(--space-4)',
                    padding: 'var(--space-3) var(--space-4)',
                    background: 'var(--accent-green-muted)',
                    border: '1px solid rgba(77, 170, 118, 0.35)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.875rem',
                    color: 'var(--text-secondary)',
                  }}
                >
                  You may be eligible to file a claim. Contact your card's claims line to initiate.
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
