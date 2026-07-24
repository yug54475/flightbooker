import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import type { User } from '../types';
import { getMe } from '../api/endpoints';
import { ApiRequestError, AUTH_EXPIRED_EVENT } from '../api/client';

interface AuthState {
  token: string | null;
  userId: string | null;
  user: User | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (token: string, userId: string) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const SESSION_KEY = 'tdc_auth';

interface StoredAuth {
  token: string;
  userId: string;
}

function loadFromSession(): StoredAuth | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

function saveToSession(token: string, userId: string) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ token, userId }));
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const stored = loadFromSession();
    return {
      token: stored?.token ?? null,
      userId: stored?.userId ?? null,
      user: null,
      isLoading: !!stored,
    };
  });

  const refreshUser = useCallback(async () => {
    if (!state.token) return;
    try {
      const user = await getMe(state.token);
      setState((s) => ({ ...s, user, isLoading: false }));
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        clearSession();
        setState({ token: null, userId: null, user: null, isLoading: false });
      } else {
        setState((s) => ({ ...s, isLoading: false }));
      }
    }
  }, [state.token]);

  // On mount, if we have a token, fetch user
  useEffect(() => {
    if (state.token && !state.user) {
      refreshUser();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback((token: string, userId: string) => {
    saveToSession(token, userId);
    setState((s) => ({ ...s, token, userId, isLoading: true }));
    // Will trigger user fetch via the effect below
    getMe(token)
      .then((user) =>
        setState({ token, userId, user, isLoading: false }),
      )
      .catch((err: unknown) => {
        if (err instanceof ApiRequestError && err.status === 401) {
          clearSession();
          setState({
            token: null,
            userId: null,
            user: null,
            isLoading: false,
          });
          return;
        }
        setState({ token, userId, user: null, isLoading: false });
      });
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setState({ token: null, userId: null, user: null, isLoading: false });
  }, []);

  useEffect(() => {
    window.addEventListener(AUTH_EXPIRED_EVENT, logout);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, logout);
  }, [logout]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
