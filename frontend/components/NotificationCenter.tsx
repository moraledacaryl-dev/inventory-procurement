"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatters";
import { useSession } from "./SessionContext";

type Notification = { id: string; title: string; message: string; severity: string; created_at: string; is_read: boolean };

export function NotificationCenter() {
  const { can } = useSession();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const allowed = can("reports.read");

  async function load() {
    if (!allowed) return;
    setLoading(true);
    try { setNotifications(await api<Notification[]>("/notifications")); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [allowed]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);

  async function markRead(notification: Notification) {
    if (notification.is_read) return;
    const updated = await api<Notification>(`/notifications/${notification.id}/read`, { method: "POST" });
    setNotifications(current => current.map(item => item.id === updated.id ? updated : item));
  }

  if (!allowed) return null;
  const unread = notifications.filter(item => !item.is_read).length;

  return (
    <div className="notification-center" ref={rootRef}>
      <button className="icon-button" type="button" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M10 19h4"/></svg>
        {unread ? <span className="notification-count">{unread > 99 ? "99+" : unread}</span> : null}
      </button>
      {open ? (
        <section className="notification-popover" role="dialog" aria-label="Notifications">
          <div className="notification-popover__header"><div><strong>Notifications</strong><span>{unread} unread</span></div><button type="button" className="text-button" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button></div>
          <div className="notification-list">
            {!notifications.length && !loading ? <div className="notification-empty">No operational notifications.</div> : null}
            {notifications.map(item => <button type="button" key={item.id} className={`notification-item ${item.is_read ? "is-read" : "is-unread"}`} onClick={() => void markRead(item)}><span className={`notification-item__severity severity-${item.severity}`} aria-hidden="true"/><span className="notification-item__copy"><strong>{item.title}</strong><span>{item.message}</span><small>{formatDateTime(item.created_at)}{item.is_read ? " · Read" : " · Mark as read"}</small></span></button>)}
          </div>
        </section>
      ) : null}
    </div>
  );
}
