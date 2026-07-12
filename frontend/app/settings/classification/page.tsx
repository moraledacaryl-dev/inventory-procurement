"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { DataTable } from "../../../components/DataTable";
import { FeedbackBanner, FeedbackTone } from "../../../components/FeedbackBanner";
import { FormField, FormSection } from "../../../components/FormField";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";

type Dimension = {
  id: string;
  dimension_type: string;
  code: string;
  name: string;
  description?: string | null;
  behavior_key?: string | null;
  parent_id?: string | null;
  workspace_id?: string | null;
  sort_order: number;
  settings: Record<string, unknown>;
  is_system: boolean;
  is_active: boolean;
};
type Category = { id: string; name: string; parent_id?: string | null; sort_order: number; is_active: boolean };
type ItemClassification = { item_id: string; sku: string; name: string; primary_workspace_id?: string | null; record_class_id?: string | null; item_type_id?: string | null; department_id?: string | null; cost_center_id?: string | null; default_location_id?: string | null; is_classified: boolean };
type Bootstrap = { dimensions: Record<string, Dimension[]>; categories: Category[]; summary: { unclassified_items: number; active_workspaces: number; active_item_types: number } };
type Feedback = { tone: FeedbackTone; title: string; message?: string } | null;

type MasterKey = "workspace" | "business_unit" | "department" | "cost_center" | "record_class" | "item_type" | "location_type" | "asset_class" | "depreciation_method" | "condition_status" | "movement_reason";
const MASTER_LABELS: Record<MasterKey, string> = {
  workspace: "Workspaces",
  business_unit: "Business units",
  department: "Departments & outlets",
  cost_center: "Cost centers",
  record_class: "Record classes",
  item_type: "Item types",
  location_type: "Location types",
  asset_class: "Asset classes",
  depreciation_method: "Depreciation methods",
  condition_status: "Condition statuses",
  movement_reason: "Movement reasons",
};
const MASTER_KEYS = Object.keys(MASTER_LABELS) as MasterKey[];

const EMPTY = { code: "", name: "", description: "", behavior_key: "", parent_id: "", workspace_id: "", sort_order: "0" };

export default function Page() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [items, setItems] = useState<ItemClassification[]>([]);
  const [selectedMaster, setSelectedMaster] = useState<MasterKey>("workspace");
  const [draft, setDraft] = useState(EMPTY);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [itemEdits, setItemEdits] = useState<Record<string, { primary_workspace_id: string; item_type_id: string; department_id: string; cost_center_id: string }>>({});

  const load = useCallback(async () => {
    setLoading(true); setLoadError("");
    try {
      const [structure, unclassified] = await Promise.all([
        api<Bootstrap>("/classification/bootstrap"),
        api<ItemClassification[]>("/classification/items?unclassified=true&limit=1000"),
      ]);
      setBootstrap(structure); setItems(unclassified);
      setItemEdits(Object.fromEntries(unclassified.map(item => [item.item_id, {
        primary_workspace_id: item.primary_workspace_id || "",
        item_type_id: item.item_type_id || "",
        department_id: item.department_id || "",
        cost_center_id: item.cost_center_id || "",
      }])));
    } catch (error) { setLoadError((error as Error).message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const dimensions = bootstrap?.dimensions || {};
  const workspaces = dimensions.workspace || [];
  const recordClasses = dimensions.record_class || [];
  const currentRows = (dimensions[selectedMaster] || []).filter(row => showInactive || row.is_active);
  const parentOptions = selectedMaster === "item_type" ? recordClasses : dimensions[selectedMaster] || [];

  function workspaceName(id?: string | null) { return workspaces.find(row => row.id === id)?.name || "—"; }
  function dimensionName(type: string, id?: string | null) { return (dimensions[type] || []).find(row => row.id === id)?.name || "—"; }

  async function createMaster(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.code.trim() || !draft.name.trim()) { setFeedback({ tone: "error", title: "Code and name are required" }); return; }
    setSaving(true); setFeedback(null);
    try {
      await api("/classification/dimensions", { method: "POST", body: JSON.stringify({
        dimension_type: selectedMaster,
        code: draft.code.trim(),
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        behavior_key: draft.behavior_key.trim() || null,
        parent_id: draft.parent_id || null,
        workspace_id: draft.workspace_id || null,
        sort_order: Number(draft.sort_order || 0),
      }) });
      setDraft(EMPTY); setFeedback({ tone: "success", title: `${MASTER_LABELS[selectedMaster]} updated`, message: "The new record is available immediately in classification forms." }); await load();
    } catch (error) { setFeedback({ tone: "error", title: "Master record could not be created", message: (error as Error).message }); }
    finally { setSaving(false); }
  }

  async function toggle(row: Dimension) {
    try {
      await api(`/classification/dimensions/${row.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !row.is_active }) });
      setFeedback({ tone: "success", title: row.is_active ? "Record deactivated" : "Record restored", message: row.name }); await load();
    } catch (error) { setFeedback({ tone: "error", title: "Status could not be changed", message: (error as Error).message }); }
  }

  function setItemField(itemId: string, key: keyof (typeof itemEdits)[string], value: string) {
    setItemEdits(current => ({ ...current, [itemId]: { ...current[itemId], [key]: value, ...(key === "primary_workspace_id" ? { item_type_id: "", department_id: "", cost_center_id: "" } : {}) } }));
  }

  async function saveItem(item: ItemClassification) {
    const edit = itemEdits[item.item_id];
    if (!edit?.primary_workspace_id || !edit.item_type_id) { setFeedback({ tone: "error", title: "Workspace and item type are required", message: item.name }); return; }
    try {
      await api(`/classification/items/${item.item_id}`, { method: "PATCH", body: JSON.stringify({
        primary_workspace_id: edit.primary_workspace_id,
        item_type_id: edit.item_type_id,
        department_id: edit.department_id || null,
        cost_center_id: edit.cost_center_id || null,
        additional_workspace_ids: [],
      }) });
      setFeedback({ tone: "success", title: "Item classified", message: `${item.sku} · ${item.name}` }); await load();
    } catch (error) { setFeedback({ tone: "error", title: "Item could not be classified", message: (error as Error).message }); }
  }

  const rows = useMemo(() => currentRows.map(row => [
    row.name,
    <code key={`${row.id}-code`}>{row.code}</code>,
    row.behavior_key || "—",
    row.parent_id ? dimensionName(row.dimension_type === "item_type" ? "record_class" : row.dimension_type, row.parent_id) : "—",
    workspaceName(row.workspace_id),
    row.sort_order,
    <StatusBadge key={`${row.id}-status`} status={row.is_active ? "active" : "inactive"} />,
    <button key={`${row.id}-action`} className="secondary compact" type="button" onClick={() => void toggle(row)}>{row.is_active ? "Deactivate" : "Restore"}</button>,
  ]), [currentRows, dimensions]);

  return <AppShell title="Operating Structure" description="Configure how F&B, Hotel, shared operations, reusable property, and future fixed assets are classified. Visible names and defaults are editable; protected behavior keys preserve system integrity.">
    {feedback ? <FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}
    <section className="classification-summary">
      <div className="metric-card"><span>Active workspaces</span><strong>{bootstrap?.summary.active_workspaces ?? "—"}</strong><small>Used by the global workspace selector</small></div>
      <div className="metric-card"><span>Active item types</span><strong>{bootstrap?.summary.active_item_types ?? "—"}</strong><small>Drives item behavior automatically</small></div>
      <div className={`metric-card ${bootstrap?.summary.unclassified_items ? "metric-card--attention" : ""}`}><span>Unclassified items</span><strong>{bootstrap?.summary.unclassified_items ?? "—"}</strong><small>Existing records requiring migration</small></div>
    </section>

    <section className="card section-gap">
      <div className="topline"><div><h2>Editable masters</h2><p>Seeded defaults are starting points only. Rename, reorder, deactivate, or add operational records without changing code.</p></div><label className="catalogue-toggle"><input type="checkbox" checked={showInactive} onChange={event => setShowInactive(event.target.checked)} /><span>Include inactive</span></label></div>
      <div className="master-tabs" role="tablist" aria-label="Classification masters">{MASTER_KEYS.map(key => <button type="button" role="tab" aria-selected={selectedMaster === key} className={selectedMaster === key ? "active" : ""} key={key} onClick={() => { setSelectedMaster(key); setDraft(EMPTY); }}>{MASTER_LABELS[key]}</button>)}</div>
      <div className="classification-layout">
        <form onSubmit={createMaster} className="classification-form">
          <FormSection title={`Add ${MASTER_LABELS[selectedMaster].toLowerCase()}`} description="Codes are stable references. Names and descriptions are what staff see.">
            <FormField label="Code" name="dimension-code" required hint="Lowercase code, for example cafe or minibar."><input value={draft.code} onChange={event => setDraft(current => ({ ...current, code: event.target.value }))} /></FormField>
            <FormField label="Name" name="dimension-name" required><input value={draft.name} onChange={event => setDraft(current => ({ ...current, name: event.target.value }))} /></FormField>
            <FormField label="Description" name="dimension-description"><textarea rows={3} value={draft.description} onChange={event => setDraft(current => ({ ...current, description: event.target.value }))} /></FormField>
            <FormField label="Behavior key" name="dimension-behavior" hint="Optional machine meaning. System-seeded behavior keys cannot later be changed."><input value={draft.behavior_key} onChange={event => setDraft(current => ({ ...current, behavior_key: event.target.value }))} /></FormField>
            {selectedMaster === "item_type" ? <FormField label="Record class" name="dimension-parent" required><select value={draft.parent_id} onChange={event => setDraft(current => ({ ...current, parent_id: event.target.value }))}><option value="">Select record class</option>{recordClasses.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField> : null}
            {!["workspace", "record_class", "business_unit", "location_type", "asset_class", "depreciation_method", "condition_status", "movement_reason"].includes(selectedMaster) ? <FormField label="Workspace" name="dimension-workspace"><select value={draft.workspace_id} onChange={event => setDraft(current => ({ ...current, workspace_id: event.target.value }))}><option value="">Shared or not scoped</option>{workspaces.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></FormField> : null}
            <FormField label="Sort order" name="dimension-sort"><input type="number" value={draft.sort_order} onChange={event => setDraft(current => ({ ...current, sort_order: event.target.value }))} /></FormField>
          </FormSection>
          <div className="form-actions"><button className="primary" disabled={saving}>{saving ? "Saving…" : "Add record"}</button></div>
        </form>
        <DataTable columns={["Name", "Code", "Behavior", "Parent", "Workspace", "Order", "Status", "Action"]} rows={rows} rowIds={currentRows.map(row => row.id)} loading={loading} error={loadError} onRetry={() => void load()} searchPlaceholder={`Search ${MASTER_LABELS[selectedMaster].toLowerCase()}`} exportFileName={`hidden-oasis-${selectedMaster}`} caption={MASTER_LABELS[selectedMaster]} emptyTitle="No records" emptyMessage="Add the first record for this master." />
      </div>
    </section>

    <section className="card section-gap">
      <div className="topline"><div><h2>Existing-item migration</h2><p>Classify legacy items deliberately. Choosing the item type derives the record class automatically—there is no recipe-eligibility checkbox.</p></div><span className={`badge ${items.length ? "warning" : "success"}`}>{items.length ? `${items.length} remaining` : "Complete"}</span></div>
      {items.length ? <div className="migration-list">{items.map(item => {
        const edit = itemEdits[item.item_id] || { primary_workspace_id: "", item_type_id: "", department_id: "", cost_center_id: "" };
        const itemTypes = (dimensions.item_type || []).filter(row => row.is_active && row.workspace_id === edit.primary_workspace_id);
        const departments = (dimensions.department || []).filter(row => row.is_active && (!row.workspace_id || row.workspace_id === edit.primary_workspace_id));
        const costCenters = (dimensions.cost_center || []).filter(row => row.is_active && (!row.workspace_id || row.workspace_id === edit.primary_workspace_id));
        return <div className="migration-row" key={item.item_id}>
          <div className="migration-identity"><strong>{item.sku}</strong><span>{item.name}</span></div>
          <select aria-label={`Workspace for ${item.name}`} value={edit.primary_workspace_id} onChange={event => setItemField(item.item_id, "primary_workspace_id", event.target.value)}><option value="">Workspace</option>{workspaces.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          <select aria-label={`Item type for ${item.name}`} value={edit.item_type_id} disabled={!edit.primary_workspace_id} onChange={event => setItemField(item.item_id, "item_type_id", event.target.value)}><option value="">Item type</option>{itemTypes.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          <select aria-label={`Department for ${item.name}`} value={edit.department_id} disabled={!edit.primary_workspace_id} onChange={event => setItemField(item.item_id, "department_id", event.target.value)}><option value="">Department optional</option>{departments.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          <select aria-label={`Cost center for ${item.name}`} value={edit.cost_center_id} disabled={!edit.primary_workspace_id} onChange={event => setItemField(item.item_id, "cost_center_id", event.target.value)}><option value="">Cost center optional</option>{costCenters.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          <button className="primary compact" type="button" onClick={() => void saveItem(item)}>Save</button>
        </div>;
      })}</div> : <div className="empty-panel"><strong>All items are classified</strong><p>New items will use the same workspace and item-type structure automatically.</p></div>}
    </section>
  </AppShell>;
}
