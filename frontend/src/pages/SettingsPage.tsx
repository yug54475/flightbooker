import { useAuth } from '../store/auth';
import { PolicySetupPage } from './PolicySetupPage';
import { fmtTier } from '../utils/formatters';

export function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Manage your account and rebooking policy</p>
      </div>

      {/* Account details (read-only) */}
      <div className="card mb-6">
        <h2 style={{ fontSize: '1rem', marginBottom: 'var(--space-5)' }}>Account</h2>

        <div className="grid-2" style={{ gap: 'var(--space-5)' }}>
          <div>
            <div
              className="mono"
              style={{
                fontSize: '0.7rem',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--text-tertiary)',
                marginBottom: '6px',
              }}
            >
              Name
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              {user?.name ?? '—'}
            </div>
          </div>

          <div>
            <div
              className="mono"
              style={{
                fontSize: '0.7rem',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--text-tertiary)',
                marginBottom: '6px',
              }}
            >
              Email
            </div>
            <div style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>
              {user?.email ?? '—'}
            </div>
          </div>

          <div>
            <div
              className="mono"
              style={{
                fontSize: '0.7rem',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--text-tertiary)',
                marginBottom: '6px',
              }}
            >
              Card tier
            </div>
            <div style={{ color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
              {user ? fmtTier(user.card_tier) : '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Policy form — reuses PolicySetupPage in settings mode */}
      <h2 style={{ fontSize: '1rem', marginBottom: 'var(--space-5)', color: 'var(--text-secondary)' }}>
        Rebooking policy
      </h2>
      <PolicySetupPage />
    </div>
  );
}
