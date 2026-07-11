"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatMoney, formatQuantity } from "../lib/formatters";
import { Can } from "./SessionContext";
import { FeedbackBanner } from "./FeedbackBanner";
import { StatusBadge } from "./StatusBadge";

type Unit = { id: string; code: string; name: string };
type Supplier = { id: string; code: string; name: string };
type Location = { id: string; code: string; name: string };
type Configuration = {
  barcodes: { id: string; barcode: string; barcode_type: string; is_primary: boolean }[];
  conversions: { id: string; from_unit_id: string; from_unit_code: string; to_unit_id: string; to_unit_code: string; multiplier: string; is_active: boolean }[];
  supplier_items: { id: string; supplier_id: string; supplier_code: string; supplier_name: string; supplier_sku: string | null; last_price: string; lead_time_days: number; minimum_order_quantity: string; is_preferred: boolean }[];
  location_settings: { id: string; location_id: string; location_code: string; location_name: string; minimum_stock: string; reorder_quantity: string; maximum_stock: string | null; preferred_supplier_id: string | null; preferred_supplier_name: string | null; cycle_count_days: number; is_active: boolean }[];
};

type Feedback = { tone: "success" | "error" | "info"; title: string; message?: string } | null;

export function ItemConfigurationPanel({ itemId, baseUnitId }: { itemId: string; baseUnitId: string }) {
  const [configuration, setConfiguration] = useState<Configuration | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [config, unitRows, supplierRows, locationRows] = await Promise.all([
        api<Configuration>(`/items/${itemId}/configuration`),
        api<Unit[]>("/units"),
        api<Supplier[]>("/suppliers"),
        api<Location[]>("/locations"),
      ]);
      setConfiguration(config);
      setUnits(unitRows);
      setSuppliers(supplierRows);
      setLocations(locationRows);
    } catch (error) {
      setFeedback({ tone: "error", title: "Configuration unavailable", message: (error as Error).message });
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      setFeedback({ tone: "success", title: success });
      await load();
    } catch (error) {
      setFeedback({ tone: "error", title: "Configuration could not be saved", message: (error as Error).message });
    } finally {
      setBusy(false);
    }
  }

  function formData(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    return new FormData(event.currentTarget);
  }

  async function addBarcode(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const data = formData(event);
    await run(() => api(`/items/${itemId}/barcodes`, { method: "POST", body: JSON.stringify({ barcode: data.get("barcode"), barcode_type: data.get("barcode_type"), is_primary: data.get("is_primary") === "on" }) }), "Barcode added");
    form.reset();
  }

  async function addConversion(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const data = formData(event);
    await run(() => api(`/items/${itemId}/conversions`, { method: "POST", body: JSON.stringify({ from_unit_id: data.get("from_unit_id"), to_unit_id: data.get("to_unit_id"), multiplier: Number(data.get("multiplier")) }) }), "Unit conversion added");
    form.reset();
  }

  async function addSupplier(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const data = formData(event);
    const supplierId = String(data.get("supplier_id"));
    await run(() => api(`/suppliers/${supplierId}/items`, { method: "POST", body: JSON.stringify({ item_id: itemId, supplier_sku: data.get("supplier_sku") || null, last_price: Number(data.get("last_price") || 0), lead_time_days: Number(data.get("lead_time_days") || 0), minimum_order_quantity: Number(data.get("minimum_order_quantity") || 1), is_preferred: data.get("is_preferred") === "on" }) }), "Supplier linked");
    form.reset();
  }

  async function addLocationSetting(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const data = formData(event);
    await run(() => api("/item-location-settings", { method: "POST", body: JSON.stringify({ item_id: itemId, location_id: data.get("location_id"), minimum_stock: Number(data.get("minimum_stock") || 0), reorder_quantity: Number(data.get("reorder_quantity") || 0), maximum_stock: data.get("maximum_stock") ? Number(data.get("maximum_stock")) : null, preferred_supplier_id: data.get("preferred_supplier_id") || null, cycle_count_days: Number(data.get("cycle_count_days") || 30) }) }), "Location policy added");
    form.reset();
  }

  if (loading && !configuration) return <section className="card section-gap"><p>Loading item configuration…</p></section>;

  return (
    <section className="catalogue-config section-gap">
      <div className="topline"><div><h2>Purchasing and stock configuration</h2><p>Configure scannable identities, transaction units, supplier terms, and location-specific replenishment policies.</p></div></div>
      {feedback ? <FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      <div className="catalogue-config-grid">
        <article className="card config-card">
          <h3>Barcodes</h3><p>Assign one or more globally unique scan codes.</p>
          <div className="config-list">{configuration?.barcodes.length ? configuration.barcodes.map(row => <div className="config-row" key={row.id}><div><strong>{row.barcode}</strong><span>{row.barcode_type}</span></div>{row.is_primary ? <StatusBadge status="primary" /> : <span>Alternate</span>}<Can permission="items.*"><button className="text-button danger-text" disabled={busy} onClick={() => void run(() => api(`/items/${itemId}/barcodes/${row.id}`, { method: "DELETE" }), "Barcode removed")}>Remove</button></Can></div>) : <div className="config-empty">No barcodes configured.</div>}</div>
          <Can permission="items.*"><form className="config-form" onSubmit={addBarcode}><input name="barcode" placeholder="Barcode" required minLength={3}/><select name="barcode_type" defaultValue="EAN13"><option>EAN13</option><option>UPC</option><option>CODE128</option><option>QR</option><option>INTERNAL</option></select><label className="inline-check"><input type="checkbox" name="is_primary"/> Primary</label><button className="secondary" disabled={busy}>Add barcode</button></form></Can>
        </article>

        <article className="card config-card">
          <h3>Unit conversions</h3><p>Define exact multipliers between purchasing, storage, and issue units.</p>
          <div className="config-list">{configuration?.conversions.length ? configuration.conversions.map(row => <div className="config-row" key={row.id}><div><strong>1 {row.from_unit_code} = {formatQuantity(row.multiplier)} {row.to_unit_code}</strong><span>{row.is_active ? "Available for transactions" : "Inactive"}</span></div><StatusBadge status={row.is_active ? "active" : "inactive"}/></div>) : <div className="config-empty">No unit conversions configured.</div>}</div>
          <Can permission="items.*"><form className="config-form" onSubmit={addConversion}><select name="from_unit_id" defaultValue={baseUnitId}>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select><span className="form-equation">×</span><input name="multiplier" type="number" min="0.000001" step="0.000001" placeholder="Multiplier" required/><span className="form-equation">=</span><select name="to_unit_id" defaultValue="" required><option value="">To unit</option>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select><button className="secondary" disabled={busy}>Add conversion</button></form></Can>
        </article>

        <article className="card config-card">
          <h3>Supplier-item records</h3><p>Maintain supplier SKU, price, lead time, MOQ, and preferred-source status.</p>
          <div className="config-list">{configuration?.supplier_items.length ? configuration.supplier_items.map(row => <div className="config-row config-row-wide" key={row.id}><div><strong>{row.supplier_code} — {row.supplier_name}</strong><span>{row.supplier_sku || "No supplier SKU"} · {formatMoney(row.last_price)} · {row.lead_time_days} days · MOQ {formatQuantity(row.minimum_order_quantity)}</span></div>{row.is_preferred ? <StatusBadge status="preferred"/> : <span>Alternate</span>}<Can permission="suppliers.*"><button className="text-button danger-text" disabled={busy} onClick={() => void run(() => api(`/supplier-items/${row.id}`, { method: "DELETE" }), "Supplier unlinked")}>Remove</button></Can></div>) : <div className="config-empty">No suppliers linked.</div>}</div>
          <Can permission="suppliers.*"><form className="config-form config-form-wide" onSubmit={addSupplier}><select name="supplier_id" required defaultValue=""><option value="">Supplier</option>{suppliers.map(row => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><input name="supplier_sku" placeholder="Supplier SKU"/><input name="last_price" type="number" min="0" step="0.0001" placeholder="Last price"/><input name="lead_time_days" type="number" min="0" placeholder="Lead days"/><input name="minimum_order_quantity" type="number" min="0.0001" step="0.0001" defaultValue="1"/><label className="inline-check"><input type="checkbox" name="is_preferred"/> Preferred</label><button className="secondary" disabled={busy}>Link supplier</button></form></Can>
        </article>

        <article className="card config-card">
          <h3>Location policies</h3><p>Override global replenishment and count settings for each storage location.</p>
          <div className="config-list">{configuration?.location_settings.length ? configuration.location_settings.map(row => <div className="config-row config-row-wide" key={row.id}><div><strong>{row.location_code} — {row.location_name}</strong><span>Min {formatQuantity(row.minimum_stock)} · Reorder {formatQuantity(row.reorder_quantity)} · Max {row.maximum_stock ? formatQuantity(row.maximum_stock) : "None"} · Count every {row.cycle_count_days} days</span><span>{row.preferred_supplier_name ? `Preferred supplier: ${row.preferred_supplier_name}` : "No location supplier override"}</span></div><StatusBadge status={row.is_active ? "active" : "inactive"}/></div>) : <div className="config-empty">No location-specific policies configured.</div>}</div>
          <Can permission="inventory.*"><form className="config-form config-form-wide" onSubmit={addLocationSetting}><select name="location_id" required defaultValue=""><option value="">Location</option>{locations.map(row => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><input name="minimum_stock" type="number" min="0" step="0.0001" placeholder="Minimum"/><input name="reorder_quantity" type="number" min="0" step="0.0001" placeholder="Reorder qty"/><input name="maximum_stock" type="number" min="0" step="0.0001" placeholder="Maximum"/><select name="preferred_supplier_id" defaultValue=""><option value="">No supplier override</option>{suppliers.map(row => <option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><input name="cycle_count_days" type="number" min="1" max="3650" defaultValue="30"/><button className="secondary" disabled={busy}>Add policy</button></form></Can>
        </article>
      </div>
    </section>
  );
}
