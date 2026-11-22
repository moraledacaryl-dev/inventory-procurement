"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const helpByRoute: Record<string, { title: string; summary: string; steps: string[] }> = {
  "/dashboard": { title: "Dashboard help", summary: "See what needs attention today. Open an item or order to check it.", steps: ["Check items running low.", "Open the related item or purchase order.", "Ask your supervisor before adjusting stock that does not match."] },
  "/items": { title: "Items help", summary: "Use one item record for each product you keep in stock.", steps: ["Search by item name or stock code (SKU).", "Check the unit, such as piece, bottle, or kilogram.", "Ask your manager before making a new item if one already exists."] },
  "/purchasing": { title: "Purchasing help", summary: "Follow the order: see what is low, request it, get approval, then order.", steps: ["To order: check suggested items and quantities.", "Requests: ask an authorized manager to approve the request.", "Quotes & orders: compare suppliers and open the approved purchase order.", "Received a delivery? Open Receiving to record what actually arrived."] },
  "/receiving": { title: "Receiving help", summary: "Record only what the supplier delivered, not what you expected to receive.", steps: ["Select the purchase order and check where the items should go.", "For each item, enter how many arrived. If damaged, enter how many were rejected and why.", "Enter the delivery receipt (DR) number, review the totals, then confirm.", "If the connection fails, check the receipt history before trying again."] },
  "/counts": { title: "Stock count help", summary: "Count the actual items on the shelf or in the storage area.", steps: ["Open a count for the correct location.", "Count each item and enter the number you can see. Enter 0 if none are there.", "Save your work before leaving or submitting.", "If stock has moved during the count, tell your manager and recount as needed."] },
  "/stock": { title: "Stock movement help", summary: "Choose what happened to the stock before recording it.", steps: ["Received from a supplier? Use Receiving if there is a purchase order.", "Issued or used stock? Choose Issue.", "Moved stock to another storage area? Choose Transfer.", "Fixing an incorrect balance? Choose Adjustment, write the reason, and ask a manager if unsure.", "Review item, quantity and location before confirming."] },
  "/production": { title: "Production help", summary: "Record ingredients used and the finished food or drinks.", steps: ["Check that the recipe and quantities are correct.", "Record actual output and any waste.", "Confirm only after checking the numbers."] },
};

export function HelpPanel() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const help = helpByRoute[pathname] || (pathname.startsWith("/counts/") ? helpByRoute["/counts"] : { title: "Workspace help", summary: "Use the navigation to open the operational module that owns the record or action.", steps: ["Search by item, supplier, location, or order number.", "Only actions allowed by your role are shown.", "Ask your supervisor when you cannot open an action."] });

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); triggerRef.current?.focus(); } };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);

  return (
    <div className="help-center" ref={rootRef}>
      <button ref={triggerRef} className="icon-button help-button" type="button" aria-label="Help" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.5 2.5 0 1 1 3.7 2.2c-1 .5-1.5 1.2-1.5 2.3M12 17h.01"/></svg>
      </button>
      {open ? <section className="help-popover" role="dialog" aria-label={help.title}><div className="help-popover__header"><strong>{help.title}</strong><button ref={closeRef} type="button" className="text-button" onClick={() => {setOpen(false); triggerRef.current?.focus();}}>Close</button></div><p>{help.summary}</p><ol>{help.steps.map(step => <li key={step}>{step}</li>)}</ol><div className="help-popover__footer">Need more help? Ask your supervisor before posting stock or approving a request.</div></section> : null}
    </div>
  );
}
