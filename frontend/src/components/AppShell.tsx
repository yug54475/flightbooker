import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { initials, fmtTier } from '../utils/formatters';

const NAV_ITEMS = [
  { to: '/dashboard',      label: 'Dashboard',      icon: '◉' },
  { to: '/notifications',  label: 'Notifications',  icon: '◎' },
  { to: '/insurance',      label: 'Insurance',       icon: '◈' },
  { to: '/settings',       label: 'Settings',        icon: '◌' },
];

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="app-shell">
      {/* Mobile toggle */}
      <button
        className="nav-toggle"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Toggle navigation"
        aria-expanded={mobileOpen}
      >
        {mobileOpen ? '✕' : '☰'}
      </button>

      {/* Overlay */}
      <div
        className={`nav-overlay ${mobileOpen ? 'open' : ''}`}
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <nav className={`app-nav ${mobileOpen ? 'open' : ''}`} aria-label="Main navigation">
        <div className="nav-logo">
          <div className="nav-logo-text">Concierge</div>
          <div className="nav-logo-sub">Travel Disruption AI</div>
        </div>

        <ul className="nav-links" role="list">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <span className="nav-icon" aria-hidden="true">{icon}</span>
                {label}
              </NavLink>
            </li>
          ))}
        </ul>

        {user && (
          <div className="nav-footer">
            <button
              type="button"
              className="nav-user"
              onClick={handleLogout}
              title="Sign out"
              aria-label={`Signed in as ${user.name}. Sign out.`}
            >
              <div className="nav-user-avatar" aria-hidden="true">
                {initials(user.name)}
              </div>
              <div className="nav-user-info">
                <div className="nav-user-name">{user.name}</div>
                <div className="nav-user-tier">{fmtTier(user.card_tier)} Card</div>
              </div>
            </button>
          </div>
        )}
      </nav>

      {/* Main content */}
      <main className="app-main">
        {children}
      </main>
    </div>
  );
}
