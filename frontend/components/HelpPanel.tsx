"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const helpByRoute: Record<string, { title: string; summary: string; steps: string[] }> = {
  "/dashboard": { title: "Dashboard help", summary: "Use the dashboard to review operational exceptions and move into the source workflow.", steps: ["Review low-stock and pending purchasing indicators.", "Open the related module before changing records.", "Use reports for dated or location-specific analysis."] },
  "/items": { title: "Items help", summary: "Items are the canonical inventory identities used by purchasing, recipes, production, POS mappings, and accounting events.", steps: ["Use a stable unique SKU.", "Choose the stock base unit carefully.", "Avoid duplicate records for the same physical item."] },
  "/purchasing": { title: "Purchasing help", summary: "Requisitions establish need; purchase orders authorize supply; receiving confirms what physically arrived.", steps: ["Review reorder suggestions before generating a requisition.", "Do not approve a request you submitted yourself.", "Use receiving for partial, rejected, or damaged quantities."] },
  "/receiving": { title: "Receiving help", summary: "Post only quantities physically received and inspected.", steps: ["Confirm the purchase order and destination.", "Separate accepted and rejected quantities.", "Record the supplier document reference before posting."] },
  "/counts": { title: "Inventory count help", summary: "Counts compare physical stock with the recorded ledger.", steps: ["Count the assigned location and scope only.", "Use blind entry when required.", "Investigate material variances before approval."] },
  "/production": { title: "Production help", summary: "Production consumes approved recipe ingredients and creates finished output.", steps: ["Confirm ingredient availability before starting.", "Record actual output and waste accurately.", "Do not complete a batch until quantities are verified."] },
};

export function HelpPanel() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const help = helpByRoute[pathname] || { title: "Workspace help", summary: "Use the navigation to open the operational module that owns the record or action.", steps: ["Search by SKU, supplier, location, requisition, or PO number.", "Only actions allowed by your role are shown.", "Contact an administrator when required access is missing."] };

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);

  return (
    <div className="help-center" ref={rootRef}>
      <button className="icon-button help-button" type="button" aria-label="Help" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.5 2.5 0 1 1 3.7 2.2c-1 .5-1.5 1.2-1.5 2.3M12 17h.01"/></svg>
      </button>
      {open ? <section className="help-popover" role="dialog" aria-label={help.title}><div className="help-popover__header"><strong>{help.title}</strong><button type="button" className="text-button" onClick={() => setOpen(false)}>Close</button></div><p>{help.summary}</p><ol>{help.steps.map(step => <li key={step}>{step}</li>)}</ol><div className="help-popover__footer">Context: <code>{pathname}</code></div></section> : null}
    </div>
  );
}
