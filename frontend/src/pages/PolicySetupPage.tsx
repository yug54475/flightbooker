import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../store/auth';
import { getPolicy, updatePolicy } from '../api/endpoints';
import { useToast } from '../store/toast';
import { fmtPrice } from '../utils/formatters';
import { LoadingCenter } from '../components/ui/Spinner';
import { DataErrorState } from '../components/ui/DataState';

export function PolicySetupPage() {
  const { token, user } = useAuth();
  const { showSuccess, showError } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const isSetupFlow = location.pathname === '/policy-setup';

  const { data: policy, isLoading, error, refetch } = useQuery({
    queryKey: ['policy'],
    queryFn: () => getPolicy(token!),
    enabled: !!token,
  });

  const [maxFlight, setMaxFlight] = useState(150);
  const [maxHotel, setMaxHotel] = useState(100);
  const [allowDowngrade, setAllowDowngrade] = useState(false);

  useEffect(() => {
    if (policy) {
      setMaxFlight(policy.max_price_delta);
      setMaxHotel(policy.max_hotel_price_delta);
      setAllowDowngrade(policy.allow_cabin_downgrade);
    }
  }, [policy]);

  const mutation = useMutation({
    mutationFn: () =>
      updatePolicy(
        {
          max_price_delta: maxFlight,
          allow_cabin_downgrade: allowDowngrade,
          max_hotel_price_delta: maxHotel,
        },
        token!,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policy'] });
      showSuccess('Policy updated successfully.');
      if (isSetupFlow) {
        navigate('/dashboard');
      }
    },
    onError: (err: Error) => {
      showError(err.message);
    },
  });

  if (isLoading) return <LoadingCenter label="Loading your policy…" />;

  if (error) {
    return (
      <div className={isSetupFlow ? 'setup-state-page' : ''}>
        <DataErrorState
          title="Your rebooking policy could not be loaded"
          error={error}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: isSetupFlow ? '100vh' : undefined,
        display: 'flex',
        alignItems: isSetupFlow ? 'center' : undefined,
        justifyContent: isSetupFlow ? 'center' : undefined,
        padding: 'var(--space-8) var(--space-4)',
        background: isSetupFlow ? 'var(--bg-deep)' : undefined,
      }}
    >
      <div style={{ width: '100%', maxWidth: 560 }}>
        {isSetupFlow && (
          <div style={{ marginBottom: 'var(--space-8)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px' }}>
              Step 2 of 2
            </div>
            <h1 style={{ marginBottom: 'var(--space-2)' }}>Your rebooking policy</h1>
            <p style={{ color: 'var(--text-secondary)' }}>
              These settings control when your concierge can rebook automatically.
              Raising your tolerance means more disruptions get resolved without you needing to approve anything.
            </p>
          </div>
        )}

        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-8)' }}>
          {/* Flight price delta slider */}
          <div className="slider-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <label htmlFor="slider-flight" className="form-label" style={{ marginBottom: 0 }}>
                Flight price tolerance
              </label>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '1.25rem',
                  fontWeight: 700,
                  color: 'var(--accent-amber)',
                }}
              >
                {fmtPrice(maxFlight)}
              </span>
            </div>
            <input
              id="slider-flight"
              type="range"
              className="slider"
              min={0}
              max={2000}
              step={25}
              value={maxFlight}
              onChange={(e) => setMaxFlight(Number(e.target.value))}
            />
            <div className="slider-labels">
              <span>$0</span>
              <span>$1,000</span>
              <span>$2,000</span>
            </div>
            <p className="form-hint">
              Your concierge can rebook flights up to{' '}
              <strong style={{ color: 'var(--text-primary)' }}>{fmtPrice(maxFlight)}</strong>{' '}
              more expensive than the original without asking.
            </p>
          </div>

          <hr className="divider" style={{ margin: 0 }} />

          {/* Hotel price delta slider */}
          <div className="slider-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <label htmlFor="slider-hotel" className="form-label" style={{ marginBottom: 0 }}>
                Hotel price tolerance
              </label>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '1.25rem',
                  fontWeight: 700,
                  color: 'var(--accent-teal)',
                }}
              >
                {fmtPrice(maxHotel)}
              </span>
            </div>
            <input
              id="slider-hotel"
              type="range"
              className="slider"
              min={0}
              max={500}
              step={25}
              value={maxHotel}
              onChange={(e) => setMaxHotel(Number(e.target.value))}
            />
            <div className="slider-labels">
              <span>$0</span>
              <span>$250</span>
              <span>$500</span>
            </div>
            <p className="form-hint">
              Your concierge can change hotel bookings up to{' '}
              <strong style={{ color: 'var(--text-primary)' }}>{fmtPrice(maxHotel)}</strong>{' '}
              more expensive per night.
            </p>
          </div>

          <hr className="divider" style={{ margin: 0 }} />

          {/* Cabin downgrade toggle */}
          <div className="form-group">
            <span className="form-label">Cabin class downgrade</span>
            <div className="toggle-container">
              <div>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 500, marginBottom: '4px' }}>
                  Allow cabin downgrade
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                  If no equivalent cabin is available, permit a lower class to secure a seat sooner.
                </p>
              </div>
              <label className="toggle" htmlFor="toggle-downgrade">
                <input
                  id="toggle-downgrade"
                  type="checkbox"
                  checked={allowDowngrade}
                  onChange={(e) => setAllowDowngrade(e.target.checked)}
                  role="switch"
                  aria-checked={allowDowngrade}
                />
                <span className="toggle-track" />
              </label>
            </div>
          </div>

          {/* Confidence explainer */}
          <div
            style={{
              padding: 'var(--space-4)',
              background: 'var(--accent-amber-muted)',
              border: '1px solid var(--border-amber)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <p
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.7rem',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--accent-amber)',
                marginBottom: '6px',
              }}
            >
              How confidence scoring works
            </p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Your concierge scores every rebooking option against your price tolerance, cabin preference, loyalty
              programme match, and arrival time. Options scoring{' '}
              <strong style={{ color: 'var(--text-primary)' }}>above 90%</strong> are booked automatically.
              Anything lower is sent to you for approval. Raising your tolerance means higher scores and fewer
              approvals needed from you.
            </p>
          </div>

          <button
            id="policy-save"
            className="btn btn-primary btn-lg btn-full"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? 'Saving…'
              : isSetupFlow
              ? 'Save policy & go to Dashboard →'
              : 'Save policy'}
          </button>

          {isSetupFlow && user && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ alignSelf: 'center' }}
              onClick={() => navigate('/dashboard')}
            >
              Skip for now
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
