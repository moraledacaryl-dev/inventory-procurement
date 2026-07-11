import { ReactNode } from "react";

export function LoadingState({
  title = "Loading records",
  rows = 5,
}: {
  title?: string;
  rows?: number;
}) {
  return (
    <div className="async-state async-state--loading" role="status" aria-live="polite">
      <span className="sr-only">{title}</span>
      <div className="async-state__skeleton async-state__skeleton--title" />
      {Array.from({ length: rows }, (_, index) => (
        <div className="async-state__skeleton" key={index} />
      ))}
    </div>
  );
}

export function ErrorState({
  title = "Unable to load records",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="async-state async-state--error" role="alert">
      <div className="async-state__icon" aria-hidden="true">!</div>
      <div className="async-state__copy">
        <strong>{title}</strong>
        {message ? <span>{message}</span> : null}
      </div>
      {onRetry ? <button type="button" className="secondary" onClick={onRetry}>Try again</button> : null}
    </div>
  );
}

export function EmptyState({
  title = "No records yet",
  message = "Records will appear here once activity begins.",
  icon = "—",
  action,
}: {
  title?: string;
  message?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <strong>{title}</strong>
      <span>{message}</span>
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}
