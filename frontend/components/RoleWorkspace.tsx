"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatters";
import { ErrorState, LoadingState } from "./AsyncState";

type ExceptionItem = {
  key: string;
  category: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  count: number;
  href: string;
  oldest_at: string | null;
};

type Workspace = {
  title: string;
  summary: string;
  categories: string[];
  quick_actions: { label: string; href: string }[];
};

type ExceptionResponse = {
  as_of: string;
  role: string;
  workspace: Workspace;
  summary: { total: number; critical: number; warning: number };
  exceptions: ExceptionItem[];
};

export function RoleWorkspace({ locationId }: { locationId?: string }) {
  const [data, setData] = useState<ExceptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const query = locationId ? `?location_id=${encodeURIComponent(locationId)}` : "";
    try {
      setData(await api<ExceptionResponse>(`/dashboard/exceptions${query}`));
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setLoading(false);
    }
  }, [locationId]);

  useEffect(() => { void load(); }, [load]);

  if (error) return <ErrorState title="Action centre unavailable" message={error} onRetry={() => void load()} />;
  if (loading) return <LoadingState title="Loading role workspace" rows={3} />;
  if (!data) return null;

  return (
    <section className="role-workspace" aria-labelledby="role-workspace-title">
      <div className="role-workspace__header">
        <div>
          <div className="page-kicker">Role workspace</div>
          <h2 id="role-workspace-title">{data.workspace.title}</h2>
          <p>{data.workspace.summary}</p>
        </div>
        <div className="exception-summary" aria-label={`${data.summary.total} exception groups`}>
          <span><strong>{data.summary.total}</strong> open groups</span>
          <span className="critical"><strong>{data.summary.critical}</strong> critical</span>
          <span className="warning"><strong>{data.summary.warning}</strong> warning</span>
        </div>
      </div>

      <div className="role-workspace__actions" aria-label="Role quick actions">
        {data.workspace.quick_actions.map((action, index) => (
          <Link key={action.href} className={`quick-action-button ${index === 0 ? "primary-action" : ""}`} href={action.href}>{action.label}</Link>
        ))}
      </div>

      <div className="exception-grid">
        {data.exceptions.length ? data.exceptions.map(item => (
          <Link className={`exception-card exception-card--${item.severity}`} href={item.href} key={item.key}>
            <div className="exception-card__top">
              <span className="exception-card__category">{item.category}</span>
              <span className={`exception-card__severity exception-card__severity--${item.severity}`}>{item.severity}</span>
            </div>
            <div className="exception-card__body">
              <strong>{item.title}</strong>
              <p>{item.message}</p>
            </div>
            <div className="exception-card__footer">
              <span>{item.count} affected</span>
              <span>{item.oldest_at ? `Oldest ${formatDateTime(item.oldest_at)}` : `Checked ${formatDateTime(data.as_of)}`}</span>
              <span aria-hidden="true">Open →</span>
            </div>
          </Link>
        )) : (
          <div className="exception-clear">
            <div aria-hidden="true">✓</div>
            <strong>No role-relevant exceptions</strong>
            <span>The current operational checks found no unresolved exception groups for this workspace.</span>
          </div>
        )}
      </div>
    </section>
  );
}
