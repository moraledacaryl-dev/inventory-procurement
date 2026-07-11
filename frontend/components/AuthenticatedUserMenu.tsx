"use client";

import { useEffect, useRef, useState } from "react";
import { api, logout } from "../lib/api";

type SessionUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] || "U") + (parts.length > 1 ? parts[parts.length - 1][0] : "");
}

function roleLabel(role: string) {
  return role.replace(/[_-]+/g, " ").replace(/\b\w/g, character => character.toUpperCase());
}

export function AuthenticatedUserMenu() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    void api<SessionUser>("/auth/me")
      .then(value => { if (active) setUser(value); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
    } catch {
      setSigningOut(false);
    }
  }

  const displayName = user?.full_name || "Loading account…";
  const displayRole = user ? roleLabel(user.role) : "Checking session";

  return (
    <div className="authenticated-user" ref={containerRef}>
      <button className="user-menu user-menu-button" type="button" onClick={() => setOpen(value => !value)} aria-haspopup="menu" aria-expanded={open}>
        <div className="user-avatar" aria-hidden="true">{user ? initials(user.full_name).slice(0, 2).toUpperCase() : "…"}</div>
        <div className="user-copy"><strong>{displayName}</strong><span>{displayRole}</span></div>
        <span className="user-menu-chevron" aria-hidden="true">⌄</span>
      </button>
      {open ? (
        <div className="user-popover" role="menu">
          <div className="user-popover__identity">
            <strong>{displayName}</strong>
            <span>{user?.email || "Retrieving account details"}</span>
          </div>
          <div className="user-popover__role"><span>Role</span><strong>{displayRole}</strong></div>
          <button type="button" role="menuitem" className="user-popover__logout" onClick={signOut} disabled={signingOut}>{signingOut ? "Signing out…" : "Sign out"}</button>
        </div>
      ) : null}
    </div>
  );
}
