import { ReactNode } from "react";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger" | "violet";

const toneByStatus: Record<string, StatusTone> = {
  active: "success",
  approved: "success",
  completed: "success",
  received: "success",
  closed: "success",
  posted: "success",
  healthy: "success",
  ready: "success",
  draft: "neutral",
  inactive: "neutral",
  cancelled: "neutral",
  submitted: "info",
  pending: "warning",
  planned: "info",
  in_transit: "info",
  partial: "warning",
  partially_received: "warning",
  overdue: "danger",
  rejected: "danger",
  failed: "danger",
  dead_letter: "danger",
  low_stock: "warning",
  out_of_stock: "danger",
};

function humanize(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, character => character.toUpperCase());
}

export function statusTone(status: string): StatusTone {
  return toneByStatus[status.trim().toLowerCase()] ?? "neutral";
}

export function StatusBadge({
  status,
  label,
  tone,
  icon,
}: {
  status: string;
  label?: string;
  tone?: StatusTone;
  icon?: ReactNode;
}) {
  const resolvedTone = tone ?? statusTone(status);
  return (
    <span className={`status-badge status-badge--${resolvedTone}`}>
      {icon ? <span className="status-badge__icon" aria-hidden="true">{icon}</span> : null}
      <span>{label ?? humanize(status)}</span>
    </span>
  );
}
