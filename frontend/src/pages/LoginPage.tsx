import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { login as apiLogin } from '../api/endpoints';
import { ApiRequestError } from '../api/client';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await apiLogin({ email, password });
      login(res.token, res.user_id);
      navigate('/dashboard');
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-bg-grid" aria-hidden="true" />
      <div className="auth-bg-glow" aria-hidden="true" />

      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-wordmark">Concierge</div>
          <div className="auth-logo-sub">Travel Disruption AI · Card Benefits</div>
        </div>

        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-subtitle">Sign in to your concierge account</p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="login-email" className="form-label">Email address</label>
            <input
              id="login-email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="login-password" className="form-label">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary btn-lg btn-full"
            disabled={loading || !email || !password}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="auth-footer">
          Don't have an account?{' '}
          <Link to="/signup" id="nav-to-signup">Create account</Link>
        </div>

        {/* Demo credentials hint */}
        <div
          style={{
            marginTop: '24px',
            padding: '12px 16px',
            background: 'var(--bg-input)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
          }}
        >
          <p
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--text-tertiary)',
              marginBottom: '8px',
            }}
          >
            Demo Accounts (password: demo1234)
          </p>
          {[
            { email: 'amir@example.com', tier: 'Premium', note: 'pre-disrupted' },
            { email: 'sara@example.com', tier: 'Mid', note: 'active' },
            { email: 'jordan@example.com', tier: 'Entry', note: 'active' },
          ].map(({ email: e, tier, note }) => (
            <button
              key={e}
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ justifyContent: 'flex-start', width: '100%', gap: '8px', marginBottom: '2px' }}
              onClick={() => { setEmail(e); setPassword('demo1234'); }}
            >
              <span className="mono" style={{ color: 'var(--accent-teal)' }}>{e}</span>
              <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                {tier} · {note}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
