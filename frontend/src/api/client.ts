import type { ApiError } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
export const AUTH_EXPIRED_EVENT = 'concierge:auth-expired';

// ---------------------------------------------------------------------------
// Shared error class
// ---------------------------------------------------------------------------
export class ApiRequestError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper — reads the standard { error: { code, message } } envelope
// ---------------------------------------------------------------------------
async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiRequestError(
      0,
      'network_error',
      'The concierge service could not be reached. Check that the backend is running, then try again.',
    );
  }

  if (res.status === 204) return undefined as unknown as T;

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    const envelope = body as ApiError | null;
    const code = envelope?.error?.code ?? 'internal_error';
    const message = envelope?.error?.message ?? `HTTP ${res.status}`;

    if (res.status === 401 && token && typeof window !== 'undefined') {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }

    throw new ApiRequestError(res.status, code, message);
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Convenience wrappers
// ---------------------------------------------------------------------------
export const api = {
  get: <T>(path: string, token?: string | null) =>
    request<T>(path, { method: 'GET' }, token),

  post: <T>(path: string, body: unknown, token?: string | null) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }, token),

  patch: <T>(path: string, body: unknown, token?: string | null) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }, token),
};
