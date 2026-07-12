"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner, FeedbackTone } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { ALL_OPERATIONS, readWorkspaceScope } from "../../components/WorkspaceSwitcher";
import { useFormDraft } from "../../hooks/useFormDraft";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { api } from "../../lib/api";
import { formatMoney, formatQuantity } from "../../lib/formatters";

type Ref = { id: string; name: string; code?: string };
type Dimension = { id: string; dimension_type: string; code: string; name: string; behavior_key?: string | null; parent_id?: string | null; workspace_id?: string | null; is_active: boolean };
type Bootstrap = { dimensions: Record<string, Dimension[]> };
type Item = { id: string; sku: string; name: string; minimum_stock: string; standard_cost: string; is_active: boolean; track_stock: boolean; allow_negative_stock: boolean; primary_workspace_id?: string | null; item_type_id?: string | null; record_class_id?: string | null };
type ItemDraft = { sku: string; name: string; category: string; unit: string; workspace: string; itemType: string; department: string; costCenter: string; defaultLocation: string; minimum: string; cost: string };
type Feedback = { tone: FeedbackTone; title: string; message?: string } | null;
type FieldErrors = Partial<Record<keyof ItemDraft, string>>;
const EMPTY_DRAFT: ItemDraft = { sku: "", name: "", category: "", unit: "", workspace: "", itemType: "", department: "", costCenter: "", defaultLocation: "", minimum: "0", cost: "0" };

export default function Page() {
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Ref[]>([]);
  const [units, setUnits] = useState<Ref[]>([]);
  const [locations, setLocations] = useState<Ref[]>([]);
  const [dimensions, setDimensions] = useState<Record<string, Dimension[]>>({});
  const [scope, setScope] = useState(ALL_OPERATIONS);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const { draft, setDraft, clearDraft, restored } = useFormDraft<ItemDraft>("inventory:item-draft:v2", EMPTY_DRAFT);
  const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(EMPTY_DRAFT), [draft]);
  useUnsavedChanges(isDirty && !saving);

  useEffect(() => {
    setScope(readWorkspaceScope());
    const handle = (event: Event) => setScope((event as CustomEvent<string>).detail || ALL_OPERATIONS);
    window.addEventListener("hidden-oasis:workspace-change", handle);
    return () => window.removeEventListener("hidden-oasis:workspace-change", handle);
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setLoadError("");
    try {
      const suffix = scope !== ALL_OPERATIONS ? `&workspace_id=${encodeURIComponent(scope)}` : "";
      const itemRequest = showInactive
        ? Promise.all([api<Item[]>(`/items?active=true${suffix}`), api<Item[]>(`/items?active=false${suffix}`)]).then(([active, inactive]) => [...active, ...inactive].sort((a, b) => a.sku.localeCompare(b.sku)))
        : api<Item[]>(`/items?active=true${suffix}`);
      const [itemRecords, categoryRecords, unitRecords, locationRecords, structure] = await Promise.all([itemRequest, api<Ref[]>("/categories"), api<Ref[]>("/units"), api<Ref[]>("/locations"), api<Bootstrap>("/classification/bootstrap")]);
      setItems(itemRecords); setCategories(categoryRecords); setUnits(unitRecords); setLocations(locationRecords); setDimensions(structure.dimensions);
      if (!draft.workspace && scope !== ALL_OPERATIONS) setDraft(current => ({ ...current, workspace: scope }));
    } catch (error) { setLoadError((error as Error).message); }
    finally { setLoading(false); }
  }, [showInactive, scope, draft.workspace, setDraft]);
  useEffect(() => { void load(); }, [load]);

  const workspaces = (dimensions.workspace || []).filter(row => row.is_active);
  const itemTypes = (dimensions.item_type || []).filter(row => row.is_active && row.workspace_id === draft.workspace);
  const departments = (dimensions.department || []).filter(row => row.is_active && (!row.workspace_id || row.workspace_id === draft.workspace));
  const costCenters = (dimensions.cost_center || []).filter(row => row.is_active && (!row.workspace_id || row.workspace_id === draft.workspace));
  const recordClasses = dimensions.record_class || [];
  const selectedType = itemTypes.find(row => row.id === draft.itemType);
  const derivedRecordClass = recordClasses.find(row => row.id === selectedType?.parent_id)?.name;
  const names = useMemo(() => Object.fromEntries(Object.values(dimensions).flat().map(row => [row.id, row.name])), [dimensions]);

  function update<K extends keyof ItemDraft>(key: K, value: ItemDraft[K]) {
    setDraft(current => ({ ...current, [key]: value, ...(key === "workspace" ? { itemType: "", department: "", costCenter: "" } : {}) }));
    setFieldErrors(current => ({ ...current, [key]: undefined })); setFeedback(null);
  }
  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!draft.sku.trim()) errors.sku = "Enter a SKU.";
    else if (!/^[A-Za-z0-9._-]+$/.test(draft.sku.trim())) errors.sku = "Use letters, numbers, periods, underscores, or hyphens only.";
    else if (items.some(item => item.sku.toLowerCase() === draft.sku.trim().toLowerCase())) errors.sku = "This SKU already exists.";
    if (!draft.name.trim()) errors.name = "Enter the item name.";
    if (!draft.workspace) errors.workspace = "Select the operating workspace.";
    if (!draft.itemType) errors.itemType = "Select the item type.";
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
      await api("/items", { method: "POST", body: JSON.stringify({
        sku: draft.sku.trim(), name: draft.name.trim(), category_id: draft.category, base_unit_id: draft.unit,
        primary_workspace_id: draft.workspace, item_type_id: draft.itemType,
        department_id: draft.department || null, cost_center_id: draft.costCenter || null,
        default_location_id: draft.defaultLocation || null,
        minimum_stock: Number(draft.minimum || 0), standard_cost: Number(draft.cost || 0),
      }) });
      const createdName = draft.name.trim(); clearDraft(); setFieldErrors({}); setFeedback({ tone: "success", title: "Item created", message: `${createdName} is classified and ready for its workspace workflows.` }); await load();
    } catch (error) { setFeedback({ tone: "error", title: "Item could not be saved", message: (error as Error).message }); }
    finally { setSaving(false); }
  }
  function discardDraft() { clearDraft(); setFieldErrors({}); setFeedback({ tone: "info", title: "Draft cleared", message: "The unsaved item details were removed." }); setConfirmDiscard(false); }

  return <AppShell title="Items" description="Maintain a shared catalogue while keeping F&B, Hotel, reusable property, assets, and shared operations clearly classified.">
    <section className="card"><div className="topline"><div><h2>Create item</h2><p>Choose the workspace and item type once. The system derives the record class and future workflow behavior automatically.</p></div>{restored && isDirty ? <span className="badge warning">Draft saved</span> : null}</div>
      <form onSubmit={submit} noValidate>
        <FormSection title="Operational identity" description="The item type drives its behavior. There is no separate recipe-eligibility setting.">
          <FormField label="Workspace" name="item-workspace" required error={fieldErrors.workspace}><select value={draft.workspace} onChange={event => update("workspace", event.target.value)}><option value="">Select workspace</option>{workspaces.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField>
          <FormField label="Item type" name="item-type" required error={fieldErrors.itemType} hint={derivedRecordClass ? `Record class: ${derivedRecordClass}` : "The record class is derived automatically."}><select value={draft.itemType} disabled={!draft.workspace} onChange={event => update("itemType", event.target.value)}><option value="">Select item type</option>{itemTypes.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField>
          <FormField label="Department or outlet" name="item-department" hint="Optional. Use when the item primarily belongs to one team."><select value={draft.department} disabled={!draft.workspace} onChange={event => update("department", event.target.value)}><option value="">Not assigned</option>{departments.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField>
          <FormField label="Cost center" name="item-cost-center" hint="Optional accounting and reporting scope."><select value={draft.costCenter} disabled={!draft.workspace} onChange={event => update("costCenter", event.target.value)}><option value="">Not assigned</option>{costCenters.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField>
        </FormSection>
        <FormSection title="Catalogue identity" description="The SKU becomes the canonical item reference across connected systems.">
          <FormField label="SKU" name="item-sku" required hint="Example: COF-BEAN-1KG." error={fieldErrors.sku}><input value={draft.sku} onChange={event => update("sku", event.target.value)} /></FormField>
          <FormField label="Item name" name="item-name" required error={fieldErrors.name}><input value={draft.name} onChange={event => update("name", event.target.value)} /></FormField>
          <FormField label="Category" name="item-category" required error={fieldErrors.category}><select value={draft.category} onChange={event => update("category", event.target.value)}><option value="">Select category</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></FormField>
          <FormField label="Base unit" name="item-unit" required error={fieldErrors.unit}><select value={draft.unit} onChange={event => update("unit", event.target.value)}><option value="">Select unit</option>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.code || unit.name}</option>)}</select></FormField>
        </FormSection>
        <FormSection title="Inventory defaults" description="These defaults can be refined per location after creation.">
          <FormField label="Default location" name="item-location"><select value={draft.defaultLocation} onChange={event => update("defaultLocation", event.target.value)}><option value="">No default location</option>{locations.map(location => <option key={location.id} value={location.id}>{location.code ? `${location.code} · ` : ""}{location.name}</option>)}</select></FormField>
          <FormField label="Minimum stock" name="item-minimum" required error={fieldErrors.minimum}><input value={draft.minimum} onChange={event => update("minimum", event.target.value)} type="number" step="0.0001" min="0" /></FormField>
          <FormField label="Standard cost" name="item-cost" required error={fieldErrors.cost}><input value={draft.cost} onChange={event => update("cost", event.target.value)} type="number" step="0.0001" min="0" /></FormField>
        </FormSection>
        <div className="form-actions"><button type="button" className="secondary" disabled={!isDirty || saving} onClick={() => setConfirmDiscard(true)}>Clear draft</button><button className="primary" disabled={saving}>{saving ? "Creating item…" : "Create item"}</button></div>
      </form>{feedback ? <FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}</section>
    <section className="card section-gap"><div className="topline"><div><h2>Item master</h2><p>{scope === ALL_OPERATIONS ? "Showing all operations." : `Scoped to ${names[scope] || "the selected workspace"}.`} Switch workspaces in the header without rebuilding filters.</p></div><label className="catalogue-toggle"><input type="checkbox" checked={showInactive} onChange={event => setShowInactive(event.target.checked)} /><span>Include inactive</span></label></div>
      <DataTable columns={["SKU", "Name", "Workspace", "Item type", "Minimum", "Standard cost", "Status"]} rows={items.map(item => [<Link key={item.id} className="catalogue-link" href={`/items/${item.id}`}>{item.sku}</Link>, <Link key={`${item.id}-name`} className="catalogue-link" href={`/items/${item.id}`}>{item.name}</Link>, item.primary_workspace_id ? names[item.primary_workspace_id] || "Classified" : <span key={`${item.id}-workspace`} className="badge warning">Unclassified</span>, item.item_type_id ? names[item.item_type_id] || "—" : "—", formatQuantity(item.minimum_stock), formatMoney(item.standard_cost), <StatusBadge key={`${item.id}-status`} status={item.is_active ? "active" : "inactive"} />])} rowIds={items.map(item => item.id)} loading={loading} error={loadError} onRetry={() => void load()} searchPlaceholder="Search by SKU, name, workspace, type, cost, or status" exportFileName="hidden-oasis-items" caption="Hidden Oasis item master" emptyTitle="No items found" emptyMessage={showInactive ? "No catalogue records are available in this workspace." : "Create the first item, change workspace, or include inactive records."} />
    </section>
    <ConfirmDialog open={confirmDiscard} title="Clear this item draft?" description="All unsaved catalogue details in this form will be removed." confirmLabel="Clear draft" tone="danger" onConfirm={discardDraft} onCancel={() => setConfirmDiscard(false)} />
  </AppShell>;
}
