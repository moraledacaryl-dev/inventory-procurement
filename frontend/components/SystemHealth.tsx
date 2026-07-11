"use client";

import { useEffect, useState } from "react";
import { API } from "../lib/api";

type HealthState = "checking" | "healthy" | "degraded" | "offline";

export function SystemHealth() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const response = await fetch(`${API}/ready`, { cache: "no-store", credentials: "include" });
        const body = await response.json().catch(() => ({}));
        if (!active) return;
        setState(response.ok && body.status === "ready" && body.database === "ok" ? "healthy" : "degraded");
      } catch {
        if (active) setState("offline");
      }
    }
    void check();
    const timer = window.setInterval(check, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const label = state === "healthy" ? "System healthy" : state === "degraded" ? "System degraded" : state === "offline" ? "System unavailable" : "Checking system";
  const detail = state === "healthy" ? "API and database ready" : state === "degraded" ? "A readiness check failed" : state === "offline" ? "API could not be reached" : "Verifying API and database";

  return <div className={`system-health system-health--${state}`} title={detail}><span className="system-health__dot"/><div><strong>{label}</strong><span>{detail}</span></div></div>;
}
