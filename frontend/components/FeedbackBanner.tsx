import { ReactNode } from "react";

export type FeedbackTone = "success" | "error" | "warning" | "info";

export function FeedbackBanner({
  tone,
  title,
  message,
  action,
}: {
  tone: FeedbackTone;
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className={`feedback-banner feedback-banner--${tone}`} role={tone === "error" ? "alert" : "status"} aria-live="polite">
      <div className="feedback-banner__icon" aria-hidden="true">{tone === "success" ? "✓" : tone === "error" ? "!" : tone === "warning" ? "△" : "i"}</div>
      <div className="feedback-banner__copy">
        <strong>{title}</strong>
        {message ? <span>{message}</span> : null}
      </div>
      {action ? <div className="feedback-banner__action">{action}</div> : null}
    </div>
  );
}
