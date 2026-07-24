import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './store/auth';
import { AppShell } from './components/AppShell';
import { LoadingCenter } from './components/ui/Spinner';

/** Redirect to /login if not authenticated */
export function RequireAuth({ withShell = true }: { withShell?: boolean }) {
  const { token, isLoading } = useAuth();

  if (isLoading) return <LoadingCenter label="Checking session…" />;
  if (!token) return <Navigate to="/login" replace />;

  return withShell ? (
    <AppShell>
      <Outlet />
    </AppShell>
  ) : (
    <Outlet />
  );
}

/** Redirect to /dashboard if already authenticated */
export function RedirectIfAuthed() {
  const { token, isLoading } = useAuth();
  if (isLoading) return <LoadingCenter label="Checking session…" />;
  if (token) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
