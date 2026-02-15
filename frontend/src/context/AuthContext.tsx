import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { Role, User } from "@/api/types";
import { getMe, loginWithInitData, switchRole, updateLocale } from "@/api/auth";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  authenticated: boolean;
  login: (initData: string) => Promise<void>;
  setRole: (role: Role) => Promise<void>;
  setLocale: (locale: "en" | "ru") => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (initData: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await loginWithInitData(initData);
      localStorage.setItem("token", resp.access_token);
      setUser(resp.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const setRole = useCallback(async (role: Role) => {
    try {
      const updated = await switchRole(role);
      setUser(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Role switch failed");
    }
  }, []);

  const setLocale = useCallback(async (locale: "en" | "ru") => {
    try {
      const updated = await updateLocale(locale);
      setUser(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Locale update failed");
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
  }, []);

  // On mount: try to restore session from existing token
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      authenticated: user !== null,
      login,
      setRole,
      setLocale,
      logout,
    }),
    [user, loading, error, login, setRole, setLocale, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
