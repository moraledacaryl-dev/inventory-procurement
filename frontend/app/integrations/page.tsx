"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { api } from "../../lib/api";

type Event = {
  id: string;
  direction: string;
  source_system: string;
  destination_system: string;
  event_type: string;
  aggregate_id: string;
  status: string;
  attempts: number;
  last_error: string | null;
  created_at: string;
};

export default function Page() {
  const [rows, setRows] = useState<Event[]>([]);
  const [status, setStatus] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api(`/integration-events${status ? `?status=${status}` : ""}`));
    } catch (error) {
      setMsg((error as Error).message);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function retry(id: string) {
    try {
      await api(`/integration-events/${id}/retry`, { method: "POST" });
      setMsg("Event queued for retry.");
      await load();
    } catch (error) {
      setMsg((error as Error).message);
    }
  }

  return (
    <AppShell title="Integrations">
      <section className="grid">
        <div className="card">
          <h2>POS synchronization</h2>
          <p>Govern product mappings, recipe readiness, sale consumption, refunds, voids, and stock-document traceability.</p>
          <Link className="primary compact" href="/integrations/pos">Open POS workspace</Link>
        </div>
      </section>
      <section className="card section-gap">
        <div className="topline">
          <div>
            <h2>Event inbox and outbox</h2>
            <p>Durable, idempotent exchange with Accounting, POS, Staff, and Command Center.</p>
          </div>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="dead_letter">Dead letter</option>
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Direction</th><th>Route</th><th>Event</th><th>Aggregate</th><th>Status</th><th>Attempts</th><th>Action</th></tr>
            </thead>
            <tbody>
              {rows.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.created_at).toLocaleString()}</td>
                  <td>{entry.direction}</td>
                  <td>{entry.source_system} → {entry.destination_system}</td>
                  <td>{entry.event_type}</td>
                  <td>{entry.aggregate_id}</td>
                  <td>{entry.status}</td>
                  <td>{entry.attempts}</td>
                  <td>{["failed", "dead_letter"].includes(entry.status) ? <button className="secondary" onClick={() => retry(entry.id)}>Retry</button> : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {msg && <p className="status">{msg}</p>}
      </section>
    </AppShell>
  );
}
