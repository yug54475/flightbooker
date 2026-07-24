import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './store/auth';
import { ToastProvider } from './store/toast';
import { ToastSurface } from './components/ui/ToastSurface';
import { RequireAuth, RedirectIfAuthed } from './guards';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { PolicySetupPage } from './pages/PolicySetupPage';
import { DashboardPage } from './pages/DashboardPage';
import { DisruptionPage } from './pages/DisruptionPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { InsurancePage } from './pages/InsurancePage';
import { SettingsPage } from './pages/SettingsPage';
import { ApiRequestError } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, error) => {
        // Never retry on 401 (handled by auth store) or 403
        if (
          error instanceof ApiRequestError &&
          (error.status === 401 || error.status === 403)
        ) {
          return false;
        }
        return failureCount < 2;
      },
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              {/* Public routes — redirect to dashboard if already logged in */}
              <Route element={<RedirectIfAuthed />}>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
              </Route>

              {/* Policy setup — requires auth but no shell (full-page) */}
              <Route element={<RequireAuth withShell={false} />}>
                <Route path="/policy-setup" element={<PolicySetupPage />} />
              </Route>

              {/* Protected app routes */}
              <Route element={<RequireAuth />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/disruption/event/:eventId" element={<DisruptionPage />} />
                <Route path="/disruption/:jobId" element={<DisruptionPage />} />
                <Route path="/notifications" element={<NotificationsPage />} />
                <Route path="/insurance" element={<InsurancePage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              {/* Catch-all */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </BrowserRouter>
          <ToastSurface />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
