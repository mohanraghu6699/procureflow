import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchMe, login as loginApi } from "../api/endpoints";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  // Re-reads the signed-in user from the server (for example after a required password change).
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }

    const stored = localStorage.getItem("user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem("user");
      }
    }

    // Re-validate the session against the server and refresh role/department in
    // case they changed since login (e.g. an admin updated this user), rather
    // than trusting the cached copy in localStorage indefinitely. A 401 here is
    // handled globally by the axios interceptor (clears storage, redirects to
    // /login); other failures (e.g. offline) just keep the cached user.
    fetchMe()
      .then((freshUser) => {
        setUser(freshUser);
        localStorage.setItem("user", JSON.stringify(freshUser));
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token, user: loggedInUser } = await loginApi(email, password);
    localStorage.setItem("access_token", access_token);
    localStorage.setItem("user", JSON.stringify(loggedInUser));
    setUser(loggedInUser);
  }

  async function refreshUser() {
    const freshUser = await fetchMe();
    localStorage.setItem("user", JSON.stringify(freshUser));
    setUser(freshUser);
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, refreshUser }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
