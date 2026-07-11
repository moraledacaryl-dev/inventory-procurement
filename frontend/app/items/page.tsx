"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner, FeedbackTone } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { useFormDraft } from "../../hooks/useFormDraft";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { api } from "../../lib/api";
import { formatMoney, formatQuantity } from "../../lib/formatters";

type Ref = { id: string; name: string; code?: string };
type Item = { id: string; sku: string; name: string; minimum_stock: string; standard_cost: string; is_active: boolean; track_stock: boolean; allow_negative_stock: boolean };
type ItemDraft = { sku: string; name: string; category: string; unit: string; minimum: string; cost: string };
type Feedback = { tone: FeedbackTone; title: string; message?: string } | null;
type FieldErrors = Partial<Record<keyof ItemDraft, string>>;
const EMPTY_DRAFT: ItemDraft = { sku: "", name: "", category: "", unit: "", minimum: "0", cost: "0" };

export default function Page() {
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Ref[]>([]);
  const [units, setUnits] = useState<Ref[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const { draft, setDraft, clearDraft, restored } = useFormDraft<ItemDraft>("inventory:item-draft", EMPTY_DRAFT);
  const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(EMPTY_DRAFT), [draft]);
  useUnsavedChanges(isDirty && !saving);

  const load = useCallback(async () => {
    setLoading(true); setLoadError("");
    try {
      const [itemRecords, categoryRecords, unitRecords] = await Promise.all([api<Item[]>(`/items?active=${showInactive ? "" : "true"}`), api<Ref[]>("/categories"), api<Ref[]>("/units")]);
      setItems(itemRecords); setCategories(categoryRecords); setUnits(unitRecords);
    } catch (error) { setLoadError((error as Error).message); }
    finally { setLoading(false); }
  }, [showInactive]);
  useEffect(() => { void load(); }, [load]);

  function update<K extends keyof ItemDraft>(key: K, value: ItemDraft[K]) { setDraft(current => ({ ...current, [key]: value })); setFieldErrors(current => ({ ...current, [key]: undefined })); setFeedback(null); }
  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!draft.sku.trim()) errors.sku = "Enter a SKU.";
    else if (!/^[A-Za-z0-9._-]+$/.test(draft.sku.trim())) errors.sku = "Use letters, numbers, periods, underscores, or hyphens only.";
    else if (items.some(item => item.sku.toLowerCase() === draft.sku.trim().toLowerCase())) errors.sku = "This SKU already exists.";
    if (!draft.name.trim()) errors.name = "Enter the item name.";
    if (!draft.category) errors.category = "Select a category.";
    if (!draft.unit) errors.unit = "Select a base unit.";
    if (!Number.isFinite(Number(draft.minimum)) || Number(draft.minimum) < 0) errors.minimum = "Enter zero or a positive quantity.";
    if (!Number.isFinite(Number(draft.cost)) || Number(draft.cost) < 0) errors.cost = "Enter zero or a positive cost.";
    return errors;
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const errors = validate();
    if (Object.keys(errors).length) { setFieldErrors(errors); setFeedback({ tone: "error", title: "Check the highlighted fields", message: "The item was not saved because some information is missing or invalid." }); return; }
    setSaving(true); setFeedback(null);
    try {
      await api("/items", { method: "POST", body: JSON.stringify({ sku: draft.sku.trim(), name: draft.name.trim(), category_id: draft.category, base_unit_id: draft.unit, minimum_stock: Number(draft.minimum || 0), standard_cost: Number(draft.cost || 0) }) });
      const createdName = draft.name.trim(); clearDraft(); setFieldErrors({}); setFeedback({ tone: "success", title: "Item created", message: `${createdName} is now available for inventory and procurement workflows.` }); await load();
    } catch (error) { setFeedback({ tone: "error", title: "Item could not be saved", message: (error as Error).message }); }
    finally { setSaving(false); }
  }
  function discardDraft() { clearDraft(); setFieldErrors({}); setFeedback({ tone: "info", title: "Draft cleared", message: "The unsaved item details were removed." }); setConfirmDiscard(false); }

  return <AppShell title="Items" description="Maintain the catalogue used by stock, purchasing, recipes, production, and connected apps.">
    <section className="card"><div className="topline"><div><h2>Create item</h2><p>Use a stable SKU. Detailed stock, costing, and lifecycle controls are available after creation.</p></div>{restored && isDirty ? <span className="badge warning">Draft saved</span> : null}</div>
      <form onSubmit={submit} noValidate><FormSection title="Catalogue identity" description="The SKU becomes the canonical item reference across connected systems."><FormField label="SKU" name="item-sku" required hint="Example: COF-BEAN-1KG." error={fieldErrors.sku}><input value={draft.sku} onChange={event => update("sku", event.target.value)} /></FormField><FormField label="Item name" name="item-name" required error={fieldErrors.name}><input value={draft.name} onChange={event => update("name", event.target.value)} /></FormField><FormField label="Category" name="item-category" required error={fieldErrors.category}><select value={draft.category} onChange={event => update("category", event.target.value)}><option value="">Select category</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></FormField><FormField label="Base unit" name="item-unit" required error={fieldErrors.unit}><select value={draft.unit} onChange={event => update("unit", event.target.value)}><option value="">Select unit</option>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.code || unit.name}</option>)}</select></FormField></FormSection>
      <FormSection title="Inventory controls"><FormField label="Minimum stock" name="item-minimum" required error={fieldErrors.minimum}><input value={draft.minimum} onChange={event => update("minimum", event.target.value)} type="number" step="0.0001" min="0" /></FormField><FormField label="Standard cost" name="item-cost" required error={fieldErrors.cost}><input value={draft.cost} onChange={event => update("cost", event.target.value)} type="number" step="0.0001" min="0" /></FormField></FormSection>
      <div className="form-actions"><button type="button" className="secondary" disabled={!isDirty || saving} onClick={() => setConfirmDiscard(true)}>Clear draft</button><button className="primary" disabled={saving}>{saving ? "Creating item…" : "Create item"}</button></div></form>{feedback ? <FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}</section>
    <section className="card section-gap"><div className="topline"><div><h2>Item master</h2><p>Open an item to review stock by location, valuation, movement history, and lifecycle controls.</p></div><label className="catalogue-toggle"><input type="checkbox" checked={showInactive} onChange={event => setShowInactive(event.target.checked)} /><span>Include inactive</span></label></div>
      <DataTable columns={["SKU", "Name", "Minimum", "Standard cost", "Controls", "Status"]} rows={items.map(item => [<Link key={item.id} className="catalogue-link" href={`/items/${item.id}`}>{item.sku}</Link>, <Link key={`${item.id}-name`} className="catalogue-link" href={`/items/${item.id}`}>{item.name}</Link>, formatQuantity(item.minimum_stock), formatMoney(item.standard_cost), `${item.track_stock ? "Stock tracked" : "Non-stock"}${item.allow_negative_stock ? " · negative allowed" : ""}`, <StatusBadge key={`${item.id}-status`} status={item.is_active ? "active" : "inactive"} />])} rowIds={items.map(item => item.id)} loading={loading} error={loadError} onRetry={() => void load()} searchPlaceholder="Search by SKU, name, cost, control, or status" exportFileName="hidden-oasis-items" caption="Hidden Oasis item master" emptyTitle="No items found" emptyMessage={showInactive ? "No catalogue records are available." : "Create the first item or include inactive records."} />
    </section>
    <ConfirmDialog open={confirmDiscard} title="Clear this item draft?" description="All unsaved catalogue details in this form will be removed." confirmLabel="Clear draft" tone="danger" onConfirm={discardDraft} onCancel={() => setConfirmDiscard(false)} />
  </AppShell>;
}
