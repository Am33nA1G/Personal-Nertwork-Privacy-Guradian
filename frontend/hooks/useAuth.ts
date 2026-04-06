import { useState, useEffect, useCallback } from 'react';
import { apiLogin, apiSetup } from '../lib/api';

const TOKEN_KEY = 'pnpg_token';

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [needsSetup, setNeedsSetup] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Restore session token if present. Setup state is discovered lazily on the first login
    // attempt: POST /api/v1/auth/login returns HTTP 503 with { detail: "Run setup first" }
    // when no password has been configured. /api/v1/health does NOT expose a needs_setup flag.
    // The dashboard always shows the login form first; the setup branch is only entered after
    // the 503 response is received.
    const stored = sessionStorage.getItem(TOKEN_KEY);
    setToken(stored);
  }, []);

  const login = useCallback(async (password: string) => {
    setError(null);
    setLoading(true);
    try {
      const res = await apiLogin(password);
      // Backend returns HTTP 503 + { detail: "Run setup first" } when no password is configured.
      // This is the ONLY signal for first-run state; /api/v1/health does not expose it.
      if (res.detail === 'Run setup first') {
        setNeedsSetup(true);
        setLoading(false);
        return;
      }
      const tok = res?.data?.access_token;
      if (!tok) {
        setError(res?.detail ?? 'Login failed');
        setLoading(false);
        return;
      }
      sessionStorage.setItem(TOKEN_KEY, tok);
      setToken(tok);
    } catch {
      setError('Network error \u2014 is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  const setup = useCallback(async (password: string) => {
    setError(null);
    try {
      const res = await apiSetup(password);
      if (res?.data?.message) {
        setNeedsSetup(false);
        await login(password);
      } else {
        setError(res?.detail ?? 'Setup failed');
      }
    } catch {
      setError('Network error');
    }
  }, [login]);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  return { token, needsSetup, loading, error, login, setup, logout };
}
