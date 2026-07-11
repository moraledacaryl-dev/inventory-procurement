"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "./SessionContext";

type SearchRecord = { id: string; type: string; title: string; subtitle: string; href: string; keywords: string };
type Item = { id: string; sku: string; name: string };
type Supplier = { id: string; code: string; name: string; contact_name?: string | null };
type Location = { id: string; code: string; name: string };
type Requisition = { id: string; requisition_number: string; department: string; status: string };
type PurchaseOrder = { id: string; purchase_order_number: string; status: string; supplier_id: string };

export function GlobalSearch() {
  const { canAccessModule } = useSession();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState<SearchRecord[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
        rootRef.current?.querySelector<HTMLInputElement>("input")?.focus();
      }
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", key);
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      const jobs: Promise<SearchRecord[]>[] = [];
      if (canAccessModule("items")) jobs.push(api<Item[]>("/items").then(rows => rows.map(row => ({ id: row.id, type: "Item", title: `${row.sku} — ${row.name}`, subtitle: "Inventory item", href: `/items?item=${row.id}`, keywords: `${row.sku} ${row.name}` }))));
      if (canAccessModule("suppliers")) jobs.push(api<Supplier[]>("/suppliers").then(rows => rows.map(row => ({ id: row.id, type: "Supplier", title: `${row.code} — ${row.name}`, subtitle: row.contact_name || "Supplier", href: `/suppliers?supplier=${row.id}`, keywords: `${row.code} ${row.name} ${row.contact_name || ""}` }))));
      if (canAccessModule("locations")) jobs.push(api<Location[]>("/locations").then(rows => rows.map(row => ({ id: row.id, type: "Location", title: `${row.code} — ${row.name}`, subtitle: "Stock location", href: `/locations?location=${row.id}`, keywords: `${row.code} ${row.name}` }))));
      if (canAccessModule("purchasing")) {
        jobs.push(api<Requisition[]>("/requisitions").then(rows => rows.map(row => ({ id: row.id, type: "Requisition", title: row.requisition_number, subtitle: `${row.department} · ${row.status}`, href: `/purchasing?requisition=${row.id}`, keywords: `${row.requisition_number} ${row.department} ${row.status}` }))));
        jobs.push(api<PurchaseOrder[]>("/purchase-orders").then(rows => rows.map(row => ({ id: row.id, type: "Purchase order", title: row.purchase_order_number, subtitle: row.status, href: `/purchasing?purchase_order=${row.id}`, keywords: `${row.purchase_order_number} ${row.status}` }))));
      }
      try {
        const groups = await Promise.all(jobs);
        if (active) setRecords(groups.flat());
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [canAccessModule]);

  const results = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (normalized.length < 2) return [];
    return records.filter(record => record.keywords.toLocaleLowerCase().includes(normalized)).slice(0, 12);
  }, [query, records]);

  return (
    <div className="global-search-shell" ref={rootRef}>
      <label className="global-search">
        <span className="sr-only">Search records</span>
        <input type="search" value={query} onFocus={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setOpen(true); }} placeholder="Search items, suppliers, POs…" />
        <span className="global-search__shortcut" aria-hidden="true">⌘K</span>
      </label>
      {open ? (
        <div className="global-search-results" role="dialog" aria-label="Global search results">
          {!query.trim() ? <div className="global-search-empty"><strong>Search operational records</strong><span>Enter at least two characters. Results respect your current permissions.</span></div> : null}
          {query.trim().length === 1 ? <div className="global-search-empty"><span>Enter one more character to search.</span></div> : null}
          {query.trim().length >= 2 && loading ? <div className="global-search-empty"><span>Loading searchable records…</span></div> : null}
          {query.trim().length >= 2 && !loading && !results.length ? <div className="global-search-empty"><strong>No matching records</strong><span>Try a SKU, supplier code, PO number, location, or item name.</span></div> : null}
          {results.map(result => <Link key={`${result.type}-${result.id}`} href={result.href} className="global-search-result" onClick={() => setOpen(false)}><span className="global-search-result__type">{result.type}</span><span className="global-search-result__copy"><strong>{result.title}</strong><span>{result.subtitle}</span></span><span aria-hidden="true">→</span></Link>)}
        </div>
      ) : null}
    </div>
  );
}
