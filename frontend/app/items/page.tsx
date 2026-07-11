"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";
import { formatMoney, formatQuantity } from "../../lib/formatters";

type Ref = { id: string; name: string; code?: string };
type Item = {
  id: string;
  sku: string;
  name: string;
  minimum_stock: string;
  standard_cost: string;
  is_active: boolean;
};

type Feedback = { type: "success" | "error"; message: string } | null;

export default function Page() {
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Ref[]>([]);
  const [units, setUnits] = useState<Ref[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [itemRecords, categoryRecords, unitRecords] = await Promise.all([
        api<Item[]>("/items"),
        api<Ref[]>("/categories"),
        api<Ref[]>("/units"),
      ]);
      setItems(itemRecords);
      setCategories(categoryRecords);
      setUnits(unitRecords);
    } catch (error) {
      setLoadError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setSaving(true);
    setFeedback(null);
    try {
      await api("/items", {
        method: "POST",
        body: JSON.stringify({
          sku: data.get("sku"),
          name: data.get("name"),
          category_id: data.get("category"),
          base_unit_id: data.get("unit"),
          minimum_stock: data.get("minimum") || 0,
          standard_cost: data.get("cost") || 0,
        }),
      });
      form.reset();
      setFeedback({ type: "success", message: "Item created." });
      await load();
    } catch (error) {
      setFeedback({ type: "error", message: (error as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell title="Items">
      <section className="card">
        <h2>Create item</h2>
        <form className="inline-form" onSubmit={submit}>
          <input name="sku" placeholder="SKU" required />
          <input name="name" placeholder="Item name" required />
          <select name="category" required>
            <option value="">Category</option>
            {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <select name="unit" required>
            <option value="">Unit</option>
            {units.map(unit => <option key={unit.id} value={unit.id}>{unit.code || unit.name}</option>)}
          </select>
          <input name="minimum" type="number" step="0.0001" min="0" placeholder="Minimum" />
          <input name="cost" type="number" step="0.0001" min="0" placeholder="Standard cost" />
          <button className="primary compact" disabled={saving}>{saving ? "Adding…" : "Add item"}</button>
        </form>
        {feedback ? <p className={`status status--${feedback.type}`} role={feedback.type === "error" ? "alert" : "status"}>{feedback.message}</p> : null}
      </section>

      <section className="card section-gap">
        <h2>Item master</h2>
        <DataTable
          columns={["SKU", "Name", "Minimum", "Standard cost", "Status"]}
          rows={items.map(item => [
            item.sku,
            item.name,
            formatQuantity(item.minimum_stock),
            formatMoney(item.standard_cost),
            <StatusBadge key={`${item.id}-status`} status={item.is_active ? "active" : "inactive"} />,
          ])}
          rowIds={items.map(item => item.id)}
          loading={loading}
          error={loadError}
          onRetry={() => void load()}
          searchPlaceholder="Search by SKU, name, cost, or status"
          exportFileName="hidden-oasis-items"
          caption="Hidden Oasis item master"
          emptyTitle="No items yet"
          emptyMessage="Create the first inventory item to begin building the catalogue."
        />
      </section>
    </AppShell>
  );
}
