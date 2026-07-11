"use client";

import { ReactNode, useEffect, useRef } from "react";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  busy = false,
  children,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [busy, onCancel, open]);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title" aria-describedby={description ? "confirm-dialog-description" : undefined}>
        <div className={`confirm-dialog__icon confirm-dialog__icon--${tone}`} aria-hidden="true">{tone === "danger" ? "!" : "?"}</div>
        <div className="confirm-dialog__body">
          <h2 id="confirm-dialog-title">{title}</h2>
          {description ? <p id="confirm-dialog-description">{description}</p> : null}
          {children}
        </div>
        <div className="confirm-dialog__actions">
          <button ref={cancelRef} type="button" className="secondary" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button type="button" className={tone === "danger" ? "danger-button" : "primary"} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}
