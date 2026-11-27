"use client";

import { FormEvent, useRef, useState } from "react";
import { api } from "../lib/api";
import { ConfirmDialog } from "./ConfirmDialog";

type WorkOrder = { id: string; work_order_number: string; title: string };

export function MaintenanceCompletion({ order, onSaved, onClose }: {
  order: WorkOrder; onSaved: () => Promise<void>; onClose: () => void;
}) {
  const form = useRef<HTMLFormElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function complete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api(`/maintenance/work-orders/${order.id}/complete`, { method: "POST", body: JSON.stringify({
        labor_cost: Number(data.get("labor_cost")), external_cost: Number(data.get("external_cost")),
        downtime_hours: Number(data.get("downtime_hours")), completion_notes: data.get("completion_notes") || null,
      }) });
      await onSaved(); onClose();
    } catch (exception) { setError((exception as Error).message); }
    finally { setBusy(false); }
  }
  return <ConfirmDialog open title="Complete work order" description={`${order.work_order_number} · ${order.title}`}
    confirmLabel="Complete work order" busy={busy} onConfirm={() => form.current?.requestSubmit()} onCancel={onClose}>
    <form ref={form} className="configuration-editor" aria-label="Completion details" data-training="maintenance-completion-form" onSubmit={complete}>
      <p className="configuration-editor-note">Enter the actual costs and downtime. Use 0 where none applies.</p>
      <label>Labor cost (PHP)<input name="labor_cost" type="number" min="0" step="0.01" required/></label>
      <label>Other costs (PHP)<input name="external_cost" type="number" min="0" step="0.01" required/></label>
      <label>Downtime (hours)<input name="downtime_hours" type="number" min="0" step="0.01" required/></label>
      <label>Completion notes<input name="completion_notes" maxLength={2000}/></label>
      {error && <p className="configuration-editor-error" role="alert">{error}</p>}
      <button type="submit" hidden disabled={busy}>Complete work order</button>
    </form>
  </ConfirmDialog>;
}
