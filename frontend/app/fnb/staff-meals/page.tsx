"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";
import { stableDraftIdempotency, type DraftIdempotencyState } from "../../../lib/draftIdempotency";

type Item = { id: string; sku: string; name: string; base_unit_id: string; track_stock: boolean; is_active: boolean };
type Unit = { id: string; code: string };
type Location = { id: string; code: string; name: string; is_active: boolean };
type MealLine = { id?: string; item_id: string; quantity: string | number; unit_cost?: string | number };
type Meal = { id: string; meal_number: string; meal_name: string; meal_period?: string | null; servings: number; location_id: string; status: string; created_at: string; lines: MealLine[] };
type PreviewLine = { item_id: string; sku: string; item_name: string; quantity: string; available_quantity: string; unit_cost: string; line_cost: string };
type Preview = { servings: number; total_cost: string; cost_per_serving: string; lines: PreviewLine[] };

const blankLine = (): MealLine => ({ item_id: "", quantity: "" });
const money = (value: string | number) => Number(value || 0).toLocaleString("en-PH", { style: "currency", currency: "PHP", minimumFractionDigits: 2 });

export default function Page() {
  const [items, setItems] = useState<Item[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [mealName, setMealName] = useState("");
  const [mealPeriod, setMealPeriod] = useState("Lunch");
  const [servings, setServings] = useState("1");
  const [locationId, setLocationId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<MealLine[]>([blankLine()]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const draftIdempotency = useRef<DraftIdempotencyState | null>(null);

  const itemById = useMemo(() => Object.fromEntries(items.map(x => [x.id, x])), [items]);
  const unitById = useMemo(() => Object.fromEntries(units.map(x => [x.id, x])), [units]);
  const locationById = useMemo(() => Object.fromEntries(locations.map(x => [x.id, x])), [locations]);

  const load = useCallback(async () => {
    try {
      const [i, u, l, m] = await Promise.all([
        api<Item[]>("/items?active=true"),
        api<Unit[]>("/units"),
        api<Location[]>("/locations"),
        api<Meal[]>("/staff-meals?limit=50"),
      ]);
      setItems(i.filter(x => x.track_stock));
      setUnits(u);
      setLocations(l.filter(x => x.is_active));
      setMeals(m);
      setLocationId(current => current || l.find(x => x.is_active)?.id || "");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const payload = () => {
    const draft = {
      meal_name: mealName.trim(),
      meal_period: mealPeriod || null,
      servings: Number(servings),
      location_id: locationId,
      notes: notes.trim() || null,
      lines: lines.filter(x => x.item_id && Number(x.quantity) > 0).map(x => ({ item_id: x.item_id, quantity: String(x.quantity) })),
    };
    const state = stableDraftIdempotency(draft, draftIdempotency.current);
    draftIdempotency.current = state;
    return { ...draft, idempotency_key: state.key };
  };

  async function estimate() {
    setError("");
    setSuccess("");
    try {
      const p = payload();
      if (!p.meal_name || !p.location_id || p.lines.length === 0) throw new Error("Enter a meal name, location, and at least one ingredient.");
      const result = await api<Preview>("/staff-meals/preview", { method: "POST", body: JSON.stringify(p) });
      setPreview(result);
    } catch (e) {
      setPreview(null);
      setError((e as Error).message);
    }
  }

  async function post() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const p = payload();
      if (!p.meal_name || !p.location_id || p.lines.length === 0) throw new Error("Enter a meal name, location, and at least one ingredient.");
      await api<Meal>("/staff-meals", { method: "POST", body: JSON.stringify(p) });
      draftIdempotency.current = null;
      setMealName("");
      setNotes("");
      setLines([blankLine()]);
      setPreview(null);
      setSuccess("Staff meal posted. Ingredient stock has been deducted and the cost is recorded in the audit trail.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function reverse(meal: Meal) {
    if (!window.confirm(`Reverse ${meal.meal_number} — ${meal.meal_name}? This restores the posted ingredient quantities to inventory.`)) return;
    setError("");
    try {
      await api<Meal>(`/staff-meals/${meal.id}/reverse`, { method: "POST" });
      setSuccess(`${meal.meal_number} reversed.`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function copyPrevious() {
    const previous = meals.find(x => x.status === "posted") || meals[0];
    if (!previous) {
      setError("There is no previous staff meal to copy.");
      return;
    }
    draftIdempotency.current = null;
    setMealName(previous.meal_name);
    setMealPeriod(previous.meal_period || "Lunch");
    setServings(String(previous.servings));
    setLocationId(previous.location_id);
    setLines(previous.lines.map(x => ({ item_id: x.item_id, quantity: String(x.quantity) })));
    setPreview(null);
    setSuccess(`Copied ${previous.meal_number}. Review the quantities before posting today's meal.`);
  }

  function updateLine(index: number, key: "item_id" | "quantity", value: string) {
    setLines(current => current.map((row, i) => i === index ? { ...row, [key]: value } : row));
    setPreview(null);
  }

  const previewByItem = useMemo(() => Object.fromEntries((preview?.lines || []).map(x => [x.item_id, x])), [preview]);

  return <AppShell title="Staff Meals" description="Record what the kitchen actually used for staff meals. No recipe is required; every posting is costed and auditable.">
    {error ? <FeedbackBanner tone="error" title="Staff meal action failed" message={error} /> : null}
    {success ? <FeedbackBanner tone="success" title="Staff meal updated" message={success} /> : null}

    <section className="card">
      <div className="topline">
        <div>
          <span className="page-kicker">Daily internal consumption</span>
          <h2>Record staff meal</h2>
          <p>Enter the actual ingredients taken from stock. Preview the cost, then post once the quantities are correct.</p>
        </div>
        <button className="secondary compact" type="button" onClick={copyPrevious}>Copy previous</button>
      </div>

      <div className="form-grid">
        <label className="field">Meal name
          <input value={mealName} onChange={e => { setMealName(e.target.value); setPreview(null); }} placeholder="e.g. Chicken adobo" maxLength={180} />
        </label>
        <label className="field">Meal period
          <select value={mealPeriod} onChange={e => { setMealPeriod(e.target.value); setPreview(null); }}>
            <option>Breakfast</option><option>Lunch</option><option>Dinner</option><option>Other</option>
          </select>
        </label>
        <label className="field">Servings
          <input type="number" min="1" max="500" value={servings} onChange={e => { setServings(e.target.value); setPreview(null); }} />
        </label>
        <label className="field">Stock location
          <select value={locationId} onChange={e => { setLocationId(e.target.value); setPreview(null); }}>
            <option value="">Select location</option>
            {locations.map(x => <option value={x.id} key={x.id}>{x.code} — {x.name}</option>)}
          </select>
        </label>
      </div>

      <div className="section-title">
        <div><h2>Ingredients used</h2><p>Add only what was actually taken from inventory.</p></div>
        <button className="secondary compact" type="button" onClick={() => { setLines(x => [...x, blankLine()]); setPreview(null); }}>+ Add ingredient</button>
      </div>

      <div className="data-table-shell">
        <div className="table-wrap">
          <table aria-label="Staff meal ingredients">
            <thead><tr><th>Ingredient</th><th>Quantity</th><th>Available</th><th>Cost</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {lines.map((line, index) => {
                const item = itemById[line.item_id];
                const unit = item ? unitById[item.base_unit_id] : undefined;
                const cost = previewByItem[line.item_id];
                return <tr key={index}>
                  <td>
                    <label className="sr-only" htmlFor={`ingredient-${index}`}>Ingredient {index + 1}</label>
                    <select id={`ingredient-${index}`} value={line.item_id} onChange={e => updateLine(index, "item_id", e.target.value)}>
                      <option value="">Select ingredient</option>
                      {items.map(x => <option value={x.id} key={x.id}>{x.sku} — {x.name}</option>)}
                    </select>
                  </td>
                  <td>
                    <label className="sr-only" htmlFor={`quantity-${index}`}>Quantity for ingredient {index + 1}</label>
                    <input id={`quantity-${index}`} type="number" min="0" step="any" value={line.quantity} onChange={e => updateLine(index, "quantity", e.target.value)} />
                    <small className="muted"> {unit?.code || "base unit"}</small>
                  </td>
                  <td>{cost ? cost.available_quantity : "—"}</td>
                  <td>{cost ? money(cost.line_cost) : "—"}</td>
                  <td><button className="secondary compact" type="button" disabled={lines.length === 1} onClick={() => { setLines(x => x.filter((_, i) => i !== index)); setPreview(null); }}>Remove</button></td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>
      </div>

      <label className="field section-gap">Notes
        <textarea value={notes} onChange={e => { setNotes(e.target.value); setPreview(null); }} placeholder="Optional preparation or service notes" />
      </label>

      <div className="grid section-gap" aria-label="Staff meal cost summary">
        <div className="card"><span className="page-kicker">Total food cost</span><strong>{preview ? money(preview.total_cost) : "—"}</strong><p>{preview ? "Based on current inventory costing." : "Preview to calculate."}</p></div>
        <div className="card"><span className="page-kicker">Cost per serving</span><strong>{preview ? money(preview.cost_per_serving) : "—"}</strong><p>{preview ? `${preview.servings} serving${preview.servings === 1 ? "" : "s"}.` : "Calculated from servings."}</p></div>
        <div className="card"><span className="page-kicker">Ingredients</span><strong>{preview ? preview.lines.length : lines.filter(x => x.item_id && Number(x.quantity) > 0).length}</strong><p>Actual stock lines in this meal.</p></div>
      </div>

      <div className="button-row">
        <button className="secondary" type="button" onClick={estimate} disabled={saving}>Preview cost</button>
        <button className="primary" type="button" disabled={saving} onClick={post}>{saving ? "Posting…" : "Post staff meal"}</button>
      </div>
      <p className="muted section-gap">Posted meals are immutable. If something is wrong, reverse the posting and enter the corrected meal.</p>
    </section>

    <section className="card section-gap">
      <div className="topline">
        <div><span className="page-kicker">Audit trail</span><h2>Recent staff meals</h2><p>Latest internal-consumption postings and reversals.</p></div>
      </div>
      <div className="data-table-shell">
        <div className="table-wrap">
          <table aria-label="Recent staff meals">
            <thead><tr><th>Meal</th><th>Period</th><th>Servings</th><th>Location</th><th>Posted</th><th>Status</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {meals.map(meal => <tr key={meal.id}>
                <td><strong style={{ fontSize: 13 }}>{meal.meal_number}</strong><br /><small>{meal.meal_name}</small></td>
                <td>{meal.meal_period || "—"}</td>
                <td>{meal.servings}</td>
                <td>{locationById[meal.location_id]?.name || "Unknown location"}</td>
                <td>{new Date(meal.created_at).toLocaleString()}</td>
                <td><StatusBadge status={meal.status} /></td>
                <td>{meal.status === "posted" ? <button className="secondary compact" type="button" onClick={() => void reverse(meal)}>Reverse</button> : null}</td>
              </tr>)}
              {meals.length === 0 ? <tr><td colSpan={7}><div className="empty-state"><strong>No staff meals yet</strong><span>Post the first staff meal above.</span></div></td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </AppShell>;
}
