import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { type Session } from "./api";

// The session lives in sessionStorage: it ends when the tab closes, and the token expires on the server anyway.
const KEY = "smartvitals.session";

function load(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    const session = raw ? (JSON.parse(raw) as Session) : null;
    return session && session.expiresAt > Date.now() ? session : null;
  } catch {
    return null;
  }
}

interface AuthValue {
  session: Session | null;
  signIn: (session: Session) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(load);

  const signIn = useCallback((value: Session) => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(value));
    } catch {
      /* private mode: keep it in memory only */
    }
    setSession(value);
  }, []);

  const signOut = useCallback(() => {
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
    setSession(null);
  }, []);

  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(signOut, Math.max(session.expiresAt - Date.now(), 0));
    return () => window.clearTimeout(timer);
  }, [session, signOut]);

  return <AuthContext.Provider value={{ session, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth outside AuthProvider");
  return value;
}
