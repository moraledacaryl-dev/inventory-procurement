"use client";

import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

export type SessionUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  permissions: string[];
  accessible_modules: string[];
};

type SessionContextValue = {
  user: SessionUser | null;
  loading: boolean;
  can: (permission: string) => boolean;
  canAccessModule: (module: string) => boolean;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function permissionMatches(granted: string, requested: string) {
  if (granted === "*" || granted === requested) return true;
  const [domain, action] = requested.split(".", 2);
  return granted === `${domain}.*` || granted === "*.read" && action === "read";
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void api<SessionUser>("/auth/me")
      .then(value => { if (active) setUser(value); })
      .catch(() => undefined)
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const value = useMemo<SessionContextValue>(() => ({
    user,
    loading,
    can: permission => Boolean(user?.permissions.some(granted => permissionMatches(granted, permission))),
    canAccessModule: module => Boolean(user?.accessible_modules.includes(module)),
  }), [loading, user]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used within SessionProvider");
  return value;
}

export function Can({ permission, children, fallback = null }: { permission: string; children: ReactNode; fallback?: ReactNode }) {
  const { can, loading } = useSession();
  if (loading) return null;
  return can(permission) ? <>{children}</> : <>{fallback}</>;
}
