"use client";

import { useEffect, useState } from "react";
import { API } from "../lib/api";

type HealthState = "checking" | "healthy" | "degraded" | "offline";

export function SystemHealth() {
  const training=process.env.NEXT_PUBLIC_INVENTORY_TRAINING==="1";
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const response = await fetch(`${API}/${training?"health":"ready"}`, { cache: "no-store", credentials: "include" });
        const body = await response.json().catch(() => ({}));
        if (!active) return;
        setState(response.ok && (training?body.status==="ok":body.status === "ready" && body.database === "ok") ? "healthy" : "degraded");
      } catch {
        if (active) setState("offline");
      }
    }
    void check();
    const timer = window.setInterval(check, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, [training]);

  const label = training?(state==="healthy"?"Practice connected":state==="checking"?"Checking practice":"Practice unavailable"):state === "healthy" ? "System healthy" : state === "degraded" ? "System degraded" : state === "offline" ? "System unavailable" : "Checking system";
  const detail = training?(state==="healthy"?"Training service is available":state==="checking"?"Checking the training service":"Reconnect to practice from your course"):state === "healthy" ? "API and database ready" : state === "degraded" ? "A readiness check failed" : state === "offline" ? "API could not be reached" : "Verifying API and database";

  return <div className={`system-health system-health--${state}`} title={detail}><span className="system-health__dot"/><div><strong>{label}</strong><span>{detail}</span></div></div>;
}
