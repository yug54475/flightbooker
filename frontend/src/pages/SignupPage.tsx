import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { signup as apiSignup } from '../api/endpoints';
import { ApiRequestError } from '../api/client';

type CardTier = 'premium' | 'mid' | 'entry';

const TIERS: { value: CardTier; icon: string; name: string; desc: string }[] = [
  { value: 'premium', icon: '◈', name: 'Premium', desc: 'Full concierge + insurance' },
  { value: 'mid',     icon: '◎', name: 'Mid-Tier', desc: 'Core rebooking benefits' },
  { value: 'entry',   icon: '◌', name: 'Entry',    desc: 'Basic rebooking only' },
];

export function SignupPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cardTier, setCardTier] = useState<CardTier>('mid');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      const res = await apiSignup({ name, email, password, card_tier: cardTier });
      login(res.token, res.user_id);
      navigate('/policy-setup');
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

      <div className="auth-card" style={{ maxWidth: 500 }}>
        <div className="auth-logo">
          <div className="auth-logo-wordmark">Concierge</div>
          <div className="auth-logo-sub">Travel Disruption AI · Card Benefits</div>
        </div>

        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">
          Set up your concierge in under a minute
        </p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="signup-name" className="form-label">Full name</label>
            <input
              id="signup-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              required
              autoComplete="name"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="signup-email" className="form-label">Email address</label>
            <input
              id="signup-email"
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
            <label htmlFor="signup-password" className="form-label">Password</label>
            <input
              id="signup-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              required
              autoComplete="new-password"
              minLength={6}
              maxLength={128}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <span className="form-label" id="tier-label">Card tier</span>
            <div className="tier-picker" role="radiogroup" aria-labelledby="tier-label">
              {TIERS.map(({ value, icon, name: tname, desc }) => (
                <label key={value} className="tier-option" htmlFor={`tier-${value}`}>
                  <input
                    id={`tier-${value}`}
                    type="radio"
                    name="card_tier"
                    value={value}
                    checked={cardTier === value}
                    onChange={() => setCardTier(value)}
                    disabled={loading}
                  />
                  <div className="tier-card">
                    <span className="tier-icon" aria-hidden="true">{icon}</span>
                    <span className="tier-name">{tname}</span>
                    <span className="tier-desc">{desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="form-error" role="alert">{error}</div>
          )}

          <button
            id="signup-submit"
            type="submit"
            className="btn btn-primary btn-lg btn-full"
            disabled={loading || !name || !email || !password}
          >
            {loading ? 'Creating account…' : 'Create account & set policy →'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" id="nav-to-login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
