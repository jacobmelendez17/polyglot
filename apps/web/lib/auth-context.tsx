"use client";

// Client-side auth state. Tokens live in memory + localStorage so a refresh of
// the page keeps you signed in. The access token is short-lived; on a 401 we try
// the refresh token once before giving up. (When Auth.js lands, this swaps to
// httpOnly cookies; components consume the same useAuth() shape either way.)

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import { api, ApiClientError, type Me, type Tokens } from "./api";

const STORAGE_KEY = "polyglot.tokens";

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function readTokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

function writeTokens(tokens: Tokens | null) {
  if (typeof window === "undefined") return;
  if (tokens) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  else window.localStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async (tokens: Tokens) => {
    try {
      const me = await api.me(tokens.access_token);
      setUser(me);
      return true;
    } catch (err) {
      // Access token likely expired — try one refresh.
      if (err instanceof ApiClientError && err.status === 401) {
        try {
          const next = await api.refresh(tokens.refresh_token);
          writeTokens(next);
          const me = await api.me(next.access_token);
          setUser(me);
          return true;
        } catch {
          writeTokens(null);
          setUser(null);
          return false;
        }
      }
      return false;
    }
  }, []);

  // Bootstrap session on first load.
  useEffect(() => {
    const tokens = readTokens();
    if (!tokens) {
      setLoading(false);
      return;
    }
    loadUser(tokens).finally(() => setLoading(false));
  }, [loadUser]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    writeTokens(tokens);
    await loadUser(tokens);
  }, [loadUser]);

  const signup = useCallback(async (email: string, password: string) => {
    const tokens = await api.signup(email, password);
    writeTokens(tokens);
    await loadUser(tokens);
  }, [loadUser]);

  const logout = useCallback(async () => {
    const tokens = readTokens();
    if (tokens) {
      try { await api.logout(tokens.refresh_token); } catch { /* best effort */ }
    }
    writeTokens(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout }),
    [user, loading, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
