"use client";

import { FormEvent, useRef, useState } from "react";
import { api } from "../lib/api";
import { ConfirmDialog } from "./ConfirmDialog";
import type { Configuration } from "./ItemConfigurationPanel";

export type ConfigurationEdit =
  | { kind: "barcode"; row: Configuration["barcodes"][number] }
  | { kind: "conversion"; row: Configuration["conversions"][number] }
  | { kind: "supplier"; row: Configuration["supplier_items"][number] }
  | { kind: "policy"; row: Configuration["location_settings"][number] };

type Option = { id: string; code: string; name: string };
const titles = { barcode: "Edit barcode", conversion: "Edit unit conversion", supplier: "Edit supplier terms", policy: "Edit location policy" };

export function ItemConfigurationEditor({ itemId, edit, units, suppliers, onSaved, onClose }: {
  itemId: string; edit: ConfigurationEdit; units: Option[]; suppliers: Option[];
  onSaved: () => Promise<void>; onClose: () => void;
}) {
  const form = useRef<HTMLFormElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const number = (name: string) => Number(data.get(name));
    const checked = (name: string) => data.get(name) === "on";
    let path: string;
    let body: Record<string, unknown>;
    if (edit.kind === "barcode") {
      path = `/items/${itemId}/barcodes/${edit.row.id}`;
      body = { barcode: data.get("barcode"), barcode_type: data.get("barcode_type"), is_primary: checked("is_primary") };
    } else if (edit.kind === "conversion") {
      if (data.get("from_unit_id") === data.get("to_unit_id")) { setError("Choose different From and To units."); return; }
      path = `/items/${itemId}/conversions/${edit.row.id}`;
      body = { from_unit_id: data.get("from_unit_id"), to_unit_id: data.get("to_unit_id"), multiplier: number("multiplier"), is_active: checked("is_active") };
    } else if (edit.kind === "supplier") {
      path = `/supplier-items/${edit.row.id}`;
      body = { supplier_sku: data.get("supplier_sku") || null, last_price: number("last_price"), lead_time_days: number("lead_time_days"), minimum_order_quantity: number("minimum_order_quantity"), is_preferred: checked("is_preferred") };
    } else {
      path = `/item-location-settings/${edit.row.id}`;
      if (data.get("maximum_stock") !== "" && number("maximum_stock") < number("minimum_stock")) { setError("Maximum stock must be at least the minimum."); return; }
      body = { minimum_stock: number("minimum_stock"), reorder_quantity: number("reorder_quantity"), maximum_stock: data.get("maximum_stock") === "" ? null : number("maximum_stock"), preferred_supplier_id: data.get("preferred_supplier_id") || null, cycle_count_days: number("cycle_count_days"), is_active: checked("is_active") };
    }
    setBusy(true); setError("");
    try {
      await api(path, { method: "PATCH", body: JSON.stringify(body) });
      await onSaved();
      onClose();
    } catch (exception) { setError((exception as Error).message); }
    finally { setBusy(false); }
  }

  return <ConfirmDialog open title={titles[edit.kind]} confirmLabel="Save changes" busy={busy}
    onConfirm={() => form.current?.requestSubmit()} onCancel={onClose}>
    <form ref={form} className="configuration-editor" aria-label={titles[edit.kind]} data-training={`edit-${edit.kind}-form`} onSubmit={save}>
      {edit.kind === "barcode" && <>
        <label>Barcode<input name="barcode" required minLength={3} maxLength={100} defaultValue={edit.row.barcode}/></label>
        <label>Code type<select name="barcode_type" defaultValue={edit.row.barcode_type}>{Array.from(new Set([edit.row.barcode_type,"EAN13","UPC","CODE128","QR","INTERNAL"])).map(type=><option key={type}>{type}</option>)}</select></label>
        <label className="inline-check"><input name="is_primary" type="checkbox" defaultChecked={edit.row.is_primary}/> Primary barcode</label>
      </>}
      {edit.kind === "conversion" && <>
        <p className="configuration-editor-note">Check the direction: 1 From unit equals the multiplier in To units.</p>
        <label>From unit<select name="from_unit_id" required defaultValue={edit.row.from_unit_id}>{units.map(unit=><option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label>
        <label>Multiplier<input name="multiplier" type="number" min="0.000001" step="0.000001" required defaultValue={edit.row.multiplier}/></label>
        <label>To unit<select name="to_unit_id" required defaultValue={edit.row.to_unit_id}>{units.map(unit=><option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label>
        <label className="inline-check"><input name="is_active" type="checkbox" defaultChecked={edit.row.is_active}/> Available for new entries</label>
      </>}
      {edit.kind === "supplier" && <>
        <p className="configuration-editor-note">{edit.row.supplier_name}</p>
        <label>Supplier item code<input name="supplier_sku" maxLength={100} defaultValue={edit.row.supplier_sku || ""}/></label>
        <label>Last price (PHP)<input name="last_price" type="number" min="0" step="0.0001" required defaultValue={edit.row.last_price}/></label>
        <label>Delivery lead time (days)<input name="lead_time_days" type="number" min="0" max="3650" step="1" required defaultValue={edit.row.lead_time_days}/></label>
        <label>Minimum order quantity<input name="minimum_order_quantity" type="number" min="0.0001" step="0.0001" required defaultValue={edit.row.minimum_order_quantity}/></label>
        <label className="inline-check"><input name="is_preferred" type="checkbox" defaultChecked={edit.row.is_preferred}/> Preferred supplier</label>
      </>}
      {edit.kind === "policy" && <>
        <p className="configuration-editor-note">{edit.row.location_name}</p>
        <label>Minimum stock<input name="minimum_stock" type="number" min="0" step="0.0001" required defaultValue={edit.row.minimum_stock}/></label>
        <label>Reorder quantity<input name="reorder_quantity" type="number" min="0" step="0.0001" required defaultValue={edit.row.reorder_quantity}/></label>
        <label>Maximum stock (optional)<input name="maximum_stock" type="number" min="0" step="0.0001" defaultValue={edit.row.maximum_stock ?? ""}/></label>
        <label>Preferred supplier<select name="preferred_supplier_id" defaultValue={edit.row.preferred_supplier_id || ""}><option value="">No supplier override</option>{suppliers.map(supplier=><option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>)}</select></label>
        <label>Count every (days)<input name="cycle_count_days" type="number" min="1" max="3650" step="1" required defaultValue={edit.row.cycle_count_days}/></label>
        <label className="inline-check"><input name="is_active" type="checkbox" defaultChecked={edit.row.is_active}/> Active policy</label>
      </>}
      {error && <p className="configuration-editor-error" role="alert">{error}</p>}
      <button type="submit" hidden disabled={busy}>Save changes</button>
    </form>
  </ConfirmDialog>;
}
