import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { initials, fmtTier } from '../utils/formatters';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Trips', icon: 'TR' },
  { to: '/notifications', label: 'Notifications', icon: 'NT' },
  { to: '/insurance', label: 'Benefits', icon: 'BN' },
  { to: '/settings', label: 'Settings', icon: 'ST' },
];

interface AppShellProps {
  children: React.ReactNode;
}

const SIDEBAR_PREFERENCE_KEY = 'concierge_sidebar_hidden';

export function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_PREFERENCE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  function handleLogout() {
    logout();
    navigate('/login');
  }

  function setSidebarVisibility(hidden: boolean) {
    setSidebarHidden(hidden);
    try {
      localStorage.setItem(SIDEBAR_PREFERENCE_KEY, String(hidden));
    } catch {
      // The preference is non-essential; the control still works in memory.
    }
  }

  return (
    <div className={`app-shell ${sidebarHidden ? 'sidebar-hidden' : ''}`}>
      {/* Mobile toggle */}
      <button
        className="nav-toggle"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Toggle navigation"
        aria-expanded={mobileOpen}
        aria-controls="main-sidebar"
      >
        {mobileOpen ? '✕' : '☰'}
      </button>

      {sidebarHidden && (
        <button
          type="button"
          className="sidebar-reopen"
          onClick={() => setSidebarVisibility(false)}
          aria-label="Show sidebar"
          title="Show sidebar"
          aria-controls="main-sidebar"
        >
          <span aria-hidden="true">›</span>
          <span>Menu</span>
        </button>
      )}

      {/* Overlay */}
      <div
        className={`nav-overlay ${mobileOpen ? 'open' : ''}`}
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <nav
        id="main-sidebar"
        className={`app-nav ${mobileOpen ? 'open' : ''}`}
        aria-label="Main navigation"
      >
        <div className="nav-logo">
          <div>
            <div className="nav-logo-mark" aria-hidden="true">C</div>
            <div className="nav-logo-text">Concierge</div>
            <div className="nav-logo-sub">Cardmember Travel</div>
          </div>
          <button
            type="button"
            className="nav-collapse"
            onClick={() => setSidebarVisibility(true)}
            aria-label="Hide sidebar"
            title="Hide sidebar"
          >
            ‹
          </button>
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
            <div className="nav-user">
              <div className="nav-user-avatar" aria-hidden="true">
                {initials(user.name)}
              </div>
              <div className="nav-user-info">
                <div className="nav-user-name">{user.name}</div>
                <div className="nav-user-tier">{fmtTier(user.card_tier)} Card</div>
              </div>
            </div>
            <button
              type="button"
              className="nav-logout"
              onClick={handleLogout}
              aria-label={`Sign out ${user.name}`}
            >
              <span>Sign out</span>
              <span aria-hidden="true">↗</span>
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
